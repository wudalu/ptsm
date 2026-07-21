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
from topic_radar.output.report import generate_report
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

    def test_write_preserves_an_earlier_same_day_scan_artifact(self, tmp_path):
        first = TopicScanResult(
            scan_date="2026-07-21",
            platforms=["weibo"],
            scan_summary="first scan",
        )
        second = TopicScanResult(
            scan_date="2026-07-21",
            platforms=["douyin"],
            scan_summary="second scan",
        )

        first_path = first.write(str(tmp_path))
        second_path = second.write(str(tmp_path))

        assert first_path != second_path
        assert json.loads(first_path.read_text(encoding="utf-8"))["scan_summary"] == "first scan"
        assert json.loads(second_path.read_text(encoding="utf-8"))["scan_summary"] == "second scan"

    def test_report_uses_the_same_unique_stem_as_its_json_artifact(self, tmp_path):
        first = TopicScanResult(
            scan_date="2026-07-21",
            platforms=["weibo"],
            scan_summary="first scan",
        )
        second = TopicScanResult(
            scan_date="2026-07-21",
            platforms=["douyin"],
            scan_summary="second scan",
        )

        first_json = first.write(str(tmp_path))
        first_report = generate_report(first, str(tmp_path))
        second_json = second.write(str(tmp_path))
        second_report = generate_report(second, str(tmp_path))

        assert first_json.stem.removeprefix("topic-scan") == first_report.stem.removeprefix("topic-brief")
        assert second_json.stem.removeprefix("topic-scan") == second_report.stem.removeprefix("topic-brief")
        assert first_report != second_report
        assert "weibo" in first_report.read_text(encoding="utf-8")
        assert "douyin" in second_report.read_text(encoding="utf-8")

    def test_platform_errors_recorded(self):
        result = TopicScanResult(
            scan_date="2026-05-03",
            platforms=["xiaohongshu"],
            platform_errors={"weibo": "mcp-trends-hub not installed"},
        )
        assert result.platform_errors["weibo"] == "mcp-trends-hub not installed"

    def test_schema_v2_serializes_scan_quality_evidence_and_empty_clusters(self):
        result = TopicScanResult(
            scan_date="2026-05-03",
            platforms=["weibo"],
            scan_quality="partial",
            evidence=[
                {
                    "evidence_id": "evidence:1",
                    "platform": "weibo",
                    "title": "有效样本",
                    "normalized_heat": 1.0,
                }
            ],
        )

        data = json.loads(result.to_json())

        assert data["schema_version"] == 2
        assert data["scan_quality"] == "partial"
        assert data["evidence"][0]["evidence_id"] == "evidence:1"
        assert data["topic_clusters"] == []

    def test_report_includes_scan_quality(self, tmp_path):
        report = generate_report(
            TopicScanResult(
                scan_date="2026-05-03",
                platforms=["weibo"],
                scan_quality="partial",
            ),
            str(tmp_path),
        )

        assert "**Scan quality:** partial" in report.read_text(encoding="utf-8")

    def test_schema_v2_serializes_cluster_and_enriched_angle_provenance(self):
        result = TopicScanResult(
            scan_date="2026-07-21",
            platforms=["weibo"],
            topic_clusters=[
                {
                    "cluster_id": "cluster:abc",
                    "event_fingerprint": "event:def",
                    "representative_title": "成都暴雨致多处积水",
                    "evidence_ids": ["evidence:weibo"],
                    "platforms": ["weibo"],
                    "score": 1.0,
                }
            ],
            recommended_angles=[
                {
                    "vertical": "城市天气",
                    "angle": "暴雨天通勤避坑清单",
                    "cluster_id": "cluster:abc",
                    "event_fingerprint": "event:def",
                    "evidence_ids": ["evidence:weibo"],
                    "angle_signature": "angle:123",
                    "novelty_state": "new",
                    "ranking_score": 1.2,
                }
            ],
        )

        data = json.loads(result.to_json())

        assert data["topic_clusters"][0]["evidence_ids"] == ["evidence:weibo"]
        assert data["recommended_angles"][0]["event_fingerprint"] == "event:def"


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
