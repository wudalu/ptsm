"""All-or-nothing local rendering for psychology text carousels."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from typing import Any, Mapping, Protocol, Sequence

from PIL import Image, UnidentifiedImageError

from ptsm.domain.psychology_carousel import (
    normalize_psychology_carousel_plan,
)


_MANIFEST_NAME = "manifest.json"
_MANIFEST_SCHEMA = "ptsm.image_carousel_manifest"
_MANIFEST_VERSION = 1
_MANIFEST_FIELDS = {
    "schema",
    "version",
    "set_id",
    "provider",
    "model",
    "style",
    "carousel_style",
    "image_count",
    "provenance",
    "pages",
}
_PAGE_FIELDS = {
    "slide_id",
    "order",
    "role",
    "style",
    "headline",
    "body_lines",
    "filename",
    "path",
    "visible_text_summary",
    "prompt_sha256",
    "page_sha256",
    "file_sha256",
    "provenance",
}
_RECEIPT_FIELDS = {
    "status",
    "provider",
    "style",
    "carousel_style",
    "model",
    "image_count",
    "set_id",
    "manifest_path",
    "manifest_sha256",
    "generated_image_paths",
    "pages",
    "provenance",
}


class _ImageRenderer(Protocol):
    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]: ...


class ImageCarouselTransactionError(RuntimeError):
    """A carousel set could not be safely committed."""


def verify_committed_carousel_set(
    *,
    image_plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    output_stem: str,
) -> dict[str, object]:
    """Rebuild and verify the canonical receipt for one immutable set."""
    plan = normalize_psychology_carousel_plan(image_plan)
    stem = _validate_output_stem(output_stem)
    if not isinstance(receipt, Mapping) or set(receipt) != _RECEIPT_FIELDS:
        raise ImageCarouselTransactionError("carousel receipt has an invalid shape")
    raw_manifest_path = receipt.get("manifest_path")
    if not isinstance(raw_manifest_path, str) or not raw_manifest_path:
        raise ImageCarouselTransactionError("carousel receipt has an invalid manifest path")
    manifest_path = Path(raw_manifest_path)
    if (
        not manifest_path.is_absolute()
        or manifest_path.name != _MANIFEST_NAME
        or Path(os.path.abspath(manifest_path)) != manifest_path
    ):
        raise ImageCarouselTransactionError("carousel receipt has an invalid manifest path")

    raw_set_id = receipt.get("set_id")
    if (
        not isinstance(raw_set_id, str)
        or len(raw_set_id) != 64
        or any(character not in "0123456789abcdef" for character in raw_set_id)
    ):
        raise ImageCarouselTransactionError("carousel receipt has an invalid set id")
    expected_set_id = raw_set_id
    final_path = manifest_path.parent
    if final_path.name != f"{stem}-{expected_set_id[:16]}":
        raise ImageCarouselTransactionError("carousel receipt does not match its plan")
    canonical = _reuse_identical_set(
        final_path=final_path,
        expected_plan=plan,
        output_stem=stem,
        expected_set_id=expected_set_id,
    )
    if dict(receipt) != canonical:
        raise ImageCarouselTransactionError("carousel receipt is not canonical")
    return canonical


class ImageCarouselTransaction:
    """Render, verify, and atomically commit one immutable image set."""

    def __init__(self, *, renderer: _ImageRenderer) -> None:
        self.renderer = renderer

    def generate(
        self,
        *,
        image_plan: Mapping[str, Any],
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        plan = normalize_psychology_carousel_plan(image_plan)
        stem = _validate_output_stem(output_stem)

        raw_destination_root = Path(output_dir)
        if raw_destination_root.is_symlink():
            raise ImageCarouselTransactionError(
                "carousel output directory must not be a symlink"
            )
        raw_destination_root.mkdir(parents=True, exist_ok=True)
        root_entry = raw_destination_root.lstat()
        if stat.S_ISLNK(root_entry.st_mode) or not stat.S_ISDIR(root_entry.st_mode):
            raise ImageCarouselTransactionError("carousel output directory is not regular")
        destination_root = raw_destination_root.resolve(strict=True)
        if not os.path.samestat(root_entry, destination_root.stat()):
            raise ImageCarouselTransactionError(
                "carousel output directory identity changed"
            )

        staging_path = Path(
            tempfile.mkdtemp(
                prefix=f".{stem}-staging-",
                dir=destination_root,
            )
        )
        staging_identity = staging_path.lstat()
        try:
            rendered = self._render_pages(
                plan=plan,
                staging_path=staging_path,
                output_stem=stem,
            )
            _validate_complete_staging_set(
                staging_path=staging_path,
                pages=rendered.pages,
                include_manifest=False,
            )
            set_id = _set_id_for_rendered_set(
                provider=rendered.provider,
                model=rendered.model,
                style=str(plan["carousel_style"]),
                provenance=rendered.provenance,
                pages=rendered.pages,
            )
            final_path = destination_root / f"{stem}-{set_id[:16]}"
            final_pages = _finalize_page_evidence(rendered.pages, final_path=final_path)
            manifest = {
                "schema": _MANIFEST_SCHEMA,
                "version": _MANIFEST_VERSION,
                "set_id": set_id,
                "provider": rendered.provider,
                "model": rendered.model,
                "style": str(plan["carousel_style"]),
                "carousel_style": str(plan["carousel_style"]),
                "image_count": len(final_pages),
                "provenance": rendered.provenance,
                "pages": final_pages,
            }
            manifest_bytes = _canonical_json_bytes(manifest, trailing_newline=True)
            _write_fsynced_file(staging_path / _MANIFEST_NAME, manifest_bytes)
            _validate_complete_staging_set(
                staging_path=staging_path,
                pages=rendered.pages,
                include_manifest=True,
            )
            _fsync_directory(staging_path)

            if final_path.exists() or final_path.is_symlink():
                result = _reuse_identical_set(
                    final_path=final_path,
                    expected_plan=plan,
                    output_stem=stem,
                    expected_set_id=set_id,
                )
                _cleanup_owned_directory(staging_path, staging_identity)
                return result

            try:
                os.rename(staging_path, final_path)
            except OSError as exc:
                if final_path.exists() or final_path.is_symlink():
                    result = _reuse_identical_set(
                        final_path=final_path,
                        expected_plan=plan,
                        output_stem=stem,
                        expected_set_id=set_id,
                    )
                    _cleanup_owned_directory(staging_path, staging_identity)
                    return result
                raise ImageCarouselTransactionError(
                    "carousel set atomic rename failed"
                ) from exc

            committed_identity = final_path.lstat()
            try:
                _fsync_directory(destination_root)
                return _reuse_identical_set(
                    final_path=final_path,
                    expected_plan=plan,
                    output_stem=stem,
                    expected_set_id=set_id,
                )
            except BaseException:
                _cleanup_owned_directory(final_path, committed_identity)
                try:
                    _fsync_directory(destination_root)
                except OSError:
                    pass
                raise
        except ImageCarouselTransactionError:
            _cleanup_owned_directory(staging_path, staging_identity)
            raise
        except Exception as exc:
            _cleanup_owned_directory(staging_path, staging_identity)
            raise ImageCarouselTransactionError(
                f"carousel transaction failed: {exc}"
            ) from exc

    def _render_pages(
        self,
        *,
        plan: Mapping[str, Any],
        staging_path: Path,
        output_stem: str,
    ) -> "_RenderedSet":
        pages: list[dict[str, object]] = []
        returned_paths: set[Path] = set()
        provider = ""
        model = ""
        provenance: dict[str, object] = {}
        slides = plan["slides"]
        if not isinstance(slides, Sequence):
            raise ImageCarouselTransactionError("carousel slides are invalid")

        for raw_slide in slides:
            if not isinstance(raw_slide, Mapping):
                raise ImageCarouselTransactionError("carousel slide is invalid")
            order = int(raw_slide["order"])
            slide_id = str(raw_slide["slide_id"])
            filename = f"{output_stem}-{order:02d}-{slide_id}.png"
            expected_path = staging_path / filename
            page_payload = {
                "style": str(plan["carousel_style"]),
                "slide_id": slide_id,
                "order": order,
                "role": str(raw_slide["role"]),
                "headline": str(raw_slide["headline"]),
                "body_lines": list(raw_slide["body_lines"]),
                "page_count": len(slides),
            }
            prompt = _canonical_json_bytes(page_payload).decode("utf-8")
            try:
                renderer_result = self.renderer.generate(
                    prompt=prompt,
                    output_dir=staging_path,
                    output_stem=filename.removesuffix(".png"),
                )
            except Exception as exc:
                raise ImageCarouselTransactionError(
                    f"renderer failed on page {order}: {exc}"
                ) from exc

            returned_path = _single_renderer_path(
                renderer_result,
                staging_path=staging_path,
                expected_path=expected_path,
                returned_paths=returned_paths,
                page_order=order,
            )
            returned_paths.add(returned_path)
            file_sha256 = _verify_and_hash_png(returned_path, page_order=order)
            page_provider, page_model, page_provenance = _renderer_metadata(
                renderer_result,
                expected_style=str(plan["carousel_style"]),
                page_order=order,
            )
            if not pages:
                provider = page_provider
                model = page_model
                provenance = page_provenance
            elif (
                page_provider != provider
                or page_model != model
                or page_provenance != provenance
            ):
                raise ImageCarouselTransactionError(
                    f"renderer metadata changed on page {order}"
                )

            semantic_page = {
                "slide_id": slide_id,
                "order": order,
                "role": str(raw_slide["role"]),
                "style": str(plan["carousel_style"]),
                "headline": str(raw_slide["headline"]),
                "body_lines": list(raw_slide["body_lines"]),
            }
            pages.append(
                {
                    **semantic_page,
                    "filename": filename,
                    "visible_text_summary": _visible_text_summary(raw_slide),
                    "prompt_sha256": _sha256_bytes(prompt.encode("utf-8")),
                    "page_sha256": _sha256_bytes(_canonical_json_bytes(semantic_page)),
                    "file_sha256": file_sha256,
                    "provenance": page_provenance,
                }
            )

        return _RenderedSet(
            pages=pages,
            provider=provider,
            model=model,
            provenance=provenance,
        )


class _RenderedSet:
    def __init__(
        self,
        *,
        pages: list[dict[str, object]],
        provider: str,
        model: str,
        provenance: dict[str, object],
    ) -> None:
        self.pages = pages
        self.provider = provider
        self.model = model
        self.provenance = provenance


def _validate_output_stem(output_stem: str) -> str:
    stem = str(output_stem).strip()
    if (
        not stem
        or stem in {".", ".."}
        or len(stem) > 128
        or Path(stem).name != stem
        or any(character in stem for character in ("/", "\\", "\0"))
        or any(ord(character) < 32 for character in stem)
    ):
        raise ValueError("output_stem must be one safe filename component")
    return stem


def _single_renderer_path(
    renderer_result: Mapping[str, object],
    *,
    staging_path: Path,
    expected_path: Path,
    returned_paths: set[Path],
    page_order: int,
) -> Path:
    raw_paths = renderer_result.get("generated_image_paths")
    if raw_paths is None:
        raw_paths = renderer_result.get("image_paths")
    if (
        not isinstance(raw_paths, Sequence)
        or isinstance(raw_paths, (str, bytes))
        or len(raw_paths) != 1
    ):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} must return exactly one path"
        )
    raw_path = raw_paths[0]
    if not isinstance(raw_path, (str, os.PathLike)):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned an invalid path"
        )
    returned_path = Path(raw_path)
    if not returned_path.is_absolute():
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned a relative path"
        )
    normalized_path = Path(os.path.abspath(returned_path))
    try:
        normalized_path.relative_to(staging_path)
    except ValueError as exc:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned a path outside staging"
        ) from exc
    if normalized_path in returned_paths:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned a duplicate path"
        )
    if normalized_path != expected_path:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned the wrong stable path"
        )
    return normalized_path


def _verify_and_hash_png(path: Path, *, page_order: int) -> str:
    try:
        entry = path.lstat()
    except FileNotFoundError as exc:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output is missing"
        ) from exc
    except OSError as exc:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output is unreadable"
        ) from exc
    if stat.S_ISLNK(entry.st_mode) or not stat.S_ISREG(entry.st_mode):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output is not a regular file"
        )
    if entry.st_nlink != 1:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output must be a single-link file"
        )
    if entry.st_mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH) == 0:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output is not readable"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} output is not readable"
        ) from exc
    try:
        opened_entry = os.fstat(fd)
        if not stat.S_ISREG(opened_entry.st_mode) or not os.path.samestat(
            entry, opened_entry
        ):
            raise ImageCarouselTransactionError(
                f"renderer page {page_order} output identity changed"
            )
        try:
            with os.fdopen(os.dup(fd), "rb") as image_stream:
                with Image.open(image_stream) as image:
                    if image.format != "PNG":
                        raise ImageCarouselTransactionError(
                            f"renderer page {page_order} output is not PNG"
                        )
                    image.verify()
        except (OSError, SyntaxError, UnidentifiedImageError) as exc:
            raise ImageCarouselTransactionError(
                f"renderer page {page_order} output is not a readable PNG"
            ) from exc
        os.lseek(fd, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        while chunk := os.read(fd, 1024 * 1024):
            digest.update(chunk)
        os.fsync(fd)
        if not os.path.samestat(opened_entry, os.fstat(fd)):
            raise ImageCarouselTransactionError(
                f"renderer page {page_order} output identity changed"
            )
        return digest.hexdigest()
    finally:
        os.close(fd)


def _renderer_metadata(
    renderer_result: Mapping[str, object],
    *,
    expected_style: str,
    page_order: int,
) -> tuple[str, str, dict[str, object]]:
    if renderer_result.get("status") != "generated":
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} did not report generated status"
        )
    provider = str(renderer_result.get("provider") or "").strip()
    model = str(renderer_result.get("model") or "").strip()
    style = str(renderer_result.get("style") or "").strip()
    raw_provenance = renderer_result.get("provenance")
    if not provider or not model or style != expected_style:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned invalid metadata"
        )
    if not isinstance(raw_provenance, Mapping):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned invalid provenance"
        )
    try:
        provenance = json.loads(_canonical_json_bytes(raw_provenance))
    except (TypeError, ValueError) as exc:
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned invalid provenance"
        ) from exc
    if not isinstance(provenance, dict):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} returned invalid provenance"
        )
    if not _is_local_renderer_provenance(provenance):
        raise ImageCarouselTransactionError(
            f"renderer page {page_order} must return local provenance"
        )
    return provider, model, provenance


def _is_local_renderer_provenance(provenance: Mapping[str, object]) -> bool:
    return (
        set(provenance) == {"source", "renderer", "watermark_removal"}
        and provenance.get("source") == "ptsm_local_renderer"
        and isinstance(provenance.get("renderer"), str)
        and bool(str(provenance.get("renderer")).strip())
        and provenance.get("watermark_removal") == "skip"
    )


def _visible_text_summary(slide: Mapping[str, object]) -> str:
    body_lines = slide.get("body_lines")
    lines = (
        [str(line) for line in body_lines]
        if isinstance(body_lines, Sequence) and not isinstance(body_lines, (str, bytes))
        else []
    )
    return " | ".join([str(slide.get("headline") or ""), *lines])[:180]


def _validate_complete_staging_set(
    *,
    staging_path: Path,
    pages: Sequence[Mapping[str, object]],
    include_manifest: bool,
) -> None:
    expected_names = {str(page["filename"]) for page in pages}
    if include_manifest:
        expected_names.add(_MANIFEST_NAME)
    try:
        actual_names = {entry.name for entry in staging_path.iterdir()}
    except OSError as exc:
        raise ImageCarouselTransactionError("staging set is not readable") from exc
    if actual_names != expected_names:
        raise ImageCarouselTransactionError("staging set contains unexpected entries")
    for page in pages:
        order = int(page["order"])
        path = staging_path / str(page["filename"])
        current_hash = _verify_and_hash_png(path, page_order=order)
        if current_hash != page["file_sha256"]:
            raise ImageCarouselTransactionError(
                f"staging page {order} changed after rendering"
            )


def _set_id_for_rendered_set(
    *,
    provider: str,
    model: str,
    style: str,
    provenance: Mapping[str, object],
    pages: Sequence[Mapping[str, object]],
) -> str:
    identity_pages = [
        {
            key: page[key]
            for key in (
                "slide_id",
                "order",
                "role",
                "style",
                "headline",
                "body_lines",
                "visible_text_summary",
                "prompt_sha256",
                "page_sha256",
                "file_sha256",
                "provenance",
            )
        }
        for page in pages
    ]
    identity = {
        "schema": _MANIFEST_SCHEMA,
        "version": _MANIFEST_VERSION,
        "provider": provider,
        "model": model,
        "style": style,
        "provenance": provenance,
        "pages": identity_pages,
    }
    return _sha256_bytes(_canonical_json_bytes(identity))


def _finalize_page_evidence(
    pages: Sequence[Mapping[str, object]],
    *,
    final_path: Path,
) -> list[dict[str, object]]:
    finalized: list[dict[str, object]] = []
    for page in pages:
        filename = str(page["filename"])
        finalized.append({**page, "path": str(final_path / filename)})
    return finalized


def _reuse_identical_set(
    *,
    final_path: Path,
    expected_plan: Mapping[str, object],
    output_stem: str,
    expected_set_id: str,
) -> dict[str, object]:
    try:
        entry = final_path.lstat()
        if stat.S_ISLNK(entry.st_mode) or not stat.S_ISDIR(entry.st_mode):
            raise ImageCarouselTransactionError("conflicting manifest or set path")
        manifest_path = final_path / _MANIFEST_NAME
        manifest_entry = manifest_path.lstat()
        if stat.S_ISLNK(manifest_entry.st_mode) or not stat.S_ISREG(
            manifest_entry.st_mode
        ):
            raise ImageCarouselTransactionError("conflicting manifest or set path")
        manifest_read_bits = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
        if manifest_entry.st_nlink != 1 or not (
            manifest_entry.st_mode & manifest_read_bits
        ):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        manifest_flags = os.O_RDONLY
        if hasattr(os, "O_NOFOLLOW"):
            manifest_flags |= os.O_NOFOLLOW
        manifest_fd = os.open(manifest_path, manifest_flags)
        try:
            opened_manifest = os.fstat(manifest_fd)
            if not os.path.samestat(manifest_entry, opened_manifest):
                raise ImageCarouselTransactionError(
                    "conflicting manifest for carousel set"
                )
            chunks: list[bytes] = []
            while chunk := os.read(manifest_fd, 1024 * 1024):
                chunks.append(chunk)
            actual_manifest_bytes = b"".join(chunks)
        finally:
            os.close(manifest_fd)
        actual_manifest = json.loads(actual_manifest_bytes)
        if not isinstance(actual_manifest, dict) or actual_manifest_bytes != (
            _canonical_json_bytes(actual_manifest, trailing_newline=True)
        ):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        if set(actual_manifest) != _MANIFEST_FIELDS:
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")

        raw_pages = actual_manifest.get("pages")
        raw_slides = expected_plan.get("slides")
        if not isinstance(raw_pages, list) or not isinstance(raw_slides, Sequence):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        expected_header = {
            "schema": _MANIFEST_SCHEMA,
            "version": _MANIFEST_VERSION,
            "set_id": expected_set_id,
            "style": str(expected_plan["carousel_style"]),
            "carousel_style": str(expected_plan["carousel_style"]),
            "image_count": len(raw_slides),
        }
        if any(actual_manifest.get(key) != value for key, value in expected_header.items()):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        provider = str(actual_manifest.get("provider") or "").strip()
        model = str(actual_manifest.get("model") or "").strip()
        provenance = actual_manifest.get("provenance")
        if (
            not provider
            or not model
            or not isinstance(provenance, dict)
            or not _is_local_renderer_provenance(provenance)
        ):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        if len(raw_pages) != len(raw_slides):
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        expected_names = {_MANIFEST_NAME}
        generated_paths: list[str] = []
        for page, slide in zip(raw_pages, raw_slides, strict=True):
            if not isinstance(page, dict) or not isinstance(slide, Mapping):
                raise ImageCarouselTransactionError("conflicting manifest for carousel set")
            if set(page) != _PAGE_FIELDS:
                raise ImageCarouselTransactionError("conflicting manifest for carousel set")
            order = int(slide["order"])
            filename = f"{output_stem}-{order:02d}-{slide['slide_id']}.png"
            path = final_path / filename
            semantic_page = {
                "slide_id": str(slide["slide_id"]),
                "order": order,
                "role": str(slide["role"]),
                "style": str(expected_plan["carousel_style"]),
                "headline": str(slide["headline"]),
                "body_lines": list(slide["body_lines"]),
            }
            page_payload = {
                "style": str(expected_plan["carousel_style"]),
                "slide_id": str(slide["slide_id"]),
                "order": order,
                "role": str(slide["role"]),
                "headline": str(slide["headline"]),
                "body_lines": list(slide["body_lines"]),
                "page_count": len(raw_slides),
            }
            expected_page = {
                **semantic_page,
                "filename": filename,
                "path": str(path),
                "visible_text_summary": _visible_text_summary(slide),
                "prompt_sha256": _sha256_bytes(_canonical_json_bytes(page_payload)),
                "page_sha256": _sha256_bytes(_canonical_json_bytes(semantic_page)),
                "provenance": provenance,
            }
            if any(page.get(key) != value for key, value in expected_page.items()):
                raise ImageCarouselTransactionError("conflicting manifest for carousel set")
            expected_names.add(filename)
            file_sha256 = _verify_and_hash_png(path, page_order=order)
            if file_sha256 != page.get("file_sha256"):
                raise ImageCarouselTransactionError("conflicting manifest for carousel set")
            generated_paths.append(str(path))
        actual_set_id = _set_id_for_rendered_set(
            provider=provider,
            model=model,
            style=str(actual_manifest["style"]),
            provenance=provenance,
            pages=raw_pages,
        )
        if actual_set_id != expected_set_id:
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
        actual_names = {path.name for path in final_path.iterdir()}
        if actual_names != expected_names:
            raise ImageCarouselTransactionError("conflicting manifest for carousel set")
    except ImageCarouselTransactionError:
        raise
    except (OSError, ValueError, TypeError, json.JSONDecodeError, KeyError) as exc:
        raise ImageCarouselTransactionError(
            "conflicting manifest for carousel set"
        ) from exc

    return {
        "status": "committed",
        "provider": str(actual_manifest["provider"]),
        "style": str(actual_manifest["style"]),
        "carousel_style": str(actual_manifest["carousel_style"]),
        "model": str(actual_manifest["model"]),
        "image_count": int(actual_manifest["image_count"]),
        "set_id": str(actual_manifest["set_id"]),
        "manifest_path": str(manifest_path),
        "manifest_sha256": _sha256_bytes(actual_manifest_bytes),
        "generated_image_paths": generated_paths,
        "pages": raw_pages,
        "provenance": dict(actual_manifest["provenance"]),
    }


def _write_fsynced_file(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(content):
            offset += os.write(fd, content[offset:])
        os.fsync(fd)
    finally:
        os.close(fd)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(path, flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _cleanup_owned_directory(path: Path, identity: os.stat_result) -> None:
    """Best-effort cleanup without authorizing deletion by a mutable pathname."""
    try:
        current = path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        return
    if not _matching_directory_identity(current, identity):
        return

    parent_fd: int | None = None
    try:
        parent_fd = _open_directory_descriptor(path.parent)
        _cleanup_named_owned_directory(
            parent_fd=parent_fd,
            entry_name=path.name,
            expected_identity=identity,
        )
    except (OSError, NotImplementedError, TypeError):
        # Cleanup must never broaden an already failing transaction into a
        # pathname-based delete. An unprovable entry is deliberately retained.
        return
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


def _cleanup_named_owned_directory(
    *,
    parent_fd: int,
    entry_name: str,
    expected_identity: os.stat_result,
) -> bool:
    directory_fd = _open_matching_child_directory(
        parent_fd=parent_fd,
        entry_name=entry_name,
        expected_identity=expected_identity,
    )
    if directory_fd is None:
        return False
    try:
        _cleanup_directory_contents(directory_fd)
        opened_identity = os.fstat(directory_fd)
        if not _named_directory_matches(
            parent_fd=parent_fd,
            entry_name=entry_name,
            expected_identity=opened_identity,
        ):
            return False
        try:
            os.rmdir(entry_name, dir_fd=parent_fd)
        except FileNotFoundError:
            return False
        except OSError:
            return False
        return True
    finally:
        os.close(directory_fd)


def _cleanup_directory_contents(directory_fd: int) -> None:
    try:
        entry_names = os.listdir(directory_fd)
    except OSError:
        return
    for entry_name in entry_names:
        try:
            entry_identity = os.stat(
                entry_name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            continue
        except OSError:
            continue
        if stat.S_ISDIR(entry_identity.st_mode) and not stat.S_ISLNK(
            entry_identity.st_mode
        ):
            _cleanup_named_owned_directory(
                parent_fd=directory_fd,
                entry_name=entry_name,
                expected_identity=entry_identity,
            )
            continue
        try:
            current_identity = os.stat(
                entry_name,
                dir_fd=directory_fd,
                follow_symlinks=False,
            )
            if not os.path.samestat(entry_identity, current_identity):
                continue
            os.unlink(entry_name, dir_fd=directory_fd)
        except FileNotFoundError:
            continue
        except OSError:
            continue


def _open_directory_descriptor(path: Path | str, *, dir_fd: int | None = None) -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError("safe directory cleanup is unsupported")
    flags = (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    descriptor = os.open(path, flags, dir_fd=dir_fd)
    try:
        identity = os.fstat(descriptor)
        if stat.S_ISLNK(identity.st_mode) or not stat.S_ISDIR(identity.st_mode):
            raise OSError("safe directory cleanup target is invalid")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_matching_child_directory(
    *,
    parent_fd: int,
    entry_name: str,
    expected_identity: os.stat_result,
) -> int | None:
    try:
        entry_before = os.stat(
            entry_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError:
        return None
    if not _matching_directory_identity(entry_before, expected_identity):
        return None
    try:
        descriptor = _open_directory_descriptor(entry_name, dir_fd=parent_fd)
    except OSError:
        return None
    try:
        opened_identity = os.fstat(descriptor)
        entry_after = os.stat(
            entry_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        if not (
            _matching_directory_identity(entry_before, opened_identity)
            and _matching_directory_identity(entry_after, opened_identity)
            and _matching_directory_identity(expected_identity, opened_identity)
        ):
            os.close(descriptor)
            return None
        return descriptor
    except OSError:
        os.close(descriptor)
        return None


def _named_directory_matches(
    *,
    parent_fd: int,
    entry_name: str,
    expected_identity: os.stat_result,
) -> bool:
    try:
        current_identity = os.stat(
            entry_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except OSError:
        return False
    return _matching_directory_identity(current_identity, expected_identity)


def _matching_directory_identity(
    first: os.stat_result,
    second: os.stat_result,
) -> bool:
    return (
        stat.S_ISDIR(first.st_mode)
        and not stat.S_ISLNK(first.st_mode)
        and stat.S_ISDIR(second.st_mode)
        and not stat.S_ISLNK(second.st_mode)
        and os.path.samestat(first, second)
    )


def _canonical_json_bytes(
    payload: Mapping[str, object],
    *,
    trailing_newline: bool = False,
) -> bytes:
    text = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


__all__ = [
    "ImageCarouselTransaction",
    "ImageCarouselTransactionError",
    "verify_committed_carousel_set",
]
