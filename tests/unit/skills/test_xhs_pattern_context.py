from __future__ import annotations

import json
from pathlib import Path

from ptsm.skills.runtime_context import XhsPatternContextBuilder


def test_xhs_pattern_context_builder_renders_local_snapshot(tmp_path: Path) -> None:
    current = tmp_path / "current.json"
    current.write_text(
        json.dumps(
            {
                "status": "available",
                "lane": "human_enrichment",
                "created_at": "2026-05-17T00:30:00Z",
                "source_snapshot": str(tmp_path / "patterns-2026-05-17.json"),
                "patterns": [
                    {
                        "pattern_id": "human_enrichment.sudden_realization.001",
                        "lane": "human_enrichment",
                        "status": "candidate",
                        "title_hook": "sudden_realization",
                        "body_structure": "ordinary friction -> one variable -> checklist -> comment",
                        "image_sequence": [
                            "cover",
                            "before state",
                            "variable/material flat lay",
                            "mini checklist",
                            "after state",
                            "comment invitation",
                        ],
                        "save_trigger": "三步清单",
                        "comment_trigger": "评论区交一个具体例子",
                        "example_titles": ["突然意识到书桌也需要丰容"],
                        "source_sample_ids": ["note-1"],
                        "cover_ratio": "3:4",
                        "created_at": "2026-05-17T00:30:00Z",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    context = XhsPatternContextBuilder(pattern_path=current).build(
        scene="把书桌改成十分钟手作角",
        domain="人类丰容实验",
        playbook_id="human_enrichment_daily_post",
    )

    assert context is not None
    assert "# XHS Format Pattern Library Context" in context
    assert "human_enrichment.sudden_realization.001" in context
    assert "sudden_realization" in context
    assert "ordinary friction -> one variable -> checklist -> comment" in context
    assert "3:4" in context
    assert "不要复写样本标题" in context


def test_xhs_pattern_context_builder_returns_none_for_missing_snapshot(tmp_path: Path) -> None:
    context = XhsPatternContextBuilder(pattern_path=tmp_path / "missing.json").build(
        scene="把书桌改成十分钟手作角",
        domain="人类丰容实验",
        playbook_id="human_enrichment_daily_post",
    )

    assert context is None
