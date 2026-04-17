from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import pickle
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver


def _checkpoint_namespace_factory() -> defaultdict[str, Any]:
    return defaultdict(dict)


class FileCheckpointSaver(InMemorySaver):
    """Persist LangGraph checkpoints to a local pickle file."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        super().__init__()
        self.storage = defaultdict(_checkpoint_namespace_factory)
        self.writes = defaultdict(dict)
        self.blobs = {}
        self._load()

    def put(self, config, checkpoint, metadata, new_versions):
        saved_config = super().put(config, checkpoint, metadata, new_versions)
        self._persist()
        return saved_config

    def put_writes(self, config, writes, task_id, task_path: str = "") -> None:
        super().put_writes(config, writes, task_id, task_path)
        self._persist()

    def delete_thread(self, thread_id: str) -> None:
        super().delete_thread(thread_id)
        self._persist()

    def _load(self) -> None:
        if not self.path.exists():
            return
        payload = pickle.loads(self.path.read_bytes())
        self.storage = defaultdict(_checkpoint_namespace_factory)
        for thread_id, namespaces in payload.get("storage", {}).items():
            self.storage[thread_id] = defaultdict(dict, namespaces)
        self.writes = defaultdict(dict, payload.get("writes", {}))
        self.blobs = payload.get("blobs", {})

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "storage": {
                thread_id: {
                    checkpoint_ns: dict(checkpoints)
                    for checkpoint_ns, checkpoints in namespaces.items()
                }
                for thread_id, namespaces in self.storage.items()
            },
            "writes": dict(self.writes),
            "blobs": dict(self.blobs),
        }
        self.path.write_bytes(pickle.dumps(payload))
