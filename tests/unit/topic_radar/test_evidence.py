from __future__ import annotations

import pytest

from topic_radar.analysis.evidence import (
    EvidenceRecord,
    ScanQuality,
    append_topic_history,
    canonicalize_platforms,
    canonicalize_trending_items,
    cluster_evidence,
    determine_scan_quality,
    read_recent_topic_history,
    select_recommended_angles,
)
from topic_radar.platforms.weibo import TrendingItem


def test_platform_aliases_are_canonical_and_deduplicated():
    assert canonicalize_platforms(["xhs", "weibo", "xiaohongshu", "抖音"]) == [
        "xiaohongshu",
        "weibo",
        "douyin",
    ]


def test_platform_aliases_accept_ascii_and_full_width_commas():
    assert canonicalize_platforms("小红书，微博,xhs") == [
        "xiaohongshu",
        "weibo",
    ]


def test_xhs_feed_duplicates_collapse_and_merge_matched_queries():
    items = [
        TrendingItem(
            rank=2,
            title="下班后我终于不内耗了",
            hot_score=120,
            platform="xiaohongshu",
            metadata={"feed_id": "note-1", "author": "小王", "keyword": "下班"},
        ),
        TrendingItem(
            rank=1,
            title="换一个标题也还是同一篇",
            hot_score=300,
            platform="xiaohongshu",
            metadata={"feed_id": "note-1", "author": "小王", "keyword": "内耗"},
        ),
    ]

    canonical, evidence = canonicalize_trending_items({"xhs": items})

    assert list(canonical) == ["xiaohongshu"]
    assert len(canonical["xiaohongshu"]) == 1
    item = canonical["xiaohongshu"][0]
    assert item.rank == 1
    assert item.hot_score == 300
    assert item.metadata["matched_queries"] == ["下班", "内耗"]
    assert evidence[0].source_identity == "xiaohongshu:feed:note-1"
    assert evidence[0].matched_queries == ["下班", "内耗"]


def test_xhs_without_feed_id_uses_normalized_title_and_author_identity():
    first = TrendingItem(
        rank=1,
        title="  下班后，先别回消息！ ",
        hot_score=30,
        platform="xiaohongshu",
        metadata={"author": "阿 白", "keyword": "下班"},
    )
    second = TrendingItem(
        rank=2,
        title="下班后先别回消息",
        hot_score=20,
        platform="xiaohongshu",
        metadata={"author": "阿白", "keyword": "职场"},
    )

    canonical, evidence = canonicalize_trending_items({"xiaohongshu": [first, second]})

    assert len(canonical["xiaohongshu"]) == 1
    assert evidence[0].source_identity == "xiaohongshu:title:下班后先别回消息:阿白"
    assert evidence[0].matched_queries == ["下班", "职场"]


@pytest.mark.parametrize("known_first", [False, True])
def test_xhs_mixed_feed_id_and_title_author_bridge_to_one_authoritative_source(
    known_first: bool,
):
    idless = TrendingItem(
        rank=2,
        title="睡前恢复小练习",
        hot_score=80,
        platform="xiaohongshu",
        metadata={"author": "同一作者", "keyword": "睡眠恢复"},
    )
    known = TrendingItem(
        rank=1,
        title="睡前恢复小练习",
        hot_score=120,
        platform="xiaohongshu",
        metadata={"feed_id": "real-a", "author": "同一作者", "keyword": "办公室恢复"},
    )

    canonical, evidence = canonicalize_trending_items(
        {"xiaohongshu": [known, idless] if known_first else [idless, known]}
    )

    assert len(canonical["xiaohongshu"]) == 1
    assert evidence[0].source_identity == "xiaohongshu:feed:real-a"
    assert set(evidence[0].matched_queries) == {"睡眠恢复", "办公室恢复"}
    assert evidence[0].source_observation_count == 2


def test_xhs_mixed_identity_bridge_keeps_a_later_distinct_feed_id():
    idless = TrendingItem(
        rank=3,
        title="睡前恢复小练习",
        hot_score=80,
        platform="xiaohongshu",
        metadata={"author": "同一作者", "keyword": "睡眠恢复"},
    )
    first_known = TrendingItem(
        rank=2,
        title="睡前恢复小练习",
        hot_score=100,
        platform="xiaohongshu",
        metadata={"feed_id": "real-a", "author": "同一作者", "keyword": "办公室恢复"},
    )
    second_known = TrendingItem(
        rank=1,
        title="睡前恢复小练习",
        hot_score=120,
        platform="xiaohongshu",
        metadata={"feed_id": "real-b", "author": "同一作者", "keyword": "睡前恢复"},
    )

    canonical, evidence = canonicalize_trending_items(
        {"xiaohongshu": [idless, first_known, second_known]}
    )

    assert len(canonical["xiaohongshu"]) == 2
    assert {record.source_identity for record in evidence} == {
        "xiaohongshu:feed:real-a",
        "xiaohongshu:feed:real-b",
    }
    counts = {record.source_identity: record.source_observation_count for record in evidence}
    assert counts["xiaohongshu:feed:real-a"] == 2
    assert counts["xiaohongshu:feed:real-b"] == 1


def test_xhs_ambiguous_known_ids_do_not_absorb_a_later_idless_observation():
    first_known = TrendingItem(
        rank=1,
        title="睡前恢复小练习",
        hot_score=120,
        platform="xiaohongshu",
        metadata={"feed_id": "real-a", "author": "同一作者", "keyword": "睡眠恢复"},
    )
    second_known = TrendingItem(
        rank=2,
        title="睡前恢复小练习",
        hot_score=100,
        platform="xiaohongshu",
        metadata={"feed_id": "real-b", "author": "同一作者", "keyword": "办公室恢复"},
    )
    later_idless = TrendingItem(
        rank=3,
        title="睡前恢复小练习",
        hot_score=80,
        platform="xiaohongshu",
        metadata={"author": "同一作者", "keyword": "睡前恢复"},
    )

    canonical, evidence = canonicalize_trending_items(
        {"xiaohongshu": [first_known, second_known, later_idless]}
    )

    assert len(canonical["xiaohongshu"]) == 3
    by_identity = {record.source_identity: record for record in evidence}
    assert set(by_identity) == {
        "xiaohongshu:feed:real-a",
        "xiaohongshu:feed:real-b",
        "xiaohongshu:title:睡前恢复小练习:同一作者",
    }
    assert by_identity["xiaohongshu:feed:real-a"].matched_queries == ["睡眠恢复"]
    assert by_identity["xiaohongshu:feed:real-b"].matched_queries == ["办公室恢复"]
    assert by_identity["xiaohongshu:title:睡前恢复小练习:同一作者"].matched_queries == ["睡前恢复"]


def test_xhs_without_feed_or_author_uses_url_before_title_identity():
    first = TrendingItem(
        rank=1,
        title="同名笔记",
        hot_score=30,
        url="https://www.xiaohongshu.com/explore/note-a",
        platform="xiaohongshu",
    )
    second = TrendingItem(
        rank=2,
        title="同名笔记",
        hot_score=20,
        url="https://www.xiaohongshu.com/explore/note-b",
        platform="xiaohongshu",
    )

    canonical, evidence = canonicalize_trending_items({"xiaohongshu": [first, second]})

    assert len(canonical["xiaohongshu"]) == 2
    assert {record.source_identity for record in evidence} == {
        "xiaohongshu:url:https://www.xiaohongshu.com/explore/note-a",
        "xiaohongshu:url:https://www.xiaohongshu.com/explore/note-b",
    }


def test_xhs_without_source_identifiers_preserves_distinct_observations():
    first = TrendingItem(rank=1, title="同名笔记", hot_score=30, platform="xiaohongshu")
    second = TrendingItem(rank=2, title="同名笔记", hot_score=20, platform="xiaohongshu")

    canonical, evidence = canonicalize_trending_items({"xiaohongshu": [first, second]})

    assert len(canonical["xiaohongshu"]) == 2
    assert len({record.source_identity for record in evidence}) == 2
    assert all("xiaohongshu:1" not in record.source_identity for record in evidence)


def test_non_xhs_identity_is_platform_and_canonical_title():
    first = TrendingItem(rank=1, title="AI 工具提效", hot_score=100, platform="weibo")
    second = TrendingItem(rank=2, title="ai工具提效！", hot_score=90, platform="weibo")

    canonical, evidence = canonicalize_trending_items({"weibo": [first, second]})

    assert len(canonical["weibo"]) == 1
    assert evidence[0].source_identity == "weibo:title:ai工具提效"


def test_evidence_heat_is_normalized_within_each_platform():
    canonical, evidence = canonicalize_trending_items(
        {
            "weibo": [
                TrendingItem(rank=1, title="微博高热", hot_score=1_000_000, platform="weibo"),
                TrendingItem(rank=2, title="微博低热", hot_score=500_000, platform="weibo"),
            ],
            "douyin": [
                TrendingItem(rank=1, title="抖音高热", hot_score=100, platform="douyin"),
                TrendingItem(rank=2, title="抖音低热", hot_score=50, platform="douyin"),
            ],
        }
    )

    assert canonical["weibo"][0].title == "微博高热"
    heat = {record.title: record.normalized_heat for record in evidence}
    assert heat["微博高热"] == 1.0
    assert heat["抖音高热"] == 1.0
    assert heat["微博低热"] == heat["抖音低热"] == 0.5


def test_scan_quality_distinguishes_completed_partial_and_insufficient_evidence():
    valid = {"weibo": [TrendingItem(rank=1, title="有效样本", platform="weibo")]}

    assert determine_scan_quality(valid, {}, ["weibo"]) is ScanQuality.COMPLETED
    assert determine_scan_quality(valid, {"xhs": "login required"}, ["weibo", "xhs"]) is ScanQuality.PARTIAL
    assert determine_scan_quality({}, {"weibo": "empty"}, ["weibo"]) is ScanQuality.INSUFFICIENT_EVIDENCE


def _evidence(
    evidence_id: str,
    platform: str,
    title: str,
    *,
    normalized_heat: float = 1.0,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        source_identity=f"{platform}:{evidence_id}",
        platform=platform,
        title=title,
        canonical_title="",
        event_fingerprint="",
        hot_score=100,
        normalized_heat=normalized_heat,
        matched_queries=[],
    )


def test_cluster_evidence_groups_conservative_chinese_paraphrases_with_stable_provenance():
    clustered, clusters = cluster_evidence(
        [
            _evidence("evidence:weibo", "weibo", "成都暴雨致多处积水"),
            _evidence("evidence:douyin", "douyin", "成都突降暴雨 多地积水"),
        ]
    )

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster.cluster_id.startswith("cluster:")
    assert cluster.event_fingerprint.startswith("event:")
    assert cluster.evidence_ids == ["evidence:douyin", "evidence:weibo"]
    assert cluster.platforms == ["douyin", "weibo"]
    assert cluster.score > 0
    assert {record.event_fingerprint for record in clustered} == {cluster.event_fingerprint}


def test_cluster_evidence_does_not_merge_items_that_only_share_generic_words():
    _clustered, clusters = cluster_evidence(
        [
            _evidence("evidence:rain", "weibo", "网友热议成都暴雨"),
            _evidence("evidence:metro", "douyin", "网友热议上海地铁"),
        ]
    )

    assert len(clusters) == 2


def test_cluster_evidence_does_not_merge_shared_subject_with_conflicting_object():
    _clustered, clusters = cluster_evidence(
        [
            _evidence("evidence:romance", "weibo", "张三回应恋情传闻"),
            _evidence("evidence:tax", "douyin", "张三回应税务传闻"),
        ]
    )

    assert len(clusters) == 2


def test_cluster_evidence_avoids_a_single_link_bridge_between_conflicting_events():
    _clustered, clusters = cluster_evidence(
        [
            _evidence("evidence:romance", "weibo", "张三回应恋情传闻"),
            _evidence("evidence:bridge", "douyin", "张三回应恋情税务传闻"),
            _evidence("evidence:tax", "zhihu", "张三回应税务传闻"),
        ]
    )

    assert len(clusters) == 2
    assert max(len(cluster.evidence_ids) for cluster in clusters) == 2


def test_mmr_selection_keeps_only_one_angle_per_event_cluster():
    _clustered, clusters = cluster_evidence(
        [
            _evidence("evidence:event-a", "weibo", "成都暴雨致多处积水"),
            _evidence("evidence:event-b", "douyin", "北京暴雪导致航班延误"),
        ]
    )
    first, second = clusters
    candidates = [
        {
            "vertical": "城市天气",
            "angle": "暴雨天通勤避坑清单",
            "why_discussion_likely": "可复制",
            "confidence": 0.9,
            "cluster_id": first.cluster_id,
            "evidence_ids": first.evidence_ids,
        },
        {
            "vertical": "城市天气",
            "angle": "暴雨后的城市恢复观察",
            "why_discussion_likely": "有共鸣",
            "confidence": 0.85,
            "cluster_id": first.cluster_id,
            "evidence_ids": first.evidence_ids,
        },
        {
            "vertical": "城市天气",
            "angle": "暴雪天航班改签真实经验",
            "why_discussion_likely": "有用",
            "confidence": 0.8,
            "cluster_id": second.cluster_id,
            "evidence_ids": second.evidence_ids,
        },
    ]

    selected = select_recommended_angles(candidates, clusters, max_recommendations=3)

    assert len(selected) == 2
    assert {angle["cluster_id"] for angle in selected} == {
        first.cluster_id,
        second.cluster_id,
    }
    assert all(angle["angle_signature"].startswith("angle:") for angle in selected)
    assert all(angle["novelty_state"] == "new" for angle in selected)
    assert all(isinstance(angle["ranking_score"], float) for angle in selected)


def test_mmr_selection_rejects_unexpanded_template_placeholders():
    _clustered, clusters = cluster_evidence(
        [_evidence("evidence:work", "weibo", "打工人下班后如何恢复")]
    )
    cluster = clusters[0]

    selected = select_recommended_angles(
        [
            {
                "vertical": "打工人日常",
                "angle": "工位上的{action}，旁边同事问我链接",
                "why_discussion_likely": "模板泄漏不应进入推荐。",
                "cluster_id": cluster.cluster_id,
                "evidence_ids": cluster.evidence_ids,
            }
        ],
        clusters,
    )

    assert selected == []


def test_history_cooldown_suppresses_exact_event_angle_but_allows_new_angle(tmp_path):
    _clustered, clusters = cluster_evidence(
        [_evidence("evidence:rain", "weibo", "成都暴雨致多处积水")]
    )
    cluster = clusters[0]
    repeated = {
        "vertical": "城市天气",
        "angle": "暴雨天通勤避坑清单",
        "why_discussion_likely": "可复制",
        "confidence": 0.9,
        "cluster_id": cluster.cluster_id,
        "evidence_ids": cluster.evidence_ids,
    }
    first = select_recommended_angles([repeated], clusters)
    append_topic_history(tmp_path, "2026-07-20", first)

    history = read_recent_topic_history(tmp_path, "2026-07-21", history_days=14)
    suppressed = select_recommended_angles(
        [repeated],
        clusters,
        history_records=history,
        scan_date="2026-07-21",
        history_days=14,
    )
    new_angle = select_recommended_angles(
        [{**repeated, "angle": "暴雨后小区排水到底靠不靠谱"}],
        clusters,
        history_records=history,
        scan_date="2026-07-21",
        history_days=14,
    )

    assert suppressed == []
    assert len(new_angle) == 1
    assert new_angle[0]["angle_signature"] != first[0]["angle_signature"]


def test_history_cooldown_suppresses_semantic_event_alias_across_separate_scans(tmp_path):
    _first_evidence, first_clusters = cluster_evidence(
        [_evidence("evidence:first", "weibo", "成都暴雨致多处积水")]
    )
    first_cluster = first_clusters[0]
    candidate = {
        "vertical": "城市天气",
        "angle": "暴雨天通勤避坑清单",
        "why_discussion_likely": "可复制",
        "confidence": 0.9,
        "cluster_id": first_cluster.cluster_id,
        "evidence_ids": first_cluster.evidence_ids,
    }
    first = select_recommended_angles([candidate], first_clusters)
    append_topic_history(tmp_path, "2026-07-20", first)

    _second_evidence, second_clusters = cluster_evidence(
        [_evidence("evidence:second", "douyin", "成都突降暴雨 多地积水")]
    )
    second_cluster = second_clusters[0]
    history = read_recent_topic_history(tmp_path, "2026-07-21", history_days=14)
    same_event = select_recommended_angles(
        [{**candidate, "cluster_id": second_cluster.cluster_id, "evidence_ids": second_cluster.evidence_ids}],
        second_clusters,
        history_records=history,
        scan_date="2026-07-21",
    )

    _different_evidence, different_clusters = cluster_evidence(
        [_evidence("evidence:heat", "douyin", "成都高温发布橙色预警")]
    )
    different_cluster = different_clusters[0]
    different_event = select_recommended_angles(
        [{**candidate, "cluster_id": different_cluster.cluster_id, "evidence_ids": different_cluster.evidence_ids}],
        different_clusters,
        history_records=history,
        scan_date="2026-07-21",
    )

    assert first_cluster.event_fingerprint != second_cluster.event_fingerprint
    assert same_event == []
    assert len(different_event) == 1
