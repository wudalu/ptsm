from __future__ import annotations

import asyncio
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
    """MCP client that isolates HTTP and stdio servers during bounded discovery."""

    streamable_http_sse_read_timeout = timedelta(minutes=15)
    tool_discovery_timeout = 20.0

    def __init__(
        self,
        xhs_server_url: str = "http://localhost:18060/mcp",
        enable_trends_hub: bool = False,
    ) -> None:
        self._xhs_url = xhs_server_url
        self._enable_trends_hub = enable_trends_hub
        self._tools: dict[str, dict[str, Any]] = {}
        self._loaded_servers: set[str] = set()
        self._server_errors: dict[str, Exception] = {}
        self._clients: dict[str, MultiServerMCPClient] = {}

    async def get_tools(
        self,
        server: str | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Load tools per server so one broken MCP cannot poison another."""
        if server is not None:
            await self._load_server_tools(server, timeout=timeout)
            return self._tools

        for server_name in self._server_names():
            try:
                await self._load_server_tools(server_name, timeout=timeout)
            except Exception:
                # Callers asking for the aggregate can still use healthy
                # servers; server-specific calls retain the original error.
                continue
        return self._tools

    async def _load_server_tools(self, server: str, *, timeout: float | None = None) -> None:
        if server not in self._server_names():
            return
        if server in self._server_errors:
            raise self._server_errors[server]
        if server in self._loaded_servers:
            return

        client = _make_single_client(server, self._xhs_url)
        try:
            discovery_timeout = (
                self.tool_discovery_timeout if timeout is None else timeout
            )
            raw = await asyncio.wait_for(client.get_tools(), timeout=discovery_timeout)
        except Exception as exc:
            self._server_errors[server] = exc
            await _close_safely(client)
            raise

        self._clients[server] = client
        self._loaded_servers.add(server)
        for tool in raw:
            tool_server = getattr(tool, "server_name", None) or server
            self._tools.setdefault(tool_server, {})[tool.name] = tool

    async def health(self) -> dict[str, ServerHealth]:
        result: dict[str, ServerHealth] = {}
        server_names = self._server_names()

        for name in server_names:
            client: MultiServerMCPClient | None = None
            try:
                client = _make_single_client(name, self._xhs_url)
                raw = await asyncio.wait_for(
                    client.get_tools(),
                    timeout=self.tool_discovery_timeout,
                )
                tools = {}
                for tool in raw:
                    srv = getattr(tool, "server_name", None) or name
                    tools.setdefault(srv, {})[tool.name] = tool
                server_tools = tools.get(name, {})
                result[name] = ServerHealth(
                    name=name,
                    reachable=len(server_tools) > 0,
                    tool_count=len(server_tools),
                    tool_names=sorted(server_tools),
                )
            except Exception as exc:
                result[name] = ServerHealth(
                    name=name,
                    reachable=False,
                    error=_clean_error(exc),
                )
            finally:
                await _close_safely(client)
        return result

    async def invoke_tool(
        self, server: str, tool_name: str, payload: dict[str, object],
        timeout: float = 20.0,
    ) -> object:
        tools = await self.get_tools(server, timeout=timeout)
        server_tools = tools.get(server, {})
        if tool_name not in server_tools:
            raise KeyError(f"Tool '{tool_name}' not found on server '{server}'")
        return await asyncio.wait_for(
            server_tools[tool_name].arun(payload, tool_call_id=f"topic_radar:{tool_name}"),
            timeout=timeout,
        )

    async def list_tools(self, server: str) -> list[str]:
        tools = await self.get_tools(server)
        return sorted(tools.get(server, {}))

    def _server_names(self) -> list[str]:
        return ["xiaohongshu"] + (["trends_hub"] if self._enable_trends_hub else [])

def _make_single_client(name: str, xhs_url: str) -> MultiServerMCPClient:
    if name == "xiaohongshu":
        servers = {"xiaohongshu": {
            "transport": "http",
            "url": xhs_url,
            "sse_read_timeout": McpClient.streamable_http_sse_read_timeout,
        }}
    else:
        servers = {"trends_hub": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-trends-hub"],
        }}
    return MultiServerMCPClient(servers)


async def _close_safely(client: MultiServerMCPClient | None) -> None:
    try:
        if hasattr(client, "close"):
            await client.close()
    except Exception:
        pass


def _clean_error(exc: BaseException) -> str:
    msg = str(exc)
    if isinstance(exc, asyncio.TimeoutError) or "Timeout" in type(exc).__name__:
        return "timeout (MCP server may not be logged in or browser not ready)"
    if "unhandled errors in a TaskGroup" in msg:
        parts: list[str] = []
        if hasattr(exc, "exceptions"):
            for sub in exc.exceptions:  # type: ignore[attr-defined]
                sub_msg = str(sub).strip()
                if sub_msg:
                    parts.append(sub_msg)
        if parts:
            detail = "; ".join(parts[:2])
            if "500" in detail:
                return "MCP server internal error (500) — browser session may not be ready, try restarting the MCP server"
            return detail
        return "MCP connection failed — check if server is healthy"
    if "cannot access local variable" in msg:
        return "connection failed (MCP server unreachable)"
    return msg.split("\n")[0][:120]


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
