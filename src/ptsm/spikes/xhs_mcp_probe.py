from __future__ import annotations

import argparse
import asyncio
from datetime import timedelta
import json
from typing import Any, Sequence

from langchain_mcp_adapters.client import MultiServerMCPClient


def build_server_config(server_url: str) -> dict[str, dict[str, object]]:
    """Build the minimal HTTP MCP client config for xiaohongshu-mcp."""
    return {
        "xiaohongshu": {
            "transport": "http",
            "url": server_url,
            "sse_read_timeout": timedelta(minutes=15),
        }
    }


def build_publish_content_args(
    *, final_content: dict[str, Any], image_paths: list[str]
) -> dict[str, Any]:
    """Map local final_content into xiaohongshu-mcp publish_content args."""
    hashtags = [str(tag).lstrip("#").strip() for tag in final_content.get("hashtags", [])]
    return {
        "title": str(final_content["title"]).strip(),
        "content": str(final_content["body"]).strip(),
        "images": image_paths,
        "tags": [tag for tag in hashtags if tag],
    }


async def run_probe(
    *,
    server_url: str,
    keyword: str | None = None,
    publish_args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Probe status/search/publish tools from a running xiaohongshu-mcp server."""
    client = MultiServerMCPClient(build_server_config(server_url))
    tools = await client.get_tools()

    by_name = {tool.name: tool for tool in tools}
    result: dict[str, Any] = {"server_url": server_url, "tools": sorted(by_name)}

    status_tool = by_name["check_login_status"]
    result["check_login_status"] = await status_tool.ainvoke({})

    if keyword:
        search_tool = by_name["search_feeds"]
        result["search_feeds"] = await search_tool.ainvoke({"keyword": keyword})

    if publish_args:
        publish_tool = by_name["publish_content"]
        result["publish_content"] = await publish_tool.ainvoke(publish_args)

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xhs-mcp-probe")
    parser.add_argument(
        "--server-url",
        default="http://localhost:18060/mcp",
    )
    parser.add_argument("--keyword")
    parser.add_argument("--publish-json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    publish_args = json.loads(args.publish_json) if args.publish_json else None
    result = asyncio.run(
        run_probe(
            server_url=args.server_url,
            keyword=args.keyword,
            publish_args=publish_args,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
