from __future__ import annotations

from pathlib import Path

from ptsm.application.services.side_effect_ledger import SideEffectLedger


def test_side_effect_ledger_persists_records_and_requires_matching_key(
    tmp_path: Path,
) -> None:
    ledger_path = tmp_path / "side-effects.json"
    ledger = SideEffectLedger(path=ledger_path)

    ledger.record(
        thread_id="thread-1",
        step="publish",
        idempotency_key="publish:abc",
        result={"status": "published", "post_id": "post-123"},
    )

    reloaded = SideEffectLedger(path=ledger_path)

    assert reloaded.read(
        thread_id="thread-1",
        step="publish",
        idempotency_key="publish:abc",
    ) == {"status": "published", "post_id": "post-123"}
    assert (
        reloaded.read(
            thread_id="thread-1",
            step="publish",
            idempotency_key="publish:def",
        )
        is None
    )
