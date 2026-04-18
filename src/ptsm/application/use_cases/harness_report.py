from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ptsm.application.use_cases.doctor import run_doctor
from ptsm.application.use_cases.harness_gc import (
    DEFAULT_PLAN_RUNS_RETENTION_DAYS,
    DEFAULT_RUNS_RETENTION_DAYS,
    run_harness_gc,
)
from ptsm.application.use_cases.harness_evals import run_harness_evals
from ptsm.config.settings import Settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def run_harness_report(
    *,
    settings: Settings | None = None,
    publisher: XiaohongshuMcpPublisher | None = None,
    project_root: Path | str = ".",
    now: datetime | None = None,
    account_id: str | None = None,
    platform: str | None = None,
    playbook_id: str | None = None,
    plan_path: str | None = None,
    runs_retention_days: int = DEFAULT_RUNS_RETENTION_DAYS,
    plan_runs_retention_days: int = DEFAULT_PLAN_RUNS_RETENTION_DAYS,
    max_stale_docs: int | None = None,
    max_gc_candidates: int | None = None,
    min_run_completion_rate: float | None = None,
    min_plan_completion_rate: float | None = None,
) -> dict[str, object]:
    current_time = now or datetime.now(timezone.utc)
    root = Path(project_root)
    doctor = run_doctor(
        settings=settings,
        publisher=publisher,
        project_root=root,
        now=current_time,
        runs_retention_days=runs_retention_days,
        plan_runs_retention_days=plan_runs_retention_days,
    )
    gc = run_harness_gc(
        project_root=root,
        now=current_time,
        runs_retention_days=runs_retention_days,
        plan_runs_retention_days=plan_runs_retention_days,
        apply=False,
    )
    evals = run_harness_evals(
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
        plan_path=plan_path,
        runs_base_dir=root / ".ptsm" / "runs",
        plan_runs_base_dir=root / ".ptsm" / "plan_runs",
    )
    thresholds = _evaluate_thresholds(
        doctor=doctor,
        gc=gc,
        evals=evals,
        max_stale_docs=max_stale_docs,
        max_gc_candidates=max_gc_candidates,
        min_run_completion_rate=min_run_completion_rate,
        min_plan_completion_rate=min_plan_completion_rate,
    )

    return {
        "generated_at": current_time.isoformat(),
        "status": _overall_status(doctor=doctor, thresholds=thresholds),
        "filters": {
            "account_id": account_id,
            "platform": platform,
            "playbook_id": playbook_id,
            "plan_path": plan_path,
        },
        "retention": {
            "runs_retention_days": runs_retention_days,
            "plan_runs_retention_days": plan_runs_retention_days,
        },
        "doctor": doctor,
        "gc": gc,
        "evals": evals,
        "thresholds": thresholds,
    }


def _evaluate_thresholds(
    *,
    doctor: dict[str, object],
    gc: dict[str, object],
    evals: dict[str, object],
    max_stale_docs: int | None,
    max_gc_candidates: int | None,
    min_run_completion_rate: float | None,
    min_plan_completion_rate: float | None,
) -> dict[str, object]:
    configured: dict[str, int | float] = {}
    violations: list[dict[str, object]] = []

    stale_docs = _doctor_stale_docs(doctor)
    if max_stale_docs is not None:
        configured["max_stale_docs"] = max_stale_docs
        if stale_docs > max_stale_docs:
            violations.append(
                {
                    "name": "max_stale_docs",
                    "actual": stale_docs,
                    "expected": f"<= {max_stale_docs}",
                }
            )

    gc_candidates = int(gc.get("candidate_count", 0))
    if max_gc_candidates is not None:
        configured["max_gc_candidates"] = max_gc_candidates
        if gc_candidates > max_gc_candidates:
            violations.append(
                {
                    "name": "max_gc_candidates",
                    "actual": gc_candidates,
                    "expected": f"<= {max_gc_candidates}",
                }
            )

    run_completion_rate = float(evals["runs"]["completion_rate"])
    if min_run_completion_rate is not None:
        configured["min_run_completion_rate"] = min_run_completion_rate
        if run_completion_rate < min_run_completion_rate:
            violations.append(
                {
                    "name": "min_run_completion_rate",
                    "actual": run_completion_rate,
                    "expected": f">= {min_run_completion_rate}",
                }
            )

    plan_completion_rate = float(evals["plan_runs"]["completion_rate"])
    if min_plan_completion_rate is not None:
        configured["min_plan_completion_rate"] = min_plan_completion_rate
        if plan_completion_rate < min_plan_completion_rate:
            violations.append(
                {
                    "name": "min_plan_completion_rate",
                    "actual": plan_completion_rate,
                    "expected": f">= {min_plan_completion_rate}",
                }
            )

    return {
        "configured": configured,
        "violations": violations,
    }


def _doctor_stale_docs(doctor: dict[str, object]) -> int:
    checks = doctor.get("checks", [])
    if not isinstance(checks, list):
        return 0
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") != "harness_docs_freshness":
            continue
        details = check.get("details")
        if not isinstance(details, dict):
            return 0
        stale_docs = details.get("stale_docs", [])
        if not isinstance(stale_docs, list):
            return 0
        return len(stale_docs)
    return 0


def _overall_status(
    *,
    doctor: dict[str, object],
    thresholds: dict[str, object],
) -> str:
    doctor_status = str(doctor.get("status", "ok"))
    if doctor_status == "error":
        return "error"
    if thresholds["violations"]:
        return "warning"
    if doctor_status == "warning":
        return "warning"
    return "ok"
