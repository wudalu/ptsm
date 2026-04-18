from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from ptsm.application.use_cases.harness_report import run_harness_report
from ptsm.config.settings import Settings


class FakePreflightPublisher:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def preflight(self) -> dict[str, object]:
        return self.payload


def test_run_harness_report_composes_doctor_gc_and_evals(tmp_path: Path) -> None:
    _write_active_doc(
        tmp_path / "docs" / "runtime.md",
        last_verified="2026-01-01",
    )
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)

    _write_run(
        tmp_path / ".ptsm" / "runs" / "run-1",
        summary={
            "run_id": "run-1",
            "status": "completed",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "started_at": "2026-04-18T10:00:00+00:00",
            "finished_at": "2026-04-18T10:05:00+00:00",
        },
        events=[
            {
                "timestamp": "2026-04-18T10:01:00+00:00",
                "run_id": "run-1",
                "event": "publish_finished",
                "status": "completed",
            }
        ],
    )
    _write_run(
        tmp_path / ".ptsm" / "runs" / "run-2",
        summary={
            "run_id": "run-2",
            "status": "failed",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "started_at": "2026-04-18T11:00:00+00:00",
            "finished_at": "2026-04-18T11:05:00+00:00",
        },
        events=[
            {
                "timestamp": "2026-04-18T11:01:00+00:00",
                "run_id": "run-2",
                "event": "publish_finished",
                "status": "failed",
            }
        ],
    )
    _write_plan_run_pair(
        tmp_path / ".ptsm" / "plan_runs" / "demo-failed.json",
        generated_at="2026-04-18T13:00:00+00:00",
        status="failed",
        failure_reason="pytest_failed",
    )
    _write_plan_run_pair(
        tmp_path / ".ptsm" / "plan_runs" / "demo-passed.json",
        generated_at="2026-04-18T12:30:00+00:00",
        status="completed",
        failure_reason=None,
    )

    result = run_harness_report(
        settings=Settings(_env_file=None),
        publisher=FakePreflightPublisher({"status": "ready"}),
        project_root=tmp_path,
        now=datetime(2026, 4, 18, 14, 0, tzinfo=timezone.utc),
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
        max_stale_docs=0,
        max_gc_candidates=0,
        min_run_completion_rate=0.75,
        min_plan_completion_rate=0.75,
    )

    assert result["generated_at"] == "2026-04-18T14:00:00+00:00"
    assert result["filters"] == {
        "account_id": "acct-fk-local",
        "platform": "xiaohongshu",
        "playbook_id": "fengkuang_daily_post",
        "plan_path": None,
    }
    assert result["retention"] == {
        "runs_retention_days": 30,
        "plan_runs_retention_days": 30,
    }
    assert result["doctor"]["status"] == "warning"
    assert result["gc"]["status"] == "dry-run"
    assert result["evals"]["runs"]["completion_rate"] == 0.5
    assert result["evals"]["plan_runs"]["completion_rate"] == 0.5
    assert result["status"] == "warning"
    assert result["thresholds"] == {
        "configured": {
            "max_stale_docs": 0,
            "max_gc_candidates": 0,
            "min_run_completion_rate": 0.75,
            "min_plan_completion_rate": 0.75,
        },
        "violations": [
            {"name": "max_stale_docs", "actual": 1, "expected": "<= 0"},
            {"name": "min_run_completion_rate", "actual": 0.5, "expected": ">= 0.75"},
            {"name": "min_plan_completion_rate", "actual": 0.5, "expected": ">= 0.75"},
        ],
    }


def test_run_harness_report_marks_warning_when_only_thresholds_fail(
    tmp_path: Path,
) -> None:
    _write_active_doc(
        tmp_path / "docs" / "runtime.md",
        last_verified="2026-04-18",
    )
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)

    _write_run(
        tmp_path / ".ptsm" / "runs" / "run-1",
        summary={
            "run_id": "run-1",
            "status": "completed",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "started_at": "2026-04-18T10:00:00+00:00",
            "finished_at": "2026-04-18T10:05:00+00:00",
        },
        events=[],
    )
    _write_run(
        tmp_path / ".ptsm" / "runs" / "run-2",
        summary={
            "run_id": "run-2",
            "status": "failed",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "started_at": "2026-04-18T11:00:00+00:00",
            "finished_at": "2026-04-18T11:05:00+00:00",
        },
        events=[],
    )

    result = run_harness_report(
        settings=Settings(_env_file=None),
        publisher=FakePreflightPublisher({"status": "ready"}),
        project_root=tmp_path,
        now=datetime(2026, 4, 18, 14, 0, tzinfo=timezone.utc),
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
        min_run_completion_rate=0.9,
    )

    assert result["doctor"]["status"] == "ok"
    assert result["gc"]["candidate_count"] == 0
    assert result["thresholds"] == {
        "configured": {"min_run_completion_rate": 0.9},
        "violations": [
            {"name": "min_run_completion_rate", "actual": 0.5, "expected": ">= 0.9"}
        ],
    }
    assert result["status"] == "warning"


def _write_active_doc(path: Path, *, last_verified: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            "title: Demo Doc\n"
            "status: active\n"
            "owner: ptsm\n"
            f"last_verified: {last_verified}\n"
            "source_of_truth: true\n"
            "related_paths:\n"
            "  - src/demo.py\n"
            "---\n\n"
            "# Demo\n"
        ),
        encoding="utf-8",
    )


def _write_run(run_dir: Path, *, summary: dict[str, object], events: list[dict[str, object]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + ("\n" if events else ""),
        encoding="utf-8",
    )


def _write_plan_run_pair(
    state_path: Path,
    *,
    generated_at: str,
    status: str,
    failure_reason: str | None,
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "plan_path": "docs/plans/demo.md",
                "status": status,
                "tasks": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    evidence_path = state_path.with_suffix(".evidence.json")
    tasks = []
    if failure_reason is not None:
        tasks.append(
            {
                "title": "Task 1",
                "status": "failed",
                "failure_reason": failure_reason,
                "attempt_history": [],
            }
        )
    evidence_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "kind": "ptsm.run_plan.verification_evidence",
                "generated_at": generated_at,
                "plan_path": "docs/plans/demo.md",
                "state_path": str(state_path),
                "status": status,
                "tasks": tasks,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
