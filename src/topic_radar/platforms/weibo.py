from __future__ import annotations

from dataclasses import dataclass

from topic_radar.mcp_client import McpClient, extract_json_payload
from topic_radar.platforms.xiaohongshu import PlatformUnavailable


@dataclass
class TrendingItem:
    rank: int
    title: str
    hot_score: int = 0
    label: str = ""
    url: str = ""
    platform: str = ""


class WeiboPlatform:
    platform_name = "weibo"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def get_trending(self, limit: int = 30) -> list[TrendingItem]:
        try:
            payload = await self._client.invoke_tool(
                "trends_hub", "get-weibo-trending", {}
            )
        except (KeyError, ConnectionError, OSError) as exc:
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
                "trends_hub", "get-douyin-trending", {}
            )
        except (KeyError, ConnectionError, OSError) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        items = _parse_trending_items(payload, platform="douyin")
        return items[:limit]


def _parse_trending_items(payload: object, *, platform: str) -> list[TrendingItem]:
    data = extract_json_payload(payload)
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
        rank = _to_rank(item.get("rank") or item.get("index") or item.get("position"), idx)
        hot_score = _pick_int(item, "hot", "hotScore", "heat", "score", "hot_value", "value")
        label = _pick_str(item, "label", "tag", "type", "mark")
        url = _pick_str(item, "url", "link", "share_url", "shareUrl")

        items.append(TrendingItem(
            rank=rank,
            title=title,
            hot_score=hot_score,
            label=label,
            url=url,
            platform=platform,
        ))
    return items


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
