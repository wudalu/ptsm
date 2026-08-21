from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest

import ptsm.infrastructure.memory.store as memory_store
from ptsm.infrastructure.memory.store import (
    ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER,
    FileExecutionMemory,
    InMemoryExecutionMemory,
)


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
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }
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
                    item=lesson,
                ),
                stores,
            )
        )

    winners = [reservation for reservation in reservations if reservation is not None]
    assert len(winners) == 1
    reservation_id = winners[0]
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
            item=lesson,
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
                ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
            },
        )

    recycled_reservation_id = (
        stores[1].reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
    )
    assert recycled_reservation_id is not None
    assert (
        stores[0].reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
        is None
    )


@pytest.mark.parametrize("store_kind", ("in_memory", "file"))
def test_psychology_reservation_uses_only_marked_ordinary_history(
    store_kind: str,
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    store = (
        InMemoryExecutionMemory()
        if store_kind == "in_memory"
        else FileExecutionMemory(path=tmp_path / "execution-memory.json")
    )
    included_fingerprint = f"{7:064x}"
    included_lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": included_fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }
    store.record(namespace=namespace, item=included_lesson)
    for index in range(8, 19):
        store.record(
            namespace=namespace,
            item={
                "playbook_id": "modern_psychology_post",
                "psychology_carousel_inner_fingerprint": f"{index:064x}",
                ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
            },
        )

    ignored_fingerprint = "b" * 64
    store.record(
        namespace=namespace,
        item={
            "playbook_id": "modern_psychology_post",
            "psychology_learning_mode": "learning_series",
            "psychology_carousel_inner_fingerprint": ignored_fingerprint,
        },
    )
    store.record(
        namespace=namespace,
        item={
            "playbook_id": "other_playbook",
            "psychology_carousel_inner_fingerprint": ignored_fingerprint,
            ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
        },
    )
    store.record(
        namespace=namespace,
        item={
            "playbook_id": "modern_psychology_post",
            "psychology_carousel_inner_fingerprint": "not-a-fingerprint",
            ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
        },
    )
    store.record(
        namespace=namespace,
        item={
            "playbook_id": "modern_psychology_post",
            "psychology_carousel_inner_fingerprint": ignored_fingerprint,
        },
    )

    assert (
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=included_fingerprint,
            item=included_lesson,
        )
        is None
    )
    ignored_lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": ignored_fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }
    with pytest.raises(ValueError, match="ordinary psychology carousel"):
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=ignored_fingerprint,
            item={
                "playbook_id": "modern_psychology_post",
                "psychology_carousel_inner_fingerprint": ignored_fingerprint,
            },
        )
    reservation_id = store.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=ignored_fingerprint,
        item=ignored_lesson,
    )
    assert reservation_id is not None
    store.release_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=ignored_fingerprint,
        reservation_id=reservation_id,
    )


@pytest.mark.parametrize("store_kind", ("in_memory", "file"))
def test_expired_psychology_carousel_reservation_is_recovered_for_retry(
    store_kind: str,
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = "a" * 64
    now = [1_000.0]
    store = (
        InMemoryExecutionMemory(clock=lambda: now[0])
        if store_kind == "in_memory"
        else FileExecutionMemory(
            path=tmp_path / "execution-memory.json",
            clock=lambda: now[0],
        )
    )
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }

    first_reservation_id = store.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        item=lesson,
    )

    assert first_reservation_id is not None
    now[0] += 60 * 60
    assert not store.commit_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=first_reservation_id,
        item=lesson,
    )
    retry_reservation_id = store.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        item=lesson,
    )
    assert retry_reservation_id is not None
    assert retry_reservation_id != first_reservation_id


@pytest.mark.parametrize("store_kind", ("in_memory", "file"))
def test_psychology_carousel_reservation_renewal_is_owner_fenced_and_settlement_stops_it(
    store_kind: str,
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = "c" * 64
    now = [1_000.0]
    store = (
        InMemoryExecutionMemory(clock=lambda: now[0])
        if store_kind == "in_memory"
        else FileExecutionMemory(
            path=tmp_path / "execution-memory.json",
            clock=lambda: now[0],
        )
    )
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }
    reservation_id = store.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        item=lesson,
    )

    assert reservation_id is not None
    assert not store.renew_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id="not-the-owner",
    )
    now[0] += memory_store._PSYCHOLOGY_CAROUSEL_RESERVATION_LEASE_SECONDS - 1
    assert store.renew_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
    )

    # This is past the original 20-minute deadline, but the owner renewed it.
    now[0] += 2
    assert (
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
        is None
    )

    store.release_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
    )
    assert (
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
        is not None
    )


@pytest.mark.parametrize("store_kind", ("in_memory", "file"))
def test_commit_pending_carousel_reservation_reconciles_before_a_retry_can_render(
    store_kind: str,
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = "d" * 64
    now = [1_000.0]
    memory_path = tmp_path / "execution-memory.json"
    store = (
        InMemoryExecutionMemory(clock=lambda: now[0])
        if store_kind == "in_memory"
        else FileExecutionMemory(
            path=memory_path,
            clock=lambda: now[0],
        )
    )
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
        "title": "账本已持久化的轮播",
    }
    reservation_id = store.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        item=lesson,
    )

    assert reservation_id is not None
    assert store.mark_psychology_carousel_inner_fingerprint_commit_pending(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        item=lesson,
    )
    # A late cleanup must never delete the durable post-ledger marker.
    store.release_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
    )
    now[0] += memory_store._PSYCHOLOGY_CAROUSEL_RESERVATION_LEASE_SECONDS * 2
    if store_kind == "file":
        # The post-ledger marker must survive the process that could not finish
        # the memory promotion.
        store = FileExecutionMemory(path=memory_path, clock=lambda: now[0])

    # Reserving a retry first promotes the pending marker, then rejects the
    # duplicate before a second renderer invocation can start.
    assert (
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
        is None
    )
    assert store.search(namespace=namespace) == [lesson]


def test_file_execution_memory_recovers_legacy_reservation_without_lease(
    tmp_path: Path,
) -> None:
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = "b" * 64
    reservation_namespace = (
        *namespace,
        "__psychology_carousel_inner_fingerprint_reservations",
    )
    memory_path = tmp_path / "execution-memory.json"
    memory_path.write_text(
        json.dumps(
            {
                json.dumps(list(reservation_namespace)): [
                    {
                        "playbook_id": "modern_psychology_post",
                        "psychology_carousel_inner_fingerprint": fingerprint,
                        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
                        "reservation_id": "legacy-unleased-reservation",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    store = FileExecutionMemory(path=memory_path, clock=lambda: 1_000.0)
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }

    assert (
        store.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=fingerprint,
            item=lesson,
        )
        is not None
    )


def test_file_execution_memory_fails_closed_without_cross_process_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(memory_store, "fcntl", None)
    store = FileExecutionMemory(path=tmp_path / "execution-memory.json")

    with pytest.raises(RuntimeError, match="cross-process file locking"):
        store.search(namespace=("accounts", "acct-psychology-local", "lessons"))


def test_file_execution_memory_fsyncs_parent_after_atomic_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if memory_store.fcntl is None:
        pytest.skip("FileExecutionMemory fails closed where flock is unavailable")

    calls: list[tuple[str, object]] = []
    original_replace = memory_store.os.replace
    original_open = memory_store.os.open
    original_fsync = memory_store.os.fsync

    def track_replace(source: object, destination: object) -> None:
        calls.append(("replace", destination))
        original_replace(source, destination)

    def track_open(path: object, flags: int, *args: object, **kwargs: object) -> int:
        calls.append(("open_directory", Path(path)))
        return original_open(path, flags, *args, **kwargs)

    def track_fsync(file_descriptor: int) -> None:
        calls.append(("fsync", file_descriptor))
        original_fsync(file_descriptor)

    monkeypatch.setattr(memory_store.os, "replace", track_replace)
    monkeypatch.setattr(memory_store.os, "open", track_open)
    monkeypatch.setattr(memory_store.os, "fsync", track_fsync)
    memory_path = tmp_path / "execution-memory.json"

    FileExecutionMemory(path=memory_path).record(
        namespace=("accounts", "acct-psychology-local", "lessons"),
        item={"playbook_id": "modern_psychology_post"},
    )

    replace_index = next(
        index for index, (event, _) in enumerate(calls) if event == "replace"
    )
    assert calls[replace_index + 1] == ("open_directory", memory_path.parent)
    assert calls[replace_index + 2][0] == "fsync"
