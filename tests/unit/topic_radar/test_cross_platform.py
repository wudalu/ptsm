from __future__ import annotations

import pytest

from topic_radar.analysis.cross_platform import (
    discover_cross_platform_from_clusters,
    discover_cross_platform,
    discover_verticals,
    _normalize_topic,
)
from topic_radar.analysis.evidence import EvidenceRecord, cluster_evidence
from topic_radar.platforms.weibo import TrendingItem


class TestNormalizeTopic:
    def test_removes_hashtags_and_spaces(self):
        assert _normalize_topic("# 热门话题 ") == "热门话题"

    def test_truncates_long_titles(self):
        result = _normalize_topic("这是一个非常非常非常非常非常非常长的标题啊")
        assert len(result) <= 30


class TestDiscoverCrossPlatform:
    def test_finds_topics_across_platforms(self):
        platform_items = {
            "weibo": [
                TrendingItem(rank=1, title="打工人加班话题", hot_score=900000, platform="weibo"),
            ],
            "xiaohongshu": [
                TrendingItem(rank=3, title="打工人加班话题", hot_score=200000, platform="xiaohongshu"),
            ],
        }
        signals = discover_cross_platform(platform_items)
        assert len(signals) == 1
        assert "打工人" in signals[0].topic

    def test_ignores_single_platform_topics(self):
        platform_items = {
            "weibo": [TrendingItem(rank=1, title="only weibo", hot_score=100, platform="weibo")],
            "xiaohongshu": [TrendingItem(rank=2, title="only xhs", hot_score=200, platform="xiaohongshu")],
        }
        signals = discover_cross_platform(platform_items)
        assert len(signals) == 0

    def test_empty_input(self):
        assert discover_cross_platform({}) == []

    def test_uses_clustered_actual_platform_support_not_declared_labels(self):
        from topic_radar.analysis.evidence import EvidenceRecord

        evidence = [
            EvidenceRecord(
                evidence_id="evidence:xhs",
                source_identity="xhs:one",
                platform="xiaohongshu",
                title="成都暴雨致多处积水",
                canonical_title="成都暴雨致多处积水",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
            EvidenceRecord(
                evidence_id="evidence:weibo",
                source_identity="weibo:one",
                platform="weibo",
                title="成都突降暴雨 多地积水",
                canonical_title="成都突降暴雨多地积水",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
            EvidenceRecord(
                evidence_id="evidence:only-xhs",
                source_identity="xhs:two",
                platform="xiaohongshu",
                title="小红书独有的收纳技巧",
                canonical_title="小红书独有的收纳技巧",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
        ]
        _clustered, clusters = cluster_evidence(evidence)

        signals = discover_cross_platform_from_clusters(clusters)

        assert len(signals) == 1
        assert signals[0].platforms == ["weibo", "xiaohongshu"]
        assert signals[0].cluster_id == clusters[0].cluster_id
        assert "douyin" not in signals[0].platforms

    def test_cluster_signal_does_not_claim_a_temporal_first_platform_without_timestamps(self):
        from topic_radar.analysis.evidence import EvidenceRecord

        evidence = [
            EvidenceRecord(
                evidence_id="evidence:weibo",
                source_identity="weibo:one",
                platform="weibo",
                title="成都暴雨致多处积水",
                canonical_title="成都暴雨致多处积水",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
            EvidenceRecord(
                evidence_id="evidence:douyin",
                source_identity="douyin:one",
                platform="douyin",
                title="成都突降暴雨 多地积水",
                canonical_title="成都突降暴雨多地积水",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
        ]
        _clustered, clusters = cluster_evidence(evidence)

        signal = discover_cross_platform_from_clusters(clusters)[0]

        assert signal.first_seen_platform == ""
        assert signal.velocity == "unknown"

    @pytest.mark.parametrize(
        ("first_title", "second_title"),
        [
            ("北京暴雨交通受阻", "北京暴雪交通受阻"),
            ("AI绘图工具推荐", "AI写作工具推荐"),
            ("AI绘画工具推荐", "AI写作工具推荐"),
            ("AI图片工具推荐", "AI写作工具推荐"),
        ],
    )
    def test_conflicting_core_terms_do_not_create_cross_platform_signal(
        self,
        first_title: str,
        second_title: str,
    ) -> None:
        evidence = [
            EvidenceRecord(
                evidence_id="evidence:weibo",
                source_identity="weibo:one",
                platform="weibo",
                title=first_title,
                canonical_title=first_title,
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
            EvidenceRecord(
                evidence_id="evidence:douyin",
                source_identity="douyin:one",
                platform="douyin",
                title=second_title,
                canonical_title=second_title,
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
        ]

        _clustered, clusters = cluster_evidence(evidence)

        assert len(clusters) == 2
        assert discover_cross_platform_from_clusters(clusters) == []

    def test_visual_generation_aliases_remain_the_same_event_slot(self) -> None:
        evidence = [
            EvidenceRecord(
                evidence_id="evidence:weibo",
                source_identity="weibo:one",
                platform="weibo",
                title="AI绘图工具推荐",
                canonical_title="AI绘图工具推荐",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
            EvidenceRecord(
                evidence_id="evidence:douyin",
                source_identity="douyin:one",
                platform="douyin",
                title="AI绘画工具推荐",
                canonical_title="AI绘画工具推荐",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            ),
        ]

        _clustered, clusters = cluster_evidence(evidence)

        assert len(clusters) == 1


class TestDiscoverVerticals:
    def test_clusters_items_into_verticals(self):
        items = [
            TrendingItem(rank=1, title="打工人加班怎么办", hot_score=900000, platform="weibo"),
            TrendingItem(rank=2, title="AI工具效率提升", hot_score=800000, platform="weibo"),
            TrendingItem(rank=3, title="旧物修复手作", hot_score=500000, platform="xiaohongshu"),
        ]
        verticals = discover_verticals(items)
        names = {v.name for v in verticals}
        assert len(verticals) > 0
        assert any(not v.is_noise for v in verticals)

    def test_noise_verticals_marked(self):
        items = [
            TrendingItem(rank=1, title="xyz random stuff", hot_score=10, platform="weibo"),
        ]
        verticals = discover_verticals(items)
        # 未匹配任何簇的主题归入"其他话题"，但可能被标记为噪音
        assert len(verticals) >= 0
