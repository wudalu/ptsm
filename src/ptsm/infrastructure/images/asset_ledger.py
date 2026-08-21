from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any, Mapping

from ptsm.infrastructure.images.image_file_evidence import verify_image_file_set

DEFAULT_GENERATED_IMAGE_ASSET_LEDGER = (
    Path("outputs") / "artifacts" / "generated-image-assets" / "assets.jsonl"
)
_LEDGER_DIRECTORY_COMPONENTS = ("outputs", "artifacts", "generated-image-assets")
_LEDGER_READ_CHUNK_SIZE = 1024 * 1024
_TEMP_CREATE_ATTEMPTS = 128


@dataclass(frozen=True)
class _PinnedLedgerDirectory:
    base_path: Path
    components: tuple[str, ...]
    descriptors: tuple[int, ...]

    @property
    def parent_fd(self) -> int:
        return self.descriptors[-1]


def append_generated_image_assets(
    *,
    base_dir: Path,
    artifact_path: str,
    playbook_id: str,
    account_id: str,
    image_generation: dict[str, Any] | None,
) -> dict[str, object] | None:
    if not isinstance(image_generation, dict):
        return None
    image_paths = list(
        image_generation.get("generated_image_paths")
        or image_generation.get("image_paths")
        or []
    )
    if not image_paths:
        return None

    page_evidence = _ordered_page_evidence(
        image_generation=image_generation,
        image_paths=[str(path) for path in image_paths],
    )
    expected_pages = (
        [page for page in page_evidence if page is not None]
        if any(page is not None for page in page_evidence)
        else None
    )
    verified_paths = verify_image_file_set(
        image_paths=[str(path) for path in image_paths],
        expected_pages=expected_pages,
    )
    ledger_path = base_dir / DEFAULT_GENERATED_IMAGE_ASSET_LEDGER
    entries = [
        _build_asset_entry(
            image_path=image_path,
            artifact_path=artifact_path,
            playbook_id=playbook_id,
            account_id=account_id,
            image_generation=image_generation,
            page=page_evidence[index],
        )
        for index, image_path in enumerate(verified_paths)
    ]
    pinned_directory = _open_or_create_ledger_directory(base_dir=base_dir)
    try:
        _append_entries_atomically(
            pinned_directory=pinned_directory,
            ledger_name=ledger_path.name,
            entries=entries,
        )
    finally:
        _close_pinned_ledger_directory(pinned_directory)

    return {
        "status": "recorded",
        "ledger_path": str(ledger_path),
        "entry_count": len(entries),
    }


def verify_generated_image_asset_receipt_intent(
    *,
    base_dir: Path,
    receipt_intent: Mapping[str, object],
) -> bool:
    """Verify one full, immutable carousel batch against the durable ledger.

    A receipt intent is recovered only when every expected page appears once
    in the same ledger projection.  A matching individual JSONL line is never
    enough to promote carousel memory after a crash.
    """
    expected_projection = _receipt_intent_ledger_projection(receipt_intent)
    if expected_projection is None:
        return False
    ledger_path = base_dir / DEFAULT_GENERATED_IMAGE_ASSET_LEDGER
    if not ledger_path.exists():
        return False
    pinned_directory = _open_or_create_ledger_directory(base_dir=base_dir)
    try:
        _assert_pinned_ledger_directory(pinned_directory)
        ledger_name = ledger_path.name
        lock_name = f".{ledger_name}.lock"
        lock_fd = _open_or_create_ledger_lock(
            parent_fd=pinned_directory.parent_fd,
            lock_name=lock_name,
        )
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_SH)
            try:
                _assert_valid_ledger_lock(
                    parent_fd=pinned_directory.parent_fd,
                    lock_name=lock_name,
                    lock_fd=lock_fd,
                )
                _assert_pinned_ledger_directory(pinned_directory)
                raw_ledger, _ = _read_existing_ledger(
                    parent_fd=pinned_directory.parent_fd,
                    ledger_name=ledger_name,
                )
                _assert_pinned_ledger_directory(pinned_directory)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
    finally:
        _close_pinned_ledger_directory(pinned_directory)

    entries = _parse_ledger_entries(raw_ledger)
    actual_projection = [
        _ledger_entry_projection(entry)
        for entry in entries
        if _ledger_entry_matches_receipt_scope(
            entry,
            expected_projection=expected_projection,
        )
    ]
    return actual_projection == expected_projection["pages"]


def _build_asset_entry(
    *,
    image_path: str,
    artifact_path: str,
    playbook_id: str,
    account_id: str,
    image_generation: dict[str, Any],
    page: dict[str, Any] | None,
) -> dict[str, object]:
    provenance = image_generation.get("provenance")
    provenance_source = ""
    if isinstance(provenance, dict):
        provenance_source = str(provenance.get("source") or "")
    image_plan = image_generation.get("image_plan")
    image_plan_payload = image_plan if isinstance(image_plan, dict) else {}
    prompt_material = _prompt_material(image_generation=image_generation)
    entry: dict[str, object] = {
        "created_at": _timestamp(),
        "image_path": image_path,
        "artifact_path": artifact_path,
        "playbook_id": playbook_id,
        "account_id": account_id,
        "provider": str(image_generation.get("provider") or ""),
        "style": str(image_generation.get("style") or ""),
        "model": str(image_generation.get("model") or ""),
        "provenance_source": provenance_source,
        "image_plan": image_plan_payload,
        "prompt_hash": hashlib.sha256(prompt_material.encode("utf-8")).hexdigest(),
    }
    if page is not None:
        entry.update(
            {
                "carousel_plan_fingerprint": str(
                    image_generation.get("carousel_plan_fingerprint") or ""
                ),
                "set_id": str(image_generation.get("set_id") or ""),
                "manifest_sha256": str(
                    image_generation.get("manifest_sha256") or ""
                ),
                "slide_id": str(page.get("slide_id") or ""),
                "page_order": int(page["order"]),
                "page_role": str(page.get("role") or ""),
                "page_style": str(page.get("style") or ""),
                "page_sha256": str(page.get("page_sha256") or ""),
                "page_file_sha256": str(page.get("file_sha256") or ""),
            }
        )
    return entry


def _receipt_intent_ledger_projection(
    receipt_intent: Mapping[str, object],
) -> dict[str, object] | None:
    required_fields = {
        "account_id",
        "playbook_id",
        "artifact_path",
        "carousel_plan_fingerprint",
        "set_id",
        "manifest_sha256",
        "pages",
    }
    if set(receipt_intent) != required_fields:
        return None
    static_fields = {
        key: receipt_intent.get(key)
        for key in required_fields - {"pages"}
    }
    if (
        not all(isinstance(value, str) and value for value in static_fields.values())
        or not _is_lower_sha256(static_fields["carousel_plan_fingerprint"])
        or not _is_lower_sha256(static_fields["set_id"])
        or not _is_lower_sha256(static_fields["manifest_sha256"])
    ):
        return None
    raw_pages = receipt_intent.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        return None
    expected_pages: list[dict[str, object]] = []
    for expected_order, raw_page in enumerate(raw_pages, start=1):
        required_page_fields = {
            "order",
            "slide_id",
            "path",
            "page_sha256",
            "file_sha256",
        }
        if not isinstance(raw_page, Mapping) or set(raw_page) != required_page_fields:
            return None
        order = raw_page.get("order")
        slide_id = raw_page.get("slide_id")
        path = raw_page.get("path")
        page_sha256 = raw_page.get("page_sha256")
        file_sha256 = raw_page.get("file_sha256")
        if (
            not isinstance(order, int)
            or isinstance(order, bool)
            or order != expected_order
            or not isinstance(slide_id, str)
            or not slide_id
            or not isinstance(path, str)
            or not path
            or not _is_lower_sha256(page_sha256)
            or not _is_lower_sha256(file_sha256)
        ):
            return None
        expected_pages.append(
            {
                "order": order,
                "slide_id": slide_id,
                "path": path,
                "page_sha256": page_sha256,
                "file_sha256": file_sha256,
            }
        )
    return {**static_fields, "pages": expected_pages}


def _parse_ledger_entries(raw_ledger: bytes) -> list[dict[str, object]]:
    decoded = raw_ledger.decode("utf-8")
    if not decoded:
        return []
    entries: list[dict[str, object]] = []
    for line in decoded.splitlines():
        if not line:
            raise ValueError("generated image asset ledger contains a blank entry")
        entry = json.loads(line)
        if not isinstance(entry, dict):
            raise ValueError("generated image asset ledger entry must be an object")
        entries.append(entry)
    return entries


def _ledger_entry_matches_receipt_scope(
    entry: Mapping[str, object],
    *,
    expected_projection: Mapping[str, object],
) -> bool:
    return all(
        entry.get(key) == expected_projection.get(key)
        for key in (
            "account_id",
            "playbook_id",
            "artifact_path",
            "carousel_plan_fingerprint",
            "set_id",
            "manifest_sha256",
        )
    )


def _ledger_entry_projection(entry: Mapping[str, object]) -> dict[str, object]:
    return {
        "order": entry.get("page_order"),
        "slide_id": entry.get("slide_id"),
        "path": entry.get("image_path"),
        "page_sha256": entry.get("page_sha256"),
        "file_sha256": entry.get("page_file_sha256"),
    }


def _is_lower_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _ordered_page_evidence(
    *,
    image_generation: dict[str, Any],
    image_paths: list[str],
) -> list[dict[str, Any] | None]:
    pages_value = image_generation.get("pages")
    carousel_style = str(image_generation.get("carousel_style") or "").strip()
    declared_count = image_generation.get("image_count")
    if declared_count is not None and (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count != len(image_paths)
    ):
        raise ValueError("generated image count does not match image paths")
    if not carousel_style and pages_value is None:
        return [None] * len(image_paths)
    if not isinstance(pages_value, list) or len(pages_value) != len(image_paths):
        raise ValueError("carousel page evidence does not match image paths")

    pages: list[dict[str, Any] | None] = []
    for expected_order, (image_path, page_value) in enumerate(
        zip(image_paths, pages_value, strict=True),
        start=1,
    ):
        if not isinstance(page_value, dict):
            raise ValueError("carousel page evidence must contain objects")
        try:
            page_order = int(page_value["order"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("carousel page evidence has an invalid order") from exc
        if page_order != expected_order or str(page_value.get("path") or "") != image_path:
            raise ValueError("carousel page evidence does not match manifest order")
        pages.append(page_value)
    return pages


def _append_entries_atomically(
    *,
    pinned_directory: _PinnedLedgerDirectory,
    ledger_name: str,
    entries: list[dict[str, object]],
) -> None:
    encoded_entries = "".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        for entry in entries
    ).encode("utf-8")
    parent_fd = pinned_directory.parent_fd
    _assert_pinned_ledger_directory(pinned_directory)
    lock_name = f".{ledger_name}.lock"
    lock_fd = _open_or_create_ledger_lock(
        parent_fd=parent_fd,
        lock_name=lock_name,
    )
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            _assert_valid_ledger_lock(
                parent_fd=parent_fd,
                lock_name=lock_name,
                lock_fd=lock_fd,
            )
            _assert_pinned_ledger_directory(pinned_directory)
            existing, expected_ledger = _read_existing_ledger(
                parent_fd=parent_fd,
                ledger_name=ledger_name,
            )
            if existing and not existing.endswith(b"\n"):
                existing += b"\n"
            descriptor, temporary_name = _create_temporary_ledger(
                parent_fd=parent_fd,
                ledger_name=ledger_name,
            )
            replaced = False
            try:
                _write_descriptor(descriptor, existing + encoded_entries)
                os.fsync(descriptor)
                _assert_named_regular_single_link(
                    parent_fd=parent_fd,
                    entry_name=temporary_name,
                    descriptor=descriptor,
                    message="generated image asset ledger temporary file is invalid",
                )
                _assert_pinned_ledger_directory(pinned_directory)
                _assert_valid_ledger_lock(
                    parent_fd=parent_fd,
                    lock_name=lock_name,
                    lock_fd=lock_fd,
                )
                _assert_ledger_destination_unchanged(
                    parent_fd=parent_fd,
                    ledger_name=ledger_name,
                    expected=expected_ledger,
                )
                os.replace(
                    temporary_name,
                    ledger_name,
                    src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd,
                )
                replaced = True
                os.fsync(parent_fd)
                _assert_pinned_ledger_directory(pinned_directory)
                _assert_named_regular_single_link(
                    parent_fd=parent_fd,
                    entry_name=ledger_name,
                    descriptor=descriptor,
                    message="generated image asset ledger is invalid",
                )
                _assert_valid_ledger_lock(
                    parent_fd=parent_fd,
                    lock_name=lock_name,
                    lock_fd=lock_fd,
                )
            finally:
                os.close(descriptor)
                if not replaced:
                    _unlink_temporary_ledger(
                        parent_fd=parent_fd,
                        temporary_name=temporary_name,
                    )
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
    finally:
        os.close(lock_fd)


def _open_or_create_ledger_directory(*, base_dir: Path) -> _PinnedLedgerDirectory:
    descriptors: list[int] = []
    try:
        descriptors.append(_open_pinned_base_directory(base_dir=base_dir))
        for component in _LEDGER_DIRECTORY_COMPONENTS:
            _assert_pinned_directory_chain(
                base_path=base_dir,
                components=_LEDGER_DIRECTORY_COMPONENTS[: len(descriptors) - 1],
                descriptors=tuple(descriptors),
            )
            descriptors.append(
                _open_or_create_child_directory(
                    parent_fd=descriptors[-1],
                    component=component,
                )
            )
            _assert_pinned_directory_chain(
                base_path=base_dir,
                components=_LEDGER_DIRECTORY_COMPONENTS[: len(descriptors) - 1],
                descriptors=tuple(descriptors),
            )
        return _PinnedLedgerDirectory(
            base_path=base_dir,
            components=_LEDGER_DIRECTORY_COMPONENTS,
            descriptors=tuple(descriptors),
        )
    except BaseException:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
        raise


def _open_pinned_base_directory(*, base_dir: Path) -> int:
    flags = _directory_open_flags()
    descriptor: int | None = None
    try:
        path_identity = os.stat(base_dir, follow_symlinks=False)
        _assert_directory_identity(path_identity)
        descriptor = os.open(base_dir, flags)
        opened_identity = os.fstat(descriptor)
        final_identity = os.stat(base_dir, follow_symlinks=False)
        _assert_matching_directories(entry=path_identity, opened=opened_identity)
        _assert_matching_directories(entry=final_identity, opened=opened_identity)
        return descriptor
    except OSError as exc:
        if descriptor is not None:
            os.close(descriptor)
        raise _invalid_directory_error(exc.errno) from None


def _open_or_create_child_directory(*, parent_fd: int, component: str) -> int:
    created = False
    try:
        try:
            os.mkdir(component, 0o777, dir_fd=parent_fd)
            created = True
        except FileExistsError:
            pass
        if created:
            os.fsync(parent_fd)
        descriptor = os.open(
            component,
            _directory_open_flags(),
            dir_fd=parent_fd,
        )
    except OSError as exc:
        raise _invalid_directory_error(exc.errno) from None
    try:
        _assert_named_directory(
            parent_fd=parent_fd,
            component=component,
            descriptor=descriptor,
        )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _assert_pinned_ledger_directory(
    pinned_directory: _PinnedLedgerDirectory,
) -> None:
    _assert_pinned_directory_chain(
        base_path=pinned_directory.base_path,
        components=pinned_directory.components,
        descriptors=pinned_directory.descriptors,
    )


def _assert_pinned_directory_chain(
    *,
    base_path: Path,
    components: tuple[str, ...],
    descriptors: tuple[int, ...],
) -> None:
    if len(descriptors) != len(components) + 1:
        raise _invalid_directory_error(errno.ELOOP)
    try:
        base_entry = os.stat(base_path, follow_symlinks=False)
        base_identity = os.fstat(descriptors[0])
        _assert_matching_directories(entry=base_entry, opened=base_identity)
        for parent_fd, component, child_fd in zip(
            descriptors[:-1],
            components,
            descriptors[1:],
            strict=True,
        ):
            _assert_named_directory(
                parent_fd=parent_fd,
                component=component,
                descriptor=child_fd,
            )
    except OSError as exc:
        raise _invalid_directory_error(exc.errno) from None


def _assert_named_directory(
    *,
    parent_fd: int,
    component: str,
    descriptor: int,
) -> None:
    try:
        entry = os.stat(
            component,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        opened = os.fstat(descriptor)
    except OSError as exc:
        raise _invalid_directory_error(exc.errno) from None
    _assert_matching_directories(entry=entry, opened=opened)


def _assert_matching_directories(
    *,
    entry: os.stat_result,
    opened: os.stat_result,
) -> None:
    _assert_directory_identity(entry)
    _assert_directory_identity(opened)
    if not os.path.samestat(entry, opened):
        raise _invalid_directory_error(errno.ELOOP)


def _assert_directory_identity(identity: os.stat_result) -> None:
    if stat.S_ISLNK(identity.st_mode) or not stat.S_ISDIR(identity.st_mode):
        raise _invalid_directory_error(errno.ELOOP)


def _directory_open_flags() -> int:
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise _invalid_directory_error(errno.ENOTSUP)
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _invalid_directory_error(error_number: int | None) -> OSError:
    return OSError(
        error_number or errno.ELOOP,
        "generated image asset ledger directory is invalid",
    )


def _close_pinned_ledger_directory(
    pinned_directory: _PinnedLedgerDirectory,
) -> None:
    for descriptor in reversed(pinned_directory.descriptors):
        os.close(descriptor)


def _read_existing_ledger(
    *,
    parent_fd: int,
    ledger_name: str,
) -> tuple[bytes, os.stat_result | None]:
    try:
        entry_before = os.stat(
            ledger_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return b"", None
    except OSError as exc:
        raise _invalid_ledger_error(exc.errno) from None
    _assert_regular_single_link_identity(entry_before)

    if not hasattr(os, "O_NOFOLLOW"):
        raise _invalid_ledger_error(errno.ENOTSUP)
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(ledger_name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise _invalid_ledger_error(exc.errno) from None
    try:
        try:
            descriptor_before = os.fstat(descriptor)
        except OSError as exc:
            raise _invalid_ledger_error(exc.errno) from None
        _assert_matching_regular_single_link(
            entry=entry_before,
            identity=descriptor_before,
        )
        payload = _read_descriptor(descriptor)
        try:
            descriptor_after = os.fstat(descriptor)
            entry_after = os.stat(
                ledger_name,
                dir_fd=parent_fd,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise _invalid_ledger_error(exc.errno) from None
        if not (
            _stable_file_snapshot(entry_before)
            == _stable_file_snapshot(descriptor_before)
            == _stable_file_snapshot(descriptor_after)
            == _stable_file_snapshot(entry_after)
        ):
            raise _invalid_ledger_error(errno.ELOOP)
        return payload, entry_after
    finally:
        os.close(descriptor)


def _read_descriptor(descriptor: int) -> bytes:
    chunks: list[bytes] = []
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while chunk := os.read(descriptor, _LEDGER_READ_CHUNK_SIZE):
            chunks.append(chunk)
    except OSError as exc:
        raise _invalid_ledger_error(exc.errno) from None
    return b"".join(chunks)


def _create_temporary_ledger(*, parent_fd: int, ledger_name: str) -> tuple[int, str]:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError(
            errno.ENOTSUP,
            "generated image asset ledger temporary file is invalid",
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    flags |= getattr(os, "O_CLOEXEC", 0)
    for _ in range(_TEMP_CREATE_ATTEMPTS):
        temporary_name = f".{ledger_name}.{secrets.token_hex(16)}.tmp"
        try:
            descriptor = os.open(
                temporary_name,
                flags,
                0o600,
                dir_fd=parent_fd,
            )
        except FileExistsError:
            continue
        except OSError as exc:
            raise OSError(
                exc.errno or errno.EIO,
                "generated image asset ledger temporary file is invalid",
            ) from None
        try:
            _assert_named_regular_single_link(
                parent_fd=parent_fd,
                entry_name=temporary_name,
                descriptor=descriptor,
                message="generated image asset ledger temporary file is invalid",
            )
            return descriptor, temporary_name
        except BaseException:
            os.close(descriptor)
            _unlink_temporary_ledger(
                parent_fd=parent_fd,
                temporary_name=temporary_name,
            )
            raise
    raise OSError(
        errno.EEXIST,
        "generated image asset ledger temporary file is invalid",
    )


def _write_descriptor(descriptor: int, payload: bytes) -> None:
    remaining = memoryview(payload)
    try:
        while remaining:
            written = os.write(descriptor, remaining)
            if written <= 0:
                raise OSError(errno.EIO, "asset ledger write made no progress")
            remaining = remaining[written:]
    except OSError as exc:
        raise OSError(
            exc.errno or errno.EIO,
            "generated image asset ledger temporary file is invalid",
        ) from None


def _assert_ledger_destination_unchanged(
    *,
    parent_fd: int,
    ledger_name: str,
    expected: os.stat_result | None,
) -> None:
    try:
        observed = os.stat(
            ledger_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        if expected is None:
            return
        raise _invalid_ledger_error(errno.ENOENT) from None
    except OSError as exc:
        raise _invalid_ledger_error(exc.errno) from None
    if expected is None:
        raise _invalid_ledger_error(errno.ELOOP)
    _assert_regular_single_link_identity(observed)
    if _stable_file_snapshot(observed) != _stable_file_snapshot(expected):
        raise _invalid_ledger_error(errno.ELOOP)


def _assert_named_regular_single_link(
    *,
    parent_fd: int,
    entry_name: str,
    descriptor: int,
    message: str,
) -> None:
    try:
        entry = os.stat(
            entry_name,
            dir_fd=parent_fd,
            follow_symlinks=False,
        )
        identity = os.fstat(descriptor)
    except OSError as exc:
        raise OSError(exc.errno or errno.EIO, message) from None
    try:
        _assert_matching_regular_single_link(entry=entry, identity=identity)
    except OSError as exc:
        raise OSError(exc.errno or errno.ELOOP, message) from None


def _assert_matching_regular_single_link(
    *,
    entry: os.stat_result,
    identity: os.stat_result,
) -> None:
    _assert_regular_single_link_identity(entry)
    _assert_regular_single_link_identity(identity)
    if not os.path.samestat(entry, identity):
        raise _invalid_ledger_error(errno.ELOOP)


def _assert_regular_single_link_identity(identity: os.stat_result) -> None:
    if (
        stat.S_ISLNK(identity.st_mode)
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
    ):
        raise _invalid_ledger_error(errno.ELOOP)


def _stable_file_snapshot(identity: os.stat_result) -> tuple[int, ...]:
    return (
        identity.st_dev,
        identity.st_ino,
        identity.st_mode,
        identity.st_nlink,
        identity.st_size,
        identity.st_mtime_ns,
        identity.st_ctime_ns,
    )


def _invalid_ledger_error(error_number: int | None) -> OSError:
    return OSError(
        error_number or errno.ELOOP,
        "generated image asset ledger is invalid",
    )


def _unlink_temporary_ledger(*, parent_fd: int, temporary_name: str) -> None:
    try:
        os.unlink(temporary_name, dir_fd=parent_fd)
    except FileNotFoundError:
        return


def _open_or_create_ledger_lock(
    *,
    parent_fd: int,
    lock_name: str,
) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError(
            errno.ENOTSUP,
            "generated image asset ledger locking is unsupported",
        )
    flags = os.O_RDWR | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    created = False
    try:
        try:
            lock_fd = os.open(
                lock_name,
                flags | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=parent_fd,
            )
            created = True
        except FileExistsError:
            lock_fd = os.open(lock_name, flags, dir_fd=parent_fd)
    except OSError as exc:
        raise OSError(
            exc.errno or errno.ELOOP,
            "generated image asset ledger lock is invalid",
        ) from None
    try:
        _assert_valid_ledger_lock(
            parent_fd=parent_fd,
            lock_name=lock_name,
            lock_fd=lock_fd,
        )
        os.fsync(lock_fd)
        if created:
            os.fsync(parent_fd)
        _assert_valid_ledger_lock(
            parent_fd=parent_fd,
            lock_name=lock_name,
            lock_fd=lock_fd,
        )
        return lock_fd
    except BaseException:
        os.close(lock_fd)
        raise


def _assert_valid_ledger_lock(
    *,
    parent_fd: int,
    lock_name: str,
    lock_fd: int,
) -> None:
    try:
        entry = os.stat(lock_name, dir_fd=parent_fd, follow_symlinks=False)
        identity = os.fstat(lock_fd)
    except OSError:
        raise OSError(
            errno.ELOOP,
            "generated image asset ledger lock is invalid",
        ) from None
    if (
        not stat.S_ISREG(entry.st_mode)
        or stat.S_ISLNK(entry.st_mode)
        or not stat.S_ISREG(identity.st_mode)
        or entry.st_nlink != 1
        or identity.st_nlink != 1
        or not os.path.samestat(entry, identity)
    ):
        raise OSError(
            errno.ELOOP,
            "generated image asset ledger lock is invalid",
        )


def _prompt_material(*, image_generation: dict[str, Any]) -> str:
    prompt = image_generation.get("prompt")
    if prompt:
        return str(prompt)
    return json.dumps(
        {
            "provider": image_generation.get("provider"),
            "style": image_generation.get("style"),
            "model": image_generation.get("model"),
            "image_plan": image_generation.get("image_plan"),
            "runtime_context_summary": image_generation.get("runtime_context_summary"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
