from __future__ import annotations

from collections import defaultdict


class InMemoryExecutionMemory:
    """Minimal long-term memory adapter for dry-run execution lessons."""

    def __init__(self) -> None:
        self._storage: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)

    def record(self, namespace: tuple[str, ...], item: dict[str, object]) -> None:
        self._storage[namespace].append(item)

    def search(self, namespace: tuple[str, ...]) -> list[dict[str, object]]:
        return list(self._storage.get(namespace, []))

