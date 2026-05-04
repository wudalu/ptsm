from __future__ import annotations

import pytest

from topic_radar.mcp_client import (
    ServerHealth,
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
