from __future__ import annotations

import json
from pathlib import Path

from ptsm.infrastructure.observability.run_store import RunStore


def test_run_store_writes_events_and_summary(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)

    run = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.append_event(
        run.run_id,
        event="publish_started",
        step="publish",
        payload={"mode": "dry-run"},
    )
    summary = store.finish(
        run.run_id,
        status="completed",
        payload={"artifact_path": "outputs/artifacts/demo.json"},
    )

    events_path = tmp_path / run.run_id / "events.jsonl"
    summary_path = tmp_path / run.run_id / "summary.json"

    assert events_path.exists()
    assert summary_path.exists()

    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert events[0]["event"] == "run_started"
    assert events[1]["event"] == "publish_started"
    assert events[-1]["event"] == "run_finished"
    assert events[-1]["status"] == "completed"

    saved_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["run_id"] == run.run_id
    assert saved_summary["status"] == "completed"
    assert saved_summary["artifact_path"] == "outputs/artifacts/demo.json"
