from __future__ import annotations

import errno
import hashlib
import os
import re
import stat
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_READ_CHUNK_SIZE = 1024 * 1024


class ImageFileEvidenceError(ValueError):
    """Raised when an image set cannot be verified without following aliases."""

    _MESSAGES = {
        "image_file_set_empty": "At least one image path is required",
        "image_file_path_invalid": "image path is invalid",
        "image_file_missing": "image path is missing",
        "image_file_symlink_rejected": "image path symlink is not allowed",
        "image_file_not_regular": "image path must be a regular file",
        "image_file_unreadable": "image path must be readable",
        "image_file_duplicate": "image paths contain duplicate files",
        "image_file_evidence_invalid": "image file evidence is invalid",
        "image_file_hash_mismatch": "image file hash does not match evidence",
        "image_file_identity_changed": "image file changed during verification",
    }

    def __init__(self, code: str):
        self.code = code
        super().__init__(f"{code}: {self._MESSAGES[code]}")


@dataclass(frozen=True)
class _ExpectedPage:
    path: str
    file_sha256: str


@dataclass(frozen=True)
class _OpenedImageFile:
    path: str
    descriptor: int
    before: os.stat_result
    opened: os.stat_result


def verify_image_file_set(
    *,
    image_paths: Sequence[str],
    expected_pages: Sequence[Mapping[str, object]] | None = None,
) -> list[str]:
    """Verify regular image files and optional ordered hash evidence.

    Paths are opened without following symlinks where the platform supports it.
    Device/inode identity is compared between ``lstat``, the opened descriptor,
    and a final path lookup so aliases and path replacement are rejected.
    """

    paths = _normalize_paths(image_paths)
    pages = _normalize_expected_pages(expected_pages=expected_pages, image_paths=paths)
    opened_files: list[_OpenedImageFile] = []
    try:
        seen_identities: set[tuple[int, int]] = set()
        for path in paths:
            opened_file = _open_image_file(path)
            opened_files.append(opened_file)
            identity = _identity(opened_file.opened)
            if identity in seen_identities:
                raise ImageFileEvidenceError("image_file_duplicate")
            seen_identities.add(identity)

        digests = [
            _descriptor_sha256(opened_file.descriptor)
            for opened_file in opened_files
        ]

        for opened_file in opened_files:
            _verify_final_snapshot(opened_file)

        if pages is not None:
            for digest, expected_page in zip(digests, pages, strict=True):
                if digest != expected_page.file_sha256:
                    raise ImageFileEvidenceError("image_file_hash_mismatch")
    finally:
        for opened_file in opened_files:
            os.close(opened_file.descriptor)

    return paths


def _normalize_paths(image_paths: Sequence[str]) -> list[str]:
    if isinstance(image_paths, (str, bytes)):
        raise ImageFileEvidenceError("image_file_path_invalid")
    paths: list[str] = []
    for value in image_paths:
        if not isinstance(value, str) or not value.strip():
            raise ImageFileEvidenceError("image_file_path_invalid")
        paths.append(value)
    if not paths:
        raise ImageFileEvidenceError("image_file_set_empty")
    return paths


def _normalize_expected_pages(
    *,
    expected_pages: Sequence[Mapping[str, object]] | None,
    image_paths: list[str],
) -> list[_ExpectedPage] | None:
    if expected_pages is None:
        return None
    if isinstance(expected_pages, (str, bytes)) or len(expected_pages) != len(
        image_paths
    ):
        raise ImageFileEvidenceError("image_file_evidence_invalid")

    pages: list[_ExpectedPage] = []
    for expected_order, (image_path, page) in enumerate(
        zip(image_paths, expected_pages, strict=True),
        start=1,
    ):
        if not isinstance(page, Mapping):
            raise ImageFileEvidenceError("image_file_evidence_invalid")
        order = page.get("order")
        evidence_path = page.get("path")
        file_sha256 = page.get("file_sha256")
        if (
            not isinstance(order, int)
            or isinstance(order, bool)
            or order != expected_order
            or not isinstance(evidence_path, str)
            or evidence_path != image_path
            or not isinstance(file_sha256, str)
            or _SHA256_RE.fullmatch(file_sha256) is None
        ):
            raise ImageFileEvidenceError("image_file_evidence_invalid")
        pages.append(_ExpectedPage(path=evidence_path, file_sha256=file_sha256))
    return pages


def _open_image_file(path: str) -> _OpenedImageFile:
    before = _safe_lstat(path)
    if stat.S_ISLNK(before.st_mode):
        raise ImageFileEvidenceError("image_file_symlink_rejected")
    if not stat.S_ISREG(before.st_mode):
        raise ImageFileEvidenceError("image_file_not_regular")

    descriptor = _safe_open(path)
    try:
        opened = _safe_fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise ImageFileEvidenceError("image_file_not_regular")
        if _identity(before) != _identity(opened):
            raise ImageFileEvidenceError("image_file_identity_changed")
        return _OpenedImageFile(
            path=path,
            descriptor=descriptor,
            before=before,
            opened=opened,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _verify_final_snapshot(opened_file: _OpenedImageFile) -> None:
    after_descriptor = _safe_fstat(opened_file.descriptor)
    after_path = _safe_lstat(opened_file.path)
    if stat.S_ISLNK(after_path.st_mode):
        raise ImageFileEvidenceError("image_file_identity_changed")
    if not stat.S_ISREG(after_path.st_mode):
        raise ImageFileEvidenceError("image_file_identity_changed")
    if not (
        _stable_snapshot(opened_file.before)
        == _stable_snapshot(opened_file.opened)
        == _stable_snapshot(after_descriptor)
        == _stable_snapshot(after_path)
    ):
        raise ImageFileEvidenceError("image_file_identity_changed")


def _safe_lstat(path: str) -> os.stat_result:
    try:
        return os.lstat(path)
    except FileNotFoundError:
        raise ImageFileEvidenceError("image_file_missing") from None
    except OSError:
        raise ImageFileEvidenceError("image_file_unreadable") from None


def _safe_open(path: str) -> int:
    flags = os.O_RDONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_NONBLOCK", 0)
    try:
        return os.open(path, flags)
    except OSError as exc:
        if exc.errno == errno.ELOOP:
            raise ImageFileEvidenceError("image_file_symlink_rejected") from None
        if exc.errno == errno.ENOENT:
            raise ImageFileEvidenceError("image_file_missing") from None
        raise ImageFileEvidenceError("image_file_unreadable") from None


def _safe_fstat(descriptor: int) -> os.stat_result:
    try:
        return os.fstat(descriptor)
    except OSError:
        raise ImageFileEvidenceError("image_file_unreadable") from None


def _descriptor_sha256(descriptor: int) -> str:
    digest = hashlib.sha256()
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        while chunk := os.read(descriptor, _READ_CHUNK_SIZE):
            digest.update(chunk)
    except OSError:
        raise ImageFileEvidenceError("image_file_unreadable") from None
    return digest.hexdigest()


def _identity(value: os.stat_result) -> tuple[int, int]:
    return (value.st_dev, value.st_ino)


def _stable_snapshot(value: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
