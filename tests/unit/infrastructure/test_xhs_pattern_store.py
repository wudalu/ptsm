from __future__ import annotations

import json
from pathlib import Path

from ptsm.domain.xhs_patterns import PostFormatPattern
from ptsm.infrastructure.xhs_patterns.store import XhsPatternStore


def test_pattern_store_writes_snapshot_and_current(tmp_path: Path) -> None:
    store = XhsPatternStore(root=tmp_path)
    pattern = PostFormatPattern(
        pattern_id="human_enrichment.sudden_realization.001",
        lane="human_enrichment",
        status="candidate",
        title_hook="sudden_realization",
        body_structure="ordinary friction -> one variable -> checklist -> comment",
        image_sequence=["cover", "before", "material", "checklist", "after", "comment"],
        save_trigger="三步清单",
        comment_trigger="评论区交一个具体例子",
        example_titles=["突然意识到书桌也需要丰容"],
        source_sample_ids=["note-1"],
        cover_ratio="3:4",
        created_at="2026-05-17T00:30:00Z",
    )

    snapshot_path = store.write_snapshot(
        lane="human_enrichment",
        patterns=[pattern],
        created_at="2026-05-17T00:30:00Z",
    )
    current_path = store.write_current(
        lane="human_enrichment",
        patterns=[pattern],
        created_at="2026-05-17T00:30:00Z",
        source_path=snapshot_path,
    )

    assert snapshot_path.exists()
    assert current_path.exists()
    current = json.loads(current_path.read_text(encoding="utf-8"))
    assert current["source_snapshot"] == str(snapshot_path)
    assert current["patterns"][0]["pattern_id"] == pattern.pattern_id

    loaded = store.read_current()
    assert loaded["patterns"][0]["title_hook"] == "sudden_realization"
