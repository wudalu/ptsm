from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ptsm.domain.ai_tech_content import (
    AiTechAudience,
    AiTechEvidenceBundle,
    AiTechEvidenceManifest,
    AiTechFact,
    AiTechNewsItem,
    AiTechTopic,
    AiTechTrendSupport,
    parse_ai_tech_evidence_bundle,
    parse_ai_tech_runtime_contract,
    validate_ai_tech_draft,
)


@pytest.mark.parametrize(
    ("fixture_name", "mode"),
    (
        ("news_brief.json", "news_brief"),
        ("hands_on.json", "hands_on"),
        ("fact_translation.json", "fact_translation"),
    ),
)
def test_ai_tech_evidence_fixtures_cover_each_supported_mode(
    fixture_name: str,
    mode: str,
) -> None:
    fixture_path = Path(__file__).parents[2] / "fixtures" / "ai_tech_evidence" / fixture_name

    bundle = parse_ai_tech_evidence_bundle(json.loads(fixture_path.read_text(encoding="utf-8")))

    assert bundle.mode == mode


def _news_brief_payload() -> dict[str, object]:
    return {
        "mode": "news_brief",
        "news_items": [
            {
                "label": "模型发布",
                "event_fingerprint": "event-model-release-001",
                "facts": ["产品发布了新的推理模型。"],
                "source_refs": ["official-release-001"],
                "trend_support": {
                    "cluster_id": "hotspot-model-release",
                    "evidence_ids": ["trend-evidence-001"],
                },
            },
            {
                "label": "开发者工具",
                "event_fingerprint": "event-developer-tools-002",
                "facts": ["开发者工具新增了批量处理能力。"],
                "source_refs": ["official-release-002"],
            },
            {
                "label": "行业应用",
                "event_fingerprint": "event-industry-use-003",
                "facts": ["该功能面向团队协作场景开放。"],
                "source_refs": ["official-release-003"],
            },
        ],
    }


def _hands_on_payload() -> dict[str, object]:
    return {
        "mode": "hands_on",
        "topic": {
            "label": "Kimi K3 更新",
            "trend_support": {
                "cluster_id": "hotspot-kimi-k3",
                "evidence_ids": ["trend-evidence-k3"],
            },
        },
        "hands_on": {
            "product": "Kimi",
            "version": "K3",
            "tested_at": "2026-07-22",
            "task": "把一份脱敏会议纪要整理成待办清单",
            "input_summary": "一份脱敏的会议纪要",
            "observed_output": "输出了按负责人分组的待办清单",
            "limitation": "时间信息仍需要人工复核",
            "test_evidence_refs": ["test-run-kimi-k3-001"],
        },
    }


def _fact_translation_payload() -> dict[str, object]:
    return {
        "mode": "fact_translation",
        "topic": {
            "label": "Kimi K3 更新",
            "trend_support": {
                "cluster_id": "hotspot-kimi-k3",
                "evidence_ids": ["trend-evidence-k3"],
            },
        },
        "facts": [
            {
                "statement": "Kimi 公布了 K3 的更新说明。",
                "source_refs": ["official-kimi-k3-release"],
            },
            {
                "statement": "更新说明列出了面向开发者的接入变化。",
                "source_refs": ["official-kimi-k3-api-notes"],
            },
        ],
        "audience": {
            "who_should_care": "正在评估中文模型接入的开发者",
            "who_can_wait": "暂时没有模型迁移计划的个人用户",
        },
    }


def test_parse_news_brief_exposes_only_safe_drafting_facts_and_opaque_manifest() -> None:
    bundle = parse_ai_tech_evidence_bundle(_news_brief_payload())

    assert bundle.mode == "news_brief"
    assert bundle.drafting_payload == {
        "mode": "news_brief",
        "news_items": (
            {
                "label": "模型发布",
                "facts": ("产品发布了新的推理模型。",),
            },
            {
                "label": "开发者工具",
                "facts": ("开发者工具新增了批量处理能力。",),
            },
            {
                "label": "行业应用",
                "facts": ("该功能面向团队协作场景开放。",),
            },
        ),
    }
    assert bundle.manifest.source_refs == (
        "official-release-001",
        "official-release-002",
        "official-release-003",
    )
    assert bundle.manifest.test_evidence_refs == ()
    assert bundle.manifest.event_fingerprints == (
        "event-model-release-001",
        "event-developer-tools-002",
        "event-industry-use-003",
    )
    assert bundle.manifest.trend_support[0].cluster_id == "hotspot-model-release"
    assert bundle.manifest.trend_support[0].evidence_ids == ("trend-evidence-001",)
    assert bundle.mode_requirements.requires_test_evidence is False
    assert "source_refs" not in str(bundle.drafting_payload)
    assert "trend-evidence-001" not in str(bundle.drafting_payload)
    assert "event-model-release-001" not in str(bundle.drafting_payload)


def test_parse_hands_on_requires_and_preserves_observed_test_structure() -> None:
    bundle = parse_ai_tech_evidence_bundle(_hands_on_payload())

    assert bundle.mode == "hands_on"
    assert bundle.drafting_payload["topic"] == "Kimi K3 更新"
    assert bundle.drafting_payload["hands_on"] == {
        "product": "Kimi",
        "version": "K3",
        "tested_at": "2026-07-22",
        "task": "把一份脱敏会议纪要整理成待办清单",
        "input_summary": "一份脱敏的会议纪要",
        "observed_output": "输出了按负责人分组的待办清单",
        "limitation": "时间信息仍需要人工复核",
    }
    assert bundle.manifest.test_evidence_refs == ("test-run-kimi-k3-001",)
    assert "test_evidence_refs" not in str(bundle.drafting_payload)
    assert bundle.mode_requirements.requires_test_evidence is True
    assert "体验" in bundle.mode_requirements.allowed_claim_kinds


def test_parse_fact_translation_requires_two_facts_and_audience_decision() -> None:
    bundle = parse_ai_tech_evidence_bundle(_fact_translation_payload())

    assert bundle.mode == "fact_translation"
    assert bundle.drafting_payload == {
        "mode": "fact_translation",
        "topic": "Kimi K3 更新",
        "facts": (
            "Kimi 公布了 K3 的更新说明。",
            "更新说明列出了面向开发者的接入变化。",
        ),
        "audience": {
            "who_should_care": "正在评估中文模型接入的开发者",
            "who_can_wait": "暂时没有模型迁移计划的个人用户",
        },
    }
    assert bundle.manifest.source_refs == (
        "official-kimi-k3-release",
        "official-kimi-k3-api-notes",
    )
    assert bundle.mode_requirements.requires_test_evidence is False
    assert "体验" not in bundle.mode_requirements.allowed_claim_kinds


def test_parse_rejects_missing_mode() -> None:
    payload = _news_brief_payload()
    payload.pop("mode")

    with pytest.raises(ValidationError, match="mode"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_news_brief_with_only_two_items() -> None:
    payload = _news_brief_payload()
    payload["news_items"] = payload["news_items"][:2]  # type: ignore[index]

    with pytest.raises(ValidationError, match="at least 3"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_news_brief_without_an_event_fingerprint() -> None:
    payload = _news_brief_payload()
    news_items = payload["news_items"]
    assert isinstance(news_items, list)
    first_item = news_items[0]
    assert isinstance(first_item, dict)
    first_item.pop("event_fingerprint")

    with pytest.raises(ValidationError, match="event_fingerprint"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_news_brief_with_duplicate_normalized_labels() -> None:
    payload = _news_brief_payload()
    news_items = payload["news_items"]
    assert isinstance(news_items, list)
    for item, label in zip(news_items, ("Kimi K3", " kimi   k3 ", "KIMI K3")):
        assert isinstance(item, dict)
        item["label"] = label

    with pytest.raises(ValidationError, match="distinct news item labels"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_full_width_and_ascii_duplicate_news_labels() -> None:
    payload = _news_brief_payload()
    news_items = payload["news_items"]
    assert isinstance(news_items, list)
    first_item = news_items[0]
    second_item = news_items[1]
    assert isinstance(first_item, dict)
    assert isinstance(second_item, dict)
    first_item["label"] = "Ｋｉｍｉ　Ｋ３"
    second_item["label"] = "Kimi K3"

    with pytest.raises(ValidationError, match="distinct news item labels"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_news_brief_different_labels_for_the_same_event() -> None:
    payload = _news_brief_payload()
    news_items = payload["news_items"]
    assert isinstance(news_items, list)
    first_item = news_items[0]
    second_item = news_items[1]
    assert isinstance(first_item, dict)
    assert isinstance(second_item, dict)
    second_item["label"] = "面向开发者的另一条标题"
    second_item["event_fingerprint"] = first_item["event_fingerprint"]

    with pytest.raises(ValidationError, match="distinct event fingerprints"):
        parse_ai_tech_evidence_bundle(payload)


@pytest.mark.parametrize("missing_field", ("version", "limitation", "test_evidence_refs"))
def test_parse_rejects_hands_on_without_required_test_evidence_fields(
    missing_field: str,
) -> None:
    payload = _hands_on_payload()
    hands_on = payload["hands_on"]
    assert isinstance(hands_on, dict)
    hands_on.pop(missing_field)

    with pytest.raises(ValidationError, match=missing_field):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_fact_translation_with_fewer_than_two_facts() -> None:
    payload = _fact_translation_payload()
    payload["facts"] = payload["facts"][:1]  # type: ignore[index]

    with pytest.raises(ValidationError, match="at least 2"):
        parse_ai_tech_evidence_bundle(payload)


@pytest.mark.parametrize(
    ("raw_key", "raw_value"),
    (
        ("source_url", "https://example.com/source"),
        ("author", "Example Author"),
        ("byline", "By Example Author"),
        ("feed_id", "feed-raw-001"),
        ("source_title", "A raw upstream headline"),
    ),
)
def test_parse_rejects_raw_source_provenance_recursively(
    raw_key: str,
    raw_value: str,
) -> None:
    payload = deepcopy(_news_brief_payload())
    news_items = payload["news_items"]
    assert isinstance(news_items, list)
    first_item = news_items[0]
    assert isinstance(first_item, dict)
    first_item["trend_support"] = {
        "cluster_id": "hotspot-model-release",
        "evidence_ids": ["trend-evidence-001"],
        "nested": {raw_key: raw_value},
    }

    with pytest.raises(ValidationError, match="Raw source provenance"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_url_as_an_opaque_source_reference() -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["source_refs"] = ["https://example.com/not-an-opaque-id"]

    with pytest.raises(ValidationError, match="opaque reference"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_bare_domain_as_an_opaque_source_reference() -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["source_refs"] = ["example.com"]

    with pytest.raises(ValidationError, match="opaque reference"):
        parse_ai_tech_evidence_bundle(payload)


def test_parse_rejects_bare_domain_in_fact_statement() -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["statement"] = "更新说明见 example.com/release。"

    with pytest.raises(ValidationError, match="raw URL or domain"):
        parse_ai_tech_evidence_bundle(payload)


@pytest.mark.parametrize(
    "unsafe_statement",
    (
        "更新说明见 //example.com/release。",
        "更新说明见 ftp://example.com/release。",
        "更新说明见 file:///tmp/release。",
        "更新说明见 mailto:news@example.com。",
    ),
)
def test_parse_rejects_protocol_relative_and_non_http_source_locators_in_facts(
    unsafe_statement: str,
) -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["statement"] = unsafe_statement

    with pytest.raises(ValidationError, match="raw URL or domain"):
        parse_ai_tech_evidence_bundle(payload)


def test_direct_news_item_construction_rejects_url_in_drafting_label() -> None:
    with pytest.raises(ValidationError, match="raw URL or domain"):
        AiTechNewsItem(
            label="https://example.com/release",
            event_fingerprint="event-direct-construction-001",
            facts=("这是经过整理的 AI 更新事实。",),
            source_refs=("source-direct-construction-001",),
        )


@pytest.mark.parametrize(
    "unsafe_statement",
    (
        "更新说明见 //intranet/release。",
        r"更新说明见 \\server\share。",
        "更新说明见 例子.测试/release。",
        "更新说明见 example。com/release。",
        "更新说明见 example｡com/release。",
        "更新说明见 例子。测试/release。",
        "更新说明见 例子｡测试/release。",
        "更新说明见 [::1]/release。",
        "更新说明见 blob:opaque-token。",
        "更新说明见 about:blank。",
    ),
)
def test_parse_rejects_non_public_and_unicode_source_locators_in_facts(
    unsafe_statement: str,
) -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["statement"] = unsafe_statement

    with pytest.raises(ValidationError, match="raw URL or domain"):
        parse_ai_tech_evidence_bundle(payload)


@pytest.mark.parametrize(
    "safe_statement",
    (
        "模型已经更新。用户可以使用新功能。",
        "这是第一句。这是第二句。",
        "Kimi 更新。面向开发者开放。",
        "模型发布。开发者工具：新增批量处理能力。",
    ),
)
def test_parse_allows_normal_chinese_sentence_separators_in_facts(
    safe_statement: str,
) -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["statement"] = safe_statement

    bundle = parse_ai_tech_evidence_bundle(payload)

    assert bundle.drafting_payload["facts"][0] == safe_statement


@pytest.mark.parametrize("safe_statement", ("v1.alpha", "model.config", "torch.compile"))
def test_parse_allows_common_ai_technical_dotted_identifiers(
    safe_statement: str,
) -> None:
    payload = _fact_translation_payload()
    facts = payload["facts"]
    assert isinstance(facts, list)
    first_fact = facts[0]
    assert isinstance(first_fact, dict)
    first_fact["statement"] = safe_statement

    bundle = parse_ai_tech_evidence_bundle(payload)

    assert bundle.drafting_payload["facts"][0] == safe_statement


def test_bundle_revalidates_a_model_constructed_nested_fact() -> None:
    unsafe_fact = AiTechFact.model_construct(
        statement="更新说明见 //intranet/release。",
        source_refs=("source-safe-001",),
    )

    with pytest.raises(ValidationError, match="raw URL or domain"):
        AiTechEvidenceBundle(
            mode="fact_translation",
            topic=AiTechTopic(label="Kimi K3 更新"),
            facts=(
                unsafe_fact,
                AiTechFact(
                    statement="更新说明列出了开发者接入变化。",
                    source_refs=("source-safe-002",),
                ),
            ),
            audience=AiTechAudience(
                who_should_care="正在评估中文模型接入的开发者",
                who_can_wait="暂时没有模型迁移计划的个人用户",
            ),
        )


def test_drafting_payload_fails_closed_for_a_model_constructed_bundle() -> None:
    unsafe_bundle = AiTechEvidenceBundle.model_construct(
        mode="fact_translation",
        topic=AiTechTopic.model_construct(label="Kimi K3 更新", trend_support=None),
        facts=(
            AiTechFact.model_construct(
                statement="更新说明见 //intranet/release。",
                source_refs=("source-safe-001",),
            ),
        ),
        audience=AiTechAudience.model_construct(
            who_should_care="正在评估中文模型接入的开发者",
            who_can_wait="暂时没有模型迁移计划的个人用户",
        ),
        news_items=(),
        hands_on=None,
    )

    with pytest.raises(ValueError, match="raw URL or domain"):
        _ = unsafe_bundle.drafting_payload


def test_drafting_payload_revalidates_a_model_constructed_bundle_mode() -> None:
    malformed_bundle = AiTechEvidenceBundle.model_construct(
        mode="generic",
        topic=None,
        facts=(),
        audience=None,
        news_items=(),
        hands_on=None,
    )

    with pytest.raises(ValidationError, match="news_brief|hands_on|fact_translation"):
        _ = malformed_bundle.drafting_payload


def test_drafting_payload_revalidates_model_constructed_fact_minimums() -> None:
    malformed_bundle = AiTechEvidenceBundle.model_construct(
        mode="fact_translation",
        topic=AiTechTopic.model_construct(label="Kimi K3 更新", trend_support=None),
        facts=(
            AiTechFact.model_construct(
                statement="更新说明列出了开发者接入变化。",
                source_refs=("source-safe-001",),
            ),
        ),
        audience=AiTechAudience.model_construct(
            who_should_care="正在评估中文模型接入的开发者",
            who_can_wait="暂时没有模型迁移计划的个人用户",
        ),
        news_items=(),
        hands_on=None,
    )

    with pytest.raises(ValidationError, match="at least 2 facts"):
        _ = malformed_bundle.drafting_payload


def test_drafting_payload_revalidates_model_constructed_fact_references() -> None:
    malformed_bundle = AiTechEvidenceBundle.model_construct(
        mode="fact_translation",
        topic=AiTechTopic.model_construct(label="Kimi K3 更新", trend_support=None),
        facts=(
            AiTechFact.model_construct(
                statement="更新说明列出了开发者接入变化。",
                source_refs=(),
            ),
            AiTechFact.model_construct(
                statement="更新还覆盖了团队权限设置。",
                source_refs=("source-safe-002",),
            ),
        ),
        audience=AiTechAudience.model_construct(
            who_should_care="正在评估中文模型接入的开发者",
            who_can_wait="暂时没有模型迁移计划的个人用户",
        ),
        news_items=(),
        hands_on=None,
    )

    with pytest.raises(ValidationError, match="source_refs"):
        _ = malformed_bundle.drafting_payload


@pytest.mark.parametrize(
    ("field_name", "unsafe_reference"),
    (
        ("source_refs", "https://example.com/release"),
        ("test_evidence_refs", "example.com"),
        ("event_fingerprints", "//intranet/event"),
    ),
)
def test_manifest_direct_construction_requires_opaque_references(
    field_name: str,
    unsafe_reference: str,
) -> None:
    with pytest.raises(ValidationError, match="opaque reference"):
        AiTechEvidenceManifest(**{field_name: (unsafe_reference,)})


def test_manifest_revalidates_model_constructed_trend_support() -> None:
    unsafe_trend_support = AiTechTrendSupport.model_construct(
        cluster_id="https://example.com/cluster",
        evidence_ids=("trend-safe-001",),
    )

    with pytest.raises(ValidationError, match="opaque reference"):
        AiTechEvidenceManifest(trend_support=(unsafe_trend_support,))


def test_parse_rejects_trend_support_without_publishable_fact_evidence() -> None:
    payload = _fact_translation_payload()
    payload["facts"] = []

    with pytest.raises(ValidationError, match="trend support alone"):
        parse_ai_tech_evidence_bundle(payload)


def test_runtime_contract_rejects_extra_provenance_and_incomplete_news_shape() -> None:
    contract = deepcopy(parse_ai_tech_evidence_bundle(_news_brief_payload()).runtime_contract)
    contract["source_refs"] = ["must-not-enter-runtime"]

    with pytest.raises(ValidationError, match="Extra inputs"):
        parse_ai_tech_runtime_contract(contract)

    incomplete = deepcopy(parse_ai_tech_evidence_bundle(_news_brief_payload()).runtime_contract)
    incomplete["drafting_payload"]["news_items"] = incomplete["drafting_payload"][
        "news_items"
    ][:1]

    with pytest.raises(ValidationError, match="at least 3"):
        parse_ai_tech_runtime_contract(incomplete)


def test_runtime_contract_requires_an_iso_test_date_for_hands_on() -> None:
    contract = deepcopy(parse_ai_tech_evidence_bundle(_hands_on_payload()).runtime_contract)
    contract["drafting_payload"]["hands_on"]["tested_at"] = "yesterday"

    with pytest.raises(ValidationError, match="tested_at"):
        parse_ai_tech_runtime_contract(contract)


def test_news_brief_draft_rejects_unsupported_hands_on_and_performance_claims() -> None:
    bundle = parse_ai_tech_evidence_bundle(_news_brief_payload())

    errors = validate_ai_tech_draft(
        bundle,
        {
            "title": "今天的 AI 更新",
            "body": "我实测后发现，这次速度提升明显。",
            "hashtags": ["#AI资讯"],
        },
    )

    assert "我实测" in errors
    assert "速度提升明显" in errors


def test_hands_on_draft_requires_the_recorded_task_output_and_limitation() -> None:
    bundle = parse_ai_tech_evidence_bundle(_hands_on_payload())

    errors = validate_ai_tech_draft(
        bundle,
        {
            "title": "K3 我试了",
            "body": "先说结论：可以用。",
            "hashtags": ["#AI资讯"],
        },
    )

    assert "recorded task" in errors
    assert "recorded observed output" in errors
    assert "recorded limitation" in errors


def test_hands_on_draft_requires_the_recorded_date_and_input_summary() -> None:
    bundle = parse_ai_tech_evidence_bundle(_hands_on_payload())
    record = bundle.drafting_payload["hands_on"]

    errors = validate_ai_tech_draft(
        bundle,
        {
            "title": "K3 实测记录",
            "body": (
                f"Kimi K3 更新：{record['product']} {record['version']}，"
                f"任务是{record['task']}，{record['observed_output']}。"
                f"限制是{record['limitation']}。"
            ),
            "hashtags": ["#AI资讯"],
        },
    )

    assert "recorded test date" in errors
    assert "recorded input summary" in errors


def test_non_hands_on_draft_rejects_unrecorded_first_person_observation() -> None:
    bundle = parse_ai_tech_evidence_bundle(_news_brief_payload())
    draft = {
        "title": "AI 科技三条更新",
        "body": (
            "模型发布：产品发布了新的推理模型。\n"
            "开发者工具：开发者工具新增了批量处理能力。\n"
            "行业应用：该功能面向团队协作场景开放。\n"
            "昨晚我拿它跑了一个工作流，结果很稳。"
        ),
        "hashtags": ["#AI资讯"],
    }

    errors = validate_ai_tech_draft(bundle, draft)

    assert "non-hands-on experience language" in errors


def test_non_hands_on_draft_rejects_claim_appended_to_an_approved_fact() -> None:
    bundle = parse_ai_tech_evidence_bundle(_news_brief_payload())
    draft = {
        "title": "AI 科技三条更新",
        "body": (
            "模型发布：产品发布了新的推理模型。\n"
            "开发者工具：开发者工具新增了批量处理能力。\n"
            "行业应用：该功能面向团队协作场景开放，实跑 benchmark 后延迟减半。"
        ),
        "hashtags": ["#AI资讯"],
    }

    errors = validate_ai_tech_draft(bundle, draft)

    assert "unapproved non-hands-on claim" in errors
