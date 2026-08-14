from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import os
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
import ptsm.domain.psychology_learning as psychology_learning
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.domain.psychology_learning import (
    CURRENT_PSYCHOLOGY_LEARNING_CONTROLLED_TEMPLATE_VERSION,
    PSYCHOLOGY_LEARNING_MODE,
    PsychologyLearningOutlineItem,
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


def _closed_learning_artifact(bundle) -> dict[str, object]:
    """Build the persisted shape used by the strict learning-artifact scanner."""
    contract = bundle.runtime_contract
    artifact: dict[str, object] = {
        "playbook_id": "modern_psychology_post",
        "account": {
            "account_id": "acct-psychology-local",
            "platform": "xiaohongshu",
        },
        "platform": "xiaohongshu",
        "scene": f"心理学学习专题：{contract['series_badge']}｜{contract['lesson_title']}",
        "publish_mode": "dry-run",
        "activated_skills": [],
        "activated_skill_details": [],
        "final_content": _valid_draft(bundle),
        "format_patterns_used": {"status": "not_used"},
        "publish_result": {"status": "dry_run"},
        "topic_selection": {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": bundle.series_id,
                "curriculum_version": contract["curriculum_version"],
                "lesson_id": bundle.lesson_id,
                "lesson_number": bundle.lesson_number,
            },
        },
        "psychology_learning_mode": PSYCHOLOGY_LEARNING_MODE,
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": contract["curriculum_version"],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
        "psychology_learning_evidence_manifest": bundle.manifest,
        "psychology_learning_gate": {
            "status": "passed",
            "series_id": bundle.series_id,
            "lesson_id": bundle.lesson_id,
            "validator": "psychology_learning_draft_contract",
            "validator_version": str(contract["controlled_template_version"]),
            "errors": [],
        },
    }
    catalog_receipt = psychology_learning.build_psychology_learning_catalog_receipt(
        bundle
    )
    if catalog_receipt is not None:
        artifact["psychology_learning_catalog_receipt"] = catalog_receipt
    return artifact


def _historic_v1_bundle(
    *,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.chdir(tmp_path)
    store = PsychologyLearningSeriesStore(trusted_provision=True)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)

    def build_v1(proposal_value, *, curriculum_version: str):
        return psychology_learning._build_confirmed_psychology_learning_catalog_for_template(
            proposal_value,
            curriculum_version=curriculum_version,
            controlled_template_version="1",
        )

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_build_confirmed_psychology_learning_catalog",
        build_v1,
    )
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    return resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )


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
    assert "catalog" not in bundle.model_dump(mode="json")


def test_each_learning_lesson_has_a_distinct_xhs_title_and_cover_hook() -> None:
    lessons = list_psychology_learning_series(
        series_id="after_work_rumination"
    )
    drafts = [render_psychology_learning_draft(lesson.runtime_contract) for lesson in lessons]

    assert len({draft["title"] for draft in drafts}) == len(lessons)
    assert len({draft["image_text"] for draft in drafts}) == len(lessons)
    assert all(len(str(draft["title"])) <= 22 for draft in drafts)


def test_builtin_learning_lesson_uses_controlled_template_v2_carousel() -> None:
    bundle = _starter_bundle()

    assert CURRENT_PSYCHOLOGY_LEARNING_CONTROLLED_TEMPLATE_VERSION == "2"
    assert bundle.runtime_contract["controlled_template_version"] == "2"

    draft = render_psychology_learning_draft(bundle.runtime_contract)
    image_plan = draft["image_plan"]
    assert image_plan["carousel_style"] == "psychology_text_card_v1"
    assert [slide["order"] for slide in image_plan["slides"]] == list(
        range(1, len(image_plan["slides"]) + 1)
    )
    assert [slide["role"] for slide in image_plan["slides"]] == [
        "cover_hook",
        "concrete_scene",
        "light_mechanism",
        "save_tool",
        "scope_boundary",
        "professional_boundary",
        "comment_prompt",
    ]
    visible = "\n".join(
        text
        for slide in image_plan["slides"]
        for text in (slide["headline"], *slide["body_lines"])
    )
    for approved_field in (
        "cover_text",
        "scene_anchor",
        "concept_label",
        "learning_goal",
        "approved_explanation",
        "applicability",
        "micro_exercise",
        "scope_limit",
        "professional_boundary",
        "comment_prompt",
    ):
        assert bundle.runtime_contract[approved_field] in visible


def test_historic_learning_template_v1_keeps_single_card_rendering() -> None:
    contract = deepcopy(_starter_bundle().runtime_contract)
    contract["controlled_template_version"] = "1"

    draft = render_psychology_learning_draft(contract)

    assert draft["image_plan"] == {
        "backend": "local_social_screenshot",
        "style": "iphone_notes",
        "role": "save_tool",
        "text_density": "low",
        "max_text_units": "3",
        "cover_text_strategy": "封面只放先别急着替自己判错和一条已批准的微练习。",
        "reason": "固定学习卡用低密度记事本截图，方便读者保存。",
        "prompt_focus": "低密度学习卡，不添加任何课程外结论。",
    }


def test_learning_template_version_rejects_unsupported_value() -> None:
    contract = deepcopy(_starter_bundle().runtime_contract)
    contract["controlled_template_version"] = "999"

    with pytest.raises(ValidationError, match="controlled template version"):
        parse_psychology_learning_runtime_contract(contract)


def test_learning_template_v2_keeps_approved_line_break_copy_inline() -> None:
    contract = deepcopy(_starter_bundle().runtime_contract)
    contract["lesson_title"] = "先识别\n## 伪标题"
    contract["cover_text"] = "第1课｜先识别\n## 伪标题"
    contract["learning_goal"] = "这一课只练“先识别\n## 伪标题”，先看眼前一步。"
    contract["scene_anchor"] = "今天又卡住时，先试试“先识别\n## 伪标题”"

    draft = render_psychology_learning_draft(contract)
    visible = "\n".join(
        text
        for slide in draft["image_plan"]["slides"]
        for text in (slide["headline"], *slide["body_lines"])
    )

    for field_name in ("lesson_title", "cover_text", "learning_goal", "scene_anchor"):
        assert contract[field_name].replace("\n", " ") in visible
    assert "\n## 伪标题" not in visible


@pytest.mark.parametrize(
    "tamper",
    (
        lambda slides: slides[0].update({"headline": "被改过的封面"}),
        lambda slides: slides[1].update({"role": "save_tool"}),
        lambda slides: slides[1].update({"order": 7}),
        lambda slides: slides[1].update({"slide_id": "changed"}),
        lambda slides: slides[1]["body_lines"].__setitem__(0, "被改过的一行"),
        lambda slides: slides.pop(),
        lambda slides: slides[1].update({"unknown": "field"}),
    ),
)
def test_learning_template_v2_rejects_any_carousel_tampering(tamper) -> None:
    bundle = _starter_bundle()
    draft = deepcopy(render_psychology_learning_draft(bundle.runtime_contract))
    tamper(draft["image_plan"]["slides"])

    errors = validate_psychology_learning_draft_contract(bundle.runtime_contract, draft)

    assert "draft must match the controlled lesson template" in errors


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


def test_non_strict_artifact_scan_accepts_only_exact_runtime_carousel_copies() -> None:
    draft = _valid_draft(_starter_bundle())
    image_plan = draft["image_plan"]
    artifact = {
        "playbook_id": "modern_psychology_post",
        "final_content": draft,
        "step_outputs": {
            "executor": {"draft_content": {"image_plan": image_plan}},
        },
        "content_review": {"image_plan": image_plan},
    }

    assert not contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=False,
    )

    artifact["content_review"] = {
        "image_plan": {
            **image_plan,
            "slides": [
                image_plan["slides"][0],
                {
                    **image_plan["slides"][1],
                    "body_lines": ["目录之外但表面安全的内页文案"],
                },
                *image_plan["slides"][2:],
            ],
        }
    }
    assert contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=False,
    )


@pytest.mark.parametrize("replacement", [None, []])
@pytest.mark.parametrize(
    "container_path",
    [
        ("content_review",),
        ("step_outputs", "executor", "draft_content"),
    ],
)
def test_non_strict_artifact_scan_rejects_non_object_runtime_carousel_copies(
    replacement: object,
    container_path: tuple[str, ...],
) -> None:
    draft = _valid_draft(_starter_bundle())
    image_plan = draft["image_plan"]
    artifact: dict[str, object] = {
        "playbook_id": "modern_psychology_post",
        "final_content": draft,
        "step_outputs": {
            "executor": {"draft_content": {"image_plan": image_plan}},
        },
        "content_review": {"image_plan": image_plan},
    }
    container: object = artifact
    for part in container_path:
        assert isinstance(container, dict)
        container = container[part]
    assert isinstance(container, dict)
    container["image_plan"] = replacement

    assert contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=False,
    )


def test_non_strict_artifact_scan_preserves_custom_catalog_pre_envelope_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The application may close a generic workflow artifact after this check."""
    monkeypatch.chdir(tmp_path)
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    catalog_receipt = psychology_learning.build_psychology_learning_catalog_receipt(
        bundle
    )
    assert catalog_receipt is not None
    generic_pre_envelope_artifact = {
        "playbook_id": "modern_psychology_post",
        "final_content": _valid_draft(bundle),
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": catalog.curriculum_version,
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_catalog_receipt": catalog_receipt,
    }

    assert not contains_psychology_learning_raw_provenance(
        generic_pre_envelope_artifact,
        strict_artifact_shape=False,
    )


@pytest.mark.parametrize(
    "tamper_field",
    (
        "psychology_learning_mode",
        "psychology_learning_gate",
        "psychology_learning_evidence_manifest",
    ),
)
def test_strict_artifact_scan_rejects_forged_learning_receipt_fields(
    tamper_field: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A shape-valid receipt still has to exactly match its selected lesson."""
    monkeypatch.chdir(tmp_path)
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    artifact = _closed_learning_artifact(bundle)

    if tamper_field == "psychology_learning_mode":
        artifact[tamper_field] = "not-learning-series"
    elif tamper_field == "psychology_learning_gate":
        artifact[tamper_field] = {
            **artifact[tamper_field],  # type: ignore[arg-type]
            "status": "failed",
        }
    else:
        artifact[tamper_field] = {
            **artifact[tamper_field],  # type: ignore[arg-type]
            "lesson_fingerprint": "lesson:forged-manifest",
        }

    assert contains_psychology_learning_raw_provenance(artifact)


def test_strict_artifact_scan_allows_only_safe_carousel_generation_evidence() -> None:
    artifact = _closed_learning_artifact(_starter_bundle())
    artifact["image_generation"] = {
        "status": "committed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "manifest_sha256": "a" * 64,
    }

    assert not contains_psychology_learning_raw_provenance(artifact)

    artifact["image_generation"] = {
        **artifact["image_generation"],  # type: ignore[arg-type]
        "manifest_path": "/private/generated/set/manifest.json",
    }
    assert contains_psychology_learning_raw_provenance(artifact)


def test_historic_v1_artifact_keeps_only_the_frozen_single_card_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    historic_artifact = _closed_learning_artifact(
        _historic_v1_bundle(monkeypatch=monkeypatch, tmp_path=tmp_path)
    )
    historic_artifact["image_generation"] = {
        "status": "generated",
        "renderer": "ptsm_local_renderer",
    }

    assert not contains_psychology_learning_raw_provenance(historic_artifact)

    current_artifact = _closed_learning_artifact(_starter_bundle())
    current_artifact["image_generation"] = historic_artifact["image_generation"]
    assert contains_psychology_learning_raw_provenance(current_artifact)

    historic_artifact["image_generation"] = {
        **historic_artifact["image_generation"],  # type: ignore[arg-type]
        "generated_image_paths": ["/private/historic-card.png"],
    }
    assert contains_psychology_learning_raw_provenance(historic_artifact)


def test_strict_artifact_scan_allows_only_bounded_carousel_failure_evidence() -> None:
    artifact = _closed_learning_artifact(_starter_bundle())
    artifact["image_generation"] = {
        "status": "failed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "reason": "psychology_carousel_generation_failed",
    }

    assert not contains_psychology_learning_raw_provenance(artifact)

    artifact["image_generation"] = {
        **artifact["image_generation"],  # type: ignore[arg-type]
        "renderer_error": "/private/generated/page-03.png",
    }
    assert contains_psychology_learning_raw_provenance(artifact)


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
        ("诊疗", None, "unsafe clinical or crisis content"),
        ("診療", None, "unsafe clinical or crisis content"),
        ("医疗", None, "unsafe clinical or crisis content"),
        ("醫療", None, "unsafe clinical or crisis content"),
        ("疗法", None, "unsafe clinical or crisis content"),
        ("療法", None, "unsafe clinical or crisis content"),
        ("诊治", None, "unsafe clinical or crisis content"),
        ("診治", None, "unsafe clinical or crisis content"),
        ("医治", None, "unsafe clinical or crisis content"),
        ("醫治", None, "unsafe clinical or crisis content"),
        ("配药", None, "unsafe clinical or crisis content"),
        ("配藥", None, "unsafe clinical or crisis content"),
        ("药剂", None, "unsafe clinical or crisis content"),
        ("藥劑", None, "unsafe clinical or crisis content"),
        ("药品", None, "unsafe clinical or crisis content"),
        ("藥品", None, "unsafe clinical or crisis content"),
        ("诊\u00b7疗", None, "unsafe clinical or crisis content"),
        ("醫\u2044療", None, "unsafe clinical or crisis content"),
        ("配\u200b藥", None, "unsafe clinical or crisis content"),
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
        "自x杀",
        "自1杀",
        "诊x断",
        "治x疗",
        "selfxharm",
    ),
)
def test_proposal_validation_rejects_marker_bypasses_with_inserted_text(
    topic: str,
) -> None:
    with pytest.raises(ValidationError, match="unsafe clinical or crisis content"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    "topic",
    (
        "self.....harm",
        "self" + "!" * 20 + "harm",
        "selfxxxxxharm",
        "self" + "x" * 52 + "harm",
        "ptxsd",
        "p75d",
    ),
)
def test_proposal_validation_rejects_extended_english_marker_bypasses(
    topic: str,
) -> None:
    with pytest.raises(ValidationError, match="unsafe clinical or crisis content"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    "topic",
    (
        "焦虑症",
        "焦慮症",
        "强迫症",
        "強迫症",
        "PTSD",
        "创伤后应激障碍",
        "創傷後應激障礙",
        "therapy",
        "焦\u00b7虑症",
    ),
)
def test_proposal_validation_rejects_direct_clinical_category_markers(
    topic: str,
) -> None:
    with pytest.raises(ValidationError, match="unsafe clinical or crisis content"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    "topic",
    (
        "例子.中国",
        "xn--fsqu00a.xn--fiqs8s",
        "example dot com",
        "example[dot]com",
        "reference: paper",
        "author: somebody",
        "link: somebody",
    ),
)
def test_proposal_validation_rejects_direct_source_shapes(topic: str) -> None:
    with pytest.raises(ValidationError, match="source locator or reference"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    "topic",
    (
        "情" + " " * 1000 + "绪",
        "情" + "\u200b" * 1000 + "绪",
    ),
)
def test_proposal_validation_limits_original_display_text_length(topic: str) -> None:
    with pytest.raises(ValidationError, match="between 2 and 60 characters"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    "topic",
    (
        " " * 1000 + "情绪",
        "情绪" + " " * 1000,
        "\u00a0" * 1000 + "情绪",
    ),
)
def test_proposal_validation_rejects_raw_oversized_topic_before_trim(
    topic: str,
) -> None:
    with pytest.raises(ValidationError, match="between 2 and 60 characters"):
        PsychologyLearningSeriesPlanIntent(topic=topic)


@pytest.mark.parametrize(
    ("kwargs", "max_length"),
    (
        ({"title": "标题" + "\u00a0" * 1000}, 60),
        ({"title": "标题", "goal": "目标" + "\u00a0" * 1000}, 120),
    ),
)
def test_proposal_validation_rejects_raw_oversized_outline_text_before_trim(
    kwargs: dict[str, str],
    max_length: int,
) -> None:
    with pytest.raises(
        ValidationError,
        match=rf"between 2 and {max_length} characters",
    ):
        PsychologyLearningOutlineItem(**kwargs)


def test_proposal_validation_keeps_reasonable_outer_whitespace_behavior() -> None:
    intent = PsychologyLearningSeriesPlanIntent(topic="  情绪整理  ")
    item = PsychologyLearningOutlineItem(title="  先记录感受  ")

    assert intent.topic == "情绪整理"
    assert item.title == "先记录感受"


def test_proposal_validation_rejects_raw_oversized_outline_id_before_scanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def should_not_scan(value: object) -> None:
        raise AssertionError(f"raw scanner should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_assert_no_raw_provenance",
        should_not_scan,
    )

    with pytest.raises(ValidationError, match="between 2 and 80 characters"):
        PsychologyLearningOutlineItem(
            id=" " * 1000 + "valid_id",
            title="先记录感受",
        )


@pytest.mark.parametrize(
    ("payload", "error"),
    (
        (
            {"topic": "情绪整理", "extra": "x" * 1007},
            "plan intent must not contain unknown fields",
        ),
        (
            {
                "topic": "情绪整理",
                "outline": [
                    {"title": "先记录感受", "extra": "x" * 1007},
                    {"title": "再回顾线索"},
                ],
            },
            "outline item must not contain unknown fields",
        ),
        (
            {
                "topic": "情绪整理",
                "outline": ["x" * 1007, {"title": "再回顾线索"}],
            },
            "outline item must be a concrete dict",
        ),
    ),
)
def test_proposal_validation_rejects_invalid_raw_shapes_before_scanning(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    error: str,
) -> None:
    def should_not_scan(value: object) -> None:
        raise AssertionError(f"raw scanner should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_assert_no_raw_provenance",
        should_not_scan,
    )

    with pytest.raises(ValidationError, match=error):
        PsychologyLearningSeriesPlanIntent.model_validate(payload)


@pytest.mark.parametrize(
    ("payload", "error"),
    (
        (
            {"topic": "情绪整理", "x" * 1007: "unexpected"},
            "plan intent field names must contain at most 80 characters",
        ),
        (
            {
                "topic": "情绪整理",
                "outline": [
                    {"title": "先记录感受", "x" * 1007: "unexpected"},
                    {"title": "再回顾线索"},
                ],
            },
            "outline item field names must contain at most 80 characters",
        ),
    ),
)
def test_proposal_validation_bounds_unknown_field_names_before_scanning_or_normalizing(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
    error: str,
) -> None:
    def should_not_scan(value: object) -> None:
        raise AssertionError(f"raw scanner should not receive {value!r}")

    def should_not_normalize(value: object) -> str:
        raise AssertionError(f"key normalizer should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_assert_no_raw_provenance",
        should_not_scan,
    )
    monkeypatch.setattr(
        psychology_learning,
        "_normalized_security_key",
        should_not_normalize,
    )

    with pytest.raises(ValidationError, match=error):
        PsychologyLearningSeriesPlanIntent.model_validate(payload)


def test_proposal_validation_rejects_too_many_raw_field_names_before_normalizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def should_not_normalize(value: object) -> str:
        raise AssertionError(f"key normalizer should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_normalized_security_key",
        should_not_normalize,
    )

    with pytest.raises(
        ValidationError,
        match="plan intent must not contain unknown fields",
    ):
        PsychologyLearningSeriesPlanIntent.model_validate(
            {
                "topic": "情绪整理",
                "outline": [{"title": "先记录感受"}, {"title": "再回顾线索"}],
                "extra": "unexpected",
            }
        )


def test_proposal_validation_rejects_non_string_raw_field_names_before_normalizing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def should_not_normalize(value: object) -> str:
        raise AssertionError(f"key normalizer should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_normalized_security_key",
        should_not_normalize,
    )

    with pytest.raises(
        ValidationError,
        match="plan intent field names must be strings",
    ):
        PsychologyLearningSeriesPlanIntent.model_validate(
            {"topic": "情绪整理", 1: "unexpected"}
        )


def test_proposal_validation_keeps_bounded_obfuscated_provenance_key_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_normalizer = psychology_learning._normalized_security_key
    normalized_values: list[object] = []

    def track_normalizer(value: object) -> str:
        normalized_values.append(value)
        return original_normalizer(value)

    def should_not_scan(value: object) -> None:
        raise AssertionError(f"raw scanner should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_normalized_security_key",
        track_normalizer,
    )
    monkeypatch.setattr(
        psychology_learning,
        "_assert_no_raw_provenance",
        should_not_scan,
    )

    with pytest.raises(ValidationError, match="provenance"):
        PsychologyLearningSeriesPlanIntent.model_validate(
            {
                "topic": "情绪整理",
                "outline": [
                    {
                        "title": "先记录感受",
                        "source\u200b_refs": "hidden-reference",
                    },
                    {"title": "再回顾线索"},
                ],
            }
        )

    assert normalized_values == ["source\u200b_refs"]


def test_proposal_validation_rejects_custom_top_level_mapping_before_scanning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CustomTopLevelMapping(Mapping[str, object]):
        def __getitem__(self, key: str) -> object:
            if key == "topic":
                return "情绪整理"
            raise KeyError(key)

        def __iter__(self):
            return iter(("topic",))

        def __len__(self) -> int:
            return 1

        def items(self):
            raise AssertionError("raw scanner should not iterate custom mappings")

    def should_not_scan(value: object) -> None:
        raise AssertionError(f"raw scanner should not receive {value!r}")

    monkeypatch.setattr(
        psychology_learning,
        "_assert_no_raw_provenance",
        should_not_scan,
    )

    with pytest.raises(ValidationError, match="plan intent must be a concrete dict"):
        PsychologyLearningSeriesPlanIntent.model_validate(CustomTopLevelMapping())


def test_proposal_validation_rejects_deceptive_outline_sequence_before_iteration() -> None:
    class DeceptiveOutline(list[dict[str, str]]):
        def __len__(self) -> int:
            return 2

        def __iter__(self):
            raise AssertionError("outline should not be consumed")

    with pytest.raises(ValidationError, match="outline must be a concrete list or tuple"):
        PsychologyLearningSeriesPlanIntent(
            topic="情绪整理",
            outline=DeceptiveOutline(),
        )


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
        "reference notes",
        "下班后的note card整理",
    ),
)
def test_proposal_validation_keeps_safe_reader_visible_unicode_text_unchanged(
    topic: str,
) -> None:

    intent = PsychologyLearningSeriesPlanIntent(topic=topic)

    assert intent.topic == topic


def test_custom_selection_requires_an_explicit_confirmed_revision(
    tmp_path,
) -> None:
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    root = tmp_path / "series-store"

    with pytest.raises(ValueError, match="explicit curriculum_version"):
        resolve_psychology_learning_selection(
            series_id=proposal.series_id_candidate,
            lesson_id="notice",
            catalog_root=root,
        )

    with pytest.raises(ValueError, match="unknown psychology learning catalog revision"):
        resolve_psychology_learning_selection(
            series_id=proposal.series_id_candidate,
            lesson_id="notice",
            curriculum_version="1",
            catalog_root=root,
        )

    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    resolved = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=root,
    )

    assert resolved.catalog is not None
    assert resolved.catalog.origin == "user_confirmed"
    assert resolved.catalog.approval.proposal_fingerprint == proposal.proposal_fingerprint
    assert [item.publication_order for item in resolved.catalog.publication_plan.items] == [
        1,
        2,
    ]


@pytest.mark.parametrize("storage_directory", ("proposals", "confirmations", "catalogs"))
def test_custom_selection_rejects_a_rebound_immutable_storage_directory(
    tmp_path: Path,
    storage_directory: str,
) -> None:
    root = tmp_path / "series-store"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    source = root / storage_directory
    outside = tmp_path / "outside" / storage_directory
    outside.parent.mkdir()
    shutil.copytree(source, outside)
    shutil.rmtree(source)
    source.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="psychology learning|catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
            catalog_root=root,
        )


def test_custom_selection_rejects_a_coherent_child_rebind_before_first_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A reader must not adopt a replacement tree after pinning only its root."""
    root = tmp_path / "series-store"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    former_root = tmp_path / "former-tree"
    replacement_root = tmp_path / "replacement-tree"
    former_root.mkdir()
    replacement_root.mkdir()
    for directory_name in ("proposals", "confirmations", "catalogs"):
        shutil.copytree(root / directory_name, replacement_root / directory_name)
    original_open_directory = (
        psychology_learning._PinnedPsychologyLearningCatalogReader._open_directory
    )
    rebound = False

    def rebind_before_first_child_read(self, *components: str) -> int:
        nonlocal rebound
        if components and not rebound:
            rebound = True
            for directory_name in ("proposals", "confirmations", "catalogs"):
                (root / directory_name).rename(former_root / directory_name)
                (replacement_root / directory_name).rename(root / directory_name)
        return original_open_directory(self, *components)

    monkeypatch.setattr(
        psychology_learning._PinnedPsychologyLearningCatalogReader,
        "_open_directory",
        rebind_before_first_child_read,
    )

    with pytest.raises(ValueError, match="psychology learning|catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
            catalog_root=root,
        )

    assert rebound


@pytest.mark.parametrize("storage_directory", ("proposals", "confirmations", "catalogs"))
def test_custom_selection_rejects_a_hard_linked_immutable_snapshot(
    tmp_path: Path,
    storage_directory: str,
) -> None:
    root = tmp_path / "series-store"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = {
        "proposals": root / "proposals" / f"{proposal.proposal_id}.json",
        "confirmations": psychology_learning.psychology_learning_series_catalog_confirmation_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=root,
        ),
        "catalogs": psychology_learning.psychology_learning_series_catalog_snapshot_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=root,
        ),
    }[storage_directory]
    os.link(snapshot_path, tmp_path / f"{storage_directory}-peer.json")

    with pytest.raises(ValueError, match="psychology learning|catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
            catalog_root=root,
        )


def test_builtin_catalog_stays_unchanged_when_a_custom_catalog_root_is_injected(
    tmp_path,
) -> None:
    baseline = list_psychology_learning_series(series_id="after_work_rumination")
    injected = list_psychology_learning_series(
        series_id="after_work_rumination",
        catalog_root=tmp_path / "series-store",
    )

    assert injected == baseline
    assert [lesson.lesson_id for lesson in injected] == [
        "notice_the_loop",
        "facts_and_stories",
        "control_and_next_step",
        "leave_work_signal",
        "close_the_replay",
        "support_boundary",
    ]
