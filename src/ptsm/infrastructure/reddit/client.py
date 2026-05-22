from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


REDDIT_OAUTH_BASE_URL = "https://oauth.reddit.com"
REDDIT_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
REDDIT_WEB_BASE_URL = "https://www.reddit.com"
_SORTS_WITH_TIME_FILTER = {"top", "controversial"}
_SUPPORTED_SORTS = {"hot", "new", "top", "rising", "controversial"}


@dataclass(frozen=True)
class RedditAccessConfig:
    """Read-only Reddit app credentials for OAuth client credentials flow."""

    client_id: str
    client_secret: str
    user_agent: str
    oauth_base_url: str = REDDIT_OAUTH_BASE_URL
    token_url: str = REDDIT_TOKEN_URL
    timeout_seconds: float = 10.0


@dataclass(frozen=True)
class RedditDiscussion:
    """Normalized Reddit post fields useful for source-aware content drafting."""

    post_id: str
    subreddit: str
    title: str
    selftext: str
    author: str
    score: int
    num_comments: int
    upvote_ratio: float
    created_utc: float
    source_url: str
    sort: str

    @property
    def engagement_score(self) -> int:
        return self.score + (self.num_comments * 4)


class RedditClient:
    """Small read-only Reddit API client using application-only OAuth."""

    def __init__(
        self,
        *,
        config: RedditAccessConfig,
        http_client: Any | None = None,
    ) -> None:
        self.config = config
        self._http_client = http_client or httpx.Client()
        self._access_token: str | None = None

    def fetch_posts(
        self,
        *,
        subreddits: list[str],
        sorts: list[str],
        time_filter: str,
        limit_per_listing: int,
    ) -> list[RedditDiscussion]:
        token = self._get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": self.config.user_agent,
        }
        posts: list[RedditDiscussion] = []
        seen: set[str] = set()
        for subreddit in _clean_subreddits(subreddits):
            for sort in _clean_sorts(sorts):
                params: dict[str, object] = {
                    "limit": min(max(int(limit_per_listing), 1), 100),
                    "raw_json": 1,
                }
                if sort in _SORTS_WITH_TIME_FILTER:
                    params["t"] = time_filter
                url = f"{self.config.oauth_base_url.rstrip('/')}/r/{subreddit}/{sort}"
                response = self._http_client.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.config.timeout_seconds,
                )
                response.raise_for_status()
                for post in _parse_listing_payload(response.json(), sort=sort):
                    if post.post_id in seen:
                        continue
                    seen.add(post.post_id)
                    posts.append(post)
        return posts

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        response = self._http_client.post(
            self.config.token_url,
            data={"grant_type": "client_credentials"},
            auth=(self.config.client_id, self.config.client_secret),
            headers={"User-Agent": self.config.user_agent},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("Reddit access_token missing from OAuth response")
        self._access_token = token
        return token


def _parse_listing_payload(payload: dict[str, Any], *, sort: str) -> list[RedditDiscussion]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    children = data.get("children")
    if not isinstance(children, list):
        return []

    posts: list[RedditDiscussion] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        if child.get("kind") != "t3":
            continue
        item = child.get("data")
        if not isinstance(item, dict):
            continue
        if bool(item.get("stickied")) or bool(item.get("over_18")):
            continue
        post_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        subreddit = str(item.get("subreddit") or "").strip()
        if not post_id or not title or not subreddit:
            continue
        posts.append(
            RedditDiscussion(
                post_id=post_id,
                subreddit=subreddit,
                title=title,
                selftext=str(item.get("selftext") or "").strip(),
                author=str(item.get("author") or "").strip(),
                score=_to_int(item.get("score")),
                num_comments=_to_int(item.get("num_comments")),
                upvote_ratio=_to_float(item.get("upvote_ratio")),
                created_utc=_to_float(item.get("created_utc")),
                source_url=_source_url(item),
                sort=sort,
            )
        )
    return posts


def _source_url(item: dict[str, Any]) -> str:
    permalink = str(item.get("permalink") or "").strip()
    if permalink:
        if permalink.startswith("http://") or permalink.startswith("https://"):
            return permalink
        return f"{REDDIT_WEB_BASE_URL}{permalink}"
    return str(item.get("url") or "").strip()


def _clean_subreddits(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        subreddit = value.strip().removeprefix("r/").removeprefix("/r/")
        if not subreddit or subreddit in seen:
            continue
        seen.add(subreddit)
        cleaned.append(subreddit)
    return cleaned


def _clean_sorts(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        sort = value.strip().lower()
        if not sort or sort in seen:
            continue
        if sort not in _SUPPORTED_SORTS:
            raise ValueError(f"Unsupported Reddit sort: {sort}")
        seen.add(sort)
        cleaned.append(sort)
    return cleaned or ["hot"]


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _to_float(value: object) -> float:
    try:
        return float(str(value).strip() or "0")
    except (TypeError, ValueError):
        return 0.0
