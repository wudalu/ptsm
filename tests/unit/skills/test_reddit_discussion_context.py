from __future__ import annotations

from ptsm.config.settings import Settings
from ptsm.infrastructure.reddit.client import RedditDiscussion
from ptsm.skills.runtime_context import RedditDiscussionContextBuilder


class FakeRedditProvider:
    def __init__(self, posts: list[RedditDiscussion]) -> None:
        self.posts = posts
        self.calls: list[dict[str, object]] = []

    def fetch_posts(
        self,
        *,
        subreddits: list[str],
        sorts: list[str],
        time_filter: str,
        limit_per_listing: int,
    ) -> list[RedditDiscussion]:
        self.calls.append(
            {
                "subreddits": subreddits,
                "sorts": sorts,
                "time_filter": time_filter,
                "limit_per_listing": limit_per_listing,
            }
        )
        return self.posts


def test_reddit_discussion_context_renders_ranked_ai_and_psychology_sources() -> None:
    provider = FakeRedditProvider(
        [
            RedditDiscussion(
                post_id="low",
                subreddit="AskReddit",
                title="What is your favorite sandwich?",
                selftext="A light thread with little translation value.",
                author="user_a",
                score=4000,
                num_comments=100,
                upvote_ratio=0.9,
                created_utc=1779417600,
                source_url="https://www.reddit.com/r/AskReddit/comments/low/",
                sort="hot",
            ),
            RedditDiscussion(
                post_id="ai",
                subreddit="OpenAI",
                title="People feel overwhelmed by AI agents at work",
                selftext="The discussion is about tiny automations, anxiety, and realistic workflows.",
                author="user_b",
                score=950,
                num_comments=230,
                upvote_ratio=0.96,
                created_utc=1779417601,
                source_url="https://www.reddit.com/r/OpenAI/comments/ai/",
                sort="top",
            ),
            RedditDiscussion(
                post_id="psy",
                subreddit="psychology",
                title="Therapists discuss burnout after constant notifications",
                selftext="People compare notification pressure, attention residue, and recovery routines.",
                author="user_c",
                score=720,
                num_comments=190,
                upvote_ratio=0.93,
                created_utc=1779417602,
                source_url="https://www.reddit.com/r/psychology/comments/psy/",
                sort="hot",
            ),
        ]
    )
    builder = RedditDiscussionContextBuilder(
        client=provider,
        subreddits=["OpenAI", "psychology"],
        sorts=["hot", "top"],
        time_filter="day",
        limit_per_listing=5,
    )

    context = builder.build(
        scene="从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度",
        domain="Reddit英文讨论转译",
        playbook_id="reddit_curation_daily_post",
    )

    assert context is not None
    assert "# Reddit Discussion Scan Live Context" in context
    assert "- status: available" in context
    assert "r/OpenAI" in context
    assert "r/psychology" in context
    assert "People feel overwhelmed by AI agents at work" in context
    assert "Therapists discuss burnout after constant notifications" in context
    assert "What is your favorite sandwich?" not in context
    assert "Chinese-reader fit" in context
    assert "只借讨论现象和观点结构，不复写原文长段" in context
    assert provider.calls == [
        {
            "subreddits": ["OpenAI", "psychology"],
            "sorts": ["hot", "top"],
            "time_filter": "day",
            "limit_per_listing": 5,
        }
    ]


def test_reddit_discussion_context_reports_missing_credentials() -> None:
    builder = RedditDiscussionContextBuilder(
        client=None,
        credentials_configured=False,
    )

    context = builder.build(
        scene="AI热点",
        domain="Reddit英文讨论转译",
        playbook_id="reddit_curation_daily_post",
    )

    assert context is not None
    assert "- status: missing_credentials" in context
    assert "REDDIT_CLIENT_ID" in context
    assert "REDDIT_CLIENT_SECRET" in context
    assert "REDDIT_USER_AGENT" in context
    assert "read-only Reddit scan" in context
    assert "Responsible Builder Policy" in context
    assert "explicit Reddit approval" in context


def test_reddit_discussion_context_uses_public_json_fallback_without_oauth_credentials() -> None:
    builder = RedditDiscussionContextBuilder.from_settings(
        Settings(
            _env_file=None,
            REDDIT_CLIENT_ID="",
            REDDIT_CLIENT_SECRET="",
            REDDIT_USER_AGENT="ptsm-test/0.1 (by /u/test)",
            REDDIT_PUBLIC_JSON_FALLBACK=True,
        )
    )

    assert builder.credentials_configured is True
    assert builder.access_mode == "public_json"
