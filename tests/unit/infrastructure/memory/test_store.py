from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ptsm.infrastructure.memory.store import FileExecutionMemory, InMemoryExecutionMemory


def test_file_execution_memory_persists_records_across_instances(
    tmp_path: Path,
) -> None:
    memory_path = tmp_path / "execution-memory.json"
    namespace = ("accounts", "acct-fk-local", "lessons")
    lesson = {
        "playbook_id": "fengkuang_daily_post",
        "scene": "周一早高峰地铁通勤",
        "attempt_count": 2,
    }

    store = FileExecutionMemory(path=memory_path)
    store.record(namespace=namespace, item=lesson)

    reloaded = FileExecutionMemory(path=memory_path)

    assert memory_path.exists()
    assert reloaded.search(namespace=namespace) == [lesson]


@pytest.mark.parametrize("store_kind", ("in_memory", "file"))
def test_psychology_inner_fingerprint_reservation_allows_one_interleaved_writer(
    store_kind: str,
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = "a" * 64
    if store_kind == "in_memory":
        shared_store = InMemoryExecutionMemory()
        stores = (shared_store, shared_store)
    else:
        memory_path = tmp_path / "execution-memory.json"
        stores = (
            FileExecutionMemory(path=memory_path),
            FileExecutionMemory(path=memory_path),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        reservations = list(
            executor.map(
                lambda store: store.reserve_psychology_carousel_inner_fingerprint(
                    namespace=namespace,
                    fingerprint=fingerprint,
                ),
                stores,
            )
        )

    winners = [reservation for reservation in reservations if reservation is not None]
    assert len(winners) == 1
    reservation_id = winners[0]
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
    }
    assert stores[0].commit_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        item=lesson,
    )
    assert (
        stores[1].reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
        )
        is None
    )
    assert stores[0].search(namespace=namespace) == [lesson]

    for index in range(12):
        stores[0].record(
            namespace=namespace,
            item={
                "playbook_id": "modern_psychology_post",
                "psychology_carousel_inner_fingerprint": f"{index:064x}",
            },
        )

    recycled_reservation_id = (
        stores[1].reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
        )
    )
    assert recycled_reservation_id is not None
    assert (
        stores[0].reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
        )
        is None
    )
