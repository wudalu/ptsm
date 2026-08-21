from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import errno
import json
import math
import os
from pathlib import Path
import re
from threading import RLock
from time import time
from typing import Callable, Iterator, Mapping, Protocol
from uuid import uuid4

try:  # pragma: no cover - Windows fails closed below when unavailable.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


_INNER_CAROUSEL_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_INNER_CAROUSEL_FINGERPRINT_FIELD = "psychology_carousel_inner_fingerprint"
_MODERN_PSYCHOLOGY_PLAYBOOK_ID = "modern_psychology_post"
_PSYCHOLOGY_CAROUSEL_FINGERPRINT_WINDOW = 12
# Local rendering, hashing, and ledger persistence should normally take seconds,
# but the lease tolerates slow disks and busy hosts while bounding crash recovery.
_PSYCHOLOGY_CAROUSEL_RESERVATION_LEASE_SECONDS = 20 * 60
_RESERVATION_LEASE_EXPIRES_AT_FIELD = "lease_expires_at"
_RESERVATION_STATE_FIELD = "state"
_RESERVATION_STATE_ACTIVE = "active"
_RESERVATION_STATE_COMMIT_PENDING = "commit_pending"
_RESERVATION_PENDING_ITEM_FIELD = "pending_item"
ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER = (
    "_ptsm_ordinary_psychology_carousel_v1"
)
_RESERVATION_NAMESPACE_COMPONENT = "__psychology_carousel_inner_fingerprint_reservations"
_FILE_LOCKS: dict[Path, RLock] = {}
_FILE_LOCKS_GUARD = RLock()
_StorageKey = tuple[str, ...] | str
_Storage = dict[_StorageKey, list[dict[str, object]]]
_NamespaceKey = Callable[[tuple[str, ...]], _StorageKey]
_Clock = Callable[[], float]


def ordinary_psychology_carousel_memory_fingerprint(
    item: Mapping[str, object],
) -> str | None:
    """Return an attested ordinary-carousel fingerprint, never inferred history."""
    raw_fingerprint = item.get(_INNER_CAROUSEL_FINGERPRINT_FIELD)
    if (
        item.get("playbook_id") != _MODERN_PSYCHOLOGY_PLAYBOOK_ID
        or item.get(ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER) is not True
        or not isinstance(raw_fingerprint, str)
        or _INNER_CAROUSEL_FINGERPRINT_PATTERN.fullmatch(raw_fingerprint) is None
    ):
        return None
    return raw_fingerprint


class ExecutionMemoryStore(Protocol):
    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None: ...

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]: ...

    def reserve_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        item: dict[str, object],
    ) -> str | None: ...

    def renew_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> bool: ...

    def mark_psychology_carousel_inner_fingerprint_commit_pending(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool: ...

    def commit_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool: ...

    def release_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> None: ...


class InMemoryExecutionMemory:
    """Minimal long-term memory adapter for dry-run execution lessons."""

    def __init__(self, *, clock: _Clock = time) -> None:
        self._storage: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
        self._lock = RLock()
        self._clock = clock

    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None:
        with self._lock:
            self._storage[namespace].append(item)

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]:
        with self._lock:
            return list(self._storage.get(namespace, []))

    def reserve_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        item: dict[str, object],
    ) -> str | None:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._lock:
            return _reserve_inner_carousel_fingerprint(
                storage=self._storage,
                namespace=namespace,
                fingerprint=fingerprint,
                namespace_key=_identity_namespace,
                now=_reservation_now(self._clock),
            )

    def renew_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        with self._lock:
            return _renew_inner_carousel_fingerprint_reservation(
                storage=self._storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                namespace_key=_identity_namespace,
                now=_reservation_now(self._clock),
            )

    def mark_psychology_carousel_inner_fingerprint_commit_pending(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._lock:
            return _mark_inner_carousel_fingerprint_commit_pending(
                storage=self._storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                item=item,
                namespace_key=_identity_namespace,
                now=_reservation_now(self._clock),
            )

    def commit_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._lock:
            return _commit_inner_carousel_fingerprint(
                storage=self._storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                item=item,
                namespace_key=_identity_namespace,
                now=_reservation_now(self._clock),
            )

    def release_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> None:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        with self._lock:
            _release_inner_carousel_fingerprint(
                storage=self._storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                namespace_key=_identity_namespace,
                now=_reservation_now(self._clock),
            )


class FileExecutionMemory:
    """Persist execution lessons on disk for reuse across runs."""

    def __init__(self, path: Path | str, *, clock: _Clock = time) -> None:
        self.path = Path(path)
        self._clock = clock

    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None:
        with self._locked_storage() as storage:
            key = self._encode_namespace(namespace)
            storage.setdefault(key, []).append(item)
            self._save(storage)

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]:
        with self._locked_storage() as storage:
            return list(storage.get(self._encode_namespace(namespace), []))

    def reserve_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        item: dict[str, object],
    ) -> str | None:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._locked_storage() as storage:
            reservation_id = _reserve_inner_carousel_fingerprint(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                namespace_key=self._encode_namespace,
                now=_reservation_now(self._clock),
            )
            self._save(storage)
            return reservation_id

    def commit_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._locked_storage() as storage:
            committed = _commit_inner_carousel_fingerprint(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                item=item,
                namespace_key=self._encode_namespace,
                now=_reservation_now(self._clock),
            )
            # A failed commit can still remove a stale reservation after
            # detecting an independently committed fingerprint.
            self._save(storage)
            return committed

    def renew_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        with self._locked_storage() as storage:
            renewed = _renew_inner_carousel_fingerprint_reservation(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                namespace_key=self._encode_namespace,
                now=_reservation_now(self._clock),
            )
            self._save(storage)
            return renewed

    def mark_psychology_carousel_inner_fingerprint_commit_pending(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        item: dict[str, object],
    ) -> bool:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        _require_ordinary_carousel_memory_item(item=item, fingerprint=fingerprint)
        with self._locked_storage() as storage:
            marked = _mark_inner_carousel_fingerprint_commit_pending(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                item=item,
                namespace_key=self._encode_namespace,
                now=_reservation_now(self._clock),
            )
            self._save(storage)
            return marked

    def release_psychology_carousel_inner_fingerprint(
        self,
        *,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
    ) -> None:
        fingerprint = _require_inner_carousel_fingerprint(fingerprint)
        _require_reservation_id(reservation_id)
        with self._locked_storage() as storage:
            _release_inner_carousel_fingerprint(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                namespace_key=self._encode_namespace,
                now=_reservation_now(self._clock),
            )
            self._save(storage)

    @contextmanager
    def _locked_storage(self) -> Iterator[dict[str, list[dict[str, object]]]]:
        if fcntl is None:
            raise RuntimeError(
                "FileExecutionMemory requires cross-process file locking on this platform"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        lock = _file_lock_for(lock_path)
        with lock:
            with lock_path.open("a+", encoding="utf-8") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield self._load()
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _load(self) -> dict[str, list[dict[str, object]]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, storage: dict[str, list[dict[str, object]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_name(f".{self.path.name}.{uuid4().hex}.tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as temporary_file:
                json.dump(storage, temporary_file, ensure_ascii=False, indent=2)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_path, self.path)
            _fsync_parent_directory(self.path.parent)
        finally:
            temporary_path.unlink(missing_ok=True)

    def _encode_namespace(self, namespace: tuple[str, ...]) -> str:
        return json.dumps(list(namespace), ensure_ascii=False)


def _file_lock_for(path: Path) -> RLock:
    with _FILE_LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(path.resolve(), RLock())


def _fsync_parent_directory(path: Path) -> None:
    """Durably persist a replace where directory fsync is supported."""
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        # Windows and some filesystems do not permit opening a directory this
        # way.  The replacement itself remains atomic; skip only that optional
        # durability barrier where the platform cannot express it.
        return
    try:
        os.fsync(directory_fd)
    except OSError as exc:
        if exc.errno not in {
            errno.EBADF,
            errno.EINVAL,
            errno.ENOTSUP,
            errno.EPERM,
        }:
            raise
    finally:
        os.close(directory_fd)


def _identity_namespace(namespace: tuple[str, ...]) -> tuple[str, ...]:
    return namespace


def _reservation_namespace(namespace: tuple[str, ...]) -> tuple[str, ...]:
    return (*namespace, _RESERVATION_NAMESPACE_COMPONENT)


def _require_inner_carousel_fingerprint(fingerprint: str) -> str:
    if not isinstance(fingerprint, str) or _INNER_CAROUSEL_FINGERPRINT_PATTERN.fullmatch(
        fingerprint
    ) is None:
        raise ValueError("psychology carousel inner fingerprint must be a lowercase SHA-256 hash")
    return fingerprint


def _require_reservation_id(reservation_id: str) -> None:
    if not isinstance(reservation_id, str) or not reservation_id:
        raise ValueError("psychology carousel reservation_id is required")


def _require_ordinary_carousel_memory_item(
    *, item: dict[str, object], fingerprint: str
) -> None:
    if ordinary_psychology_carousel_memory_fingerprint(item) != fingerprint:
        raise ValueError("ordinary psychology carousel memory item is required")


def _reservation_now(clock: _Clock) -> float:
    value = float(clock())
    if not math.isfinite(value):
        raise ValueError("psychology carousel reservation clock must be finite")
    return value


def _reserve_inner_carousel_fingerprint(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    namespace_key: _NamespaceKey,
    now: float,
) -> str | None:
    final_key = namespace_key(namespace)
    reservation_key = namespace_key(_reservation_namespace(namespace))
    _reconcile_commit_pending_inner_carousel_reservations(
        storage=storage,
        final_key=final_key,
        reservation_key=reservation_key,
    )
    _recover_expired_reservations(
        storage=storage,
        reservation_key=reservation_key,
        now=now,
    )
    if _contains_recent_inner_carousel_fingerprint(
        storage.get(final_key, []),
        fingerprint,
    ):
        return None
    reservations = storage.setdefault(reservation_key, [])
    if _contains_reservation(reservations, fingerprint=fingerprint, now=now):
        return None
    reservation_id = uuid4().hex
    reservations.append(
        {
            "playbook_id": _MODERN_PSYCHOLOGY_PLAYBOOK_ID,
            _INNER_CAROUSEL_FINGERPRINT_FIELD: fingerprint,
            ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
            "reservation_id": reservation_id,
            _RESERVATION_STATE_FIELD: _RESERVATION_STATE_ACTIVE,
            _RESERVATION_LEASE_EXPIRES_AT_FIELD: (
                now + _PSYCHOLOGY_CAROUSEL_RESERVATION_LEASE_SECONDS
            ),
        }
    )
    return reservation_id


def _renew_inner_carousel_fingerprint_reservation(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    reservation_id: str,
    namespace_key: _NamespaceKey,
    now: float,
) -> bool:
    reservation_key = namespace_key(_reservation_namespace(namespace))
    _recover_expired_reservations(
        storage=storage,
        reservation_key=reservation_key,
        now=now,
    )
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        now=now,
    )
    if reservation_index is None:
        return False
    reservations[reservation_index][_RESERVATION_LEASE_EXPIRES_AT_FIELD] = (
        now + _PSYCHOLOGY_CAROUSEL_RESERVATION_LEASE_SECONDS
    )
    return True


def _mark_inner_carousel_fingerprint_commit_pending(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    reservation_id: str,
    item: dict[str, object],
    namespace_key: _NamespaceKey,
    now: float,
) -> bool:
    final_key = namespace_key(namespace)
    reservation_key = namespace_key(_reservation_namespace(namespace))
    _recover_expired_reservations(
        storage=storage,
        reservation_key=reservation_key,
        now=now,
    )
    if _contains_recent_inner_carousel_fingerprint(
        storage.get(final_key, []),
        fingerprint,
    ):
        return False
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        now=now,
    )
    if reservation_index is None:
        return False
    reservations[reservation_index].update(
        {
            _RESERVATION_STATE_FIELD: _RESERVATION_STATE_COMMIT_PENDING,
            _RESERVATION_PENDING_ITEM_FIELD: dict(item),
        }
    )
    return True


def _commit_inner_carousel_fingerprint(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    reservation_id: str,
    item: dict[str, object],
    namespace_key: _NamespaceKey,
    now: float,
) -> bool:
    final_key = namespace_key(namespace)
    reservation_key = namespace_key(_reservation_namespace(namespace))
    _recover_expired_reservations(
        storage=storage,
        reservation_key=reservation_key,
        now=now,
    )
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        now=now,
        allow_commit_pending=True,
    )
    if reservation_index is None:
        return False
    reservation = reservations[reservation_index]
    if _reservation_is_commit_pending(reservation):
        pending_item = reservation.get(_RESERVATION_PENDING_ITEM_FIELD)
        if not isinstance(pending_item, dict) or pending_item != item:
            return False
    if _contains_recent_inner_carousel_fingerprint(
        storage.get(final_key, []),
        fingerprint,
    ):
        _drop_reservation(
            storage=storage,
            reservation_key=reservation_key,
            reservations=reservations,
            reservation_index=reservation_index,
        )
        return False
    storage.setdefault(final_key, []).append(item)
    _drop_reservation(
        storage=storage,
        reservation_key=reservation_key,
        reservations=reservations,
        reservation_index=reservation_index,
    )
    return True


def _release_inner_carousel_fingerprint(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    reservation_id: str,
    namespace_key: _NamespaceKey,
    now: float,
) -> bool:
    reservation_key = namespace_key(_reservation_namespace(namespace))
    _recover_expired_reservations(
        storage=storage,
        reservation_key=reservation_key,
        now=now,
    )
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        now=now,
    )
    if reservation_index is None:
        return False
    _drop_reservation(
        storage=storage,
        reservation_key=reservation_key,
        reservations=reservations,
        reservation_index=reservation_index,
    )
    return True


def _contains_recent_inner_carousel_fingerprint(
    items: list[dict[str, object]] | None,
    fingerprint: str,
) -> bool:
    recent_fingerprints: list[str] = []
    for item in reversed(items or []):
        ordinary_fingerprint = ordinary_psychology_carousel_memory_fingerprint(item)
        if ordinary_fingerprint is None:
            continue
        recent_fingerprints.append(ordinary_fingerprint)
        if len(recent_fingerprints) == _PSYCHOLOGY_CAROUSEL_FINGERPRINT_WINDOW:
            break
    return fingerprint in recent_fingerprints


def _contains_reservation(
    reservations: list[dict[str, object]],
    *,
    fingerprint: str,
    now: float,
) -> bool:
    return any(
        _live_reservation_fingerprint(reservation, now=now) == fingerprint
        for reservation in reservations
    )


def _reservation_index(
    reservations: list[dict[str, object]],
    *,
    fingerprint: str,
    reservation_id: str,
    now: float,
    allow_commit_pending: bool = False,
) -> int | None:
    for index, reservation in enumerate(reservations):
        if not isinstance(reservation, Mapping):
            continue
        if (
            ordinary_psychology_carousel_memory_fingerprint(reservation) != fingerprint
            or reservation.get("reservation_id") != reservation_id
        ):
            continue
        if _reservation_is_commit_pending(reservation):
            if allow_commit_pending:
                return index
            continue
        if _live_reservation_fingerprint(reservation, now=now) == fingerprint:
            return index
    return None


def _reconcile_commit_pending_inner_carousel_reservations(
    *,
    storage: _Storage,
    final_key: _StorageKey,
    reservation_key: _StorageKey,
) -> None:
    """Promote durable post-ledger markers before any retry can reserve work."""
    reservations = storage.get(reservation_key)
    if reservations is None:
        return
    pending: list[tuple[str, dict[str, object]]] = []
    retained: list[dict[str, object]] = []
    for reservation in reservations:
        if not _reservation_is_commit_pending(reservation):
            retained.append(reservation)
            continue
        fingerprint = ordinary_psychology_carousel_memory_fingerprint(reservation)
        item = reservation.get(_RESERVATION_PENDING_ITEM_FIELD)
        if (
            fingerprint is None
            or not isinstance(item, dict)
            or ordinary_psychology_carousel_memory_fingerprint(item) != fingerprint
        ):
            raise RuntimeError(
                "psychology carousel commit-pending reservation is invalid"
            )
        pending.append((fingerprint, dict(item)))

    for fingerprint, item in pending:
        if not _contains_recent_inner_carousel_fingerprint(
            storage.get(final_key, []), fingerprint
        ):
            storage.setdefault(final_key, []).append(item)
    if retained:
        storage[reservation_key] = retained
    else:
        storage.pop(reservation_key, None)


def _recover_expired_reservations(
    *,
    storage: _Storage,
    reservation_key: _StorageKey,
    now: float,
) -> None:
    reservations = storage.get(reservation_key)
    if reservations is None:
        return
    live_reservations = [
        reservation
        for reservation in reservations
        if _reservation_is_commit_pending(reservation)
        or _live_reservation_fingerprint(reservation, now=now) is not None
    ]
    if len(live_reservations) == len(reservations):
        return
    if live_reservations:
        storage[reservation_key] = live_reservations
    else:
        storage.pop(reservation_key, None)


def _live_reservation_fingerprint(
    reservation: object,
    *,
    now: float,
) -> str | None:
    if not isinstance(reservation, Mapping):
        return None
    if _reservation_state(reservation) != _RESERVATION_STATE_ACTIVE:
        return None
    fingerprint = ordinary_psychology_carousel_memory_fingerprint(reservation)
    expires_at = reservation.get(_RESERVATION_LEASE_EXPIRES_AT_FIELD)
    if (
        fingerprint is None
        or isinstance(expires_at, bool)
        or not isinstance(expires_at, (int, float))
        or not math.isfinite(float(expires_at))
        or float(expires_at) <= now
    ):
        return None
    return fingerprint


def _reservation_state(reservation: Mapping[str, object]) -> str:
    raw_state = reservation.get(_RESERVATION_STATE_FIELD)
    # No state denotes the prior on-disk active-reservation shape.
    return _RESERVATION_STATE_ACTIVE if raw_state is None else str(raw_state)


def _reservation_is_commit_pending(reservation: object) -> bool:
    return isinstance(reservation, Mapping) and (
        _reservation_state(reservation) == _RESERVATION_STATE_COMMIT_PENDING
    )


def _drop_reservation(
    *,
    storage: _Storage,
    reservation_key: _StorageKey,
    reservations: list[dict[str, object]],
    reservation_index: int,
) -> None:
    del reservations[reservation_index]
    if not reservations:
        storage.pop(reservation_key, None)
