from __future__ import annotations

import json
from pathlib import Path

from ptsm.infrastructure.observability.run_store import RunStore


def run_logs(
    *,
    run_id: str | None = None,
    artifact_path: Path | None = None,
    base_dir: Path | str = ".ptsm/runs",
) -> dict[str, object]:
    """Read stored run summary and events by run id or artifact path."""
    resolved_run_id = run_id or _resolve_run_id_from_artifact(artifact_path)
    if not resolved_run_id:
        raise ValueError("logs requires --run-id or an artifact containing run.run_id")

    store = RunStore(base_dir=base_dir)
    return {
        "run_id": resolved_run_id,
        "summary": store.read_summary(resolved_run_id),
        "events": store.read_events(resolved_run_id),
    }


def _resolve_run_id_from_artifact(artifact_path: Path | None) -> str | None:
    if artifact_path is None:
        return None
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    run = payload.get("run")
    if not isinstance(run, dict):
        return None
    run_id = run.get("run_id")
    return str(run_id) if isinstance(run_id, str) and run_id.strip() else None
