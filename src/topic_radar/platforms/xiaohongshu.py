from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from topic_radar.mcp_client import McpClient, extract_text, extract_json_payload


@dataclass
class FeedItem:
    feed_id: str | None
    title: str
    author: str
    likes: int = 0
    comments: int = 0
    shares: int = 0
    collects: int = 0
    xsec_token: str | None = None
    cover_width: int | None = None
    cover_height: int | None = None
    has_cover_url: bool = False
    raw: dict | None = None

    @property
    def engagement_score(self) -> int:
        return self.likes + (self.comments * 4) + (self.shares * 6) + (self.collects * 2)


@dataclass
class FeedDetail:
    feed_id: str
    title: str
    body: str
    author: str
    likes: int = 0
    comments_count: int = 0
    comments: list[Comment] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    url: str = ""


@dataclass
class Comment:
    author: str
    content: str
    likes: int = 0
    replies_count: int = 0

    @property
    def is_question(self) -> bool:
        return "？" in self.content or "?" in self.content or "吗" in self.content


class PlatformUnavailable(Exception):
    def __init__(self, platform: str, reason: str):
        if not reason.strip():
            reason = "connection timeout (not logged in or server unreachable)"
        super().__init__(f"{platform} unavailable: {reason}")
        self.platform = platform
        self.reason = reason


class XiaohongshuPlatform:
    platform_name = "xiaohongshu"

    def __init__(self, client: McpClient) -> None:
        self._client = client

    async def check_login(self) -> tuple[bool, str | None]:
        """Return (is_logged_in, qr_code_data_or_none)."""
        try:
            payload = await self._client.invoke_tool(
                "xiaohongshu", "check_login_status", {}
            )
        except (KeyError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        text = extract_text(payload)
        if "已登录" in text:
            return True, None

        # Try get QR code
        qr_data: str | None = None
        try:
            qr_payload = await self._client.invoke_tool(
                "xiaohongshu", "get_login_qrcode", {}
            )
            qr_data = extract_text(qr_payload)
        except Exception:
            pass
        return False, qr_data

    async def search_feeds(self, keyword: str, limit: int = 20) -> list[FeedItem]:
        try:
            payload = await self._client.invoke_tool(
                "xiaohongshu", "search_feeds", {"keyword": keyword}
            )
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        data = extract_json_payload(payload)
        if not isinstance(data, dict):
            return []

        feeds = data.get("feeds")
        if not isinstance(feeds, list):
            return []

        items: list[FeedItem] = []
        for item in feeds[:limit]:
            if not isinstance(item, dict):
                continue
            note = item.get("noteCard")
            if not isinstance(note, dict):
                continue
            title = str(note.get("displayTitle", "")).strip()
            if not title:
                continue
            user = note.get("user")
            interact = note.get("interactInfo")
            feed_id = _find_first_string(item, "id")
            xsec_token = _find_first_string(item, "xsecToken", "xsec_token")
            cover = _extract_cover_metadata(item)

            items.append(
                FeedItem(
                    feed_id=feed_id,
                    title=title,
                    author=str(user.get("nickname", "")).strip() if isinstance(user, dict) else "",
                    likes=_to_int(interact.get("likedCount")) if isinstance(interact, dict) else 0,
                    comments=_to_int(interact.get("commentCount")) if isinstance(interact, dict) else 0,
                    shares=_to_int(interact.get("sharedCount")) if isinstance(interact, dict) else 0,
                    collects=_to_int(interact.get("collectedCount")) if isinstance(interact, dict) else 0,
                    xsec_token=xsec_token,
                    cover_width=cover["cover_width"],
                    cover_height=cover["cover_height"],
                    has_cover_url=cover["has_cover_url"],
                    raw=item,
                )
            )
        return items

    async def get_feed_detail(
        self, feed_id: str, xsec_token: str, timeout: float = 20.0
    ) -> FeedDetail | None:
        try:
            payload = await self._client.invoke_tool(
                "xiaohongshu", "get_feed_detail",
                {"feed_id": feed_id, "xsec_token": xsec_token},
                timeout=timeout,
            )
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        data = extract_json_payload(payload)
        if not isinstance(data, dict):
            return None

        nested_data = data.get("data")
        if not isinstance(nested_data, dict):
            nested_data = {}
        note = data.get("note") or nested_data.get("note") or data
        if not isinstance(note, dict):
            return None

        title = str(note.get("displayTitle") or note.get("title", "")).strip()
        if not title:
            return None

        desc = str(note.get("desc") or note.get("description") or note.get("content", ""))
        user = note.get("user", {})
        interact = note.get("interactInfo") or note.get("interaction", {})
        if isinstance(interact, dict):
            likes = _to_int(interact.get("likedCount") or interact.get("likes"))
            comment_count = _to_int(interact.get("commentCount") or interact.get("comments"))
        else:
            likes = 0
            comment_count = 0

        tags = _normalize_tags(note.get("tagList") or note.get("tags") or [])

        comments: list[Comment] = []
        raw_comments = data.get("comments") or nested_data.get("comments") or note.get("comments") or []
        if isinstance(raw_comments, dict):
            raw_comments = raw_comments.get("list") or raw_comments.get("comments") or []
        if isinstance(raw_comments, list):
            for c in raw_comments:
                if isinstance(c, dict):
                    content = str(c.get("content") or c.get("text", ""))
                    if content.strip():
                        comments.append(
                            Comment(
                                author=str(c.get("userName") or c.get("author", "")),
                                content=content,
                                likes=_to_int(c.get("likeCount") or c.get("likes")),
                                replies_count=_to_int(c.get("subCommentCount") or c.get("replies")),
                            )
                        )

        return FeedDetail(
            feed_id=str(note.get("noteId") or note.get("note_id") or feed_id),
            title=title,
            body=desc,
            author=str(user.get("nickname", "")).strip() if isinstance(user, dict) else "",
            likes=likes,
            comments_count=comment_count,
            comments=comments,
            tags=tags,
            url=f"https://www.xiaohongshu.com/explore/{feed_id}",
        )

    async def list_feeds(self, limit: int = 20) -> list[FeedItem]:
        try:
            payload = await self._client.invoke_tool(
                "xiaohongshu", "list_feeds", {}
            )
        except (KeyError, ConnectionError, OSError, asyncio.TimeoutError, ExceptionGroup) as exc:
            raise PlatformUnavailable(self.platform_name, str(exc)) from exc

        data = extract_json_payload(payload)
        if not isinstance(data, dict):
            return []

        feeds = data.get("feeds")
        if not isinstance(feeds, list):
            return []

        items: list[FeedItem] = []
        for item in feeds[:limit]:
            if not isinstance(item, dict):
                continue
            note = item.get("noteCard") or item
            if not isinstance(note, dict):
                continue
            title = str(note.get("displayTitle", "")).strip()
            if not title:
                continue
            user = note.get("user")
            interact = note.get("interactInfo")
            feed_id = _find_first_string(item, "id")
            xsec_token = _find_first_string(item, "xsecToken", "xsec_token")
            cover = _extract_cover_metadata(item)

            items.append(
                FeedItem(
                    feed_id=feed_id,
                    title=title,
                    author=str(user.get("nickname", "")).strip() if isinstance(user, dict) else "",
                    likes=_to_int(interact.get("likedCount")) if isinstance(interact, dict) else 0,
                    comments=_to_int(interact.get("commentCount")) if isinstance(interact, dict) else 0,
                    shares=_to_int(interact.get("sharedCount")) if isinstance(interact, dict) else 0,
                    collects=_to_int(interact.get("collectedCount")) if isinstance(interact, dict) else 0,
                    xsec_token=xsec_token,
                    cover_width=cover["cover_width"],
                    cover_height=cover["cover_height"],
                    has_cover_url=cover["has_cover_url"],
                    raw=item,
                )
            )
        return items


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _find_first_string(payload: object, *keys: str) -> str | None:
    if isinstance(payload, dict):
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        for value in payload.values():
            found = _find_first_string(value, *keys)
            if found is not None:
                return found
        return None
    if isinstance(payload, list):
        for item in payload:
            found = _find_first_string(item, *keys)
            if found is not None:
                return found
    return None


def _normalize_tags(raw_tags: object) -> list[str]:
    if not isinstance(raw_tags, list):
        return []
    tags: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, dict):
            value = tag.get("name") or tag.get("tagName") or tag.get("title")
        else:
            value = tag
        text = str(value or "").strip().strip("#")
        if text:
            tags.append(text)
    return tags


def _extract_cover_metadata(item: dict) -> dict[str, object]:
    note = item.get("noteCard") if isinstance(item.get("noteCard"), dict) else item
    cover: object = None
    if isinstance(note, dict):
        cover = note.get("cover") or note.get("coverInfo")
        if cover is None:
            image_list = note.get("imageList") or note.get("images")
            if isinstance(image_list, list) and image_list:
                cover = image_list[0]
    width = None
    height = None
    has_url = False
    if isinstance(cover, dict):
        width = _to_optional_int(
            cover.get("width")
            or cover.get("w")
            or cover.get("imageWidth")
            or cover.get("originalWidth")
        )
        height = _to_optional_int(
            cover.get("height")
            or cover.get("h")
            or cover.get("imageHeight")
            or cover.get("originalHeight")
        )
        has_url = _contains_cover_url(cover)
    return {
        "cover_width": width,
        "cover_height": height,
        "has_cover_url": has_url,
    }


def _contains_cover_url(payload: object) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if "url" in str(key).lower() and isinstance(value, str) and value.strip():
                return True
            if _contains_cover_url(value):
                return True
    if isinstance(payload, list):
        return any(_contains_cover_url(item) for item in payload)
    return False


def _to_optional_int(value: object) -> int | None:
    parsed = _to_int(value)
    return parsed if parsed > 0 else None
