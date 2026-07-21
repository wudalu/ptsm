"""Tests for LLM analyzer — prompt construction, JSON extraction, fallback."""

from __future__ import annotations

import pytest

from topic_radar.analysis.llm_analyzer import (
    LLMAnalyzer,
    _MAX_PROMPT_CLUSTERS,
    _MAX_PROMPT_EVIDENCE_ROWS,
    _MAX_PROMPT_ITEMS_PER_PLATFORM,
    _build_user_prompt,
    _extract_json,
    validate_llm_output_evidence,
)
from topic_radar.analysis.evidence import EvidenceRecord, TopicCluster, cluster_evidence
from topic_radar.analysis.schemas import LLMAngle, LLMScanOutput, LLMVertical
from topic_radar.platforms.weibo import TrendingItem


SAMPLE_ITEMS: dict[str, list[TrendingItem]] = {
    "weibo": [
        TrendingItem(rank=1, title="国乒男团2比3瑞典", hot_score=1174594, platform="weibo"),
        TrendingItem(rank=2, title="2026五一档总票房已破5亿", hot_score=684031, platform="weibo"),
        TrendingItem(rank=3, title="公司引进AI后将员工降薪裁员", hot_score=120000, platform="weibo"),
    ],
}


class TestBuildPrompt:
    def test_renders_platforms_and_topics(self):
        prompt = _build_user_prompt(SAMPLE_ITEMS, "2026-05-04")
        assert "weibo" in prompt
        assert "国乒男团2比3瑞典" in prompt
        assert "2026五一档总票房已破5亿" in prompt
        assert "2026-05-04" in prompt

    def test_includes_output_schema(self):
        prompt = _build_user_prompt(SAMPLE_ITEMS, "2026-05-04")
        assert "scan_summary" in prompt
        assert "cross_platform_signals" in prompt
        assert "discovered_verticals" in prompt

    def test_truncates_each_platform_to_the_prompt_budget(self):
        many_items = {
            "weibo": [
                TrendingItem(rank=i, title=f"话题{i}", hot_score=100, platform="weibo")
                for i in range(50)
            ]
        }
        prompt = _build_user_prompt(many_items, "2026-05-04")
        assert f"话题{_MAX_PROMPT_ITEMS_PER_PLATFORM - 1}" in prompt
        assert f"话题{_MAX_PROMPT_ITEMS_PER_PLATFORM}" not in prompt

    def test_caps_evidence_rows_in_the_eight_platform_prompt_budget(self):
        evidence = [
            EvidenceRecord(
                evidence_id=f"evidence:{index}",
                source_identity=f"weibo:{index}",
                platform="weibo",
                title=f"测试标题{index}",
                canonical_title=f"测试标题{index}",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            )
            for index in range(_MAX_PROMPT_EVIDENCE_ROWS + 2)
        ]

        prompt = _build_user_prompt(SAMPLE_ITEMS, "2026-05-04", evidence=evidence)

        assert f"evidence:{_MAX_PROMPT_EVIDENCE_ROWS - 1}" in prompt
        assert f"evidence:{_MAX_PROMPT_EVIDENCE_ROWS}" not in prompt

    def test_distributes_bounded_evidence_and_clusters_across_all_platforms(self):
        platforms = (
            "bilibili",
            "douban",
            "douyin",
            "sspai",
            "toutiao",
            "weibo",
            "xiaohongshu",
            "zhihu",
        )
        evidence = [
            EvidenceRecord(
                evidence_id=f"evidence:{platform}:{index}",
                source_identity=f"{platform}:{index}",
                platform=platform,
                title=f"{platform} 测试话题 {index}",
                canonical_title=f"{platform}测试话题{index}",
                event_fingerprint=f"event:{platform}:{index}",
                hot_score=100 - index,
                normalized_heat=1 - (index / 100),
                matched_queries=[],
            )
            for platform in platforms
            for index in range(8)
        ]
        clusters = [
            TopicCluster(
                cluster_id=f"cluster:{platform}:{index}",
                event_fingerprint=f"event:{platform}:{index}",
                representative_title=f"{platform} 测试话题 {index}",
                evidence_ids=[f"evidence:{platform}:{index}"],
                platforms=[platform],
                score=1.0,
            )
            for platform in platforms
            for index in range(4)
        ]

        prompt = _build_user_prompt(
            SAMPLE_ITEMS,
            "2026-05-04",
            evidence=evidence,
            topic_clusters=clusters,
        )

        assert len(evidence) > _MAX_PROMPT_EVIDENCE_ROWS
        assert len(clusters) > _MAX_PROMPT_CLUSTERS
        for platform in platforms:
            assert f"evidence:{platform}:0" in prompt
            assert f"cluster:{platform}:0" in prompt

    def test_includes_evidence_and_cluster_references_when_available(self):
        evidence = [
            EvidenceRecord(
                evidence_id="evidence:weibo",
                source_identity="weibo:one",
                platform="weibo",
                title="成都暴雨致多处积水",
                canonical_title="成都暴雨致多处积水",
                event_fingerprint="",
                hot_score=100,
                normalized_heat=1.0,
                matched_queries=[],
            )
        ]
        _clustered, clusters = cluster_evidence(evidence)

        prompt = _build_user_prompt(
            SAMPLE_ITEMS,
            "2026-05-04",
            evidence=evidence,
            topic_clusters=clusters,
        )

        assert "evidence:weibo" in prompt
        assert clusters[0].cluster_id in prompt
        assert "evidence_ids" in prompt


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_code_block(self):
        raw = '```\n{"a": 1}\n```'
        assert _extract_json(raw) == {"a": 1}

    def test_json_code_block(self):
        raw = '```json\n{"a": 1}\n```'
        assert _extract_json(raw) == {"a": 1}

    def test_leading_text_stripped(self):
        raw = '一些解释\n{"a": 1}'
        with pytest.raises(ValueError):
            _extract_json(raw)

    def test_array_rejected(self):
        with pytest.raises(ValueError):
            _extract_json('[1, 2, 3]')


class TestLLMAnalyzer:
    def test_unavailable_without_api_key(self):
        analyzer = LLMAnalyzer(api_key="")
        assert analyzer.available is False
        result, method = analyzer.analyze(SAMPLE_ITEMS, "2026-05-04")
        assert result is None
        assert method == "rules"

    def test_available_with_api_key(self):
        analyzer = LLMAnalyzer(api_key="sk-test")
        assert analyzer.available is True

    def test_returns_rules_on_api_failure(self):
        analyzer = LLMAnalyzer(api_key="sk-invalid", base_url="https://invalid.example.com")
        result, method = analyzer.analyze(SAMPLE_ITEMS, "2026-05-04")
        assert result is None
        assert method == "rules"

    def test_failure_is_recorded_without_raw_exception_or_secret(self, monkeypatch):
        analyzer = LLMAnalyzer(api_key="sk-private-value")

        def fail(_prompt):
            raise RuntimeError("request failed with sk-private-value")

        monkeypatch.setattr(analyzer, "_call", fail)

        result, method = analyzer.analyze(SAMPLE_ITEMS, "2026-05-04")

        assert result is None
        assert method == "rules"
        assert analyzer.last_error == "LLM analysis failed (RuntimeError); rules fallback used"
        assert "sk-private-value" not in analyzer.last_error


def test_validate_llm_output_keeps_only_supported_angle_references():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:weibo",
            source_identity="weibo:one",
            platform="weibo",
            title="成都暴雨致多处积水",
            canonical_title="成都暴雨致多处积水",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        ),
    ]
    clustered, clusters = cluster_evidence(evidence)
    cluster = clusters[0]
    output = LLMScanOutput(
        scan_summary="天气话题",
        recommended_angles=[
            LLMAngle(
                vertical="城市天气",
                angle="暴雨天通勤避坑清单",
                why="实用",
                cluster_id=cluster.cluster_id,
                evidence_ids=[clustered[0].evidence_id],
            ),
            LLMAngle(
                vertical="城市天气",
                angle="无来源的热门观点",
                why="猜测",
                cluster_id="cluster:not-real",
                evidence_ids=["evidence:not-real"],
            ),
        ],
    )

    validated = validate_llm_output_evidence(output, clustered, clusters)

    assert validated is not None
    assert [angle.angle for angle in validated.recommended_angles] == ["暴雨天通勤避坑清单"]
    assert validated.recommended_angles[0].cluster_id == cluster.cluster_id


def test_validate_llm_output_rejects_unexpanded_template_angles_before_selection():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:weibo",
            source_identity="weibo:one",
            platform="weibo",
            title="打工人工位恢复小动作",
            canonical_title="打工人工位恢复小动作",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        )
    ]
    clustered, clusters = cluster_evidence(evidence)
    cluster = clusters[0]
    output = LLMScanOutput(
        scan_summary="模板不应占用 LLM 推荐位",
        recommended_angles=[
            LLMAngle(
                vertical="打工人日常",
                angle="工位上的{action}，同事问我是不是偷偷续命了",
                why="{reason}",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            )
        ],
    )

    assert validate_llm_output_evidence(output, clustered, clusters) is None


def test_validate_llm_output_rejects_evidence_title_in_any_drafting_field():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:weibo",
            source_identity="weibo:one",
            platform="weibo",
            title="原始热帖标题不得进入草稿",
            canonical_title="原始热帖标题不得进入草稿",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        ),
        EvidenceRecord(
            evidence_id="evidence:short-title",
            source_identity="weibo:short-title",
            platform="weibo",
            title="AI工具",
            canonical_title="AI工具",
            event_fingerprint="",
            hot_score=90,
            normalized_heat=0.9,
            matched_queries=[],
        ),
    ]
    clustered, clusters = cluster_evidence(evidence)
    cluster = clusters[0]
    output = LLMScanOutput(
        scan_summary="测试原始标题不会进入草稿字段",
        recommended_angles=[
            LLMAngle(
                vertical="原始热帖标题不得进入草稿",
                angle="安全角度",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="原始 热帖 标题 不得进入草稿",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="下班后给自己十分钟的无用恢复",
                why="原始热帖标题不得进入草稿",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="围绕原始热帖标题不得进入草稿聊聊恢复",
                angle="安全角度",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="围绕原始热帖标题不得进入草稿聊聊下班后的恢复",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="下班后给自己十分钟的无用恢复",
                why="原始热帖标题不得进入草稿让人有代入感",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="原作者的下班恢复",
                angle="安全角度",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="https://example.test/raw-source 的恢复讨论",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="下班后给自己十分钟的无用恢复",
                why="feed-secret-7 让人有代入感",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="token-secret-7 的恢复讨论",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="普通人用AI工具的恢复流程",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="小王的下班恢复",
                angle="安全角度",
                why="安全讨论诱因",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
            LLMAngle(
                vertical="人类丰容",
                angle="下班后给自己十分钟的无用恢复",
                why="具体、低门槛，容易交换自己的版本。",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            ),
        ],
    )

    validated = validate_llm_output_evidence(
        output,
        clustered,
        clusters,
        raw_provenance=[
            {
                "author": "原作者",
                "nickname": "小王",
                "url": "https://example.test/raw-source",
                "feed_id": "feed-secret-7",
                "xsec_token": "token-secret-7",
            }
        ],
    )

    assert validated is not None
    assert [angle.angle for angle in validated.recommended_angles] == [
        "下班后给自己十分钟的无用恢复"
    ]
    safe_angle = validated.recommended_angles[0]
    assert safe_angle.vertical == "人类丰容"
    assert safe_angle.why == "具体、低门槛，容易交换自己的版本。"


def test_validate_llm_output_allows_generic_short_source_title_inside_new_angle():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:generic-ai",
            source_identity="weibo:generic-ai",
            platform="weibo",
            title="AI",
            canonical_title="AI",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        )
    ]
    clustered, clusters = cluster_evidence(evidence)
    cluster = clusters[0]
    output = LLMScanOutput(
        scan_summary="通用 AI 讨论",
        recommended_angles=[
            LLMAngle(
                vertical="效率工具",
                angle="普通人用AI整理日报，省掉重复复制粘贴",
                why="具体且容易分享自己的版本。",
                cluster_id=cluster.cluster_id,
                evidence_ids=cluster.evidence_ids,
            )
        ],
    )

    validated = validate_llm_output_evidence(output, clustered, clusters)

    assert validated is not None
    assert [angle.angle for angle in validated.recommended_angles] == [
        "普通人用AI整理日报，省掉重复复制粘贴"
    ]


def test_validate_llm_output_derives_support_from_matching_vertical_sample_title():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:weibo",
            source_identity="weibo:one",
            platform="weibo",
            title="成都暴雨致多处积水",
            canonical_title="成都暴雨致多处积水",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        )
    ]
    clustered, clusters = cluster_evidence(evidence)
    output = LLMScanOutput(
        scan_summary="天气话题",
        discovered_verticals=[
            LLMVertical(
                name="城市天气",
                keywords=["暴雨"],
                confidence=0.7,
                discussion_density="medium",
                sample_topics=["成都暴雨致多处积水"],
                suggested_angles=[],
                comment_themes=[],
            )
        ],
        recommended_angles=[
            LLMAngle(
                vertical="城市天气",
                angle="暴雨天通勤避坑清单",
                why="实用",
            )
        ],
    )

    validated = validate_llm_output_evidence(output, clustered, clusters)

    assert validated is not None
    assert validated.recommended_angles[0].cluster_id == clusters[0].cluster_id
    assert validated.recommended_angles[0].evidence_ids == ["evidence:weibo"]


def test_validate_llm_output_rejects_all_unsupported_angles():
    output = LLMScanOutput(
        scan_summary="没有可验证的证据",
        recommended_angles=[
            LLMAngle(
                vertical="猜测",
                angle="无来源观点",
                why="无来源",
                evidence_ids=["evidence:missing"],
            )
        ],
    )

    assert validate_llm_output_evidence(output, [], []) is None


def test_validate_llm_output_discards_fabricated_vertical_and_normalizes_valid_provenance():
    evidence = [
        EvidenceRecord(
            evidence_id="evidence:weibo",
            source_identity="weibo:one",
            platform="weibo",
            title="成都暴雨致多处积水",
            canonical_title="成都暴雨致多处积水",
            event_fingerprint="",
            hot_score=100,
            normalized_heat=1.0,
            matched_queries=[],
        )
    ]
    clustered, clusters = cluster_evidence(evidence)
    cluster = clusters[0]
    output = LLMScanOutput(
        scan_summary="天气话题",
        discovered_verticals=[
            LLMVertical(
                name="城市天气",
                keywords=["暴雨"],
                confidence=0.7,
                discussion_density="medium",
                sample_topics=["成都暴雨致多处积水", "编造样本"],
                suggested_angles=[],
                comment_themes=[],
                cluster_ids=[cluster.cluster_id, "cluster:invented"],
                evidence_ids=[clustered[0].evidence_id, "evidence:invented"],
            ),
            LLMVertical(
                name="编造垂类",
                keywords=["编造"],
                confidence=0.9,
                discussion_density="high",
                sample_topics=["不存在的样本"],
                suggested_angles=["没有来源的角度"],
                comment_themes=[],
                cluster_ids=["cluster:invented"],
                evidence_ids=["evidence:invented"],
            ),
        ],
        recommended_angles=[
            LLMAngle(
                vertical="城市天气",
                angle="暴雨天通勤避坑清单",
                why="实用",
                cluster_id=cluster.cluster_id,
                evidence_ids=[clustered[0].evidence_id],
            )
        ],
    )

    validated = validate_llm_output_evidence(output, clustered, clusters)

    assert validated is not None
    assert [vertical.name for vertical in validated.discovered_verticals] == ["城市天气"]
    vertical = validated.discovered_verticals[0]
    assert vertical.cluster_ids == [cluster.cluster_id]
    assert vertical.evidence_ids == ["evidence:weibo"]
    assert vertical.sample_topics == ["成都暴雨致多处积水"]
