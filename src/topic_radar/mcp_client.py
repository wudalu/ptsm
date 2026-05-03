from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient


@dataclass
class ServerHealth:
    name: str
    reachable: bool
    tool_count: int = 0
    tool_names: list[str] = field(default_factory=list)
    error: str | None = None


class McpClient:
    """Multi-server MCP client supporting HTTP and stdio transports."""

    streamable_http_sse_read_timeout = timedelta(minutes=15)

    def __init__(
        self,
        xhs_server_url: str = "http://localhost:18060/mcp",
        enable_trends_hub: bool = True,
    ) -> None:
        servers: dict[str, dict[str, Any]] = {
            "xiaohongshu": {
                "transport": "http",
                "url": xhs_server_url,
                "sse_read_timeout": self.streamable_http_sse_read_timeout,
            }
        }
        if enable_trends_hub:
            servers["trends_hub"] = {
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "mcp-trends-hub"],
            }

        self._client = MultiServerMCPClient(servers)
        self._tools: dict[str, dict[str, Any]] | None = None

    async def get_tools(self) -> dict[str, dict[str, Any]]:
        if self._tools is None:
            raw = await self._client.get_tools()
            self._tools = {}
            for tool in raw:
                server = getattr(tool, "server_name", None) or _guess_server(tool.name)
                self._tools.setdefault(server, {})[tool.name] = tool
        return self._tools

    async def health(self) -> dict[str, ServerHealth]:
        result: dict[str, ServerHealth] = {}
        try:
            tools = await self.get_tools()
        except Exception as exc:
            for server_name in _infer_server_names(self._client):
                result[server_name] = ServerHealth(
                    name=server_name,
                    reachable=False,
                    error=str(exc),
                )
            return result

        for server_name in _infer_server_names(self._client):
            server_tools = tools.get(server_name, {})
            result[server_name] = ServerHealth(
                name=server_name,
                reachable=len(server_tools) > 0,
                tool_count=len(server_tools),
                tool_names=sorted(server_tools),
            )
        return result

    async def invoke_tool(
        self, server: str, tool_name: str, payload: dict[str, object]
    ) -> object:
        tools = await self.get_tools()
        server_tools = tools.get(server, {})
        if tool_name not in server_tools:
            raise KeyError(f"Tool '{tool_name}' not found on server '{server}'")
        return await server_tools[tool_name].arun(payload, tool_call_id=f"topic_radar:{tool_name}")

    async def list_tools(self, server: str) -> list[str]:
        tools = await self.get_tools()
        return sorted(tools.get(server, {}))


def _infer_server_names(client: MultiServerMCPClient) -> list[str]:
    connections = getattr(client, "_connections", {}) or getattr(client, "connections", {})
    if isinstance(connections, dict):
        return list(connections)
    return ["xiaohongshu", "trends_hub"]


def _guess_server(tool_name: str) -> str:
    if tool_name in (
        "check_login_status", "search_feeds", "list_feeds", "get_feed_detail",
        "publish_content", "like_feed", "favorite_feed",
        "post_comment_to_feed", "reply_comment_in_feed",
        "get_login_qrcode", "delete_cookies", "user_profile",
        "publish_with_video",
    ):
        return "xiaohongshu"
    return "trends_hub"


def extract_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if hasattr(payload, "content") and not isinstance(payload, (str, list, dict)):
        return extract_text(getattr(payload, "content"))
    if isinstance(payload, list):
        texts: list[str] = []
        for item in payload:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(texts)
    if isinstance(payload, tuple) and payload:
        return extract_text(payload[0])
    return json.dumps(payload, ensure_ascii=False)


def extract_json_payload(payload: object) -> object:
    if hasattr(payload, "content") and not isinstance(payload, (str, list, dict)):
        return extract_json_payload(getattr(payload, "content"))
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict) and "text" in first:
            try:
                return json.loads(str(first["text"]))
            except json.JSONDecodeError:
                return {"text": str(first["text"])}
    if isinstance(payload, tuple) and payload:
        return extract_json_payload(payload[0])
    try:
        return json.loads(extract_text(payload))
    except json.JSONDecodeError:
        return {"text": extract_text(payload)}
