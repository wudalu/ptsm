from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
from threading import RLock
from typing import Callable, Iterator, Mapping, Protocol
from uuid import uuid4

try:  # pragma: no cover - Windows uses the in-process lock below.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


_INNER_CAROUSEL_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_INNER_CAROUSEL_FINGERPRINT_FIELD = "psychology_carousel_inner_fingerprint"
_MODERN_PSYCHOLOGY_PLAYBOOK_ID = "modern_psychology_post"
_PSYCHOLOGY_CAROUSEL_FINGERPRINT_WINDOW = 12
ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER = (
    "_ptsm_ordinary_psychology_carousel_v1"
)
_RESERVATION_NAMESPACE_COMPONENT = "__psychology_carousel_inner_fingerprint_reservations"
_FILE_LOCKS: dict[Path, RLock] = {}
_FILE_LOCKS_GUARD = RLock()
_StorageKey = tuple[str, ...] | str
_Storage = dict[_StorageKey, list[dict[str, object]]]
_NamespaceKey = Callable[[tuple[str, ...]], _StorageKey]


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

    def __init__(self) -> None:
        self._storage: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
        self._lock = RLock()

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
            )


class FileExecutionMemory:
    """Persist execution lessons on disk for reuse across runs."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

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
            )
            if reservation_id is not None:
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
            )
            # A failed commit can still remove a stale reservation after
            # detecting an independently committed fingerprint.
            self._save(storage)
            return committed

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
            released = _release_inner_carousel_fingerprint(
                storage=storage,
                namespace=namespace,
                fingerprint=fingerprint,
                reservation_id=reservation_id,
                namespace_key=self._encode_namespace,
            )
            if released:
                self._save(storage)

    @contextmanager
    def _locked_storage(self) -> Iterator[dict[str, list[dict[str, object]]]]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        lock = _file_lock_for(lock_path)
        with lock:
            with lock_path.open("a+", encoding="utf-8") as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield self._load()
                finally:
                    if fcntl is not None:
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
        finally:
            temporary_path.unlink(missing_ok=True)

    def _encode_namespace(self, namespace: tuple[str, ...]) -> str:
        return json.dumps(list(namespace), ensure_ascii=False)


def _file_lock_for(path: Path) -> RLock:
    with _FILE_LOCKS_GUARD:
        return _FILE_LOCKS.setdefault(path.resolve(), RLock())


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


def _reserve_inner_carousel_fingerprint(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    namespace_key: _NamespaceKey,
) -> str | None:
    final_key = namespace_key(namespace)
    reservation_key = namespace_key(_reservation_namespace(namespace))
    if _contains_recent_inner_carousel_fingerprint(
        storage.get(final_key, []),
        fingerprint,
    ):
        return None
    reservations = storage.setdefault(reservation_key, [])
    if _contains_reservation(reservations, fingerprint=fingerprint):
        return None
    reservation_id = uuid4().hex
    reservations.append(
        {
            "playbook_id": _MODERN_PSYCHOLOGY_PLAYBOOK_ID,
            _INNER_CAROUSEL_FINGERPRINT_FIELD: fingerprint,
            ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
            "reservation_id": reservation_id,
        }
    )
    return reservation_id


def _commit_inner_carousel_fingerprint(
    *,
    storage: _Storage,
    namespace: tuple[str, ...],
    fingerprint: str,
    reservation_id: str,
    item: dict[str, object],
    namespace_key: _NamespaceKey,
) -> bool:
    final_key = namespace_key(namespace)
    reservation_key = namespace_key(_reservation_namespace(namespace))
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
    )
    if reservation_index is None:
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
) -> bool:
    reservation_key = namespace_key(_reservation_namespace(namespace))
    reservations = storage.get(reservation_key, [])
    reservation_index = _reservation_index(
        reservations,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
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
) -> bool:
    return any(
        ordinary_psychology_carousel_memory_fingerprint(reservation) == fingerprint
        for reservation in reservations
    )


def _reservation_index(
    reservations: list[dict[str, object]],
    *,
    fingerprint: str,
    reservation_id: str,
) -> int | None:
    for index, reservation in enumerate(reservations):
        if (
            ordinary_psychology_carousel_memory_fingerprint(reservation) == fingerprint
            and reservation.get("reservation_id") == reservation_id
        ):
            return index
    return None


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
