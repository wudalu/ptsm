from __future__ import annotations

from pathlib import Path

from ptsm.application.use_cases.run_events import run_run_events
from ptsm.infrastructure.observability.run_store import RunStore


def test_run_run_events_returns_filtered_events_and_totals(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)

    completed = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.append_event(
        completed.run_id,
        event="publish_finished",
        step="publish",
        status="completed",
    )
    store.finish(completed.run_id, status="completed")

    failed = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.append_event(
        failed.run_id,
        event="publish_finished",
        step="publish",
        status="failed",
    )
    store.finish(failed.run_id, status="failed")

    result = run_run_events(
        base_dir=tmp_path,
        account_id="acct-fk-local",
        event="publish_finished",
        step="publish",
        group_by="status",
        limit=10,
    )

    assert result["count"] == 2
    assert result["group_by"] == "status"
    assert result["totals"] == {"completed": 1, "failed": 1}
    assert {item["status"] for item in result["events"]} == {"completed", "failed"}
