from __future__ import annotations

from collections import Counter
from pathlib import Path

from ptsm.application.use_cases.plan_runs import run_plan_runs
from ptsm.infrastructure.observability.run_store import RunStore


def run_harness_evals(
    *,
    account_id: str | None = None,
    platform: str | None = None,
    playbook_id: str | None = None,
    plan_path: str | None = None,
    runs_base_dir: Path | str = ".ptsm/runs",
    plan_runs_base_dir: Path | str = ".ptsm/plan_runs",
    evals_base_dir: Path | str = ".ptsm/evals",
    recent_failure_limit: int = 10,
) -> dict[str, object]:
    store = RunStore(base_dir=runs_base_dir)
    runs = store.list_runs(
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
        limit=None,
    )
    run_events = store.list_events(
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
        limit=None,
    )
    plan_runs = run_plan_runs(
        plan_path=plan_path,
        limit=None,
        base_dir=plan_runs_base_dir,
    )["runs"]

    run_statuses = Counter(str(item.get("status", "unknown")) for item in runs)
    run_platforms = Counter(_string_or_unknown(item.get("platform")) for item in runs)
    run_playbooks = Counter(_string_or_unknown(item.get("playbook_id")) for item in runs)
    event_names = Counter(str(item.get("event", "unknown")) for item in run_events)
    event_statuses = Counter(_string_or_unknown(item.get("status")) for item in run_events)
    plan_statuses = Counter(str(item.get("status", "unknown")) for item in plan_runs)
    failure_reasons = Counter(
        reason
        for item in plan_runs
        for reason in item.get("failure_reasons", [])
        if reason
    )
    skill_stats = _aggregate_skill_stats(runs)
    eval_stats = _aggregate_eval_results(
        evals_base_dir=evals_base_dir,
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
    )

    return {
        "filters": {
            "account_id": account_id,
            "platform": platform,
            "playbook_id": playbook_id,
            "plan_path": plan_path,
        },
        "runs": {
            "total": len(runs),
            "completed": run_statuses.get("completed", 0),
            "completion_rate": _completion_rate(run_statuses.get("completed", 0), len(runs)),
            "by_status": dict(run_statuses),
            "by_platform": dict(run_platforms),
            "by_playbook_id": dict(run_playbooks),
        },
        "events": {
            "total": len(run_events),
            "by_event": dict(event_names),
            "by_status": dict(event_statuses),
        },
        "plan_runs": {
            "total": len(plan_runs),
            "completed": plan_statuses.get("completed", 0),
            "completion_rate": _completion_rate(
                plan_statuses.get("completed", 0), len(plan_runs)
            ),
            "by_status": dict(plan_statuses),
            "by_failure_reason": dict(failure_reasons),
        },
        "skills": skill_stats,
        "recent_failures": _recent_failures(
            runs=runs,
            plan_runs=plan_runs,
            limit=recent_failure_limit,
        ),
        "evals": eval_stats,
    }


def _completion_rate(completed: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(completed / total, 3)


def _recent_failures(
    *,
    runs: list[dict[str, object]],
    plan_runs: list[dict[str, object]],
    limit: int,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    for item in plan_runs:
        if item.get("status") != "failed":
            continue
        failures.append(
            {
                "kind": "plan_run",
                "timestamp": item.get("generated_at"),
                "status": item.get("status"),
                "plan_path": item.get("plan_path"),
                "failure_reasons": list(item.get("failure_reasons", [])),
            }
        )
    for item in runs:
        if item.get("status") != "failed":
            continue
        failures.append(
            {
                "kind": "run",
                "timestamp": item.get("finished_at") or item.get("started_at"),
                "status": item.get("status"),
                "run_id": item.get("run_id"),
                "platform": item.get("platform"),
                "playbook_id": item.get("playbook_id"),
            }
        )

    failures.sort(key=lambda item: str(item.get("timestamp", "")), reverse=True)
    return failures[:limit]


def _aggregate_skill_stats(runs: list[dict[str, object]]) -> dict[str, object]:
    by_skill: dict[str, dict[str, int | float]] = {}
    runs_with_skills = 0

    for run in runs:
        activated_skills = run.get("activated_skills")
        if not isinstance(activated_skills, list) or not activated_skills:
            continue

        runs_with_skills += 1
        completed = run.get("status") == "completed"
        runtime_context_skills = {
            str(item.get("skill_name"))
            for item in run.get("runtime_skill_details", [])
            if isinstance(item, dict) and item.get("skill_name")
        }

        for skill_name in activated_skills:
            skill_key = str(skill_name)
            current = by_skill.setdefault(
                skill_key,
                {
                    "runs": 0,
                    "completed": 0,
                    "runtime_context_runs": 0,
                },
            )
            current["runs"] = int(current["runs"]) + 1
            if completed:
                current["completed"] = int(current["completed"]) + 1
            if skill_key in runtime_context_skills:
                current["runtime_context_runs"] = int(current["runtime_context_runs"]) + 1

    for skill_name, stats in by_skill.items():
        stats["completion_rate"] = _completion_rate(
            int(stats["completed"]), int(stats["runs"])
        )

    return {
        "total_runs_with_skills": runs_with_skills,
        "by_skill": by_skill,
    }


def _string_or_unknown(value: object) -> str:
    if value in {None, ""}:
        return "unknown"
    return str(value)


def _aggregate_eval_results(
    evals_base_dir: Path | str = ".ptsm/evals",
    *,
    account_id: str | None = None,
    platform: str | None = None,
    playbook_id: str | None = None,
) -> dict[str, object]:
    from ptsm.infrastructure.evaluations.eval_store import EvalStore

    store = EvalStore(base_dir=evals_base_dir)
    eval_runs = [
        run
        for run in store.list_eval_runs(limit=None)
        if _eval_run_matches_scope(
            run,
            account_id=account_id,
            platform=platform,
            playbook_id=playbook_id,
        )
    ]

    statuses = Counter(str(r.get("status", "unknown")) for r in eval_runs)
    suite_ids = Counter(str(r.get("suite_id", "unknown")) for r in eval_runs)

    total_passed = 0
    total_failed = 0
    total_warnings = 0
    total_errors = 0
    required_failed = 0
    warning_failed = 0
    for r in eval_runs:
        counts = r.get("counts", {})
        if isinstance(counts, dict):
            total_passed += int(counts.get("passed", 0))
            total_failed += int(counts.get("failed", 0))
            total_warnings += int(counts.get("warnings", 0))
            total_errors += int(counts.get("errors", 0))
        gate = r.get("gate", {})
        if isinstance(gate, dict):
            required_failed += int(
                gate.get("required_failed", counts.get("failed", 0) if isinstance(counts, dict) else 0)
            )
            warning_failed += int(gate.get("warning_failed", 0))

    return {
        "eval_runs_total": len(eval_runs),
        "by_status": dict(statuses),
        "by_suite": dict(suite_ids),
        "results": {
            "total_passed": total_passed,
            "total_failed": total_failed,
            "total_warnings": total_warnings,
            "total_errors": total_errors,
            "required_failed": required_failed,
            "warning_failed": warning_failed,
        },
    }


def _eval_run_matches_scope(
    eval_run: dict[str, object],
    *,
    account_id: str | None,
    platform: str | None,
    playbook_id: str | None,
) -> bool:
    source = eval_run.get("source", {})
    if not isinstance(source, dict):
        return account_id is None and platform is None and playbook_id is None
    if account_id is not None and source.get("account_id") != account_id:
        return False
    if platform is not None and source.get("platform") != platform:
        return False
    if playbook_id is not None and source.get("playbook_id") != playbook_id:
        return False
    return True
