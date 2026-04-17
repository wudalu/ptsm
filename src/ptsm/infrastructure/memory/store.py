from __future__ import annotations

from collections import defaultdict
import json
from pathlib import Path
from typing import Protocol


class ExecutionMemoryStore(Protocol):
    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None: ...

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]: ...


class InMemoryExecutionMemory:
    """Minimal long-term memory adapter for dry-run execution lessons."""

    def __init__(self) -> None:
        self._storage: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)

    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None:
        self._storage[namespace].append(item)

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]:
        return list(self._storage.get(namespace, []))


class FileExecutionMemory:
    """Persist execution lessons on disk for reuse across runs."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None:
        storage = self._load()
        key = self._encode_namespace(namespace)
        storage.setdefault(key, []).append(item)
        self._save(storage)

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]:
        storage = self._load()
        return list(storage.get(self._encode_namespace(namespace), []))

    def _load(self) -> dict[str, list[dict[str, object]]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, storage: dict[str, list[dict[str, object]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(storage, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _encode_namespace(self, namespace: tuple[str, ...]) -> str:
        return json.dumps(list(namespace), ensure_ascii=False)
