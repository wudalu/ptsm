from __future__ import annotations

import pytest

from topic_radar.platforms.xiaohongshu import (
    FeedItem,
    FeedDetail,
    Comment,
    PlatformUnavailable,
    _to_int,
    _find_first_string,
)


class TestFeedItem:
    def test_engagement_score_weights_comments_heavier_than_likes(self):
        item = FeedItem(
            feed_id="abc", title="test", author="u",
            likes=100, comments=50, shares=5, collects=20,
        )
        # comments*4 + shares*6 + collects*2 + likes
        expected = 100 + 50 * 4 + 5 * 6 + 20 * 2
        assert item.engagement_score == expected

    def test_engagement_score_zero_for_empty(self):
        item = FeedItem(feed_id=None, title="", author="")
        assert item.engagement_score == 0


class TestToInt:
    def test_plain_int_string(self):
        assert _to_int("123") == 123

    def test_with_commas(self):
        assert _to_int("1,234") == 1234

    def test_none_returns_zero(self):
        assert _to_int(None) == 0

    def test_empty_returns_zero(self):
        assert _to_int("") == 0

    def test_int_directly(self):
        assert _to_int(42) == 42


class TestFindFirstString:
    def test_finds_key_in_dict(self):
        data = {"id": "abc123", "title": "hello"}
        assert _find_first_string(data, "id") == "abc123"

    def test_finds_first_matching_key(self):
        data = {"post_id": "111", "note_id": "222"}
        assert _find_first_string(data, "post_id", "note_id") == "111"

    def test_skips_non_strings(self):
        data = {"id": 123, "name": "test"}
        assert _find_first_string(data, "id") is None

    def test_recursive_search(self):
        data = {"outer": {"inner": {"xsec_token": "token123"}}}
        assert _find_first_string(data, "xsec_token") == "token123"

    def test_handles_list(self):
        data = [{"a": 1}, {"id": "found"}]
        assert _find_first_string(data, "id") == "found"


class TestComment:
    def test_question_detection_chinese(self):
        c = Comment(author="u", content="这个怎么做吗？")
        assert c.is_question is True

    def test_question_detection_english(self):
        c = Comment(author="u", content="how to do this?")
        assert c.is_question is True

    def test_non_question(self):
        c = Comment(author="u", content="写得真好")
        assert c.is_question is False


class TestPlatformUnavailable:
    def test_exception_message(self):
        exc = PlatformUnavailable("xiaohongshu", "connection refused")
        assert "xiaohongshu" in str(exc)
        assert "connection refused" in str(exc)
        assert exc.platform == "xiaohongshu"
