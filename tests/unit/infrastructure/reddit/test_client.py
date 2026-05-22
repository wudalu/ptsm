from __future__ import annotations

from typing import Any

from ptsm.infrastructure.reddit.client import (
    RedditAccessConfig,
    RedditClient,
    RedditPublicJsonClient,
    RedditPublicJsonConfig,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeHttpClient:
    def __init__(self, listing_payload: dict[str, Any]) -> None:
        self.listing_payload = listing_payload
        self.post_calls: list[dict[str, Any]] = []
        self.get_calls: list[dict[str, Any]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.post_calls.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "access_token": "token-123",
                "token_type": "bearer",
                "expires_in": 3600,
            }
        )

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.get_calls.append({"url": url, **kwargs})
        return FakeResponse(self.listing_payload)


def test_reddit_client_fetches_oauth_listing_and_normalizes_posts() -> None:
    http_client = FakeHttpClient(
        {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "abc123",
                            "name": "t3_abc123",
                            "subreddit": "OpenAI",
                            "title": "People are using GPT agents for tiny boring tasks",
                            "selftext": "A long English discussion about ordinary workflows.",
                            "author": "english_user",
                            "score": 1530,
                            "num_comments": 244,
                            "upvote_ratio": 0.94,
                            "created_utc": 1779417600,
                            "permalink": "/r/OpenAI/comments/abc123/example/",
                            "url": "https://www.reddit.com/r/OpenAI/comments/abc123/example/",
                            "stickied": False,
                            "over_18": False,
                        },
                    },
                    {
                        "kind": "t3",
                        "data": {
                            "id": "sticky",
                            "subreddit": "OpenAI",
                            "title": "Weekly thread",
                            "stickied": True,
                            "over_18": False,
                        },
                    },
                    {
                        "kind": "t3",
                        "data": {
                            "id": "nsfw",
                            "subreddit": "OpenAI",
                            "title": "Filtered post",
                            "stickied": False,
                            "over_18": True,
                        },
                    },
                ]
            }
        }
    )
    client = RedditClient(
        config=RedditAccessConfig(
            client_id="client-id",
            client_secret="client-secret",
            user_agent="ptsm-test/0.1 by test",
        ),
        http_client=http_client,
    )

    posts = client.fetch_posts(
        subreddits=["OpenAI"],
        sorts=["top"],
        time_filter="day",
        limit_per_listing=10,
    )

    assert len(posts) == 1
    post = posts[0]
    assert post.post_id == "abc123"
    assert post.subreddit == "OpenAI"
    assert post.title == "People are using GPT agents for tiny boring tasks"
    assert post.author == "english_user"
    assert post.score == 1530
    assert post.num_comments == 244
    assert post.source_url == "https://www.reddit.com/r/OpenAI/comments/abc123/example/"
    assert post.sort == "top"
    assert post.engagement_score == 2506

    assert http_client.post_calls[0]["url"] == "https://www.reddit.com/api/v1/access_token"
    assert http_client.post_calls[0]["data"] == {"grant_type": "client_credentials"}
    assert http_client.post_calls[0]["auth"] == ("client-id", "client-secret")
    assert http_client.get_calls[0]["url"] == "https://oauth.reddit.com/r/OpenAI/top"
    assert http_client.get_calls[0]["params"]["t"] == "day"
    assert http_client.get_calls[0]["params"]["raw_json"] == 1
    assert http_client.get_calls[0]["headers"]["Authorization"] == "Bearer token-123"
    assert http_client.get_calls[0]["headers"]["User-Agent"] == "ptsm-test/0.1 by test"


def test_reddit_public_json_client_fetches_listing_without_oauth_token() -> None:
    http_client = FakeHttpClient(
        {
            "data": {
                "children": [
                    {
                        "kind": "t3",
                        "data": {
                            "id": "pub123",
                            "subreddit": "ChatGPT",
                            "title": "AI workflows are changing office routines",
                            "selftext": "People compare productivity pressure and tool anxiety.",
                            "author": "public_user",
                            "score": 880,
                            "num_comments": 120,
                            "upvote_ratio": 0.91,
                            "created_utc": 1779417700,
                            "permalink": "/r/ChatGPT/comments/pub123/example/",
                            "stickied": False,
                            "over_18": False,
                        },
                    },
                ]
            }
        }
    )
    client = RedditPublicJsonClient(
        config=RedditPublicJsonConfig(
            user_agent="ptsm-test/0.1 (by /u/test)",
        ),
        http_client=http_client,
    )

    posts = client.fetch_posts(
        subreddits=["ChatGPT"],
        sorts=["hot"],
        time_filter="week",
        limit_per_listing=5,
    )

    assert [post.post_id for post in posts] == ["pub123"]
    assert posts[0].source_url == "https://www.reddit.com/r/ChatGPT/comments/pub123/example/"
    assert http_client.post_calls == []
    assert http_client.get_calls[0]["url"] == "https://www.reddit.com/r/ChatGPT/hot.json"
    assert http_client.get_calls[0]["params"] == {"limit": 5, "raw_json": 1}
    assert http_client.get_calls[0]["headers"]["User-Agent"] == "ptsm-test/0.1 (by /u/test)"
