from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.domain.xhs_patterns import PostFormatPattern


class XhsPatternStore:
    """Persist reviewed Xiaohongshu format pattern snapshots on local disk."""

    def __init__(self, *, root: Path | str = "outputs/artifacts/xhs-pattern-library") -> None:
        self.root = Path(root)

    def write_snapshot(
        self,
        *,
        lane: str,
        patterns: list[PostFormatPattern],
        created_at: str,
    ) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        day = created_at[:10] if created_at else "undated"
        path = self.root / f"patterns-{day}.json"
        payload = self._build_payload(
            lane=lane,
            patterns=patterns,
            created_at=created_at,
            source_snapshot=None,
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_current(
        self,
        *,
        lane: str,
        patterns: list[PostFormatPattern],
        created_at: str,
        source_path: Path | str,
    ) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / "current.json"
        payload = self._build_payload(
            lane=lane,
            patterns=patterns,
            created_at=created_at,
            source_snapshot=str(source_path),
        )
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read_current(self) -> dict[str, Any]:
        path = self.root / "current.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def _build_payload(
        self,
        *,
        lane: str,
        patterns: list[PostFormatPattern],
        created_at: str,
        source_snapshot: str | None,
    ) -> dict[str, Any]:
        return {
            "status": "available" if patterns else "unavailable",
            "lane": lane,
            "created_at": created_at,
            "source_snapshot": source_snapshot,
            "patterns": [pattern.to_dict() for pattern in patterns],
        }
