from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.logs import run_logs
from ptsm.infrastructure.observability.run_store import RunStore


def test_run_logs_reads_events_by_run_id(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)
    run = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
    )
    store.append_event(
        run.run_id,
        event="publish_started",
        step="publish",
        payload={"mode": "dry-run"},
    )
    store.finish(run.run_id, status="completed")

    result = run_logs(run_id=run.run_id, base_dir=tmp_path)

    assert result["run_id"] == run.run_id
    assert result["summary"]["status"] == "completed"
    assert result["events"][1]["event"] == "publish_started"


def test_run_logs_resolves_run_id_from_artifact(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path / "runs")
    run = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
    )
    store.finish(run.run_id, status="completed")

    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "run": {"run_id": run.run_id},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_logs(artifact_path=artifact_path, base_dir=tmp_path / "runs")

    assert result["run_id"] == run.run_id
    assert result["summary"]["status"] == "completed"
