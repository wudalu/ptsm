from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
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
