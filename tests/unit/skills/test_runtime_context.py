from __future__ import annotations

import asyncio
import json

from ptsm.skills import runtime_context
from ptsm.skills.runtime_context import TopicResearchContextBuilder, XhsTrendScanContextBuilder


def _search_payload(*titles: tuple[str, int, int, int, int]) -> list[dict[str, str]]:
    feeds = []
    for index, (title, likes, comments, shares, collects) in enumerate(titles):
        feeds.append(
            {
                "id": f"note-{index}",
                "noteCard": {
                    "displayTitle": title,
                    "user": {"nickname": f"author-{index}"},
                    "interactInfo": {
                        "likedCount": str(likes),
                        "commentCount": str(comments),
                        "sharedCount": str(shares),
                        "collectedCount": str(collects),
                    },
                },
            }
        )
    return [{"type": "text", "text": json.dumps({"feeds": feeds}, ensure_ascii=False)}]


class FakeMcpRunner:
    def __init__(self, *, login_text: str = "✅ 已登录") -> None:
        self.login_text = login_text
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def list_tool_names(self) -> list[str]:
        return ["check_login_status", "search_feeds"]

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        self.calls.append((tool_name, payload))
        if tool_name == "check_login_status":
            return [{"type": "text", "text": self.login_text}]
        if tool_name != "search_feeds":
            raise AssertionError(f"Unexpected tool: {tool_name}")

        keyword = str(payload["keyword"])
        if keyword == "怎么才周四":
            return _search_payload(
                ("不是已经上五天班了吗 怎么才周四", 1108, 235, 1479, 72),
                ("怎么才周四啊啊啊啊", 976, 277, 469, 4),
            )
        if keyword == "发疯文学 打工人":
            return _search_payload(
                ("评论区交出你的工牌疯话文案", 32000, 8900, 8600, 6400),
                ("又来坐牢了", 18492, 2290, 32270, 4487),
                ("面对领导时我的精神状态", 26888, 1453, 15999, 4531),
            )
        if keyword == "隐形加班":
            return _search_payload(
                ("打工人下班后自救清单Tips", 8800, 320, 1100, 9200),
                ("职场人必看！下班后线上工作也算加班", 1023, 103, 711, 208),
                ("今天你隐性加班了吗", 458, 312, 167, 115),
            )
        return _search_payload(("普通周四流水账", 12, 3, 1, 0))


class HangingMcpRunner:
    async def list_tool_names(self) -> list[str]:
        await asyncio.sleep(10)
        return ["check_login_status", "search_feeds"]

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        await asyncio.sleep(10)
        return []


def test_xhs_trend_scan_context_builder_summarizes_live_search_results() -> None:
    builder = XhsTrendScanContextBuilder(
        server_url="http://localhost:18060/mcp",
        tool_runner=FakeMcpRunner(),
    )

    context = builder.build(
        scene="周四下午四点半，工位上的我已经开始提前庆祝快解放了，但老板还在群里发新需求",
        domain="发疯文学",
        playbook_id="fengkuang_daily_post",
    )

    assert context is not None
    assert "实时站内热点扫描" in context
    assert "怎么才周四" in context
    assert "发疯文学 打工人" in context
    assert "又来坐牢了" in context
    assert "面对领导时我的精神状态" in context
    assert "隐形加班" in context
    assert "下班前被新需求拽回工位" in context
    assert "可借鉴内容机制" in context
    assert "comment_chain" in context
    assert "save_tool" in context
    assert "copyable_line" in context
    assert "评论区交出你的工牌疯话文案" in context
    assert "打工人下班后自救清单Tips" in context


def test_xhs_trend_scan_context_builder_returns_none_when_login_required() -> None:
    builder = XhsTrendScanContextBuilder(
        server_url="http://localhost:18060/mcp",
        tool_runner=FakeMcpRunner(login_text="❌ 未登录"),
    )

    context = builder.build(
        scene="周四下午老板临时加需求",
        domain="发疯文学",
        playbook_id="fengkuang_daily_post",
    )

    assert context is None


def test_xhs_trend_scan_context_builder_times_out_when_mcp_hangs() -> None:
    builder = XhsTrendScanContextBuilder(
        server_url="http://localhost:18060/mcp",
        tool_runner=HangingMcpRunner(),
        timeout_seconds=0.01,
    )

    context = builder.build(
        scene="周四下午老板临时加需求",
        domain="发疯文学",
        playbook_id="fengkuang_daily_post",
    )

    assert context is None


def test_topic_research_skips_scan_when_artifact_missing_and_not_fresh(
    monkeypatch,
    tmp_path,
) -> None:
    calls = 0

    def fake_scan(_artifact_dir: str) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(runtime_context, "_run_topic_radar_scan", fake_scan)
    builder = TopicResearchContextBuilder(artifact_dir=str(tmp_path))

    context = builder.build(
        scene="OpenAI 新多模态助手更新",
        domain="AI科技资讯",
        playbook_id="ai_tech_daily_post",
        fresh_topic_research=False,
    )

    assert context is None
    assert calls == 0
