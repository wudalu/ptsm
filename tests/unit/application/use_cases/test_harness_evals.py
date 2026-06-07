from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.harness_evals import run_harness_evals


def test_run_harness_evals_aggregates_runs_events_and_plan_runs(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    plan_runs_dir = tmp_path / "plan_runs"

    _write_run(
        runs_dir / "run-1",
        summary={
            "run_id": "run-1",
            "status": "completed",
            "command": "run-fengkuang",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "activated_skills": ["xhs_trend_scan", "fengkuang_style"],
            "runtime_skill_details": [
                {
                    "skill_name": "xhs_trend_scan",
                    "resource_type": "runtime_context",
                    "resource_id": "xhs_trend_scan:runtime_context",
                }
            ],
            "started_at": "2026-04-18T10:00:00+00:00",
            "finished_at": "2026-04-18T10:05:00+00:00",
        },
        events=[
            {"timestamp": "2026-04-18T10:01:00+00:00", "run_id": "run-1", "event": "publish_finished", "status": "completed"},
        ],
    )
    _write_run(
        runs_dir / "run-2",
        summary={
            "run_id": "run-2",
            "status": "failed",
            "command": "run-fengkuang",
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "activated_skills": ["xhs_trend_scan", "positive_reframe"],
            "runtime_skill_details": [
                {
                    "skill_name": "xhs_trend_scan",
                    "resource_type": "runtime_context",
                    "resource_id": "xhs_trend_scan:runtime_context",
                }
            ],
            "started_at": "2026-04-18T11:00:00+00:00",
            "finished_at": "2026-04-18T11:05:00+00:00",
        },
        events=[
            {"timestamp": "2026-04-18T11:01:00+00:00", "run_id": "run-2", "event": "publish_finished", "status": "failed"},
        ],
    )
    _write_run(
        runs_dir / "run-3",
        summary={
            "run_id": "run-3",
            "status": "completed",
            "command": "run-fengkuang",
            "account_id": "acct-other",
            "platform": "douyin",
            "playbook_id": "other_playbook",
            "activated_skills": ["other_skill"],
            "runtime_skill_details": [],
            "started_at": "2026-04-18T12:00:00+00:00",
            "finished_at": "2026-04-18T12:05:00+00:00",
        },
        events=[
            {"timestamp": "2026-04-18T12:01:00+00:00", "run_id": "run-3", "event": "publish_finished", "status": "completed"},
        ],
    )

    _write_plan_run(
        plan_runs_dir / "demo-failed.evidence.json",
        payload={
            "generated_at": "2026-04-18T13:00:00+00:00",
            "plan_path": "docs/plans/demo.md",
            "state_path": str(plan_runs_dir / "demo-failed.json"),
            "status": "failed",
            "tasks": [
                {
                    "title": "Task 1",
                    "status": "failed",
                    "failure_reason": "pytest_failed",
                    "attempt_history": [],
                }
            ],
        },
    )
    _write_plan_run(
        plan_runs_dir / "demo-passed.evidence.json",
        payload={
            "generated_at": "2026-04-18T12:30:00+00:00",
            "plan_path": "docs/plans/demo.md",
            "state_path": str(plan_runs_dir / "demo-passed.json"),
            "status": "completed",
            "tasks": [],
        },
    )

    result = run_harness_evals(
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
        runs_base_dir=runs_dir,
        plan_runs_base_dir=plan_runs_dir,
    )

    assert result["filters"] == {
        "account_id": "acct-fk-local",
        "platform": "xiaohongshu",
        "playbook_id": "fengkuang_daily_post",
        "plan_path": None,
    }
    assert result["runs"] == {
        "total": 2,
        "completed": 1,
        "completion_rate": 0.5,
        "by_status": {"completed": 1, "failed": 1},
        "by_platform": {"xiaohongshu": 2},
        "by_playbook_id": {"fengkuang_daily_post": 2},
    }
    assert result["events"] == {
        "total": 2,
        "by_event": {"publish_finished": 2},
        "by_status": {"completed": 1, "failed": 1},
    }
    assert result["plan_runs"] == {
        "total": 2,
        "completed": 1,
        "completion_rate": 0.5,
        "by_status": {"completed": 1, "failed": 1},
        "by_failure_reason": {"pytest_failed": 1},
    }
    assert result["skills"] == {
        "total_runs_with_skills": 2,
        "by_skill": {
            "xhs_trend_scan": {
                "runs": 2,
                "completed": 1,
                "completion_rate": 0.5,
                "runtime_context_runs": 2,
            },
            "fengkuang_style": {
                "runs": 1,
                "completed": 1,
                "completion_rate": 1.0,
                "runtime_context_runs": 0,
            },
            "positive_reframe": {
                "runs": 1,
                "completed": 0,
                "completion_rate": 0.0,
                "runtime_context_runs": 0,
            },
        },
    }
    assert result["recent_failures"] == [
        {
            "kind": "plan_run",
            "timestamp": "2026-04-18T13:00:00+00:00",
            "status": "failed",
            "plan_path": "docs/plans/demo.md",
            "failure_reasons": ["pytest_failed"],
        },
        {
            "kind": "run",
            "timestamp": "2026-04-18T11:05:00+00:00",
            "status": "failed",
            "run_id": "run-2",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
        },
    ]


def test_run_harness_evals_filters_eval_runs_by_scope(tmp_path: Path) -> None:
    evals_dir = tmp_path / "evals"
    _write_eval_run(
        evals_dir / "eval-1",
        summary={
            "eval_run_id": "eval-1",
            "suite_id": "fengkuang_daily_post.default",
            "status": "failed",
            "source": {
                "kind": "artifact",
                "path": "a.json",
                "run_id": "run-1",
                "account_id": "acct-fk-local",
                "platform": "xiaohongshu",
                "playbook_id": "fengkuang_daily_post",
            },
            "counts": {
                "targets": 1,
                "evaluators": 1,
                "passed": 0,
                "failed": 1,
                "warnings": 0,
                "errors": 0,
            },
        },
    )
    _write_eval_run(
        evals_dir / "eval-2",
        summary={
            "eval_run_id": "eval-2",
            "suite_id": "classic_poetry_quote_post.default",
            "status": "passed",
            "source": {
                "kind": "artifact",
                "path": "b.json",
                "run_id": "run-2",
                "account_id": "acct-classic-poetry-local",
                "platform": "xiaohongshu",
                "playbook_id": "classic_poetry_quote_post",
            },
            "counts": {
                "targets": 1,
                "evaluators": 1,
                "passed": 1,
                "failed": 0,
                "warnings": 0,
                "errors": 0,
            },
        },
    )

    result = run_harness_evals(
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
        runs_base_dir=tmp_path / "runs",
        plan_runs_base_dir=tmp_path / "plan_runs",
        evals_base_dir=evals_dir,
    )

    assert result["evals"] == {
        "eval_runs_total": 1,
        "by_status": {"failed": 1},
        "by_suite": {"fengkuang_daily_post.default": 1},
        "results": {
            "total_passed": 0,
            "total_failed": 1,
            "total_warnings": 0,
            "total_errors": 0,
            "required_failed": 1,
            "warning_failed": 0,
        },
    }


def _write_run(run_dir: Path, *, summary: dict[str, object], events: list[dict[str, object]]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n",
        encoding="utf-8",
    )


def _write_plan_run(path: Path, *, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "kind": "ptsm.run_plan.verification_evidence",
                **payload,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_eval_run(run_dir: Path, *, summary: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
