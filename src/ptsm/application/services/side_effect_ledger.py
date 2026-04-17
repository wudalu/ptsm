from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


class SideEffectLedger:
    """Persist successful side-effect results for safe replay and resume."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def read(
        self,
        *,
        thread_id: str,
        step: str,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        payload = self._load()
        record = (
            payload.get("threads", {})
            .get(thread_id, {})
            .get(step)
        )
        if not isinstance(record, dict):
            return None
        if record.get("idempotency_key") != idempotency_key:
            return None
        result = record.get("result")
        return dict(result) if isinstance(result, dict) else None

    def record(
        self,
        *,
        thread_id: str,
        step: str,
        idempotency_key: str,
        result: dict[str, Any],
    ) -> None:
        payload = self._load()
        threads = payload.setdefault("threads", {})
        scoped = threads.setdefault(thread_id, {})
        scoped[step] = {
            "idempotency_key": idempotency_key,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
        self._save(payload)

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"threads": {}}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"threads": {}}
        return payload

    def _save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
