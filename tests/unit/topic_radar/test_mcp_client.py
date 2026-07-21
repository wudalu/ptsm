from __future__ import annotations

import asyncio

import pytest

from topic_radar import mcp_client
from topic_radar.mcp_client import (
    McpClient,
    ServerHealth,
    _clean_error,
    _guess_server,
    extract_text,
    extract_json_payload,
)


class TestGuessServer:
    def test_xiaohongshu_tools(self):
        xhs_tools = [
            "check_login_status", "search_feeds", "list_feeds",
            "get_feed_detail", "publish_content",
        ]
        for tool in xhs_tools:
            assert _guess_server(tool) == "xiaohongshu"

    def test_unknown_tool_defaults_to_trends_hub(self):
        assert _guess_server("get_weibo_trending") == "trends_hub"
        assert _guess_server("get_douyin_trending") == "trends_hub"
        assert _guess_server("get_zhihu_trending") == "trends_hub"


class TestExtractText:
    def test_plain_string(self):
        assert extract_text("hello") == "hello"

    def test_list_of_text_blocks(self):
        payload = [{"text": "hello"}, {"text": "world"}]
        assert extract_text(payload) == "hello\nworld"

    def test_empty_payload(self):
        assert extract_text("") == ""


class TestExtractJsonPayload:
    def test_dict_passthrough(self):
        data = {"key": "value"}
        assert extract_json_payload(data) == {"key": "value"}

    def test_text_block_with_json(self):
        payload = [{"text": '{"feeds": [1, 2, 3]}'}]
        result = extract_json_payload(payload)
        assert result == {"feeds": [1, 2, 3]}

    def test_non_json_text(self):
        payload = [{"text": "plain text"}]
        result = extract_json_payload(payload)
        assert result == {"text": "plain text"}


class TestServerHealth:
    def test_reachable_server(self):
        health = ServerHealth(
            name="xiaohongshu",
            reachable=True,
            tool_count=13,
            tool_names=["check_login_status", "search_feeds"],
        )
        assert health.reachable is True
        assert health.tool_count == 13

    def test_unreachable_server(self):
        health = ServerHealth(
            name="trends_hub",
            reachable=False,
            error="connection refused",
        )
        assert health.reachable is False
        assert health.error == "connection refused"
        assert health.tool_count == 0


def test_clean_error_surfaces_nested_http_500_from_exception_group() -> None:
    exc = ExceptionGroup(
        "unhandled errors in a TaskGroup",
        [RuntimeError("HTTPStatusError: 500 Internal Server Error")],
    )

    message = _clean_error(exc)

    assert "500" in message
    assert "internal error" in message


def test_mcp_health_uses_single_server_context_when_a_tool_has_no_server_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ToolWithoutServerName:
        name = "new_xhs_tool"

    class SingleServerClient:
        async def get_tools(self) -> list[object]:
            return [ToolWithoutServerName()]

        async def close(self) -> None:
            return None

    monkeypatch.setattr(
        mcp_client,
        "_make_single_client",
        lambda _name, _xhs_url: SingleServerClient(),
    )

    health = asyncio.run(McpClient().health())

    assert health["xiaohongshu"].reachable is True
    assert health["xiaohongshu"].tool_names == ["new_xhs_tool"]


@pytest.mark.parametrize(
    ("unavailable_server", "healthy_server", "healthy_tool"),
    [
        ("xiaohongshu", "trends_hub", "get_weibo_trending"),
        ("trends_hub", "xiaohongshu", "check_login_status"),
    ],
)
def test_mcp_client_isolates_tool_loading_by_server(
    monkeypatch: pytest.MonkeyPatch,
    unavailable_server: str,
    healthy_server: str,
    healthy_tool: str,
) -> None:
    """A broken server must not poison the healthy server's tool cache."""

    class FakeTool:
        def __init__(self, server_name: str, name: str) -> None:
            self.server_name = server_name
            self.name = name

        async def arun(self, payload: dict[str, object], *, tool_call_id: str) -> str:
            return f"{self.server_name}:{self.name}"

    class FailingServerClient:
        async def get_tools(self) -> list[object]:
            raise RuntimeError(f"{unavailable_server} unavailable")

        async def close(self) -> None:
            return None

    class HealthyServerClient:
        async def get_tools(self) -> list[object]:
            return [FakeTool(healthy_server, healthy_tool)]

        async def close(self) -> None:
            return None

    class CombinedClient:
        async def get_tools(self) -> list[object]:
            raise RuntimeError("combined MCP loading failed")

    def fake_single_client(name: str, _xhs_url: str) -> object:
        if name == unavailable_server:
            return FailingServerClient()
        return HealthyServerClient()

    monkeypatch.setattr(mcp_client, "_make_single_client", fake_single_client)
    monkeypatch.setattr(
        mcp_client,
        "MultiServerMCPClient",
        lambda _servers: CombinedClient(),
    )

    async def scenario() -> None:
        client = McpClient(enable_trends_hub=True)
        unavailable_tool = (
            "check_login_status"
            if unavailable_server == "xiaohongshu"
            else "get_weibo_trending"
        )
        with pytest.raises(RuntimeError, match="unavailable"):
            await client.invoke_tool(unavailable_server, unavailable_tool, {})

        payload = await client.invoke_tool(healthy_server, healthy_tool, {})

        assert payload == f"{healthy_server}:{healthy_tool}"

    asyncio.run(scenario())


def test_mcp_client_times_out_hanging_tool_discovery_and_keeps_healthy_server(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tool discovery has the same bounded isolation guarantee as arun()."""

    class FakeTool:
        server_name = "trends_hub"
        name = "get_weibo_trending"

        async def arun(self, payload: dict[str, object], *, tool_call_id: str) -> str:
            return "healthy"

    class HangingServerClient:
        async def get_tools(self) -> list[object]:
            await asyncio.Event().wait()
            return []

        async def close(self) -> None:
            return None

    class HealthyServerClient:
        async def get_tools(self) -> list[object]:
            return [FakeTool()]

        async def close(self) -> None:
            return None

    def fake_single_client(name: str, _xhs_url: str) -> object:
        return HangingServerClient() if name == "xiaohongshu" else HealthyServerClient()

    monkeypatch.setattr(mcp_client, "_make_single_client", fake_single_client)

    async def scenario() -> None:
        client = McpClient(enable_trends_hub=True)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                client.invoke_tool("xiaohongshu", "check_login_status", {}, timeout=0.01),
                timeout=0.1,
            )

        assert isinstance(client._server_errors["xiaohongshu"], asyncio.TimeoutError)
        assert await client.invoke_tool(
            "trends_hub", "get_weibo_trending", {}, timeout=0.1
        ) == "healthy"

    asyncio.run(scenario())
