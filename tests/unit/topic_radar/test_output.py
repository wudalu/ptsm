from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from topic_radar.analysis.cross_platform import (
    CrossPlatformSignal,
    DiscoveredVertical,
)
from topic_radar.output.artifacts import TopicScanResult, build_scan_result
from topic_radar.platforms.weibo import TrendingItem


class TestTopicScanResult:
    def test_to_json(self):
        result = TopicScanResult(
            scan_date="2026-05-03",
            platforms=["weibo", "xiaohongshu"],
            discovered_verticals=[
                DiscoveredVertical(
                    name="打工人日常",
                    keywords=["打工人", "加班"],
                    confidence=0.75,
                    heat_signals={"weibo": 900000.0, "xiaohongshu": 500000.0},
                    discussion_density="high",
                    sample_topics=["打工人加班怎么办"],
                    suggested_angles=["工位上的小动作，旁边同事问我链接"],
                    comment_themes=["提问求解", "经验交换"],
                )
            ],
            cross_platform_signals=[
                CrossPlatformSignal(
                    topic="打工人加班话题",
                    platforms=["weibo", "xiaohongshu"],
                    first_seen_platform="weibo",
                    velocity="accelerating",
                )
            ],
        )
        data = json.loads(result.to_json())
        assert data["scan_date"] == "2026-05-03"
        assert len(data["platforms"]) == 2
        assert len(data["discovered_verticals"]) == 1
        assert data["discovered_verticals"][0]["name"] == "打工人日常"

    def test_write_to_file(self):
        result = TopicScanResult(
            scan_date="2026-05-03",
            platforms=["weibo"],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = result.write(tmpdir)
            assert filepath.exists()
            data = json.loads(filepath.read_text())
            assert data["scan_date"] == "2026-05-03"

    def test_output_directory_auto_created(self):
        result = TopicScanResult(scan_date="2026-05-03", platforms=["weibo"])
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "nested" / "dir"
            filepath = result.write(str(out))
            assert filepath.exists()
            assert "topic-scan-2026-05-03.json" == filepath.name

    def test_platform_errors_recorded(self):
        result = TopicScanResult(
            scan_date="2026-05-03",
            platforms=["xiaohongshu"],
            platform_errors={"weibo": "mcp-trends-hub not installed"},
        )
        assert result.platform_errors["weibo"] == "mcp-trends-hub not installed"


class TestBuildScanResult:
    def test_builds_complete_result(self):
        trending = {
            "weibo": [TrendingItem(rank=1, title="打工人话题", hot_score=800000, platform="weibo")],
        }
        verticals = [
            DiscoveredVertical(
                name="打工人日常",
                keywords=["打工人"],
                confidence=0.5,
                heat_signals={"weibo": 800000.0},
                discussion_density="medium",
                sample_topics=["打工人话题"],
            )
        ]
        cross = [
            CrossPlatformSignal(
                topic="打工人话题",
                platforms=["weibo"],
                first_seen_platform="weibo",
            )
        ]

        result = build_scan_result(
            trending_items=trending,
            verticals=verticals,
            cross_signals=cross,
            errors={"xiaohongshu": "not logged in"},
        )
        assert len(result.platforms) == 1
        assert len(result.discovered_verticals) == 1
        assert len(result.cross_platform_signals) == 1
        assert result.platform_errors["xiaohongshu"] == "not logged in"
        assert len(result.raw_trending) == 1

    def test_raw_trending_includes_xhs_teardown_identifiers(self):
        trending = {
            "xiaohongshu": [
                TrendingItem(
                    rank=1,
                    title="领导18:57发在吗",
                    hot_score=4096,
                    platform="xiaohongshu",
                    metadata={
                        "feed_id": "note-1",
                        "xsec_token": "token-1",
                        "likes": 120,
                        "comments": 9,
                        "collects": 30,
                        "shares": 4,
                    },
                )
            ],
        }

        result = build_scan_result(
            trending_items=trending,
            verticals=[],
            cross_signals=[],
        )

        assert result.raw_trending[0]["feed_id"] == "note-1"
        assert result.raw_trending[0]["xsec_token"] == "token-1"
        assert result.raw_trending[0]["likes"] == 120
        assert result.raw_trending[0]["comments"] == 9
        assert result.raw_trending[0]["collects"] == 30
        assert result.raw_trending[0]["shares"] == 4

    def test_raw_trending_default_limit_keeps_later_keyword_groups(self):
        items = []
        for index in range(45):
            keyword = "普通人用AI" if index >= 35 else "人类丰容"
            items.append(
                TrendingItem(
                    rank=index + 1,
                    title=f"{keyword} 样本 {index}",
                    hot_score=1000 - index,
                    platform="xiaohongshu",
                    metadata={"keyword": keyword, "feed_id": f"note-{index}"},
                )
            )

        result = build_scan_result(
            trending_items={"xiaohongshu": items},
            verticals=[],
            cross_signals=[],
        )

        assert len(result.raw_trending) == 45
        assert any(row["keyword"] == "普通人用AI" for row in result.raw_trending)
