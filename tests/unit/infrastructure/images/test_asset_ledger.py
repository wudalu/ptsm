from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.infrastructure.images.asset_ledger import append_generated_image_assets


def test_append_generated_image_assets_writes_jsonl_entries(tmp_path: Path) -> None:
    image_path = tmp_path / "outputs" / "generated_images" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"png")

    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="fengkuang_daily_post",
        account_id="acct-fk-local",
        image_generation={
            "provider": "local_note_card",
            "style": "wechat_chat_v1",
            "model": "local-pillow-note-card",
            "generated_image_paths": [str(image_path)],
            "provenance": {"source": "ptsm_local_renderer"},
            "image_plan": {"role": "comment_prompt", "requested_style": "wechat_chat"},
        },
    )

    ledger_path = Path(result["ledger_path"])
    entries = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]

    assert result["status"] == "recorded"
    assert ledger_path == tmp_path / "outputs" / "artifacts" / "generated-image-assets" / "assets.jsonl"
    assert len(entries) == 1
    assert entries[0]["image_path"] == str(image_path)
    assert entries[0]["provider"] == "local_note_card"
    assert entries[0]["style"] == "wechat_chat_v1"
    assert entries[0]["model"] == "local-pillow-note-card"
    assert entries[0]["provenance_source"] == "ptsm_local_renderer"
    assert entries[0]["image_plan"]["role"] == "comment_prompt"
    assert entries[0]["artifact_path"] == str(tmp_path / "artifact.json")
    assert entries[0]["playbook_id"] == "fengkuang_daily_post"
    assert entries[0]["account_id"] == "acct-fk-local"
    assert entries[0]["prompt_hash"]
    assert entries[0]["created_at"]


def test_append_generated_image_assets_skips_when_no_generated_paths(tmp_path: Path) -> None:
    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="fengkuang_daily_post",
        account_id="acct-fk-local",
        image_generation=None,
    )

    assert result is None
    assert not (
        tmp_path / "outputs" / "artifacts" / "generated-image-assets" / "assets.jsonl"
    ).exists()


def test_append_generated_image_assets_records_carousel_pages_in_manifest_order(
    tmp_path: Path,
) -> None:
    image_dir = tmp_path / "outputs" / "generated_images" / "set-1"
    image_dir.mkdir(parents=True)
    image_paths = [image_dir / f"lesson-{order:02d}.png" for order in range(1, 5)]
    for path in image_paths:
        path.write_bytes(b"png")
    pages = [
        {
            "slide_id": f"slide-{order}",
            "order": order,
            "role": role,
            "style": "psychology_text_card_v1",
            "path": str(path),
            "filename": path.name,
            "file_sha256": f"hash-{order}",
        }
        for order, role, path in zip(
            range(1, 5),
            ("cover_hook", "concrete_scene", "light_mechanism", "save_tool"),
            image_paths,
            strict=True,
        )
    ]

    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="modern_psychology_post",
        account_id="acct-psychology-local",
        image_generation={
            "provider": "local_note_card",
            "style": "psychology_text_card_v1",
            "carousel_style": "psychology_text_card_v1",
            "image_count": 4,
            "set_id": "set-1",
            "manifest_sha256": "manifest-hash",
            "generated_image_paths": [str(path) for path in image_paths],
            "pages": pages,
            "provenance": {"source": "ptsm_local_renderer"},
        },
    )

    assert result is not None
    assert result["entry_count"] == 4
    entries = _read_jsonl(Path(result["ledger_path"]))
    assert [entry["page_order"] for entry in entries] == [1, 2, 3, 4]
    assert [entry["slide_id"] for entry in entries] == [
        "slide-1",
        "slide-2",
        "slide-3",
        "slide-4",
    ]
    assert entries[0]["page_role"] == "cover_hook"
    assert entries[-1]["page_role"] == "save_tool"
    assert all(entry["set_id"] == "set-1" for entry in entries)
    assert all(entry["manifest_sha256"] == "manifest-hash" for entry in entries)
    assert [entry["page_file_sha256"] for entry in entries] == [
        "hash-1",
        "hash-2",
        "hash-3",
        "hash-4",
    ]


def test_append_generated_image_assets_rejects_misaligned_carousel_page_evidence(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    with pytest.raises(ValueError, match="does not match"):
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={
                "generated_image_paths": [str(image_path)],
                "carousel_style": "psychology_text_card_v1",
                "image_count": 2,
                "pages": [],
            },
        )


def test_append_generated_image_assets_keeps_existing_ledger_on_batch_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    original = '{"existing": true}\n'
    ledger_path.write_text(original, encoding="utf-8")
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("ptsm.infrastructure.images.asset_ledger.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert ledger_path.read_text(encoding="utf-8") == original


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
