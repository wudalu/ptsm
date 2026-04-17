from __future__ import annotations

from pathlib import Path

from ptsm.infrastructure.observability.run_store import RunStore


def run_runs(
    *,
    account_id: str | None = None,
    platform: str | None = None,
    playbook_id: str | None = None,
    status: str | None = None,
    limit: int = 20,
    base_dir: Path | str = ".ptsm/runs",
) -> dict[str, object]:
    store = RunStore(base_dir=base_dir)
    runs = store.list_runs(
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
        status=status,
        limit=limit,
    )
    return {
        "count": len(runs),
        "runs": runs,
    }
