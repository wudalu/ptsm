from __future__ import annotations

import asyncio
from datetime import timedelta
import json
from pathlib import Path
from typing import Any, Protocol, Sequence

from langchain_mcp_adapters.client import MultiServerMCPClient

from ptsm.accounts.registry import AccountProfile


class PublisherPreflightError(RuntimeError):
    """Raised when publisher preflight prevents publish execution."""

    def __init__(self, message: str, *, preflight: dict[str, Any]):
        super().__init__(message)
        self.preflight = preflight


class McpToolRunner(Protocol):
    """Async tool runner abstraction for MCP-backed publishers."""

    async def list_tool_names(self) -> list[str]:
        """List available tool names."""

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        """Invoke an MCP tool by name."""


class LangChainMcpToolRunner:
    """Thin wrapper around MultiServerMCPClient for named tool execution."""

    streamable_http_sse_read_timeout = timedelta(minutes=15)

    def __init__(self, *, server_url: str):
        self.server_url = server_url
        self._tools: dict[str, Any] | None = None

    async def list_tool_names(self) -> list[str]:
        tools = await self._load_tools()
        return sorted(tools)

    async def invoke_tool(self, tool_name: str, payload: dict[str, object]) -> object:
        tools = await self._load_tools()
        return await tools[tool_name].ainvoke(payload)

    async def _load_tools(self) -> dict[str, Any]:
        if self._tools is None:
            client = MultiServerMCPClient(
                {
                    "xiaohongshu": {
                        "transport": "http",
                        "url": self.server_url,
                        "sse_read_timeout": self.streamable_http_sse_read_timeout,
                    }
                }
            )
            tools = await client.get_tools()
            self._tools = {tool.name: tool for tool in tools}
        return self._tools


class XiaohongshuMcpPublisher:
    """Publish XiaoHongShu content through xiaohongshu-mcp."""

    platform_name = "xiaohongshu"
    provider_name = "xiaohongshu_mcp"

    def __init__(
        self,
        *,
        server_url: str,
        default_visibility: str = "仅自己可见",
        tool_runner: McpToolRunner | None = None,
    ):
        self.server_url = server_url
        self.default_visibility = default_visibility
        self.tool_runner = tool_runner or LangChainMcpToolRunner(server_url=server_url)

    def publish(
        self,
        *,
        account: AccountProfile,
        content: dict[str, Any],
        artifact_path: str,
        image_paths: Sequence[str],
        visibility: str | None,
    ) -> dict[str, Any]:
        if account.platform != self.platform_name:
            raise ValueError(
                f"Account {account.account_id} does not belong to platform {self.platform_name}"
            )

        resolved_images = self._validate_images(image_paths)
        publish_args = self._build_publish_args(
            content=content,
            image_paths=resolved_images,
            visibility=visibility or self.default_visibility,
        )
        return asyncio.run(
            self._publish_async(
                account=account,
                artifact_path=artifact_path,
                publish_args=publish_args,
            )
        )

    def preflight(self) -> dict[str, Any]:
        return asyncio.run(self._preflight_async())

    def check_publish_status(
        self,
        *,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> dict[str, Any]:
        return asyncio.run(
            self._check_publish_status_async(post_id=post_id, post_url=post_url)
        )

    async def _publish_async(
        self,
        *,
        account: AccountProfile,
        artifact_path: str,
        publish_args: dict[str, object],
    ) -> dict[str, Any]:
        preflight = await self._preflight_async(require_publish_tool=True)
        if preflight["status"] != "ready":
            raise PublisherPreflightError(
                f"xiaohongshu-mcp server at {self.server_url} is not logged in",
                preflight=preflight,
            )

        publish_response = await self.tool_runner.invoke_tool("publish_content", publish_args)
        publish_text = self._extract_text(publish_response)
        publish_metadata = self._extract_publish_metadata(publish_response)

        return {
            "status": "published",
            "platform": self.platform_name,
            "provider": self.provider_name,
            "account_id": account.account_id,
            "account_nickname": account.nickname,
            "artifact_path": artifact_path,
            "server_url": self.server_url,
            "preflight": preflight,
            "platform_payload": publish_args,
            "raw_response": publish_text,
            **publish_metadata,
        }

    async def _preflight_async(self, *, require_publish_tool: bool = False) -> dict[str, Any]:
        tool_names = await self.tool_runner.list_tool_names()
        required_tools = {"check_login_status"}
        if require_publish_tool:
            required_tools.add("publish_content")
        missing = sorted(required_tools.difference(tool_names))
        if missing:
            raise RuntimeError(f"xiaohongshu-mcp missing required tools: {missing}")

        login_status = await self.tool_runner.invoke_tool("check_login_status", {})
        login_text = self._extract_text(login_status).strip()
        preflight: dict[str, Any] = {
            "status": "ready",
            "server_url": self.server_url,
            "login_status": login_text,
            "available_tools": tool_names,
        }
        if "已登录" in login_text and "未登录" not in login_text:
            return preflight

        preflight["status"] = "login_required"
        if "get_login_qrcode" in tool_names:
            qrcode_response = await self.tool_runner.invoke_tool("get_login_qrcode", {})
            preflight["qrcode"] = self._extract_json_payload(qrcode_response)
        return preflight

    async def _check_publish_status_async(
        self,
        *,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> dict[str, Any]:
        tool_names = await self.tool_runner.list_tool_names()
        if "check_publish_status" not in tool_names:
            return {
                "status": "unsupported",
                "source": "mcp",
                "post_id": post_id,
                "post_url": post_url,
                "available_tools": tool_names,
            }

        payload: dict[str, object] = {}
        if post_id:
            payload["post_id"] = post_id
        if post_url:
            payload["post_url"] = post_url
        response = await self.tool_runner.invoke_tool("check_publish_status", payload)
        data = self._extract_json_payload(response)
        if isinstance(data, dict):
            return {
                "status": str(data.get("status", "unknown")),
                "source": "mcp",
                **data,
            }
        return {
            "status": "unknown",
            "source": "mcp",
            "post_id": post_id,
            "post_url": post_url,
            "details": data,
        }

    def _validate_images(self, image_paths: Sequence[str]) -> list[str]:
        resolved = [str(Path(path)) for path in image_paths if str(path).strip()]
        if not resolved:
            raise ValueError("At least one image path is required for xiaohongshu mcp publish")

        missing = [path for path in resolved if not Path(path).exists()]
        if missing:
            raise ValueError(f"Image paths do not exist: {missing}")
        return resolved

    def _build_publish_args(
        self,
        *,
        content: dict[str, Any],
        image_paths: list[str],
        visibility: str,
    ) -> dict[str, object]:
        hashtags = [str(tag).lstrip("#").strip() for tag in content.get("hashtags", [])]
        # Current xiaohongshu-mcp releases reject unknown fields on publish_content,
        # so keep the payload limited to the upstream tool contract.
        _ = visibility
        return {
            "title": str(content["title"]).strip(),
            "content": str(content["body"]).strip(),
            "images": image_paths,
            "tags": [tag for tag in hashtags if tag],
        }

    def _extract_text(self, payload: object) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, list):
            texts: list[str] = []
            for item in payload:
                if isinstance(item, dict) and "text" in item:
                    texts.append(str(item["text"]))
                else:
                    texts.append(json.dumps(item, ensure_ascii=False))
            return "\n".join(texts)
        return json.dumps(payload, ensure_ascii=False)

    def _extract_json_payload(self, payload: object) -> object:
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, list) and payload:
            first = payload[0]
            if isinstance(first, dict) and "text" in first:
                text = str(first["text"])
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
        try:
            return json.loads(self._extract_text(payload))
        except json.JSONDecodeError:
            return {"text": self._extract_text(payload)}

    def _extract_publish_metadata(self, payload: object) -> dict[str, object]:
        data = self._extract_json_payload(payload)
        if not isinstance(data, dict):
            return {}

        metadata: dict[str, object] = {}
        for source_key, target_key in (
            ("post_id", "post_id"),
            ("note_id", "post_id"),
            ("id", "post_id"),
            ("post_url", "post_url"),
            ("url", "post_url"),
        ):
            value = data.get(source_key)
            if isinstance(value, str) and value.strip():
                metadata[target_key] = value
        return metadata
