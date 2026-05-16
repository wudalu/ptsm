from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from topic_radar.mcp_client import McpClient, extract_text
from topic_radar.platforms.xiaohongshu import PlatformUnavailable


@dataclass
class TrendingItem:
    rank: int
    title: str
    hot_score: int = 0
    label: str = ""
    url: str = ""
    platform: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


class WeiboPlatform:
    platform_name = "weibo"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool(
                "trends_hub", "get_weibo_trending", {}
            )
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        items = _parse_trending_items(payload, platform="weibo")
        return items[:limit]


class DouyinPlatform:
    platform_name = "douyin"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool(
                "trends_hub", "get_douyin_trending", {}
            )
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        items = _parse_trending_items(payload, platform="douyin")
        return items[:limit]


class ZhihuPlatform:
    platform_name = "zhihu"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool("trends_hub", "get_zhihu_trending", {})
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc
        return _parse_trending_items(payload, platform="zhihu")[:limit]


class BilibiliPlatform:
    platform_name = "bilibili"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool("trends_hub", "get_bilibili_rank", {})
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc
        return _parse_trending_items(payload, platform="bilibili")[:limit]


class ToutiaoPlatform:
    platform_name = "toutiao"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool("trends_hub", "get_toutiao_trending", {})
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc
        return _parse_trending_items(payload, platform="toutiao")[:limit]


class DoubanPlatform:
    platform_name = "douban"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool("trends_hub", "get_douban_rank", {})
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc
        return _parse_trending_items(payload, platform="douban")[:limit]


class SspaiPlatform:
    platform_name = "sspai"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool("trends_hub", "get_sspai_rank", {})
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc
        return _parse_trending_items(payload, platform="sspai")[:limit]


def _parse_trending_items(payload: object, *, platform: str) -> list[TrendingItem]:
    text = extract_text(payload)

    # mcp-trends-hub returns XML-like format; first try JSON for other sources
    if text.startswith("{") or text.startswith("["):
        return _parse_json_items(text, platform)

    return _parse_xml_items(text, platform)


def _parse_json_items(text: str, platform: str) -> list[TrendingItem]:
    import json as _json
    try:
        data = _json.loads(text)
    except _json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return []

    candidates: list[dict] = []
    for key in ("data", "items", "list", "trending"):
        value = data.get(key)
        if isinstance(value, list):
            candidates = value
            break
    if not candidates:
        return []

    items: list[TrendingItem] = []
    for idx, item in enumerate(candidates):
        if not isinstance(item, dict):
            continue
        title = _pick_str(item, "title", "name", "topic", "keyword", "word")
        if not title:
            continue
        items.append(TrendingItem(
            rank=_to_rank(item.get("rank") or item.get("index") or item.get("position"), idx),
            title=title,
            hot_score=_pick_int(item, "hot", "hotScore", "heat", "score", "hot_value", "value"),
            label=_pick_str(item, "label", "tag", "type", "mark"),
            url=_pick_str(item, "url", "link", "share_url", "shareUrl"),
            platform=platform,
        ))
    return items


def _parse_xml_items(text: str, platform: str) -> list[TrendingItem]:
    import re
    # Parse <title>...</title>, <popularity>...</popularity>, <link>...</link> blocks
    items: list[TrendingItem] = []
    # Split by <title> to get each item
    blocks = re.split(r'\n(?=<title>)', text)
    rank = 0
    for block in blocks:
        title_m = re.search(r'<title>(.*?)</title>', block, re.DOTALL)
        if not title_m:
            continue
        title = title_m.group(1).strip()
        if not title:
            continue
        rank += 1
        pop_m = re.search(r'<popularity>(.*?)</popularity>', block)
        hot = _parse_hot_score(pop_m.group(1).strip()) if pop_m else 0
        link_m = re.search(r'<link>(.*?)</link>', block)
        url = link_m.group(1).strip() if link_m else ""
        items.append(TrendingItem(
            rank=rank, title=title, hot_score=hot,
            url=url, platform=platform,
        ))
    return items


def _parse_hot_score(raw: str) -> int:
    """Parse hot score from various Chinese formats: '862 万热度', '1174594', '1.2亿'."""
    import re as _re
    raw = raw.strip()
    if not raw:
        return 0
    # Extract numeric part
    num_match = _re.search(r'[\d.]+', raw)
    if not num_match:
        return 0
    num = float(num_match.group())
    if "亿" in raw:
        num *= 100_000_000
    elif "万" in raw:
        num *= 10_000
    return int(num)


def _to_rank(value: object, default_idx: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return default_idx + 1


def _pick_str(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _pick_int(data: dict, *keys: str) -> int:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        if isinstance(value, (float, bool)):
            return int(value)
    return 0
