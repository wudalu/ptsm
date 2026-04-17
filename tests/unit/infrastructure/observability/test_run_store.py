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


def test_run_store_lists_recent_runs_with_filters(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)

    skipped = store.start(
        command="run-fengkuang",
        account_id="acct-other",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.finish(skipped.run_id, status="failed")

    older = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.finish(older.run_id, status="completed")

    newest = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.finish(newest.run_id, status="completed")

    result = store.list_runs(
        account_id="acct-fk-local",
        platform="xiaohongshu",
        status="completed",
        limit=2,
    )

    assert [item["run_id"] for item in result] == [newest.run_id, older.run_id]


def test_run_store_lists_filtered_events_across_runs(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)

    skipped = store.start(
        command="run-fengkuang",
        account_id="acct-other",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.append_event(
        skipped.run_id,
        event="publish_started",
        step="publish",
        status="running",
    )
    store.finish(skipped.run_id, status="failed")

    matched = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.append_event(
        matched.run_id,
        event="publish_started",
        step="publish",
        status="running",
    )
    store.finish(matched.run_id, status="completed")

    events = store.list_events(
        account_id="acct-fk-local",
        playbook_id="fengkuang_daily_post",
        event="publish_started",
        step="publish",
        limit=10,
    )

    assert len(events) == 1
    assert events[0]["run_id"] == matched.run_id
    assert events[0]["account_id"] == "acct-fk-local"
    assert events[0]["event"] == "publish_started"


def test_run_store_aggregates_events_by_field(tmp_path: Path) -> None:
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

    totals = store.aggregate_events(
        account_id="acct-fk-local",
        step="publish",
        event="publish_finished",
        group_by="status",
    )

    assert totals == {"completed": 1, "failed": 1}
