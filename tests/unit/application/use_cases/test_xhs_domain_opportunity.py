from __future__ import annotations

import json
from pathlib import Path

import pytest

from topic_radar.platforms.xiaohongshu import FeedItem

from ptsm.application.use_cases.xhs_domain_opportunity import (
    _normalize_keywords,
    _strongest_title,
    run_xhs_domain_opportunity,
)


class FakeOpportunityXhs:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def search_feeds(self, keyword: str, limit: int = 20):
        self.calls.append((keyword, limit))
        rows = {
            "睡眠恢复": [
                FeedItem(
                    feed_id="sleep-1",
                    title="睡觉大于天 睡觉是成本最低收益最高的投资",
                    author="Berry充电计划",
                    likes=10102,
                    comments=182,
                    collects=5557,
                    shares=2354,
                    xsec_token="token-sleep-1",
                )
            ],
            "人类丰容": [
                FeedItem(
                    feed_id="enrichment-1",
                    title="人，你该“丰容”了!",
                    author="新周梗",
                    likes=1650,
                    comments=27,
                    collects=687,
                    shares=1453,
                    xsec_token="token-enrichment-1",
                )
            ],
            "武侠": [
                FeedItem(
                    feed_id="wuxia-1",
                    title="你读过最江湖味的一句诗",
                    author="诗念",
                    likes=169,
                    comments=56,
                    collects=153,
                    shares=16,
                    xsec_token="token-wuxia-1",
                )
            ],
        }
        return rows.get(keyword, [])[:limit]


class DuplicateOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        shared = FeedItem(
            feed_id="sleep-shared",
            title="睡觉大于天，恢复也该排进日程",
            author="Berry充电计划",
            likes=10102,
            comments=182,
            collects=5557,
            shares=2354,
            xsec_token="token-sleep-shared",
        )
        return {
            "睡眠恢复": [shared],
            "办公室恢复": [shared],
        }.get(keyword, [])[:limit]


class FallbackDuplicateOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        shared = FeedItem(
            feed_id="",
            title="睡觉大于天，恢复也该排进日程",
            author="Berry充电计划",
            likes=10102,
            comments=182,
            collects=5557,
            shares=2354,
            xsec_token="token-sleep-shared",
        )
        return {
            "睡眠恢复": [shared],
            "办公室恢复": [shared],
        }.get(keyword, [])[:limit]


class EmptyOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        return []


class LoginRequiredOpportunityXhs:
    async def check_login(self):
        return False, None

    async def search_feeds(self, keyword: str, limit: int = 20):
        raise AssertionError("search must not run before a failed login preflight")


class AllErrorOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        raise RuntimeError("search transport unavailable")


class PartialOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        if keyword == "武侠":
            raise RuntimeError("search transport unavailable")
        return [
            FeedItem(
                feed_id="sleep-1",
                title="睡觉大于天 睡觉是成本最低收益最高的投资",
                author="Berry充电计划",
                likes=10102,
                comments=182,
                collects=5557,
                shares=2354,
                xsec_token="token-sleep-1",
            )
        ][:limit]


class UnknownIdentityOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        rows = {
            "睡眠恢复": FeedItem(
                feed_id="",
                title="",
                author="",
                likes=101,
                comments=2,
                collects=3,
                shares=4,
                xsec_token="",
            ),
            "办公室恢复": FeedItem(
                feed_id="",
                title="",
                author="",
                likes=202,
                comments=3,
                collects=4,
                shares=5,
                xsec_token="",
            ),
        }
        feed = rows.get(keyword)
        return [feed] if feed is not None else []


class SameTitleAnonymousOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        return [
            FeedItem(
                feed_id="",
                title="同标题但无法确认作者",
                author="",
                likes=101 if keyword == "睡眠恢复" else 202,
            )
        ]


class BridgedIdentityOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        return [
            FeedItem(
                feed_id="sleep-bridge" if keyword == "睡眠恢复" else "",
                title="睡前恢复小练习",
                author="同一作者",
                likes=101,
            )
        ]


class DistinctKnownIdentityOpportunityXhs:
    async def search_feeds(self, keyword: str, limit: int = 20):
        return [
            FeedItem(
                feed_id="sleep-a" if keyword == "睡眠恢复" else "sleep-b",
                title="同标题但确为两篇笔记",
                author="同一作者",
                likes=101,
            )
        ]


class IdlessThenDistinctKnownIdentityOpportunityXhs:
    """The first real ID confirms the id-less bridge; the next one is distinct."""

    async def search_feeds(self, keyword: str, limit: int = 20):
        feed_ids = {
            "睡眠恢复": "",
            "办公室恢复": "sleep-a",
            "睡前恢复": "sleep-b",
        }
        return [
            FeedItem(
                feed_id=feed_ids[keyword],
                title="睡前恢复小练习",
                author="同一作者",
                likes=101,
            )
        ]


class DistinctKnownThenIdlessIdentityOpportunityXhs:
    """An ID-less row stays unresolved after a visible identity becomes ambiguous."""

    async def search_feeds(self, keyword: str, limit: int = 20):
        feed_ids = {
            "睡眠恢复": "sleep-a",
            "办公室恢复": "sleep-b",
            "睡前恢复": "",
        }
        return [
            FeedItem(
                feed_id=feed_ids[keyword],
                title="睡前恢复小练习",
                author="同一作者",
                likes=101,
            )
        ]


class DefaultKeywordsOpportunityXhs:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def search_feeds(self, keyword: str, limit: int = 20):
        self.calls.append(keyword)
        return []


def test_xhs_domain_opportunity_scores_and_maps_keywords(tmp_path: Path) -> None:
    fake_xhs = FakeOpportunityXhs()

    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "人类丰容", "武侠"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=fake_xhs,
        delay_seconds=0,
        collected_at="2026-05-30T00:00:00Z",
    )

    assert result["status"] == "completed"
    assert fake_xhs.calls == [("睡眠恢复", 5), ("人类丰容", 5), ("武侠", 5)]
    assert result["keywords"][0]["keyword"] == "睡眠恢复"
    assert result["keywords"][0]["top_score"] == 36068
    assert result["keywords"][0]["top_samples"][0]["engagement_score"] == 36068
    assert result["keywords"][0]["current_playbook_fit"] == [
        "modern_psychology_post",
        "human_enrichment_daily_post",
    ]
    assert result["keywords"][0]["new_domain_candidate"] is True
    assert result["keywords"][2]["keyword"] == "武侠"
    assert result["keywords"][2]["opportunity_tier"] == "keep_niche"

    assert result["recommendations"][0]["domain"] == "轻养生 / 睡眠恢复 / 办公室恢复"
    assert result["recommendations"][0]["recommendation"] == "new_domain_candidate"
    assert result["recommendations"][1]["domain"] == "人类丰容 / 修复系手作"

    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["methodology"]["score_formula"] == (
        "likes + comments * 4 + collects * 2 + shares * 6"
    )
    assert artifact["source"]["live_source"] == "xiaohongshu-mcp.search_feeds"

    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "Top Domains" in markdown
    assert "Existing Playbook Fit" in markdown
    assert "New Domain Candidates" in markdown
    assert "Workflow Notes" in markdown
    assert "轻养生 / 睡眠恢复 / 办公室恢复" in markdown
    assert "sleep-1" not in markdown
    assert "token-sleep-1" not in markdown


def test_xhs_domain_opportunity_deduplicates_shared_feed_and_aggregates_new_domain_candidate(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=DuplicateOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-05-31T00:00:00Z",
    )

    assert result["status"] == "completed"
    assert sum(row["sample_count"] for row in result["keywords"]) == 1
    assert len(result["recommendations"]) == 1
    recommendation = result["recommendations"][0]
    assert recommendation["domain"] == "轻养生 / 睡眠恢复 / 办公室恢复"
    assert recommendation["keywords"] == ["睡眠恢复", "办公室恢复"]
    assert recommendation["sample_count"] == 1
    assert recommendation["new_domain_candidate"] is True

    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    new_domain_section = markdown.split("## New Domain Candidates", maxsplit=1)[1]
    assert new_domain_section.count("- 轻养生 / 睡眠恢复 / 办公室恢复:") == 1
    assert (
        "- 办公室恢复: 1 shared search result(s) were deduplicated to canonical evidence "
        "returned for another requested keyword; see the aggregate domain recommendation."
    ) in markdown
    assert "办公室恢复: no successful unique samples" not in markdown
    assert "sleep-shared" not in markdown
    assert "token-sleep-shared" not in markdown


def test_xhs_domain_opportunity_uses_normalized_title_author_when_feed_id_is_missing(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=FallbackDuplicateOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:00Z",
    )

    assert sum(row["sample_count"] for row in result["keywords"]) == 1
    assert result["recommendations"][0]["sample_count"] == 1


def test_xhs_domain_opportunity_does_not_merge_distinct_unidentified_feed_observations(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=UnknownIdentityOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:00Z",
    )

    assert result["status"] == "completed"
    assert sum(row["sample_count"] for row in result["keywords"]) == 2
    assert result["recommendations"][0]["sample_count"] == 2


def test_xhs_domain_opportunity_keeps_same_title_when_author_and_id_are_missing(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=SameTitleAnonymousOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:01Z",
    )

    assert sum(row["sample_count"] for row in result["keywords"]) == 2
    assert sum(row["duplicate_sample_count"] for row in result["keywords"]) == 0


def test_xhs_domain_opportunity_bridges_feed_id_and_title_author_fallback(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=BridgedIdentityOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:02Z",
    )

    assert sum(row["sample_count"] for row in result["keywords"]) == 1
    assert sum(row["duplicate_sample_count"] for row in result["keywords"]) == 1


def test_xhs_domain_opportunity_preserves_distinct_feed_ids_with_same_title_author(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=DistinctKnownIdentityOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:03Z",
    )

    assert sum(row["sample_count"] for row in result["keywords"]) == 2
    assert sum(row["duplicate_sample_count"] for row in result["keywords"]) == 0


def test_xhs_domain_opportunity_consumes_idless_bridge_before_later_distinct_ids(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复", "睡前恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=IdlessThenDistinctKnownIdentityOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:04Z",
    )

    rows = {row["keyword"]: row for row in result["keywords"]}
    assert rows["睡眠恢复"]["sample_count"] == 1
    assert rows["办公室恢复"]["sample_count"] == 0
    assert rows["睡前恢复"]["sample_count"] == 1
    assert rows["办公室恢复"]["duplicate_sample_count"] == 1
    assert rows["睡前恢复"]["duplicate_sample_count"] == 0
    assert sum(row["sample_count"] for row in result["keywords"]) == 2


def test_xhs_domain_opportunity_keeps_idless_sample_after_known_identity_becomes_ambiguous(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "办公室恢复", "睡前恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=DistinctKnownThenIdlessIdentityOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-01T00:00:04Z",
    )

    rows = {row["keyword"]: row for row in result["keywords"]}
    assert rows["睡眠恢复"]["sample_count"] == 1
    assert rows["办公室恢复"]["sample_count"] == 1
    assert rows["睡前恢复"]["sample_count"] == 1
    assert sum(row["duplicate_sample_count"] for row in result["keywords"]) == 0


@pytest.mark.parametrize("keywords", [",", "，", " , ， \n "])
def test_xhs_domain_opportunity_requires_explicit_keywords_for_separator_only_input(
    tmp_path: Path,
    keywords: str,
) -> None:
    platform = DefaultKeywordsOpportunityXhs()

    with pytest.raises(ValueError, match="at least one explicit keyword"):
        run_xhs_domain_opportunity(
            keywords=keywords,
            sample_limit_per_keyword=5,
            output_dir=tmp_path,
            xhs_platform=platform,
            delay_seconds=0,
            collected_at="2026-06-01T00:00:05Z",
        )

    assert platform.calls == []


def test_xhs_domain_opportunity_accepts_mixed_ascii_and_full_width_separators() -> None:
    assert _normalize_keywords("睡眠恢复，办公室恢复,武侠") == [
        "睡眠恢复",
        "办公室恢复",
        "武侠",
    ]


def test_xhs_domain_opportunity_normalizes_and_truncates_display_title() -> None:
    title = "  恢复计划\n" + ("很长的标题" * 40)

    result = _strongest_title({"top_samples": [{"title": title}]})

    assert result is not None
    assert "\n" not in result
    assert result.startswith("恢复计划 很长的标题")
    assert len(result) <= 120
    assert result.endswith("…")


def test_xhs_domain_opportunity_refuses_static_tiers_when_zero_samples_or_all_errors(
    tmp_path: Path,
) -> None:
    empty = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "人类丰容"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path / "empty",
        xhs_platform=EmptyOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-02T00:00:00Z",
    )
    all_error = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "人类丰容"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path / "all-error",
        xhs_platform=AllErrorOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-02T00:00:00Z",
    )

    for result in (empty, all_error):
        assert result["status"] == "insufficient_evidence"
        assert result["recommendations"] == []
        markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
        new_domain_section = markdown.split("## New Domain Candidates", maxsplit=1)[1]
        assert "- None in this scan." in new_domain_section
        assert "act_now" not in markdown


def test_xhs_domain_opportunity_returns_login_required_diagnostic_before_search(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=LoginRequiredOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-03T00:00:00Z",
    )

    assert result["status"] == "login_required"
    assert result["keywords"] == []
    assert result["recommendations"] == []
    assert result["keyword_errors"] == {"_login": "login required"}
    artifact = json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))
    assert artifact["status"] == "login_required"


def test_xhs_domain_opportunity_keeps_real_samples_when_some_keyword_searches_fail(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "武侠"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=PartialOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-03T00:00:00Z",
    )

    assert result["status"] == "partial"
    assert result["keyword_errors"] == {"武侠": "search transport unavailable"}
    assert [row["domain"] for row in result["recommendations"]] == [
        "轻养生 / 睡眠恢复 / 办公室恢复"
    ]


def test_xhs_domain_opportunity_marks_zero_sample_keyword_as_partial(
    tmp_path: Path,
) -> None:
    result = run_xhs_domain_opportunity(
        keywords=["睡眠恢复", "没有样本的关键词"],
        sample_limit_per_keyword=5,
        output_dir=tmp_path,
        xhs_platform=FakeOpportunityXhs(),
        delay_seconds=0,
        collected_at="2026-06-04T00:00:00Z",
    )

    assert result["status"] == "partial"
    assert result["keyword_errors"] == {}
    empty_keyword = next(
        row for row in result["keywords"] if row["keyword"] == "没有样本的关键词"
    )
    assert empty_keyword["sample_count"] == 0
    assert empty_keyword["duplicate_sample_count"] == 0
    assert [row["domain"] for row in result["recommendations"]] == [
        "轻养生 / 睡眠恢复 / 办公室恢复"
    ]
