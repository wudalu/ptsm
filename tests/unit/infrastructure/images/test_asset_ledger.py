from __future__ import annotations

import json
from pathlib import Path

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
