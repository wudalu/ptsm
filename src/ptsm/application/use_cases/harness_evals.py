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
        "recent_failures": _recent_failures(
            runs=runs,
            plan_runs=plan_runs,
            limit=recent_failure_limit,
        ),
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


def _string_or_unknown(value: object) -> str:
    if value in {None, ""}:
        return "unknown"
    return str(value)
