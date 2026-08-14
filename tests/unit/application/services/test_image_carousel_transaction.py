from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Any

from PIL import Image
import pytest

import ptsm.application.services.image_carousel_transaction as transaction_module
from ptsm.application.services.image_carousel_transaction import (
    ImageCarouselTransaction,
    ImageCarouselTransactionError,
    verify_committed_carousel_set,
)


def _carousel_plan() -> dict[str, Any]:
    return {
        "backend": "local_social_screenshot",
        "style": "psychology_text_card",
        "role": "text_carousel",
        "text_density": "medium",
        "max_text_units": "4",
        "cover_text_strategy": "低密度问题式封面",
        "reason": "用语义分页说明一个关系不确定主题",
        "prompt_focus": "只呈现事实、猜测、需要和一个保存工具",
        "carousel_style": "psychology_text_card_v1",
        "slides": [
            {
                "slide_id": "cover",
                "order": 1,
                "role": "cover_hook",
                "headline": "他没回消息，我先想到了分手",
                "body_lines": ["先别急着给沉默下结论"],
            },
            {
                "slide_id": "scene",
                "order": 2,
                "role": "concrete_scene",
                "headline": "十分钟里看了八次手机",
                "body_lines": ["消息停在已发送", "身体却像已经听到答案"],
            },
            {
                "slide_id": "mechanism",
                "order": 3,
                "role": "light_mechanism",
                "headline": "不确定会催着大脑补剧情",
                "body_lines": ["事实是暂时没回复", "猜测是关系要结束"],
            },
            {
                "slide_id": "tool",
                "order": 4,
                "role": "save_tool",
                "headline": "把三栏写下来再行动",
                "body_lines": ["事实：我发出了一条消息", "猜测：他准备离开", "需要：确认彼此状态"],
            },
        ],
    }


class _ScriptedRenderer:
    provider_name = "local_note_card"

    def __init__(self, mode: str = "ok", *, seed_offset: int = 0) -> None:
        self.mode = mode
        self.seed_offset = seed_offset
        self.calls: list[dict[str, Any]] = []
        self.first_path: Path | None = None

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        payload = json.loads(prompt)
        self.calls.append(payload)
        call_number = len(self.calls)
        output_path = output_dir / f"{output_stem}.png"

        if self.mode == "raise" and call_number == 2:
            raise RuntimeError("injected middle-page failure")
        if self.mode == "duplicate" and call_number == 2:
            assert self.first_path is not None
            return self._result(self.first_path)
        if self.mode == "escape" and call_number == 2:
            escaped_path = output_dir.parent / "escaped.png"
            self._write_png(escaped_path, call_number)
            return self._result(escaped_path)
        if self.mode == "missing" and call_number == 2:
            return self._result(output_path)
        if self.mode == "directory" and call_number == 2:
            output_path.mkdir(parents=True)
            return self._result(output_path)
        if self.mode == "wrong" and call_number == 2:
            wrong_path = output_dir / "wrong.png"
            self._write_png(wrong_path, call_number)
            return self._result(wrong_path)
        if self.mode == "not_png" and call_number == 2:
            output_path.write_text("not a png", encoding="utf-8")
            return self._result(output_path)
        if self.mode == "symlink" and call_number == 2:
            escaped_path = output_dir.parent / "symlink-target.png"
            self._write_png(escaped_path, call_number)
            output_path.symlink_to(escaped_path)
            return self._result(output_path)
        if self.mode == "hardlink" and call_number == 2:
            escaped_path = output_dir.parent / "hardlink-target.png"
            self._write_png(escaped_path, call_number)
            os.link(escaped_path, output_path)
            return self._result(output_path)

        self._write_png(output_path, int(payload["order"]) + self.seed_offset)
        if call_number == 1:
            self.first_path = output_path
        if self.mode == "unreadable" and call_number == 2:
            output_path.chmod(0)
        if self.mode == "multiple" and call_number == 2:
            extra_path = output_dir / "extra.png"
            self._write_png(extra_path, call_number + 20)
            result = self._result(output_path)
            result["generated_image_paths"] = [str(output_path), str(extra_path)]
            return result
        if self.mode == "extra" and call_number == 2:
            self._write_png(output_dir / "unreported.png", call_number + 20)
        if self.mode == "mutate_previous" and call_number == 2:
            assert self.first_path is not None
            self._write_png(self.first_path, call_number + 30)
        result = self._result(output_path)
        if self.mode == "external_provenance":
            result["provenance"] = {
                "source": "external_provider",
                "renderer": "_ScriptedRenderer",
                "watermark_removal": "skip",
            }
        return result

    @staticmethod
    def _write_png(path: Path, seed: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (48, 64), (seed * 20, 80, 140)).save(path, format="PNG")

    @staticmethod
    def _result(path: Path) -> dict[str, object]:
        return {
            "status": "generated",
            "provider": "local_note_card",
            "style": "psychology_text_card_v1",
            "model": "scripted-png",
            "generated_image_paths": [str(path)],
            "provenance": {
                "source": "ptsm_local_renderer",
                "renderer": "_ScriptedRenderer",
                "watermark_removal": "skip",
            },
        }


def _transaction(renderer: _ScriptedRenderer) -> ImageCarouselTransaction:
    return ImageCarouselTransaction(renderer=renderer)


def _final_directories(output_dir: Path) -> list[Path]:
    if not output_dir.exists():
        return []
    return sorted(
        path
        for path in output_dir.iterdir()
        if path.is_dir() and "staging" not in path.name
    )


def test_transaction_commits_ordered_hashed_manifest_and_stable_names(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"
    renderer = _ScriptedRenderer()

    result = _transaction(renderer).generate(
        image_plan=_carousel_plan(),
        output_dir=output_dir,
        output_stem="artifact",
    )

    assert result["status"] == "committed"
    assert result["provider"] == "local_note_card"
    assert result["style"] == "psychology_text_card_v1"
    assert result["carousel_style"] == "psychology_text_card_v1"
    assert result["image_count"] == 4
    assert result["provenance"] == {
        "source": "ptsm_local_renderer",
        "renderer": "_ScriptedRenderer",
        "watermark_removal": "skip",
    }
    assert len(result["set_id"]) == 64
    assert set(result["set_id"]) <= set("0123456789abcdef")
    assert [Path(path).name for path in result["generated_image_paths"]] == [
        "artifact-01-cover.png",
        "artifact-02-scene.png",
        "artifact-03-mechanism.png",
        "artifact-04-tool.png",
    ]
    assert len({Path(path).parent for path in result["generated_image_paths"]}) == 1
    assert all("staging" not in path for path in result["generated_image_paths"])

    manifest_path = Path(result["manifest_path"])
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert manifest["set_id"] == result["set_id"]
    assert manifest["image_count"] == 4
    assert manifest["carousel_style"] == "psychology_text_card_v1"
    assert [page["order"] for page in manifest["pages"]] == [1, 2, 3, 4]
    assert [page["slide_id"] for page in manifest["pages"]] == [
        "cover",
        "scene",
        "mechanism",
        "tool",
    ]
    assert result["pages"] == manifest["pages"]
    assert result["manifest_sha256"] == hashlib.sha256(manifest_bytes).hexdigest()
    for page, generated_path in zip(
        manifest["pages"], result["generated_image_paths"], strict=True
    ):
        page_path = Path(generated_path)
        assert page["filename"] == page_path.name
        assert page["style"] == "psychology_text_card_v1"
        assert len(page["page_sha256"]) == 64
        assert len(page["prompt_sha256"]) == 64
        assert page["file_sha256"] == hashlib.sha256(page_path.read_bytes()).hexdigest()
        with Image.open(page_path) as image:
            assert image.format == "PNG"
            assert image.size == (48, 64)
    assert not list(output_dir.glob(".*staging*"))
    assert [page["order"] for page in renderer.calls] == [1, 2, 3, 4]
    assert all(set(page) == {
        "style", "slide_id", "order", "role", "headline", "body_lines", "page_count"
    } for page in renderer.calls)


def test_transaction_validates_the_complete_plan_before_rendering(tmp_path: Path) -> None:
    renderer = _ScriptedRenderer()
    plan = _carousel_plan()
    plan["slides"][2]["order"] = 4

    with pytest.raises(ValueError, match="order"):
        _transaction(renderer).generate(
            image_plan=plan,
            output_dir=tmp_path / "images",
            output_stem="artifact",
        )

    assert renderer.calls == []
    assert not (tmp_path / "images").exists()


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("duplicate", "duplicate"),
        ("escape", "outside"),
        ("missing", "missing"),
        ("unreadable", "readable"),
        ("directory", "regular"),
        ("multiple", "exactly one"),
        ("wrong", "wrong stable path"),
        ("not_png", "PNG"),
        ("symlink", "regular"),
        ("hardlink", "single-link"),
        ("external_provenance", "local provenance"),
    ],
)
def test_transaction_rejects_invalid_renderer_outputs_and_cleans_only_owned_staging(
    tmp_path: Path,
    mode: str,
    message: str,
) -> None:
    output_dir = tmp_path / "images"
    sentinel = output_dir / ".keep"
    sentinel.mkdir(parents=True)
    (sentinel / "owned-by-someone-else.txt").write_text("keep", encoding="utf-8")
    renderer = _ScriptedRenderer(mode)

    with pytest.raises(ImageCarouselTransactionError, match=message):
        _transaction(renderer).generate(
            image_plan=_carousel_plan(),
            output_dir=output_dir,
            output_stem="artifact",
        )

    assert sentinel.is_dir()
    assert (sentinel / "owned-by-someone-else.txt").read_text(encoding="utf-8") == "keep"
    assert not list(output_dir.glob(".*staging*"))
    assert _final_directories(output_dir) == [sentinel]
    if mode == "escape":
        assert (output_dir / "escaped.png").is_file()


@pytest.mark.parametrize("mode", ["extra", "mutate_previous"])
def test_transaction_revalidates_the_complete_staging_set_before_rename(
    monkeypatch,
    tmp_path: Path,
    mode: str,
) -> None:
    rename_calls: list[tuple[Path, Path]] = []
    original_rename = transaction_module.os.rename

    def record_rename(source: str | Path, destination: str | Path) -> None:
        rename_calls.append((Path(source), Path(destination)))
        original_rename(source, destination)

    monkeypatch.setattr(transaction_module.os, "rename", record_rename)

    with pytest.raises(ImageCarouselTransactionError, match="staging|changed"):
        _transaction(_ScriptedRenderer(mode)).generate(
            image_plan=_carousel_plan(),
            output_dir=tmp_path / "images",
            output_stem="artifact",
        )

    assert rename_calls == []
    assert _final_directories(tmp_path / "images") == []


def test_transaction_middle_page_failure_leaves_no_visible_set(tmp_path: Path) -> None:
    output_dir = tmp_path / "images"

    with pytest.raises(
        ImageCarouselTransactionError,
        match="page 2.*injected middle-page failure",
    ):
        _transaction(_ScriptedRenderer("raise")).generate(
            image_plan=_carousel_plan(),
            output_dir=output_dir,
            output_stem="artifact",
        )

    assert _final_directories(output_dir) == []
    assert not list(output_dir.glob(".*staging*"))


def test_owned_directory_cleanup_does_not_delete_a_swapped_in_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"
    owned = output_dir / ".artifact-staging-owned"
    displaced_owned = output_dir / ".artifact-staging-displaced"
    victim = output_dir / "operator-owned"
    owned.mkdir(parents=True)
    (owned / "runtime-page.png").write_bytes(b"runtime-owned")
    victim.mkdir()
    sentinel = victim / "must-survive.txt"
    sentinel.write_text("keep", encoding="utf-8")
    owned_identity = owned.lstat()
    original_lstat = Path.lstat
    swapped = False

    def swap_after_identity_check(path: Path) -> os.stat_result:
        nonlocal swapped
        identity = original_lstat(path)
        if path == owned and not swapped:
            owned.rename(displaced_owned)
            victim.rename(owned)
            swapped = True
        return identity

    monkeypatch.setattr(Path, "lstat", swap_after_identity_check)

    transaction_module._cleanup_owned_directory(owned, owned_identity)

    assert swapped
    assert (owned / sentinel.name).read_text(encoding="utf-8") == "keep"
    assert (displaced_owned / "runtime-page.png").read_bytes() == b"runtime-owned"


@pytest.mark.parametrize("output_stem", ["../escape", "nested/name", ".", ""])
def test_transaction_rejects_unsafe_output_stems_before_rendering(
    tmp_path: Path,
    output_stem: str,
) -> None:
    renderer = _ScriptedRenderer()

    with pytest.raises(ValueError, match="output_stem"):
        _transaction(renderer).generate(
            image_plan=_carousel_plan(),
            output_dir=tmp_path / "images",
            output_stem=output_stem,
        )

    assert renderer.calls == []


def test_transaction_rejects_a_symlink_output_directory_before_rendering(
    tmp_path: Path,
) -> None:
    real_output = tmp_path / "real-images"
    real_output.mkdir()
    linked_output = tmp_path / "images"
    linked_output.symlink_to(real_output, target_is_directory=True)
    renderer = _ScriptedRenderer()

    with pytest.raises(ImageCarouselTransactionError, match="symlink"):
        _transaction(renderer).generate(
            image_plan=_carousel_plan(),
            output_dir=linked_output,
            output_stem="artifact",
        )

    assert renderer.calls == []
    assert list(real_output.iterdir()) == []


def test_transaction_idempotently_reuses_an_identical_committed_set(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"
    transaction = _transaction(_ScriptedRenderer())

    first = transaction.generate(
        image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
    )
    second = transaction.generate(
        image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
    )

    assert second == first
    assert len(transaction.renderer.calls) == 8
    assert len(_final_directories(output_dir)) == 1
    assert not list(output_dir.glob(".*staging*"))


def test_transaction_safely_rolls_back_its_committed_set_when_final_verify_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"

    def fail_post_commit_verification(**_: object) -> dict[str, object]:
        raise ImageCarouselTransactionError("injected post-commit verification failure")

    monkeypatch.setattr(
        transaction_module,
        "_reuse_identical_set",
        fail_post_commit_verification,
    )

    with pytest.raises(
        ImageCarouselTransactionError,
        match="post-commit verification failure",
    ):
        _transaction(_ScriptedRenderer()).generate(
            image_plan=_carousel_plan(),
            output_dir=output_dir,
            output_stem="artifact",
        )

    assert _final_directories(output_dir) == []
    assert not list(output_dir.glob(".*staging*"))


def test_transaction_set_id_is_addressed_by_rendered_content(tmp_path: Path) -> None:
    first = _transaction(_ScriptedRenderer(seed_offset=0)).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "first",
        output_stem="artifact",
    )
    second = _transaction(_ScriptedRenderer(seed_offset=5)).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "second",
        output_stem="artifact",
    )

    assert first["set_id"] != second["set_id"]


def test_transaction_rejects_unknown_fields_in_a_committed_manifest(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"
    transaction = _transaction(_ScriptedRenderer())
    first = transaction.generate(
        image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
    )
    manifest_path = Path(first["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["unexpected"] = "field"
    manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ImageCarouselTransactionError, match="conflicting manifest"):
        transaction.generate(
            image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
        )


def test_committed_set_verifier_rejects_a_hardlinked_manifest(tmp_path: Path) -> None:
    receipt = _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )
    manifest_path = Path(receipt["manifest_path"])
    linked_copy = tmp_path / "manifest-copy.json"
    manifest_path.rename(linked_copy)
    os.link(linked_copy, manifest_path)

    with pytest.raises(ImageCarouselTransactionError, match="manifest"):
        verify_committed_carousel_set(
            image_plan=_carousel_plan(),
            receipt=receipt,
            output_stem="artifact",
        )


def test_transaction_fails_closed_when_existing_manifest_conflicts(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "images"
    transaction = _transaction(_ScriptedRenderer())
    first = transaction.generate(
        image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
    )
    manifest_path = Path(first["manifest_path"])
    manifest_path.write_text('{"set_id":"forged"}\n', encoding="utf-8")

    with pytest.raises(ImageCarouselTransactionError, match="conflicting manifest"):
        transaction.generate(
            image_plan=_carousel_plan(), output_dir=output_dir, output_stem="artifact"
        )

    assert manifest_path.read_text(encoding="utf-8") == '{"set_id":"forged"}\n'
    assert len(_final_directories(output_dir)) == 1
    assert not list(output_dir.glob(".*staging*"))


def test_transaction_fsyncs_manifest_and_staging_before_atomic_rename(
    monkeypatch,
    tmp_path: Path,
) -> None:
    events: list[str] = []
    original_fsync = transaction_module.os.fsync
    original_rename = transaction_module.os.rename

    def record_fsync(fd: int) -> None:
        mode = os.fstat(fd).st_mode
        events.append("directory-fsync" if stat.S_ISDIR(mode) else "file-fsync")
        original_fsync(fd)

    def record_rename(source: str | Path, destination: str | Path) -> None:
        assert "file-fsync" in events
        assert "directory-fsync" in events
        events.append("rename")
        original_rename(source, destination)

    monkeypatch.setattr(transaction_module.os, "fsync", record_fsync)
    monkeypatch.setattr(transaction_module.os, "rename", record_rename)

    _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )

    assert events.index("file-fsync") < events.index("rename")
    assert events.index("directory-fsync") < events.index("rename")
    assert "directory-fsync" in events[events.index("rename") + 1 :]


def test_committed_set_verifier_returns_the_exact_canonical_receipt(
    tmp_path: Path,
) -> None:
    receipt = _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )

    verified = verify_committed_carousel_set(
        image_plan=_carousel_plan(),
        receipt=receipt,
        output_stem="artifact",
    )

    assert verified == receipt


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_path",
        "missing_path",
        "manifest_hash",
        "set_id",
        "image_count",
        "unknown_field",
    ],
)
def test_committed_set_verifier_rejects_tampered_receipts(
    tmp_path: Path,
    mutation: str,
) -> None:
    receipt = _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )
    tampered = dict(receipt)
    if mutation == "wrong_path":
        paths = list(tampered["generated_image_paths"])
        paths[1] = str(tmp_path / "wrong.png")
        tampered["generated_image_paths"] = paths
    elif mutation == "missing_path":
        tampered["generated_image_paths"] = list(
            tampered["generated_image_paths"]
        )[:-1]
    elif mutation == "manifest_hash":
        tampered["manifest_sha256"] = "0" * 64
    elif mutation == "set_id":
        tampered["set_id"] = "0" * 64
    elif mutation == "image_count":
        tampered["image_count"] = 3
    else:
        tampered["unexpected"] = "field"

    with pytest.raises(ImageCarouselTransactionError, match="receipt"):
        verify_committed_carousel_set(
            image_plan=_carousel_plan(),
            receipt=tampered,
            output_stem="artifact",
        )


def test_committed_set_verifier_rejects_an_unreadable_committed_page(
    tmp_path: Path,
) -> None:
    receipt = _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )
    Path(receipt["generated_image_paths"][1]).chmod(0)

    with pytest.raises(ImageCarouselTransactionError, match="readable"):
        verify_committed_carousel_set(
            image_plan=_carousel_plan(),
            receipt=receipt,
            output_stem="artifact",
        )


def test_committed_set_verifier_rejects_a_manifest_from_the_wrong_stem(
    tmp_path: Path,
) -> None:
    receipt = _transaction(_ScriptedRenderer()).generate(
        image_plan=_carousel_plan(),
        output_dir=tmp_path / "images",
        output_stem="artifact",
    )

    with pytest.raises(ImageCarouselTransactionError, match="receipt"):
        verify_committed_carousel_set(
            image_plan=_carousel_plan(),
            receipt=receipt,
            output_stem="other-artifact",
        )
