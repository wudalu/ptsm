from __future__ import annotations

from pathlib import Path

from ptsm.application.use_cases.runs import run_runs
from ptsm.infrastructure.observability.run_store import RunStore


def test_run_runs_returns_filtered_summaries(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)

    skipped = store.start(
        command="run-fengkuang",
        account_id="acct-other",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.finish(skipped.run_id, status="failed")

    run = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    store.finish(run.run_id, status="completed")

    result = run_runs(
        base_dir=tmp_path,
        account_id="acct-fk-local",
        platform="xiaohongshu",
        status="completed",
        limit=5,
    )

    assert result["count"] == 1
    assert result["runs"][0]["run_id"] == run.run_id
    assert result["runs"][0]["account_id"] == "acct-fk-local"
