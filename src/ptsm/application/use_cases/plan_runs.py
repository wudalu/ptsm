from __future__ import annotations

import json
from pathlib import Path


def run_plan_runs(
    *,
    status: str | None = None,
    failure_reason: str | None = None,
    plan_path: str | None = None,
    limit: int | None = 20,
    base_dir: Path | str = ".ptsm/plan_runs",
) -> dict[str, object]:
    base_path = Path(base_dir)
    runs: list[dict[str, object]] = []
    for artifact_path in base_path.glob("*.evidence.json"):
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        summary = _summarize_plan_run(payload=payload, artifact_path=artifact_path)
        if status is not None and summary.get("status") != status:
            continue
        if failure_reason is not None and failure_reason not in summary["failure_reasons"]:
            continue
        if plan_path is not None and plan_path not in str(summary.get("plan_path", "")):
            continue
        runs.append(summary)

    runs.sort(key=lambda item: str(item.get("generated_at", "")), reverse=True)
    limited_runs = runs if limit is None else runs[:limit]
    return {
        "count": len(limited_runs),
        "runs": limited_runs,
    }


def _summarize_plan_run(
    *,
    payload: dict[str, object],
    artifact_path: Path,
) -> dict[str, object]:
    tasks = payload.get("tasks", [])
    failure_reasons = sorted(
        {
            str(reason)
            for task in tasks
            if isinstance(task, dict)
            for reason in _task_failure_reasons(task)
            if reason
        }
    )
    failed_task_count = sum(
        1 for task in tasks if isinstance(task, dict) and task.get("status") == "failed"
    )
    return {
        "artifact_path": str(artifact_path),
        "state_path": payload.get("state_path"),
        "plan_path": payload.get("plan_path"),
        "status": payload.get("status"),
        "generated_at": payload.get("generated_at"),
        "task_count": len(tasks) if isinstance(tasks, list) else 0,
        "failed_task_count": failed_task_count,
        "failure_reasons": failure_reasons,
    }


def _task_failure_reasons(task: dict[str, object]) -> list[str]:
    reasons = [
        str(attempt.get("failure_reason"))
        for attempt in task.get("attempt_history", [])
        if isinstance(attempt, dict) and attempt.get("failure_reason")
    ]
    if reasons:
        return reasons
    task_reason = task.get("failure_reason")
    return [str(task_reason)] if task_reason else []
