from __future__ import annotations

import json
from pathlib import Path

from ptsm.infrastructure.artifacts.file_store import FileArtifactStore


def test_file_artifact_store_merge_updates_existing_artifact(tmp_path: Path) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = store.write(
        {
            "playbook_id": "fengkuang_daily_post",
            "final_content": {"title": "打工人地铁生存实录"},
        },
        run_key="artifact-demo",
    )

    updated_path = store.merge(
        artifact_path,
        {
            "publish_result": {"status": "published"},
            "account": {"account_id": "acct-fk-local"},
            "publish_mode": "mcp-real",
        },
    )

    artifact = json.loads(updated_path.read_text(encoding="utf-8"))

    assert updated_path == artifact_path
    assert artifact["playbook_id"] == "fengkuang_daily_post"
    assert artifact["final_content"]["title"] == "打工人地铁生存实录"
    assert artifact["publish_result"]["status"] == "published"
    assert artifact["account"]["account_id"] == "acct-fk-local"
    assert artifact["publish_mode"] == "mcp-real"
