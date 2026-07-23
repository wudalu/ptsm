from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
    PsychologyLearningSeriesPlanIntent,
    PsychologyLearningSeriesProposal,
    build_psychology_learning_series_proposal,
    contains_psychology_learning_raw_provenance,
    list_psychology_learning_series,
    parse_psychology_learning_runtime_contract,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
)


def _starter_bundle():
    return resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id="notice_the_loop",
    )


def _valid_draft(bundle) -> dict[str, object]:
    return render_psychology_learning_draft(bundle.runtime_contract)


def test_starter_catalog_resolves_a_closed_six_lesson_series() -> None:
    bundle = _starter_bundle()

    assert bundle.mode == PSYCHOLOGY_LEARNING_MODE
    assert bundle.series_id == "after_work_rumination"
    assert bundle.lesson_id == "notice_the_loop"
    assert bundle.lesson_number == 1
    assert bundle.direction_id == "psychology_learning_after_work_rumination_notice_the_loop"
    assert bundle.runtime_contract["series_badge"] == "《下班后脑子停不下来》第1课"
    assert len(bundle.roadmap) == 6
    assert [lesson["lesson_number"] for lesson in bundle.roadmap] == [1, 2, 3, 4, 5, 6]
    assert all(lesson["direction_type"] == "learning_series_lesson" for lesson in bundle.roadmap)
    assert bundle.manifest["source_refs"]
    assert "source_refs" not in str(bundle.runtime_contract)
    assert "source:" not in str(bundle.runtime_contract)


def test_each_learning_lesson_has_a_distinct_xhs_title_and_cover_hook() -> None:
    lessons = list_psychology_learning_series(
        series_id="after_work_rumination"
    )
    drafts = [render_psychology_learning_draft(lesson.runtime_contract) for lesson in lessons]

    assert len({draft["title"] for draft in drafts}) == len(lessons)
    assert len({draft["image_text"] for draft in drafts}) == len(lessons)
    assert all(len(str(draft["title"])) <= 22 for draft in drafts)


@pytest.mark.parametrize(
    ("series_id", "lesson_id"),
    (
        ("unknown_series", "notice_the_loop"),
        ("after_work_rumination", "unknown_lesson"),
        ("after_work_rumination", "../notice_the_loop"),
    ),
)
def test_catalog_rejects_unknown_or_malformed_selection(
    series_id: str,
    lesson_id: str,
) -> None:
    with pytest.raises(ValueError):
        resolve_psychology_learning_selection(
            series_id=series_id,
            lesson_id=lesson_id,
        )


def test_runtime_contract_rejects_provenance_or_unapproved_fields() -> None:
    payload = deepcopy(_starter_bundle().runtime_contract)
    payload["source_refs"] = ["source:apa-rumination-2023"]

    with pytest.raises(ValidationError):
        parse_psychology_learning_runtime_contract(payload)


def test_learning_draft_gate_requires_all_approved_lesson_fields() -> None:
    bundle = _starter_bundle()
    draft = _valid_draft(bundle)

    assert validate_psychology_learning_draft_contract(bundle.runtime_contract, draft) == []

    incomplete = dict(draft)
    incomplete["body"] = str(incomplete["body"]).replace(
        bundle.runtime_contract["micro_exercise"],
        "",
    )
    errors = validate_psychology_learning_draft_contract(
        bundle.runtime_contract,
        incomplete,
    )
    assert any("micro_exercise" in error for error in errors)


def test_learning_draft_gate_rejects_unsafe_claims_and_source_reference_leakage() -> None:
    bundle = _starter_bundle()
    draft = _valid_draft(bundle)
    draft["body"] = (
        f"{draft['body']} source:apa-rumination-2023 能治好焦虑，快去自测。"
    )

    errors = validate_psychology_learning_draft_contract(bundle.runtime_contract, draft)

    assert any("source reference" in error for error in errors)
    assert any("unsafe psychology claim" in error for error in errors)


def test_learning_draft_gate_rejects_an_extra_unapproved_psychology_assertion() -> None:
    bundle = _starter_bundle()
    draft = _valid_draft(bundle)
    draft["body"] = str(draft["body"]) + "这说明你天生不适合工作。"

    errors = validate_psychology_learning_draft_contract(bundle.runtime_contract, draft)

    assert errors
    assert any("controlled lesson template" in error for error in errors)


def test_non_strict_artifact_scan_allows_only_empty_runtime_context_source_paths() -> None:
    artifact = {
        "playbook_id": "modern_psychology_post",
        "final_content": _valid_draft(_starter_bundle()),
        "runtime_skill_details": [
            {
                "skill_name": "psychology_learning_contract",
                "resource_type": "runtime_context",
                "resource_id": "psychology_learning_contract:runtime_context",
                "source_path": None,
                "content_preview": "# Psychology Learning Series Contract",
            }
        ],
    }

    assert not contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=False,
    )

    artifact["runtime_skill_details"][0]["source_path"] = "src/private-contract.md"
    assert contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=False,
    )


def test_custom_series_proposal_is_safe_and_cannot_become_a_runtime_contract() -> None:
    intent = PsychologyLearningSeriesPlanIntent(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "practice_pause",
                "title": "练习暂停一下",
                "goal": "在一个具体时刻写下可完成的下一步。",
            },
            {
                "id": "notice_pattern",
                "title": "先识别重复模式",
                "goal": "记录容易发生的具体时刻。",
            },
            {
                "id": "review_progress",
                "title": "回顾有效的小动作",
                "goal": "选一个明天继续的动作。",
            },
        ),
    )

    proposal = build_psychology_learning_series_proposal(intent)

    assert proposal.catalog.runnable is False
    assert not hasattr(proposal.catalog, "runtime_contract")
    assert [lesson.lesson_id for lesson in proposal.catalog.lessons] == [
        "practice_pause",
        "notice_pattern",
        "review_progress",
    ]
    assert [lesson.lesson_number for lesson in proposal.catalog.lessons] == [1, 2, 3]
    assert [item.lesson_id for item in proposal.publication_plan.items] == [
        "notice_pattern",
        "practice_pause",
        "review_progress",
    ]
    assert [item.canonical_lesson_number for item in proposal.publication_plan.items] == [
        2,
        1,
        3,
    ]
    serialized = proposal.model_dump(mode="json")
    assert "source_refs" not in str(serialized)
    assert "runtime_contract" not in str(serialized)
    with pytest.raises(ValidationError):
        parse_psychology_learning_runtime_contract(proposal.catalog.model_dump())


def test_custom_series_proposal_rejects_a_tampered_stable_identifier_or_fingerprint() -> None:
    proposal = build_psychology_learning_series_proposal(
        PsychologyLearningSeriesPlanIntent(topic="下班后的脑内回放")
    )
    tampered = proposal.model_dump(mode="json")
    tampered["proposal_id"] = "proposal_changed"

    with pytest.raises(ValidationError, match="proposal_id does not match"):
        PsychologyLearningSeriesProposal.model_validate(tampered)


@pytest.mark.parametrize(
    "topic,outline,error",
    (
        ("https://example.com/心理学", None, "source locator or reference"),
        ("example.xyz", None, "source locator or reference"),
        ("example\ufe0f.xyz", None, "source locator or reference"),
        ("example·xyz", None, "source locator or reference"),
        ("example·info", None, "source locator or reference"),
        ("example。technology", None, "source locator or reference"),
        ("example\ufe0fonline", None, "source locator or reference"),
        ("example\u2044site", None, "source locator or reference"),
        ("https∶∕∕example·technology", None, "source locator or reference"),
        ("example · info", None, "source locator or reference"),
        ("example 。 technology", None, "source locator or reference"),
        ("example \ufe0f online", None, "source locator or reference"),
        ("https ∶ ∕ ∕ example · technology", None, "source locator or reference"),
        ("note·card", None, "source locator or reference"),
        ("source:operator-note", None, "source locator or reference"),
        ("source\ufe0f:operator-note", None, "source locator or reference"),
        ("source·:operator-note", None, "source locator or reference"),
        ("source\u2044:operator-note", None, "source locator or reference"),
        ("source\uff0d:operator-note", None, "source locator or reference"),
        ("source\uff0f:operator-note", None, "source locator or reference"),
        ("s\u043eurce:operator-note", None, "source locator or reference"),
        ("ref\u034f:operator-note", None, "source locator or reference"),
        ("來源:operator-note", None, "source locator or reference"),
        ("參考:operator-note", None, "source locator or reference"),
        ("參考文獻 APA 2024", None, "source locator or reference"),
        ("doi 10.1000/182 的学习", None, "source locator or reference"),
        ("参考文献 APA 2024", None, "source locator or reference"),
        ("抑郁症自测", None, "unsafe clinical or crisis content"),
        ("診斷", None, "unsafe clinical or crisis content"),
        ("確診", None, "unsafe clinical or crisis content"),
        ("憂鬱症", None, "unsafe clinical or crisis content"),
        ("雙相", None, "unsafe clinical or crisis content"),
        ("人格障礙", None, "unsafe clinical or crisis content"),
        ("治療", None, "unsafe clinical or crisis content"),
        ("治癒", None, "unsafe clinical or crisis content"),
        ("藥物", None, "unsafe clinical or crisis content"),
        ("用藥", None, "unsafe clinical or crisis content"),
        ("停藥", None, "unsafe clinical or crisis content"),
        ("處方", None, "unsafe clinical or crisis content"),
        ("自測", None, "unsafe clinical or crisis content"),
        ("自殺", None, "unsafe clinical or crisis content"),
        ("自傷", None, "unsafe clinical or crisis content"),
        ("輕生", None, "unsafe clinical or crisis content"),
        ("傷害自己", None, "unsafe clinical or crisis content"),
        ("自我傷害", None, "unsafe clinical or crisis content"),
        ("自残", None, "unsafe clinical or crisis content"),
        ("自殘", None, "unsafe clinical or crisis content"),
        ("自我残害", None, "unsafe clinical or crisis content"),
        ("自我殘害", None, "unsafe clinical or crisis content"),
        ("伤害自身", None, "unsafe clinical or crisis content"),
        ("傷害自身", None, "unsafe clinical or crisis content"),
        ("自尽", None, "unsafe clinical or crisis content"),
        ("自盡", None, "unsafe clinical or crisis content"),
        ("寻死", None, "unsafe clinical or crisis content"),
        ("尋死", None, "unsafe clinical or crisis content"),
        ("寻短见", None, "unsafe clinical or crisis content"),
        ("尋短見", None, "unsafe clinical or crisis content"),
        ("结束生命", None, "unsafe clinical or crisis content"),
        ("結束生命", None, "unsafe clinical or crisis content"),
        ("了结生命", None, "unsafe clinical or crisis content"),
        ("了結生命", None, "unsafe clinical or crisis content"),
        ("服药", None, "unsafe clinical or crisis content"),
        ("服藥", None, "unsafe clinical or crisis content"),
        ("吃药", None, "unsafe clinical or crisis content"),
        ("吃藥", None, "unsafe clinical or crisis content"),
        ("断药", None, "unsafe clinical or crisis content"),
        ("斷藥", None, "unsafe clinical or crisis content"),
        ("开药", None, "unsafe clinical or crisis content"),
        ("開藥", None, "unsafe clinical or crisis content"),
        ("开方", None, "unsafe clinical or crisis content"),
        ("開方", None, "unsafe clinical or crisis content"),
        ("药方", None, "unsafe clinical or crisis content"),
        ("藥方", None, "unsafe clinical or crisis content"),
        ("自\u00b7残", None, "unsafe clinical or crisis content"),
        ("服\u2044藥", None, "unsafe clinical or crisis content"),
        ("结\u200b束生命", None, "unsafe clinical or crisis content"),
        ("危機", None, "unsafe clinical or crisis content"),
        ("自我伤害危机", None, "unsafe clinical or crisis content"),
        ("自\u200b伤应对", None, "unsafe clinical or crisis content"),
        ("自\u3000伤 journal", None, "unsafe clinical or crisis content"),
        ("自\uff0d伤 journal", None, "unsafe clinical or crisis content"),
        ("诊\u00a0断 入门", None, "unsafe clinical or crisis content"),
        ("诊\u00b7断 入门", None, "unsafe clinical or crisis content"),
        ("self\u00a0harm journal", None, "unsafe clinical or crisis content"),
        ("self\uff3fharm journal", None, "unsafe clinical or crisis content"),
        ("self\u2044harm journal", None, "unsafe clinical or crisis content"),
        ("self\u2215harm journal", None, "unsafe clinical or crisis content"),
        ("self\uff0bharm journal", None, "unsafe clinical or crisis content"),
        ("自\ufe0f伤 journal", None, "unsafe clinical or crisis content"),
        ("诊\u034f断 入门", None, "unsafe clinical or crisis content"),
        ("自\u20e3伤 journal", None, "unsafe clinical or crisis content"),
        ("\u0455\u0435lfharm journal", None, "unsupported alphabetic script"),
        ("ＡＤＨＤ日常整理", None, "unsafe clinical or crisis content"),
        (
            "情绪整理",
            (
                {"title": "先记录", "source\u200b_refs": "hidden-reference"},
                {"title": "再回顾"},
            ),
            "provenance",
        ),
        (
            "情绪整理",
            (
                {"id": "same_lesson", "title": "先记录"},
                {"id": "same_lesson", "title": "再回顾"},
            ),
            "lesson ids must be unique",
        ),
        (
            "情绪整理",
            ({"id": "only_one", "title": "只上一课"},),
            "between 2 and 6 lessons",
        ),
    ),
)
def test_custom_series_plan_intent_rejects_unsafe_or_malformed_operator_values(
    topic: str,
    outline: tuple[dict[str, str], ...] | None,
    error: str,
) -> None:
    with pytest.raises(ValidationError, match=error):
        PsychologyLearningSeriesPlanIntent(topic=topic, outline=outline)


@pytest.mark.parametrize(
    "topic",
    (
        "我的\u3000下班整理",
        "我的·下班整理",
        "我的－下班整理",
        "我的\u2044下班整理",
        "我的\ufe0f下班整理",
        "下班后的整理",
        "下班後的學習整理",
        "自我照顧練習",
        "note card",
        "下班后的note card整理",
    ),
)
def test_proposal_validation_keeps_safe_reader_visible_unicode_text_unchanged(
    topic: str,
) -> None:

    intent = PsychologyLearningSeriesPlanIntent(topic=topic)

    assert intent.topic == topic
