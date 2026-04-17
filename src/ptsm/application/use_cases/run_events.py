from __future__ import annotations

from pathlib import Path

from ptsm.infrastructure.observability.run_store import RunStore


def run_run_events(
    *,
    account_id: str | None = None,
    platform: str | None = None,
    playbook_id: str | None = None,
    run_status: str | None = None,
    event: str | None = None,
    step: str | None = None,
    event_status: str | None = None,
    group_by: str | None = None,
    limit: int = 50,
    base_dir: Path | str = ".ptsm/runs",
) -> dict[str, object]:
    store = RunStore(base_dir=base_dir)
    events = store.list_events(
        account_id=account_id,
        platform=platform,
        playbook_id=playbook_id,
        run_status=run_status,
        event=event,
        step=step,
        event_status=event_status,
        limit=limit,
    )
    return {
        "count": len(events),
        "events": events,
        "group_by": group_by,
        "totals": (
            store.aggregate_events(
                account_id=account_id,
                platform=platform,
                playbook_id=playbook_id,
                run_status=run_status,
                event=event,
                step=step,
                event_status=event_status,
                group_by=group_by,
            )
            if group_by is not None
            else {}
        ),
    }
