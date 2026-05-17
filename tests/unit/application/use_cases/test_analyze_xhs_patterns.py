from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.analyze_xhs_patterns import run_analyze_xhs_patterns


def test_analyze_xhs_patterns_writes_snapshot_and_current_library(tmp_path: Path) -> None:
    sample_path = tmp_path / "samples-2026-05-17.json"
    sample_path.write_text(
        json.dumps(
            {
                "lane": "human_enrichment",
                "collected_at": "2026-05-17T00:00:00Z",
                "samples": [
                    {
                        "sample_id": "note-1",
                        "lane": "human_enrichment",
                        "keyword": "人类丰容",
                        "title": "突然意识到书桌也需要丰容",
                        "author": "作者A",
                        "feed_id": "note-1",
                        "likes": 120,
                        "comments": 9,
                        "shares": 4,
                        "collects": 30,
                        "cover_width": 1080,
                        "cover_height": 1440,
                        "has_cover_url": True,
                        "collected_at": "2026-05-17T00:00:00Z",
                    },
                    {
                        "sample_id": "note-2",
                        "lane": "human_enrichment",
                        "keyword": "低成本改造",
                        "title": "10分钟低成本变量清单，建议收藏",
                        "author": "作者B",
                        "feed_id": "note-2",
                        "likes": 300,
                        "comments": 40,
                        "shares": 20,
                        "collects": 380,
                        "cover_width": 1080,
                        "cover_height": 1440,
                        "has_cover_url": True,
                        "collected_at": "2026-05-17T00:00:00Z",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = run_analyze_xhs_patterns(
        sample_path=sample_path,
        lane="human_enrichment",
        output_dir=tmp_path / "library",
        created_at="2026-05-17T00:30:00Z",
    )

    assert result["status"] == "completed"
    assert result["pattern_count"] >= 2
    snapshot = Path(result["snapshot_path"])
    current = Path(result["current_path"])
    assert snapshot.exists()
    assert current.exists()
    data = json.loads(current.read_text(encoding="utf-8"))
    assert data["lane"] == "human_enrichment"
    assert data["status"] == "available"
    assert any(
        pattern["title_hook"] == "sudden_realization"
        for pattern in data["patterns"]
    )
    assert all("cover_url" not in json.dumps(pattern) for pattern in data["patterns"])
