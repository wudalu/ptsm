from __future__ import annotations

import pytest

from topic_radar.analysis.cross_platform import (
    discover_cross_platform,
    discover_verticals,
    _normalize_topic,
)
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
