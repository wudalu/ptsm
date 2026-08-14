from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ptsm.infrastructure.images import image_file_evidence
from ptsm.infrastructure.images.image_file_evidence import (
    ImageFileEvidenceError,
    verify_image_file_set,
)


def _page_evidence(path: Path, *, order: int = 1) -> dict[str, object]:
    return {
        "order": order,
        "path": str(path),
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def test_verify_image_file_set_rejects_symlink_without_leaking_path(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target.png"
    target.write_bytes(b"png")
    alias = tmp_path / "alias.png"
    alias.symlink_to(target)

    with pytest.raises(ImageFileEvidenceError) as exc_info:
        verify_image_file_set(image_paths=[str(alias)])

    assert exc_info.value.code == "image_file_symlink_rejected"
    assert str(alias) not in str(exc_info.value)
    assert str(target) not in str(exc_info.value)


def test_verify_image_file_set_rejects_hardlink_aliases(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    first.write_bytes(b"png")
    alias = tmp_path / "alias.png"
    os.link(first, alias)

    with pytest.raises(ImageFileEvidenceError) as exc_info:
        verify_image_file_set(image_paths=[str(first), str(alias)])

    assert exc_info.value.code == "image_file_duplicate"


def test_verify_image_file_set_rejects_hash_mismatch(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    evidence = _page_evidence(image_path)
    evidence["file_sha256"] = "0" * 64

    with pytest.raises(ImageFileEvidenceError) as exc_info:
        verify_image_file_set(
            image_paths=[str(image_path)],
            expected_pages=[evidence],
        )

    assert exc_info.value.code == "image_file_hash_mismatch"


def test_verify_image_file_set_rejects_earlier_page_mutated_while_hashing_later_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = tmp_path / "page-1.png"
    first.write_bytes(b"page-one")
    second = tmp_path / "page-2.png"
    second.write_bytes(b"page-two")
    evidence = [
        _page_evidence(first, order=1),
        _page_evidence(second, order=2),
    ]
    original_descriptor_sha256 = image_file_evidence._descriptor_sha256
    hash_calls = 0

    def _mutate_first_while_hashing_second(descriptor: int) -> str:
        nonlocal hash_calls
        hash_calls += 1
        if hash_calls == 2:
            first.write_bytes(b"page-one-mutated")
        return original_descriptor_sha256(descriptor)

    monkeypatch.setattr(
        image_file_evidence,
        "_descriptor_sha256",
        _mutate_first_while_hashing_second,
    )

    with pytest.raises(ImageFileEvidenceError) as exc_info:
        verify_image_file_set(
            image_paths=[str(first), str(second)],
            expected_pages=evidence,
        )

    assert exc_info.value.code == "image_file_identity_changed"


def test_verify_image_file_set_requires_exact_contiguous_page_evidence(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    evidence = _page_evidence(image_path, order=2)

    with pytest.raises(ImageFileEvidenceError) as exc_info:
        verify_image_file_set(
            image_paths=[str(image_path)],
            expected_pages=[evidence],
        )

    assert exc_info.value.code == "image_file_evidence_invalid"
