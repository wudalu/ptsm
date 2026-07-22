from __future__ import annotations

import sys
import asyncio
import json
from argparse import Namespace
from types import SimpleNamespace

import pytest

from topic_radar.analysis.schemas import (
    LLMAngle,
    LLMScanOutput,
    LLMTopicSignal,
    LLMVertical,
)
from topic_radar.cli import (
    ScanOptions,
    _convert_llm_output,
    _scan,
    _scan_weibo,
    _scan_xiaohongshu,
    _teardown,
    main,
    run_scan,
)
from topic_radar.analysis.evidence import ScanQuality
from topic_radar.output.artifacts import TopicScanResult
from topic_radar.output.report import generate_report
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
        assert "xhs" in captured.out
        assert "sspai" in captured.out

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
        cross_platform_signals=[
            LLMTopicSignal(
                topic="打工人加班话题",
                platforms=["weibo", "xiaohongshu"],
                velocity="accelerating",
                discussion_value="测试单次快照不应声称速度。",
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
    assert result.cross_platform_signals[0].velocity == "unknown"
    assert result.cross_platform_signals[0].first_seen_platform == ""


def test_convert_llm_output_preserves_partial_errors_and_quality():
    llm_output = LLMScanOutput(scan_summary="只有一个有效来源")
    trending = {
        "xiaohongshu": [
            TrendingItem(rank=1, title="有效样本", hot_score=20, platform="xiaohongshu")
        ]
    }

    result = _convert_llm_output(
        llm_output,
        trending,
        "2026-05-15",
        errors={"weibo": "no trending results returned"},
        scan_quality=ScanQuality.PARTIAL,
    )

    assert result.platform_errors == {"weibo": "no trending results returned"}
    assert result.scan_quality == "partial"


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
                    cover_width=1080,
                    cover_height=1440,
                    has_cover_url=True,
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
    assert item.metadata["cover_width"] == 1080
    assert item.metadata["cover_height"] == 1440
    assert item.metadata["has_cover_url"] is True


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
            keywords="发疯文学，心理学,反刍思维，职场焦虑",
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


def test_scan_xiaohongshu_collapses_duplicate_feed_ids_and_merges_keywords(monkeypatch):
    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            return [
                FeedItem(
                    feed_id="duplicate-note",
                    title="同一篇笔记",
                    author="作者A",
                    likes=120 if keyword == "发疯文学" else 200,
                )
            ]

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            keywords="发疯文学,职场焦虑",
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert len(all_trending["xiaohongshu"]) == 1
    assert all_trending["xiaohongshu"][0].metadata["matched_queries"] == [
        "发疯文学",
        "职场焦虑",
    ]


def test_run_scan_keeps_successful_xhs_keyword_when_a_later_keyword_fails(monkeypatch, tmp_path):
    class PartiallyFailingXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            if keyword == "第二个词":
                raise RuntimeError("transport temporarily failed")
            return [
                FeedItem(
                    feed_id="successful-note",
                    title="成功采集的笔记",
                    author="作者A",
                    likes=100,
                )
            ]

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", PartiallyFailingXiaohongshu)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="xiaohongshu",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(
        run_scan(
            platforms="xhs",
            keywords="第一个词,第二个词",
            output_dir=str(tmp_path),
        )
    )

    assert result.platforms == ["xiaohongshu"]
    assert result.scan_quality == "partial"
    assert result.evidence[0]["title"] == "成功采集的笔记"
    assert result.platform_errors["xiaohongshu"] == (
        "partial keyword search failure: 第二个词 (RuntimeError)"
    )


def test_scan_xiaohongshu_reports_meaningful_error_when_every_keyword_fails(monkeypatch):
    class FailingXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            raise RuntimeError("transport temporarily failed")

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", FailingXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            keywords="第一个词,第二个词",
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert "xiaohongshu" not in all_trending
    assert errors["xiaohongshu"] == (
        "all keyword searches failed: 第一个词 (RuntimeError), 第二个词 (RuntimeError)"
    )


@pytest.mark.parametrize("keywords", [None, " , , ", "，", " , ， \n "])
def test_scan_xiaohongshu_uses_open_feed_listing_without_keywords(
    monkeypatch,
    keywords: str | None,
):
    listing_calls: list[int] = []

    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            raise AssertionError("open discovery must not issue a keyword search")

        async def list_feeds(self, limit: int = 20):
            listing_calls.append(limit)
            return []

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            keywords=keywords,
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert listing_calls == [8]
    assert errors["xiaohongshu"] == "no open feed listing results returned"


def test_scan_xiaohongshu_marks_open_listing_samples_without_a_keyword(
    monkeypatch,
):
    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            raise AssertionError("open discovery must not issue a keyword search")

        async def list_feeds(self, limit: int = 20):
            return [
                FeedItem(
                    feed_id="open-note",
                    title="开放样本",
                    author="作者A",
                    likes=12,
                )
            ]

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_xiaohongshu(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            keywords=None,
            all_trending=all_trending,
            errors=errors,
        )
    )

    item = all_trending["xiaohongshu"][0]
    assert errors == {}
    assert item.metadata["collection_mode"] == "open_feed_listing"
    assert "keyword" not in item.metadata


def test_empty_collector_results_become_platform_errors(monkeypatch):
    class EmptyWeibo:
        def __init__(self, client):
            pass

        async def get_trending(self, limit: int = 20):
            return []

    monkeypatch.setattr("topic_radar.cli.WeiboPlatform", EmptyWeibo)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_weibo(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert "weibo" not in all_trending
    assert errors["weibo"] == "no trending results returned"


def test_external_collector_exception_becomes_platform_error(monkeypatch):
    class FailingWeibo:
        def __init__(self, client):
            pass

        async def get_trending(self, limit: int = 20):
            raise RuntimeError("network transient failure")

    monkeypatch.setattr("topic_radar.cli.WeiboPlatform", FailingWeibo)
    all_trending = {}
    errors = {}

    asyncio.run(
        _scan_weibo(
            client=object(),
            config=SimpleNamespace(scan_sample_limit=8),
            all_trending=all_trending,
            errors=errors,
        )
    )

    assert all_trending == {}
    assert errors == {"weibo": "collection failed (RuntimeError)"}


def test_run_scan_alias_invokes_canonical_xhs_collector(monkeypatch, tmp_path):
    calls: list[str] = []

    async def collect_xhs(client, config, keywords, all_trending, errors):
        calls.append("xiaohongshu")
        all_trending["xiaohongshu"] = [
            TrendingItem(rank=1, title="有效样本", hot_score=100, platform="xiaohongshu")
        ]

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli._scan_xiaohongshu", collect_xhs)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="xiaohongshu",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(platforms="xhs", output_dir=str(tmp_path)))

    assert calls == ["xiaohongshu"]
    assert result.platforms == ["xiaohongshu"]
    assert result.scan_quality == "completed"


def test_default_eight_platforms_use_the_canonical_collection_path(monkeypatch, tmp_path):
    calls: list[str] = []

    class NoopClient:
        def __init__(self, **kwargs):
            pass

    async def collect_xhs(client, config, keywords, all_trending, errors):
        calls.append("xiaohongshu")
        all_trending["xiaohongshu"] = [
            TrendingItem(rank=1, title="小红书样本", hot_score=1, platform="xiaohongshu")
        ]

    async def collect_weibo(client, config, all_trending, errors):
        calls.append("weibo")
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="微博样本", hot_score=1, platform="weibo")
        ]

    async def collect_douyin(client, config, all_trending, errors):
        calls.append("douyin")
        all_trending["douyin"] = [
            TrendingItem(rank=1, title="抖音样本", hot_score=1, platform="douyin")
        ]

    async def collect_hub(client, config, platform_cls, platform_name, display_name, all_trending, errors):
        calls.append(platform_name)
        all_trending[display_name] = [
            TrendingItem(rank=1, title=f"{platform_name}样本", hot_score=1, platform=platform_name)
        ]

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli.McpClient", NoopClient)
    monkeypatch.setattr("topic_radar.cli._scan_xiaohongshu", collect_xhs)
    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli._scan_douyin", collect_douyin)
    monkeypatch.setattr("topic_radar.cli._scan_trends_hub_platform", collect_hub)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo,douyin,zhihu,bilibili,toutiao,douban,sspai,xiaohongshu",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(output_dir=str(tmp_path)))

    expected = {"xiaohongshu", "weibo", "douyin", "zhihu", "bilibili", "toutiao", "douban", "sspai"}
    assert set(calls) == expected
    assert set(result.platforms) == expected
    assert {row["platform"] for row in result.evidence} == expected


def test_rules_fallback_never_emits_unexpanded_template_angles(monkeypatch, tmp_path):
    class NoopClient:
        def __init__(self, **kwargs):
            pass

    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="打工人工位恢复小动作", hot_score=100, platform="weibo"),
            TrendingItem(rank=2, title="打工人下班后先别回消息", hot_score=90, platform="weibo"),
            TrendingItem(rank=3, title="打工人午休十分钟回血", hot_score=80, platform="weibo"),
        ]

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            self.last_error = ""

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli.McpClient", NoopClient)
    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.analysis_method == "rules"
    assert result.recommended_angles
    assert all("{" not in angle["angle"] and "}" not in angle["angle"] for angle in result.recommended_angles)


@pytest.mark.parametrize(
    ("unavailable_server", "unavailable_platform", "healthy_platform"),
    [
        ("xiaohongshu", "xiaohongshu", "weibo"),
        ("trends_hub", "weibo", "xiaohongshu"),
    ],
)
def test_run_scan_keeps_healthy_platform_when_the_other_mcp_server_is_unavailable(
    monkeypatch,
    tmp_path,
    unavailable_server: str,
    unavailable_platform: str,
    healthy_platform: str,
):
    class FakeTool:
        def __init__(self, server_name: str, name: str) -> None:
            self.server_name = server_name
            self.name = name

        async def arun(self, payload, *, tool_call_id):
            if self.name == "check_login_status":
                return [{"text": "✅ 已登录"}]
            if self.name == "search_feeds":
                return [
                    {
                        "text": json.dumps(
                            {
                                "feeds": [
                                    {
                                        "id": "xhs-healthy-1",
                                        "noteCard": {
                                            "displayTitle": "小红书恢复样本",
                                            "user": {"nickname": "作者"},
                                            "interactInfo": {
                                                "likedCount": "20",
                                                "commentCount": "2",
                                                "collectedCount": "3",
                                                "sharedCount": "1",
                                            },
                                        },
                                    }
                                ]
                            },
                            ensure_ascii=False,
                        )
                    }
                ]
            return [
                {
                    "text": json.dumps(
                        {"data": [{"title": "微博恢复样本", "hot": 100}]},
                        ensure_ascii=False,
                    )
                }
            ]

    class ServerClient:
        def __init__(self, server_name: str) -> None:
            self.server_name = server_name

        async def get_tools(self):
            if self.server_name == unavailable_server:
                raise OSError(f"{self.server_name} unavailable")
            if self.server_name == "xiaohongshu":
                return [
                    FakeTool("xiaohongshu", "check_login_status"),
                    FakeTool("xiaohongshu", "search_feeds"),
                ]
            return [FakeTool("trends_hub", "get_weibo_trending")]

        async def close(self):
            return None

    class CombinedClient:
        async def get_tools(self):
            raise OSError("combined MCP loading failed")

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            self.last_error = ""

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr(
        "topic_radar.mcp_client._make_single_client",
        lambda name, _xhs_url: ServerClient(name),
    )
    monkeypatch.setattr(
        "topic_radar.mcp_client.MultiServerMCPClient",
        lambda _servers: CombinedClient(),
    )
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="xiaohongshu,weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(
        run_scan(
            platforms="xiaohongshu,weibo",
            keywords="恢复",
            output_dir=str(tmp_path),
        )
    )

    assert result.scan_quality == "partial"
    assert result.platforms == [healthy_platform]
    assert unavailable_platform in result.platform_errors


def test_run_scan_returns_insufficient_evidence_without_creating_analyzer(monkeypatch, tmp_path):
    async def no_evidence(client, config, all_trending, errors):
        errors["weibo"] = "no trending results returned"

    class AnalyzerMustNotBeCreated:
        def __init__(self, **kwargs):
            raise AssertionError("LLM must not run without valid evidence")

    monkeypatch.setattr("topic_radar.cli._scan_weibo", no_evidence)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", AnalyzerMustNotBeCreated)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.scan_quality == "insufficient_evidence"
    assert result.recommended_angles == []
    assert result.platform_errors == {"weibo": "no trending results returned"}


def test_run_scan_preserves_xhs_source_observation_count_after_second_canonicalization(
    monkeypatch, tmp_path
):
    class LoggedInXiaohongshu:
        def __init__(self, client):
            pass

        async def check_login(self):
            return True, None

        async def search_feeds(self, keyword: str, limit: int = 20):
            return [
                FeedItem(
                    feed_id="same-feed",
                    title="同一篇笔记",
                    author="作者A",
                    likes=100,
                )
            ]

    class RulesOnlyAnalyzer:
        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli.XiaohongshuPlatform", LoggedInXiaohongshu)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", RulesOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="xiaohongshu",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(
        run_scan(
            platforms="xhs",
            keywords="发疯文学,职场焦虑",
            output_dir=str(tmp_path),
        )
    )

    assert result.evidence[0]["source_observation_count"] == 2


def test_run_scan_rejects_separator_only_platforms_and_writes_diagnostic(monkeypatch, tmp_path):
    class ClientMustNotBeCreated:
        def __init__(self, **kwargs):
            raise AssertionError("empty platform request must short-circuit before collection")

    monkeypatch.setattr("topic_radar.cli.McpClient", ClientMustNotBeCreated)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(platforms=" , , ", output_dir=str(tmp_path)))

    assert result.scan_quality == "insufficient_evidence"
    assert result.platform_errors == {"platform_request": "no platforms requested"}
    artifact = tmp_path / f"topic-scan-{result.scan_date}.json"
    assert json.loads(artifact.read_text(encoding="utf-8"))["scan_quality"] == "insufficient_evidence"


def test_scan_cli_exits_two_for_insufficient_evidence(monkeypatch, tmp_path, capsys):
    class NoopClient:
        def __init__(self, **kwargs):
            pass

    async def insufficient(*args, **kwargs):
        return TopicScanResult(
            scan_date="2026-07-21",
            platforms=[],
            scan_quality="insufficient_evidence",
            platform_errors={"platform_request": "no platforms requested"},
        )

    monkeypatch.setattr("topic_radar.cli.McpClient", NoopClient)
    monkeypatch.setattr("topic_radar.cli.run_scan", insufficient)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            xhs_mcp_server_url="http://unused",
            output_dir=str(tmp_path),
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(
            _scan(
                Namespace(
                    platforms=" , ",
                    keywords=None,
                    output_dir=str(tmp_path),
                    mcp_check=False,
                )
            )
        )

    assert exc_info.value.code == 2
    assert "Scan status: insufficient evidence" in capsys.readouterr().out


def test_scan_cli_uses_configured_artifact_dir_and_neutral_partial_status(
    monkeypatch, tmp_path, capsys
):
    async def partial(*args, **kwargs):
        return TopicScanResult(
            scan_date="2026-07-21",
            platforms=["weibo"],
            scan_quality="partial",
            platform_errors={"weibo": "collection failed (RuntimeError)"},
        )

    monkeypatch.setattr("topic_radar.cli.run_scan", partial)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            xhs_mcp_server_url="http://unused",
            output_dir=str(tmp_path),
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(
            _scan(
                Namespace(
                    platforms=None,
                    keywords=None,
                    output_dir=None,
                    mcp_check=False,
                )
            )
        )

    output = capsys.readouterr().out
    assert exc_info.value.code == 1
    assert str(tmp_path / "topic-scan-2026-07-21.json") in output
    assert str(tmp_path / "topic-brief-2026-07-21.md") in output
    assert "Scan status: partial" in output
    assert "issue(s) recorded" in output
    assert "unavailable" not in output


def test_run_scan_marks_llm_failure_partial_without_secret_detail(monkeypatch, tmp_path):
    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="有效样本", hot_score=100, platform="weibo")
        ]

    class FailingAnalyzer:
        last_error = "LLM analysis failed (RuntimeError); rules fallback used"

        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date):
            return None, "rules"

    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", FailingAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="sk-secret-not-for-artifacts",
            llm_base_url="http://unused",
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.scan_quality == "partial"
    assert result.platform_errors["llm_analysis"] == "LLM analysis failed (RuntimeError); rules fallback used"
    assert "sk-secret-not-for-artifacts" not in result.to_json()


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


def test_run_scan_enriches_only_evidence_backed_llm_angles_and_appends_history(
    monkeypatch, tmp_path
):
    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="成都暴雨致多处积水", hot_score=100, platform="weibo")
        ]

    async def collect_douyin(client, config, all_trending, errors):
        all_trending["douyin"] = [
            TrendingItem(rank=1, title="成都突降暴雨 多地积水", hot_score=100, platform="douyin")
        ]

    class EvidenceAwareAnalyzer:
        last_error = ""

        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date, *, evidence, topic_clusters):
            cluster = topic_clusters[0]
            return (
                LLMScanOutput(
                    scan_summary="天气事件引发通勤讨论",
                    cross_platform_signals=[
                        {
                            "topic": "编造的平台名单",
                            "platforms": ["xiaohongshu", "invented"],
                            "velocity": "accelerating",
                            "discussion_value": "无关",
                            "cluster_id": cluster.cluster_id,
                            "evidence_ids": cluster.evidence_ids,
                        }
                    ],
                    recommended_angles=[
                        LLMAngle(
                            vertical="城市天气",
                            angle="暴雨天通勤避坑清单",
                            why="真实可用",
                            cluster_id=cluster.cluster_id,
                            evidence_ids=cluster.evidence_ids,
                        ),
                        LLMAngle(
                            vertical="城市天气",
                            angle="没有来源的编造角度",
                            why="不应出现",
                            cluster_id="cluster:invented",
                            evidence_ids=["evidence:invented"],
                        ),
                    ],
                ),
                "llm",
            )

    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli._scan_douyin", collect_douyin)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", EvidenceAwareAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo,douyin",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="sk-test",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    first = asyncio.run(
        run_scan(
            platforms="weibo,douyin",
            output_dir=str(tmp_path),
            options=ScanOptions(max_recommendations=3),
        )
    )
    second = asyncio.run(
        run_scan(
            platforms="weibo,douyin",
            output_dir=str(tmp_path),
            options=ScanOptions(max_recommendations=3),
        )
    )

    assert first.analysis_method == "llm"
    assert len(first.topic_clusters) == 1
    assert first.cross_platform_signals[0].platforms == ["douyin", "weibo"]
    assert [angle["angle"] for angle in first.recommended_angles] == ["暴雨天通勤避坑清单"]
    assert first.recommended_angles[0]["event_fingerprint"] == first.topic_clusters[0]["event_fingerprint"]
    assert (tmp_path / "topic-radar-history.jsonl").exists()
    assert second.recommended_angles == []


def test_run_scan_uses_rules_fallback_when_llm_has_no_supported_angle(monkeypatch, tmp_path):
    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="有效热搜样本", hot_score=100, platform="weibo")
        ]

    class UnsupportedAnalyzer:
        last_error = ""

        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date, *, evidence, topic_clusters):
            return (
                LLMScanOutput(
                    scan_summary="没有可验证来源",
                    recommended_angles=[
                        LLMAngle(
                            vertical="猜测",
                            angle="没有来源的编造角度",
                            why="不应出现",
                            evidence_ids=["evidence:invented"],
                        )
                    ],
                ),
                "llm",
            )

    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", UnsupportedAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="sk-test",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.analysis_method == "rules"
    assert all(angle["angle"] != "没有来源的编造角度" for angle in result.recommended_angles)


def test_run_scan_uses_rules_fallback_when_llm_angle_has_an_unexpanded_template(
    monkeypatch,
    tmp_path,
):
    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="打工人工位恢复小动作", hot_score=100, platform="weibo"),
            TrendingItem(rank=2, title="打工人午休十分钟回血", hot_score=90, platform="weibo"),
            TrendingItem(rank=3, title="打工人下班后先别回消息", hot_score=80, platform="weibo"),
        ]

    class TemplateAnalyzer:
        last_error = ""

        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date, *, evidence, topic_clusters):
            cluster = topic_clusters[0]
            return (
                LLMScanOutput(
                    scan_summary="占位符不能作为可用选题",
                    recommended_angles=[
                        LLMAngle(
                            vertical="打工人日常",
                            angle="工位上的{action}，同事问我是不是偷偷续命了",
                            why="{reason}",
                            cluster_id=cluster.cluster_id,
                            evidence_ids=cluster.evidence_ids,
                        )
                    ],
                ),
                "llm",
            )

    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", TemplateAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="sk-test",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.analysis_method == "rules"
    assert result.recommended_angles
    assert all("{" not in angle["angle"] and "}" not in angle["angle"] for angle in result.recommended_angles)
    assert result.platform_errors["llm_analysis"] == (
        "LLM output had no verifiable recommendations; rules fallback used"
    )


def test_run_scan_falls_back_when_a_valid_llm_vertical_has_only_unsupported_angles(
    monkeypatch, tmp_path
):
    async def collect_weibo(client, config, all_trending, errors):
        all_trending["weibo"] = [
            TrendingItem(rank=1, title="打工人加班怎么办", hot_score=100, platform="weibo"),
            TrendingItem(rank=2, title="打工人工位摸鱼", hot_score=90, platform="weibo"),
            TrendingItem(rank=3, title="打工人下班后不回消息", hot_score=80, platform="weibo"),
        ]

    class VerticalOnlyAnalyzer:
        last_error = ""

        def __init__(self, **kwargs):
            pass

        def analyze(self, trending_items, scan_date, *, evidence, topic_clusters):
            cluster = topic_clusters[0]
            return (
                LLMScanOutput(
                    scan_summary="有可验证的打工人垂类，但没有可验证角度",
                    discovered_verticals=[
                        LLMVertical(
                            name="打工人日常",
                            keywords=["打工人"],
                            confidence=0.8,
                            discussion_density="high",
                            sample_topics=[cluster.representative_title],
                            suggested_angles=[],
                            comment_themes=[],
                            cluster_ids=[cluster.cluster_id],
                            evidence_ids=cluster.evidence_ids,
                        )
                    ],
                    recommended_angles=[
                        LLMAngle(
                            vertical="打工人日常",
                            angle="没有来源的编造角度",
                            why="不应出现",
                            cluster_id="cluster:invented",
                            evidence_ids=["evidence:invented"],
                        )
                    ],
                ),
                "llm",
            )

    monkeypatch.setattr("topic_radar.cli._scan_weibo", collect_weibo)
    monkeypatch.setattr("topic_radar.cli.LLMAnalyzer", VerticalOnlyAnalyzer)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="weibo",
            output_dir=str(tmp_path),
            xhs_mcp_server_url="http://unused",
            llm_model="unused",
            llm_api_key="sk-test",
            llm_base_url="http://unused",
            scan_sample_limit=8,
        ),
    )

    result = asyncio.run(run_scan(platforms="weibo", output_dir=str(tmp_path)))

    assert result.analysis_method == "rules"
    assert result.scan_quality == "partial"
    assert result.platform_errors["llm_analysis"] == (
        "LLM output had no verifiable recommendations; rules fallback used"
    )
    assert result.recommended_angles
    assert all(angle["angle"] != "没有来源的编造角度" for angle in result.recommended_angles)
    assert all(angle["evidence_ids"] for angle in result.recommended_angles)


def test_scan_cli_prints_the_unique_json_and_report_paths(monkeypatch, tmp_path, capsys):
    earlier = TopicScanResult(scan_date="2026-07-21", platforms=["weibo"])
    earlier.write(str(tmp_path))
    generate_report(earlier, str(tmp_path))
    result = TopicScanResult(scan_date="2026-07-21", platforms=["douyin"])
    json_path = result.write(str(tmp_path))
    report_path = generate_report(result, str(tmp_path))

    async def completed(*args, **kwargs):
        return result

    monkeypatch.setattr("topic_radar.cli.run_scan", completed)
    monkeypatch.setattr(
        "topic_radar.cli.get_config",
        lambda: SimpleNamespace(
            default_platforms="douyin",
            xhs_mcp_server_url="http://unused",
            output_dir=str(tmp_path),
        ),
    )

    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(
            _scan(
                Namespace(
                    platforms=None,
                    keywords=None,
                    output_dir=str(tmp_path),
                    mcp_check=False,
                )
            )
        )

    output = capsys.readouterr().out
    assert exc_info.value.code == 0
    assert str(json_path) in output
    assert str(report_path) in output
