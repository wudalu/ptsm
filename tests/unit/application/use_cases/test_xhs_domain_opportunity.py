from __future__ import annotations

import json
from pathlib import Path

from topic_radar.platforms.xiaohongshu import FeedItem

from ptsm.application.use_cases.xhs_domain_opportunity import (
    run_xhs_domain_opportunity,
)


class FakeOpportunityXhs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search_feeds(self, keyword: str, limit: int = 20):
        self.calls.append((keyword, limit))
        rows = {
            "睡眠恢复": [
                FeedItem(
                    feed_id="sleep-1",
                    title="睡觉大于天 睡觉是成本最低收益最高的投资",
                    author="Berry充电计划",
                    likes=10102,
                    comments=182,
                    collects=5557,
                    shares=2354,
                    xsec_token="token-sleep-1",
                )
            ],
            "人类丰容": [
                FeedItem(
                    feed_id="enrichment-1",
                    title="人，你该“丰容”了!",
                    author="新周梗",
                    likes=1650,
                    comments=27,
                    collects=687,
                    shares=1453,
                    xsec_token="token-enrichment-1",
                )
            ],
            "武侠": [
                FeedItem(
                    feed_id="wuxia-1",
                    title="你读过最江湖味的一句诗",
                    author="诗念",
                    likes=169,
                    comments=56,
                    collects=153,
                    shares=16,
                    xsec_token="token-wuxia-1",
                )
            ],
        }
        return rows.get(keyword, [])[:limit]


def test_xhs_domain_opportunity_scores_and_maps_keywords(tmp_path: Path) -> None:
    fake_xhs = FakeOpportunityXhs()

    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "人类丰容", "武侠"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=fake_xhs,
        delay_seconds=0,
        collected_at="2026-05-30T00:00:00Z",
    )

    assert result["status"] == "completed"
    assert fake_xhs.calls == [("睡眠恢复", 5), ("人类丰容", 5), ("武侠", 5)]
    assert result["keywords"][0]["keyword"] == "睡眠恢复"
    assert result["keywords"][0]["top_score"] == 36068
    assert result["keywords"][0]["top_samples"][0]["engagement_score"] == 36068
    assert result["keywords"][0]["current_playbook_fit"] == [
        "modern_psychology_post",
        "human_enrichment_daily_post",
    ]
    assert result["keywords"][0]["new_domain_candidate"] is True
    assert result["keywords"][2]["keyword"] == "武侠"
    assert result["keywords"][2]["opportunity_tier"] == "keep_niche"

    assert result["recommendations"][0]["domain"] == "轻养生 / 睡眠恢复 / 办公室恢复"
    assert result["recommendations"][0]["recommendation"] == "new_domain_candidate"
    assert result["recommendations"][1]["domain"] == "人类丰容 / 修复系手作"

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["methodology"]["score_formula"] == (
        "likes + comments * 4 + collects * 2 + shares * 6"
    )
    assert artifact["source"]["live_source"] == "xiaohongshu-mcp.search_feeds"

    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "Top Domains" in markdown
    assert "Existing Playbook Fit" in markdown
    assert "New Domain Candidates" in markdown
    assert "Workflow Notes" in markdown
    assert "轻养生 / 睡眠恢复 / 办公室恢复" in markdown
    assert "sleep-1" not in markdown
    assert "token-sleep-1" not in markdown
