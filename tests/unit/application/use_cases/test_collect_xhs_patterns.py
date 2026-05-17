from __future__ import annotations

import json
from pathlib import Path

from topic_radar.platforms.xiaohongshu import FeedItem

from ptsm.application.use_cases.collect_xhs_patterns import run_collect_xhs_patterns


class PartiallyFailingXhs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search_feeds(self, keyword: str, limit: int = 20):
        self.calls.append((keyword, limit))
        if keyword == "家的丰容计划":
            raise ExceptionGroup(
                "unhandled errors in a TaskGroup",
                [RuntimeError("HTTPStatusError: 500 Internal Server Error")],
            )
        return [
            FeedItem(
                feed_id=f"note-{keyword}",
                title=f"突然意识到{keyword}也需要丰容",
                author="作者A",
                likes=120,
                comments=9,
                shares=4,
                collects=30,
                xsec_token=f"token-{keyword}",
                cover_width=1080,
                cover_height=1440,
                has_cover_url=True,
            )
        ]


def test_collect_xhs_patterns_preserves_partial_successes(tmp_path: Path) -> None:
    fake_xhs = PartiallyFailingXhs()

    result = run_collect_xhs_patterns(
        lane="human_enrichment",
        keywords=["人类丰容", "家的丰容计划", "低成本改造"],
        sample_limit_per_keyword=3,
        output_dir=tmp_path,
        xhs_platform=fake_xhs,
        delay_seconds=0,
        collected_at="2026-05-17T00:00:00Z",
    )

    assert result["status"] == "partial"
    assert [call[0] for call in fake_xhs.calls] == [
        "人类丰容",
        "家的丰容计划",
        "低成本改造",
    ]
    assert len(result["samples"]) == 2
    assert "家的丰容计划" in result["keyword_errors"]
    assert "500" in result["keyword_errors"]["家的丰容计划"]

    artifact_path = Path(result["artifact_path"])
    assert artifact_path.exists()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["collection_metadata"]["successful_keywords"] == [
        "人类丰容",
        "低成本改造",
    ]
    assert artifact["collection_metadata"]["failed_keywords"] == ["家的丰容计划"]
    assert artifact["collection_metadata"]["sample_limit_per_keyword"] == 3
    assert artifact["collection_metadata"]["live_source"] == "xiaohongshu-mcp"
    assert len(artifact["samples"]) == 2
