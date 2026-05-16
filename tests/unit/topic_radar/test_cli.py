from __future__ import annotations

import sys
import asyncio
from argparse import Namespace
from types import SimpleNamespace

import pytest

from topic_radar.analysis.schemas import LLMAngle, LLMScanOutput, LLMVertical
from topic_radar.cli import _convert_llm_output, _scan_xiaohongshu, _teardown, main
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
