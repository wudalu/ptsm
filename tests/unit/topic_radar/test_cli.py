from __future__ import annotations

import sys
import asyncio
from argparse import Namespace
from types import SimpleNamespace

import pytest

from topic_radar.analysis.schemas import LLMAngle, LLMScanOutput, LLMVertical
from topic_radar.cli import _convert_llm_output, _scan_xiaohongshu, _teardown, main
from topic_radar.platforms.xiaohongshu import FeedItem
from topic_radar.platforms.weibo import TrendingItem


class TestCLIBasic:
    def test_no_args_shows_help(self, capsys):
        # Simulate no subcommand
        sys.argv = ["topic-radar"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "scan" in captured.out.lower()

    def test_scan_help(self, capsys):
        sys.argv = ["topic-radar", "scan", "--help"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "--platforms" in captured.out

    def test_teardown_help(self, capsys):
        sys.argv = ["topic-radar", "teardown", "--help"]
        try:
            main()
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "feed_id" in captured.out


def test_convert_llm_output_preserves_raw_trending_rows():
    llm_output = LLMScanOutput(
        scan_summary="发现打工人高互动内容",
        discovered_verticals=[
            LLMVertical(
                name="打工人日常",
                keywords=["打工人", "加班"],
                confidence=0.8,
                discussion_density="high",
                sample_topics=["领导18:57发在吗"],
                suggested_angles=["工牌背面的疯话接龙"],
                comment_themes=["情绪共鸣"],
            )
        ],
        recommended_angles=[
            LLMAngle(
                vertical="打工人日常",
                angle="工牌背面的疯话接龙",
                why="评论区可以自然接龙补充",
            )
        ],
    )
    trending = {
        "xiaohongshu": [
            TrendingItem(
                rank=1,
                title="领导18:57发在吗",
                hot_score=4096,
                platform="xiaohongshu",
            )
        ]
    }

    result = _convert_llm_output(llm_output, trending, "2026-05-15")

    assert result.raw_trending
    assert result.raw_trending[0]["platform"] == "xiaohongshu"
    assert result.raw_trending[0]["title"] == "领导18:57发在吗"
    assert result.raw_trending[0]["hot_score"] == 4096


def test_teardown_reports_compact_error_for_inaccessible_feed(monkeypatch, capsys):
    class FailingXiaohongshu:
        def __init__(self, client):
            pass

        async def get_feed_detail(self, feed_id: str, xsec_token: str, timeout: float = 20.0):
            return None

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", FailingXiaohongshu)

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(
            _teardown(
                Namespace(feed_id="note-404", xsec_token="token", timeout_seconds=0.1)
            )
        )

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to fetch detail for feed note-404: note inaccessible or timed out" in captured.out


def test_scan_xiaohongshu_records_not_logged_in_as_platform_error(monkeypatch):
    class LoggedOutXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return False, "qr-code"

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedOutXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=30),
            keywords="发疯文学",
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert "xiaohongshu" not in all_trending
    assert errors["xiaohongshu"] == "login required; run ptsm xhs-login-qrcode"


def test_scan_xiaohongshu_preserves_feed_metadata_for_teardown(monkeypatch):
    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            return [
                FeedItem(
                    feed_id="note-1",
                    title=f"{keyword} 工牌疯话",
                    author="作者A",
                    likes=120,
                    comments=9,
                    shares=4,
                    collects=30,
                    xsec_token="token-1",
                )
            ]

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=30),
            keywords="发疯文学",
            all_trending=all_trending,
            errors=errors,
        )
    )

    item = all_trending["xiaohongshu"][0]
    assert errors == {}
    assert item.title == "发疯文学 工牌疯话"
    assert item.url == "https://www.xiaohongshu.com/explore/note-1"
    assert item.metadata["feed_id"] == "note-1"
    assert item.metadata["xsec_token"] == "token-1"
    assert item.metadata["author"] == "作者A"
    assert item.metadata["likes"] == 120
    assert item.metadata["comments"] == 9
    assert item.metadata["collects"] == 30
    assert item.metadata["shares"] == 4
    assert item.metadata["keyword"] == "发疯文学"


def test_scan_xiaohongshu_searches_all_requested_keywords(monkeypatch):
    calls: list[tuple[str, int]] = []

    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            calls.append((keyword, limit))
            return [
                FeedItem(
                    feed_id=f"note-{keyword}",
                    title=f"{keyword} 样本",
                    author="作者A",
                    xsec_token=f"token-{keyword}",
                )
            ]

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            keywords="发疯文学,心理学,反刍思维,职场焦虑",
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert [keyword for keyword, _limit in calls] == [
        "发疯文学",
        "心理学",
        "反刍思维",
        "职场焦虑",
    ]
    assert {limit for _keyword, limit in calls} == {2}
    assert len(all_trending["xiaohongshu"]) == 4


def test_scan_xiaohongshu_records_empty_search_as_platform_error(monkeypatch):
    class EmptySearchXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            return []

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", EmptySearchXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=30),
            keywords="发疯文学,心理学",
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert "xiaohongshu" not in all_trending
    assert errors["xiaohongshu"] == "no search results returned for requested keywords"
