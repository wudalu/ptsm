from __future__ import annotations

import pytest

from topic_radar.platforms.weibo import (
    TrendingItem,
    _parse_trending_items,
    _to_rank,
    _pick_str,
    _pick_int,
)

WEIBO_SAMPLE = {
    "data": [
        {"title": "热搜话题1", "rank": 1, "hot": 950000, "label": "爆", "url": "https://weibo.com/1"},
        {"title": "热搜话题2", "rank": 2, "hot": 820000, "label": "热", "url": "https://weibo.com/2"},
        {"title": "普通话题", "rank": 3, "hot": 120000, "label": ""},
    ]
}

DOUYIN_SAMPLE = {
    "items": [
        {"word": "抖音热点1", "position": 1, "hotScore": 9500000, "label": "爆"},
        {"word": "抖音热点2", "position": 2, "hotScore": 8200000, "label": "热"},
    ]
}


class TestParseTrendingItems:
    def test_parses_weibo_format(self):
        items = _parse_trending_items(WEIBO_SAMPLE, platform="weibo")
        assert len(items) == 3
        assert items[0].title == "热搜话题1"
        assert items[0].rank == 1
        assert items[0].hot_score == 950000
        assert items[0].label == "爆"
        assert items[0].platform == "weibo"

    def test_parses_douyin_format(self):
        items = _parse_trending_items(DOUYIN_SAMPLE, platform="douyin")
        assert len(items) == 2
        assert items[0].title == "抖音热点1"
        assert items[0].rank == 1
        assert items[0].platform == "douyin"

    def test_empty_input(self):
        assert _parse_trending_items({}, platform="weibo") == []
        assert _parse_trending_items([], platform="weibo") == []

    def test_skips_items_without_title(self):
        data = {"data": [{"rank": 1}, {"title": "good", "rank": 2}]}
        items = _parse_trending_items(data, platform="weibo")
        assert len(items) == 1
        assert items[0].title == "good"

    def test_ranking_from_position_when_no_rank(self):
        data = {"data": [{"title": "a"}, {"title": "b"}, {"title": "c"}]}
        items = _parse_trending_items(data, platform="weibo")
        assert len(items) == 3
        assert items[0].rank == 1
        assert items[1].rank == 2
        assert items[2].rank == 3


class TestToRank:
    def test_int_value(self):
        assert _to_rank(5, 0) == 5

    def test_string_int(self):
        assert _to_rank("10", 0) == 10

    def test_fallback_to_default_index(self):
        assert _to_rank(None, 3) == 4  # default_idx + 1
        assert _to_rank("", 0) == 1


class TestPickStr:
    def test_first_match(self):
        data = {"title": "hello", "name": "world"}
        assert _pick_str(data, "title", "name") == "hello"

    def test_fallback_key(self):
        data = {"name": "world"}
        assert _pick_str(data, "title", "name") == "world"

    def test_empty_for_missing(self):
        assert _pick_str({}, "title") == ""


class TestPickInt:
    def test_int_direct(self):
        assert _pick_int({"hot": 100}, "hot") == 100

    def test_string_int(self):
        assert _pick_int({"hot": "200"}, "hot") == 200

    def test_fallback_key(self):
        assert _pick_int({"a": 1}, "b", "a") == 1

    def test_zero_for_missing(self):
        assert _pick_int({}, "hot") == 0
