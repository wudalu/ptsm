from __future__ import annotations

from ptsm.domain.xhs_patterns import (
    XhsSample,
    analyze_samples_to_patterns,
    normalize_xhs_sample,
)


def test_normalize_xhs_sample_keeps_evidence_without_image_url() -> None:
    sample = normalize_xhs_sample(
        {
            "title": "突然意识到书桌也需要丰容",
            "keyword": "人类丰容",
            "author": "作者A",
            "feed_id": "note-1",
            "xsec_token": "token-1",
            "likes": 120,
            "comments": 9,
            "collects": 30,
            "shares": 4,
            "cover_width": 1080,
            "cover_height": 1440,
            "has_cover_url": True,
            "cover_url": "https://example.invalid/not-reusable.jpg",
        },
        lane="human_enrichment",
        collected_at="2026-05-17T00:00:00Z",
    )

    assert sample.sample_id == "note-1"
    assert sample.lane == "human_enrichment"
    assert sample.engagement_score == 120 + 9 * 4 + 4 * 6 + 30 * 2
    assert sample.cover_ratio == "3:4"
    data = sample.to_dict()
    assert data["cover_width"] == 1080
    assert data["cover_height"] == 1440
    assert data["has_cover_url"] is True
    assert "cover_url" not in data


def test_analyze_samples_to_patterns_extracts_reusable_format_archetypes() -> None:
    samples = [
        XhsSample(
            sample_id="note-1",
            lane="human_enrichment",
            keyword="人类丰容",
            title="突然意识到书桌也需要丰容",
            author="作者A",
            likes=120,
            comments=9,
            shares=4,
            collects=30,
            cover_width=1080,
            cover_height=1440,
            has_cover_url=True,
            collected_at="2026-05-17T00:00:00Z",
        ),
        XhsSample(
            sample_id="note-2",
            lane="human_enrichment",
            keyword="低成本改造",
            title="空无一物的家vs丰容后的家",
            author="作者B",
            likes=500,
            comments=40,
            shares=20,
            collects=380,
            cover_width=1080,
            cover_height=1440,
            has_cover_url=True,
            collected_at="2026-05-17T00:00:00Z",
        ),
        XhsSample(
            sample_id="note-3",
            lane="human_enrichment",
            keyword="钩织",
            title="新手必看：这个过程原来这么简单",
            author="作者C",
            likes=300,
            comments=60,
            shares=30,
            collects=420,
            cover_width=1080,
            cover_height=1440,
            has_cover_url=True,
            collected_at="2026-05-17T00:00:00Z",
        ),
    ]

    patterns = analyze_samples_to_patterns(
        samples,
        lane="human_enrichment",
        created_at="2026-05-17T00:30:00Z",
    )

    hooks = {pattern.title_hook for pattern in patterns}
    assert "sudden_realization" in hooks
    assert "before_after_contrast" in hooks
    assert "process_or_tutorial" in hooks
    assert all(pattern.status in {"candidate", "approved"} for pattern in patterns)
    assert all(pattern.cover_ratio == "3:4" for pattern in patterns)
    assert all(pattern.source_sample_ids for pattern in patterns)
