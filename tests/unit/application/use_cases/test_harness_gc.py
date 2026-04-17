from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from ptsm.application.use_cases.harness_gc import run_harness_gc


def test_run_harness_gc_reports_stale_candidates_in_dry_run(tmp_path: Path) -> None:
    _write_completed_run(
        tmp_path / ".ptsm" / "runs" / "run-old",
        finished_at="2026-01-01T00:00:00+00:00",
    )
    _write_completed_plan_run(tmp_path / ".ptsm" / "plan_runs" / "demo.json")
    orphan_evidence = tmp_path / ".ptsm" / "plan_runs" / "orphan.evidence.json"
    orphan_evidence.parent.mkdir(parents=True, exist_ok=True)
    orphan_evidence.write_text("{}", encoding="utf-8")
    _set_old_mtime(orphan_evidence)

    result = run_harness_gc(
        project_root=tmp_path,
        now=datetime(2026, 4, 18, tzinfo=timezone.utc),
        runs_retention_days=30,
        plan_runs_retention_days=30,
    )

    assert result["status"] == "dry-run"
    assert result["candidate_count"] == 3
    reasons = {candidate["reason"] for candidate in result["candidates"]}
    assert reasons == {
        "stale_completed_run",
        "stale_completed_plan_run",
        "orphan_plan_run_evidence",
    }


def test_run_harness_gc_apply_removes_only_safe_candidates(tmp_path: Path) -> None:
    stale_run_dir = tmp_path / ".ptsm" / "runs" / "run-old"
    _write_completed_run(
        stale_run_dir,
        finished_at="2026-01-01T00:00:00+00:00",
    )
    stale_plan_state = tmp_path / ".ptsm" / "plan_runs" / "demo.json"
    stale_plan_evidence = _write_completed_plan_run(stale_plan_state)
    orphan_evidence = tmp_path / ".ptsm" / "plan_runs" / "orphan.evidence.json"
    orphan_evidence.write_text("{}", encoding="utf-8")
    _set_old_mtime(orphan_evidence)

    in_progress_state = tmp_path / ".ptsm" / "plan_runs" / "keep.json"
    in_progress_state.parent.mkdir(parents=True, exist_ok=True)
    in_progress_state.write_text(
        json.dumps({"status": "in_progress"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    runtime_state = tmp_path / ".ptsm" / "agent_runtime" / "execution-memory.json"
    runtime_state.parent.mkdir(parents=True, exist_ok=True)
    runtime_state.write_text("{}", encoding="utf-8")

    result = run_harness_gc(
        project_root=tmp_path,
        now=datetime(2026, 4, 18, tzinfo=timezone.utc),
        runs_retention_days=30,
        plan_runs_retention_days=30,
        apply=True,
    )

    assert result["status"] == "applied"
    assert result["removed_count"] == 3
    assert not stale_run_dir.exists()
    assert not stale_plan_state.exists()
    assert not stale_plan_evidence.exists()
    assert not orphan_evidence.exists()
    assert in_progress_state.exists()
    assert runtime_state.exists()


def _write_completed_run(run_dir: Path, *, finished_at: str) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "summary.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "status": "completed",
                "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": finished_at,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (run_dir / "events.jsonl").write_text("", encoding="utf-8")


def _write_completed_plan_run(state_path: Path) -> Path:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "plan_path": "docs/plans/demo.md",
                "status": "completed",
                "tasks": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _set_old_mtime(state_path)

    evidence_path = state_path.with_suffix(".evidence.json")
    evidence_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "tasks": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _set_old_mtime(evidence_path)
    return evidence_path


def _set_old_mtime(path: Path) -> None:
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp()
    path.touch(exist_ok=True)
    path.chmod(0o644)
    import os

    os.utime(path, (timestamp, timestamp))
