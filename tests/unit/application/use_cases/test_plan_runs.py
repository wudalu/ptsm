from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.plan_runs import run_plan_runs


def test_run_plan_runs_filters_evidence_summaries(tmp_path: Path) -> None:
    failed_path = tmp_path / "demo-run.evidence.json"
    failed_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "kind": "ptsm.run_plan.verification_evidence",
                "generated_at": "2026-04-18T10:00:00+00:00",
                "plan_path": "docs/plans/demo.md",
                "state_path": str(tmp_path / "demo-run.json"),
                "status": "failed",
                "tasks": [
                    {
                        "title": "Task 1: Parser",
                        "status": "failed",
                        "attempts": 1,
                        "last_failure": "Verification failed",
                        "failure_reason": "pytest_failed",
                        "attempt_history": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    completed_path = tmp_path / "other-run.evidence.json"
    completed_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "kind": "ptsm.run_plan.verification_evidence",
                "generated_at": "2026-04-18T11:00:00+00:00",
                "plan_path": "docs/plans/other.md",
                "state_path": str(tmp_path / "other-run.json"),
                "status": "completed",
                "tasks": [
                    {
                        "title": "Task 1: Runner",
                        "status": "passed",
                        "attempts": 1,
                        "last_failure": "",
                        "failure_reason": None,
                        "attempt_history": [],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_plan_runs(
        base_dir=tmp_path,
        status="failed",
        failure_reason="pytest_failed",
        plan_path="demo",
        limit=5,
    )

    assert result["count"] == 1
    assert result["runs"][0]["artifact_path"] == str(failed_path)
    assert result["runs"][0]["failure_reasons"] == ["pytest_failed"]
    assert result["runs"][0]["failed_task_count"] == 1
