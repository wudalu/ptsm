from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ptsm.domain.xhs_patterns import analyze_samples_to_patterns, load_samples_from_payload
from ptsm.infrastructure.xhs_patterns.store import XhsPatternStore


def run_analyze_xhs_patterns(
    *,
    sample_path: Path | str,
    lane: str,
    output_dir: Path | str = "outputs/artifacts/xhs-pattern-library",
    created_at: str | None = None,
) -> dict[str, Any]:
    sample_path = Path(sample_path)
    created_at = created_at or datetime.now(timezone.utc).isoformat()
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    samples = load_samples_from_payload(payload, lane=lane)
    patterns = analyze_samples_to_patterns(samples, lane=lane, created_at=created_at)
    store = XhsPatternStore(root=output_dir)
    snapshot_path = store.write_snapshot(lane=lane, patterns=patterns, created_at=created_at)
    current_path = store.write_current(
        lane=lane,
        patterns=patterns[:8],
        created_at=created_at,
        source_path=snapshot_path,
    )
    return {
        "status": "completed" if patterns else "empty",
        "lane": lane,
        "sample_count": len(samples),
        "pattern_count": len(patterns),
        "snapshot_path": str(snapshot_path),
        "current_path": str(current_path),
        "patterns": [pattern.to_dict() for pattern in patterns],
    }
