from __future__ import annotations

import errno
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
import ptsm.domain.psychology_learning as psychology_learning_domain
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.domain.psychology_learning import (
    PsychologyLearningOutlineItem,
    list_psychology_learning_series,
    psychology_learning_series_catalog_confirmation_path,
    psychology_learning_series_catalog_snapshot_path,
    psychology_learning_series_proposal_snapshot_path,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
)


def test_plan_psychology_learning_series_synthesizes_a_stable_safe_four_step_proposal() -> None:
    first = plan_psychology_learning_series(topic="下班后的脑内回放")
    second = plan_psychology_learning_series(topic="下班后的脑内回放")

    assert first.proposal_id == second.proposal_id
    assert first.proposal_fingerprint == second.proposal_fingerprint
    assert first.catalog.series_id.startswith("custom_psychology_")
    assert first.catalog.series_title == "下班后的脑内回放学习系列"
    assert first.catalog.runnable is False
    assert len(first.catalog.lessons) == 4
    assert [lesson.lesson_number for lesson in first.catalog.lessons] == [1, 2, 3, 4]
    assert [item.publication_order for item in first.publication_plan.items] == [1, 2, 3, 4]
    assert first.review.status == "safe_for_confirmation_review"
    assert "proposal-only" in first.review.safety_checks


def test_plan_psychology_learning_series_rejects_deceptive_outline_before_iteration() -> None:
    class DeceptiveOutline(list[dict[str, str]]):
        def __len__(self) -> int:
            return 2

        def __iter__(self):
            raise AssertionError("outline should not be materialized")

    with pytest.raises(TypeError, match="outline must be a concrete list or tuple"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=DeceptiveOutline(),
        )


def test_plan_psychology_learning_series_does_not_consume_non_sequence_outline() -> None:
    def unbounded_outline():
        raise AssertionError("outline should not be consumed")
        yield {"title": "never reached"}

    with pytest.raises(TypeError, match="outline must be a concrete list or tuple"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=unbounded_outline(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "outline",
    (
        [
            {"title": "先记录感受"},
            {"title": "再回顾线索"},
        ],
        (
            {"title": "先记录感受"},
            {"title": "再回顾线索"},
        ),
    ),
)
def test_plan_psychology_learning_series_accepts_concrete_outline_containers(
    outline: list[dict[str, str]] | tuple[dict[str, str], ...],
) -> None:
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=outline,
    )

    assert len(proposal.catalog.lessons) == 2


def test_plan_psychology_learning_series_accepts_validated_outline_items() -> None:
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            PsychologyLearningOutlineItem(id="notice", title="先记录感受"),
            PsychologyLearningOutlineItem(id="review", title="再回顾线索"),
        ),
    )

    assert [lesson.lesson_id for lesson in proposal.catalog.lessons] == [
        "notice",
        "review",
    ]


def test_plan_psychology_learning_series_rejects_oversized_concrete_outline() -> None:
    with pytest.raises(ValueError, match="outline must contain between 2 and 6 lessons"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=[{"title": "只做数量检查"}] * 7,
        )


def test_confirmed_custom_series_requires_exact_persisted_proposal_fingerprint(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )

    with pytest.raises(ValueError, match="unknown psychology learning proposal"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    store.persist_proposal(proposal)

    with pytest.raises(ValueError, match="proposal fingerprint"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint="proposal:wrong",
        )

    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert catalog.origin == "user_confirmed"
    assert catalog.curriculum_version == "1"
    assert catalog.approval.proposal_id == proposal.proposal_id
    assert catalog.approval.proposal_fingerprint == proposal.proposal_fingerprint
    assert catalog.publication_plan.items[0].publication_order == 1
    assert store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    ) == catalog


def test_confirmation_appends_custom_revision_and_keeps_old_snapshot_resolvable(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first_proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second_proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "understand", "title": "再区分事实和猜测"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )

    first_catalog = store.confirm(
        proposal_id=store.persist_proposal(first_proposal).proposal_id,
        proposal_fingerprint=first_proposal.proposal_fingerprint,
    )
    first_snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=first_catalog.series_id,
        curriculum_version=first_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    first_snapshot_bytes = first_snapshot_path.read_bytes()
    second_catalog = store.confirm(
        proposal_id=store.persist_proposal(second_proposal).proposal_id,
        proposal_fingerprint=second_proposal.proposal_fingerprint,
    )

    assert first_catalog.curriculum_version == "1"
    assert second_catalog.curriculum_version == "2"
    assert [lesson.lesson_id for lesson in first_catalog.lessons] == [
        "notice",
        "practice",
    ]
    assert [lesson.lesson_id for lesson in second_catalog.lessons] == [
        "notice",
        "understand",
        "practice",
    ]
    assert first_snapshot_path.read_bytes() == first_snapshot_bytes

    historic = resolve_psychology_learning_selection(
        series_id=first_catalog.series_id,
        lesson_id="practice",
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    latest = list_psychology_learning_series(
        series_id=second_catalog.series_id,
        catalog_root=store.catalog_root,
    )

    assert historic.lesson.lesson_number == 2
    assert [lesson.lesson_id for lesson in latest] == [
        "notice",
        "understand",
        "practice",
    ]


def test_custom_revision_history_fails_closed_when_an_older_snapshot_is_missing(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "understand", "title": "再区分事实和猜测"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(first)
    first_catalog = store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(second)
    second_catalog = store.confirm(
        proposal_id=second.proposal_id,
        proposal_fingerprint=second.proposal_fingerprint,
    )
    psychology_learning_series_catalog_snapshot_path(
        series_id=first_catalog.series_id,
        curriculum_version=first_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).unlink()

    with pytest.raises(ValueError, match="catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=second_catalog.series_id,
            lesson_id="notice",
            curriculum_version=second_catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )


def test_custom_revision_history_fails_closed_when_an_older_snapshot_is_tampered(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "understand", "title": "再区分事实和猜测"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(first)
    first_catalog = store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(second)
    second_catalog = store.confirm(
        proposal_id=second.proposal_id,
        proposal_fingerprint=second.proposal_fingerprint,
    )
    first_path = psychology_learning_series_catalog_snapshot_path(
        series_id=first_catalog.series_id,
        curriculum_version=first_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    tampered = json.loads(first_path.read_text(encoding="utf-8"))
    tampered["catalog_digest"] = "catalog:tampered"
    first_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid psychology learning catalog revision"):
        resolve_psychology_learning_selection(
            series_id=second_catalog.series_id,
            lesson_id="notice",
            curriculum_version=second_catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )


def test_confirmation_never_reuses_a_deleted_terminal_revision_number(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "understand", "title": "再区分事实和猜测"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    third = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "review", "title": "回顾一个有效动作"},
        ),
    )
    store.persist_proposal(first)
    store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(second)
    second_catalog = store.confirm(
        proposal_id=second.proposal_id,
        proposal_fingerprint=second.proposal_fingerprint,
    )
    psychology_learning_series_catalog_snapshot_path(
        series_id=second_catalog.series_id,
        curriculum_version=second_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).unlink()
    store.persist_proposal(third)

    with pytest.raises(ValueError, match="catalog revision"):
        store.confirm(
            proposal_id=third.proposal_id,
            proposal_fingerprint=third.proposal_fingerprint,
        )


def test_deleting_a_series_catalog_directory_preserves_its_confirmation_history(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    replacement = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "review", "title": "回顾一个有效动作"},
        ),
    )
    store.persist_proposal(first)
    catalog = store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(replacement)
    confirmation_path = psychology_learning_series_catalog_confirmation_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )

    shutil.rmtree(store.catalog_root / "catalogs" / catalog.series_id)

    assert confirmation_path.exists()
    with pytest.raises(ValueError, match="catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )
    with pytest.raises(ValueError, match="catalog revision history"):
        store.confirm(
            proposal_id=replacement.proposal_id,
            proposal_fingerprint=replacement.proposal_fingerprint,
        )


def test_confirmation_does_not_recover_a_nonterminal_missing_snapshot(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "review", "title": "回顾一个有效动作"},
        ),
    )
    store.persist_proposal(first)
    first_catalog = store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(second)
    store.confirm(
        proposal_id=second.proposal_id,
        proposal_fingerprint=second.proposal_fingerprint,
    )
    psychology_learning_series_catalog_snapshot_path(
        series_id=first_catalog.series_id,
        curriculum_version=first_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).unlink()

    with pytest.raises(ValueError, match="catalog revision history"):
        store.confirm(
            proposal_id=first.proposal_id,
            proposal_fingerprint=first.proposal_fingerprint,
        )


def test_confirmation_recovers_only_the_matching_pending_snapshot_write(
    tmp_path,
    monkeypatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    different_proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "review", "title": "回顾一个有效动作"},
        ),
    )
    store.persist_proposal(proposal)
    store.persist_proposal(different_proposal)
    expected_snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    expected_confirmation_path = psychology_learning_series_catalog_confirmation_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    original_write_new_json = psychology_learning_series_use_case._write_new_json
    snapshot_write_failed = False

    def fail_once_for_catalog_snapshot(path, payload) -> None:
        nonlocal snapshot_write_failed
        if path == expected_snapshot_path and not snapshot_write_failed:
            snapshot_write_failed = True
            raise OSError("injected catalog snapshot write failure")
        original_write_new_json(path, payload)

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_write_new_json",
        fail_once_for_catalog_snapshot,
    )

    with pytest.raises(OSError, match="injected catalog snapshot write failure"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert expected_confirmation_path.exists()
    assert not expected_snapshot_path.exists()
    with pytest.raises(ValueError, match="catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=proposal.series_id_candidate,
            lesson_id="notice",
            curriculum_version="1",
            catalog_root=store.catalog_root,
        )
    with pytest.raises(ValueError, match="catalog revision history"):
        list_psychology_learning_series(
            series_id=proposal.series_id_candidate,
            curriculum_version="1",
            catalog_root=store.catalog_root,
        )
    with pytest.raises(ValueError, match="catalog revision history"):
        store.confirm(
            proposal_id=different_proposal.proposal_id,
            proposal_fingerprint=different_proposal.proposal_fingerprint,
        )

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_write_new_json",
        original_write_new_json,
    )
    recovered = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert recovered.curriculum_version == "1"
    assert expected_snapshot_path.exists()
    assert resolve_psychology_learning_selection(
        series_id=recovered.series_id,
        lesson_id="notice",
        curriculum_version=recovered.curriculum_version,
        catalog_root=store.catalog_root,
    ).lesson.lesson_id == "notice"


def test_confirmation_retry_after_ledger_write_failure_leaves_no_snapshot_orphan(
    tmp_path,
    monkeypatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    expected_snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    expected_confirmation_path = psychology_learning_series_catalog_confirmation_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    original_link = psychology_learning_series_use_case.os.link

    def fail_for_confirmation_record(source, destination, *args, **kwargs) -> None:
        if destination == expected_confirmation_path:
            raise OSError("injected confirmation ledger write failure")
        return original_link(source, destination, *args, **kwargs)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "link",
        fail_for_confirmation_record,
    )

    with pytest.raises(OSError, match="injected confirmation ledger write failure"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert not expected_confirmation_path.exists()
    assert not expected_snapshot_path.exists()
    assert not expected_confirmation_path.parent.exists()

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "link",
        original_link,
    )
    confirmed = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert confirmed.curriculum_version == "1"
    assert expected_confirmation_path.exists()
    assert expected_snapshot_path.exists()


def test_confirmation_retries_after_an_abandoned_empty_ledger_directory(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    confirmation_path = psychology_learning_series_catalog_confirmation_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    confirmation_path.parent.mkdir(parents=True)

    confirmed = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert confirmed.curriculum_version == "1"
    assert confirmation_path.exists()


def test_confirmation_ignores_staging_cleanup_failure_after_durable_ledger_write(
    tmp_path,
    monkeypatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    original_unlink = Path.unlink
    cleanup_failed = False

    def fail_one_temp_cleanup(path, *args, **kwargs) -> None:
        nonlocal cleanup_failed
        if path.suffix == ".tmp" and not cleanup_failed:
            cleanup_failed = True
            raise OSError("injected staging cleanup failure")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_one_temp_cleanup)

    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert cleanup_failed
    assert tuple((store.catalog_root / "confirmations" / ".staging").glob("*.tmp"))
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).lesson.lesson_id == "notice"


def test_custom_revision_history_fails_closed_when_a_confirmation_record_is_missing(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    first = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    second = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "understand", "title": "再区分事实和猜测"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(first)
    first_catalog = store.confirm(
        proposal_id=first.proposal_id,
        proposal_fingerprint=first.proposal_fingerprint,
    )
    store.persist_proposal(second)
    second_catalog = store.confirm(
        proposal_id=second.proposal_id,
        proposal_fingerprint=second.proposal_fingerprint,
    )
    psychology_learning_series_catalog_confirmation_path(
        series_id=second_catalog.series_id,
        curriculum_version=second_catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).unlink()

    with pytest.raises(ValueError, match="catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=first_catalog.series_id,
            lesson_id="notice",
            curriculum_version=first_catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )


def test_confirmed_custom_lessons_are_controlled_and_progress_is_a_separate_sidecar(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "notice",
                "title": "先识别重复时刻",
                "goal": "在一个具体时刻停下来看看。",
            },
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    first_lesson = catalog.lessons[0]
    serialized = catalog.model_dump(mode="json")
    assert "https://" not in str(serialized)
    assert "source:" not in str(serialized)
    assert "在一个具体时刻停下来看看。" not in str(serialized)
    assert first_lesson.source_refs == (f"approval:{catalog.approval.approval_id}",)
    assert len(first_lesson.post_title) <= 22
    assert first_lesson.runtime_contract["lesson_title"] == "先识别重复时刻"
    assert "proposal" not in first_lesson.runtime_contract
    rendered = render_psychology_learning_draft(first_lesson.runtime_contract)
    assert validate_psychology_learning_draft_contract(
        first_lesson.runtime_contract,
        rendered,
    ) == []

    progress = store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=(first_lesson.lesson_id,),
    )

    assert progress.completed_lesson_ids == (first_lesson.lesson_id,)
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ) == progress
    with pytest.raises(ValueError, match="unknown psychology learning lesson_id"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=("unknown_lesson",),
        )
    with pytest.raises(ValueError, match="completed_lesson_ids must be unique"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=(first_lesson.lesson_id, first_lesson.lesson_id),
        )


def test_custom_catalog_resolution_fails_closed_until_matching_retry_and_for_tampered_snapshots(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    catalog_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    catalog_path.unlink()

    with pytest.raises(ValueError, match="catalog revision"):
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )
    recovered = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert recovered == catalog
    assert catalog_path.exists()

    tampered_store = PsychologyLearningSeriesStore(
        catalog_root=tmp_path / "tampered-series-store"
    )
    tampered_store.persist_proposal(proposal)
    recreated = tampered_store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    recreated_path = psychology_learning_series_catalog_snapshot_path(
        series_id=recreated.series_id,
        curriculum_version=recreated.curriculum_version,
        catalog_root=tampered_store.catalog_root,
    )
    tampered = json.loads(recreated_path.read_text(encoding="utf-8"))
    tampered["catalog_digest"] = "catalog:tampered"
    recreated_path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid psychology learning catalog revision"):
        list_psychology_learning_series(
            series_id=recreated.series_id,
            curriculum_version=recreated.curriculum_version,
            catalog_root=tampered_store.catalog_root,
        )

    missing_proposal_store = PsychologyLearningSeriesStore(
        catalog_root=tmp_path / "missing-proposal-series-store"
    )
    missing_proposal_store.persist_proposal(proposal)
    restored = missing_proposal_store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    proposal_path = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=missing_proposal_store.catalog_root,
    )
    proposal_path.unlink()

    with pytest.raises(ValueError, match="invalid psychology learning catalog revision"):
        resolve_psychology_learning_selection(
            series_id=restored.series_id,
            lesson_id="notice",
            curriculum_version=restored.curriculum_version,
            catalog_root=missing_proposal_store.catalog_root,
        )


def test_write_new_json_syncs_temp_before_link_and_destination_directory_after(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "proposals" / "proposal.json"
    path.parent.mkdir(parents=True)
    (path.parent.parent / ".staging").mkdir()
    events: list[str] = []
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_link = psychology_learning_series_use_case.os.link

    def record_fsync(fd: int) -> None:
        kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        events.append(f"{kind}-fsync")
        original_fsync(fd)

    def record_link(source: Path | str, destination: Path | str, *args: object) -> None:
        events.append("link")
        original_link(source, destination, *args)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", record_fsync)
    monkeypatch.setattr(psychology_learning_series_use_case.os, "link", record_link)

    psychology_learning_series_use_case._write_new_json(path, {"value": "one"})

    link_index = events.index("link")
    assert any(
        index < link_index and event == "file-fsync"
        for index, event in enumerate(events)
    )
    assert any(
        index > link_index and event == "directory-fsync"
        for index, event in enumerate(events)
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "one"}


def test_write_new_json_file_sync_failure_leaves_immutable_target_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "proposals" / "proposal.json"
    path.parent.mkdir(parents=True)
    staging_directory = path.parent.parent / ".staging"
    staging_directory.mkdir()
    original_fsync = psychology_learning_series_use_case.os.fsync

    def fail_file_fsync(fd: int) -> None:
        if stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("injected temporary file fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_file_fsync,
    )

    with pytest.raises(OSError, match="temporary file fsync failure"):
        psychology_learning_series_use_case._write_new_json(path, {"value": "one"})

    assert not path.exists()
    assert not tuple(staging_directory.glob("*.tmp"))


def test_immutable_retry_syncs_a_parent_entry_left_after_failed_directory_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "series-store"
    path = root / "proposals" / "proposal.json"
    root.mkdir()
    (root / ".staging").mkdir()
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_rmdir = Path.rmdir
    fd_paths: dict[int, Path] = {}

    def record_open(path: Path | str, flags: int, *args: int) -> int:
        fd = original_open(path, flags, *args)
        fd_paths[fd] = Path(path)
        return fd

    def fail_root_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == root and path.parent.is_dir():
            raise OSError(errno.ENOTSUP, "injected parent directory fsync failure")
        original_fsync(fd)

    def preserve_target_directory(directory: Path, *args: object) -> None:
        if directory == path.parent:
            raise OSError("injected best-effort cleanup failure")
        original_rmdir(directory, *args)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_root_directory_fsync,
    )
    monkeypatch.setattr(Path, "rmdir", preserve_target_directory)

    with pytest.raises(OSError, match="parent directory fsync failure"):
        psychology_learning_series_use_case._write_new_json(path, {"value": "one"})

    assert path.parent.is_dir()
    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", original_fsync)
    monkeypatch.setattr(Path, "rmdir", original_rmdir)
    fd_paths.clear()
    retry_sync_paths: list[Path] = []

    def record_retry_fsync(fd: int) -> None:
        directory = fd_paths.get(fd)
        if directory is not None:
            retry_sync_paths.append(directory)
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        record_retry_fsync,
    )

    psychology_learning_series_use_case._write_new_json(path, {"value": "one"})

    assert root in retry_sync_paths
    assert path.exists()


def test_domain_custom_catalog_reads_reject_visible_snapshot_until_directory_sync_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    fd_paths: dict[int, Path] = {}

    def record_open(path: Path | str, flags: int, *args: int) -> int:
        fd = original_open(path, flags, *args)
        fd_paths[fd] = Path(path)
        return fd

    def fail_snapshot_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == snapshot_path.parent and snapshot_path.exists():
            raise OSError(errno.ENOTSUP, "injected snapshot directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_snapshot_directory_fsync,
    )

    with pytest.raises(OSError, match="snapshot directory fsync failure"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert snapshot_path.exists()
    with pytest.raises(ValueError, match="catalog revision history"):
        list_psychology_learning_series(
            series_id=proposal.series_id_candidate,
            curriculum_version="1",
            catalog_root=store.catalog_root,
        )
    with pytest.raises(ValueError, match="catalog revision history"):
        resolve_psychology_learning_selection(
            series_id=proposal.series_id_candidate,
            lesson_id="notice",
            curriculum_version="1",
            catalog_root=store.catalog_root,
        )

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", original_fsync)

    assert list_psychology_learning_series(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    assert resolve_psychology_learning_selection(
        series_id=proposal.series_id_candidate,
        lesson_id="notice",
        curriculum_version="1",
        catalog_root=store.catalog_root,
    ).lesson.lesson_id == "notice"


def test_immutable_directory_sync_failure_requires_a_durable_retry_without_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    path = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=store.catalog_root,
    )
    path.parent.mkdir(parents=True)
    (path.parent.parent / ".staging").mkdir()
    original_fsync = psychology_learning_series_use_case.os.fsync

    def fail_destination_directory_fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode) and path.exists():
            raise OSError(errno.ENOTSUP, "injected destination directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_destination_directory_fsync,
    )

    with pytest.raises(OSError, match="destination directory fsync failure"):
        store.persist_proposal(proposal)

    persisted_bytes = path.read_bytes()
    retry_events: list[str] = []

    def record_retry_fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            retry_events.append("directory-fsync")
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        record_retry_fsync,
    )

    assert store.persist_proposal(proposal) == proposal
    assert "directory-fsync" in retry_events
    assert path.read_bytes() == persisted_bytes


def test_replace_json_syncs_temp_before_replace_and_destination_directory_after(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "progress" / "v1.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"value":"old"}', encoding="utf-8")
    events: list[str] = []
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_replace = Path.replace

    def record_fsync(fd: int) -> None:
        kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        events.append(f"{kind}-fsync")
        original_fsync(fd)

    def record_replace(source: Path, destination: Path) -> Path:
        events.append("replace")
        return original_replace(source, destination)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", record_fsync)
    monkeypatch.setattr(Path, "replace", record_replace)

    psychology_learning_series_use_case._replace_json(path, {"value": "new"})

    replace_index = events.index("replace")
    assert any(
        index < replace_index and event == "file-fsync"
        for index, event in enumerate(events)
    )
    assert any(
        index > replace_index and event == "directory-fsync"
        for index, event in enumerate(events)
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "new"}


def test_replace_json_file_sync_failure_preserves_existing_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "progress" / "v1.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"value":"old"}', encoding="utf-8")
    original_fsync = psychology_learning_series_use_case.os.fsync

    def fail_file_fsync(fd: int) -> None:
        if stat.S_ISREG(os.fstat(fd).st_mode):
            raise OSError("injected progress temporary file fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_file_fsync,
    )

    with pytest.raises(OSError, match="progress temporary file fsync failure"):
        psychology_learning_series_use_case._replace_json(path, {"value": "new"})

    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "old"}
    assert not tuple(path.parent.glob("*.tmp"))


def test_confirmation_retries_a_directory_sync_failure_without_rewriting_its_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    confirmation_path = psychology_learning_series_catalog_confirmation_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=proposal.series_id_candidate,
        curriculum_version="1",
        catalog_root=store.catalog_root,
    )
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    fd_paths: dict[int, Path] = {}

    def record_open(path: Path | str, flags: int, *args: int) -> int:
        fd = original_open(path, flags, *args)
        fd_paths[fd] = Path(path)
        return fd

    def fail_confirmation_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == confirmation_path.parent and confirmation_path.exists():
            raise OSError(errno.ENOTSUP, "injected confirmation directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_confirmation_directory_fsync,
    )

    with pytest.raises(OSError, match="confirmation directory fsync failure"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    ledger_bytes = confirmation_path.read_bytes()
    assert not snapshot_path.exists()
    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", original_fsync)
    synced_directories: list[Path] = []
    fd_paths.clear()

    def record_recovery_fsync(fd: int) -> None:
        directory = fd_paths.get(fd)
        if directory is not None:
            synced_directories.append(directory)
        original_fsync(fd)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        record_recovery_fsync,
    )

    recovered = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert confirmation_path.parent in synced_directories
    assert confirmation_path.read_bytes() == ledger_bytes
    assert snapshot_path.exists()
    assert recovered.curriculum_version == "1"


def test_progress_directory_sync_failure_is_reported_before_retrying_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=("notice",),
    )
    progress_path = store.catalog_root / "progress" / catalog.series_id / "v1.json"
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_replace = Path.replace
    fd_paths: dict[int, Path] = {}
    replace_completed = False

    def record_open(path: Path | str, flags: int, *args: int) -> int:
        fd = original_open(path, flags, *args)
        fd_paths[fd] = Path(path)
        return fd

    def record_replace(source: Path, destination: Path) -> Path:
        nonlocal replace_completed
        result = original_replace(source, destination)
        replace_completed = True
        return result

    def fail_progress_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == progress_path.parent and replace_completed:
            raise OSError(errno.ENOTSUP, "injected progress directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(Path, "replace", record_replace)
    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_progress_directory_fsync,
    )

    with pytest.raises(OSError, match="progress directory fsync failure"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=("notice", "practice"),
        )

    failed_payload = json.loads(progress_path.read_text(encoding="utf-8"))
    assert failed_payload["completed_lesson_ids"] == ["notice", "practice"]
    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", original_fsync)

    recovered = store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=("notice", "practice"),
    )

    assert recovered.completed_lesson_ids == ("notice", "practice")


def test_progress_read_rejects_a_replace_until_its_directory_sync_can_complete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=("notice",),
    )
    progress_path = store.catalog_root / "progress" / catalog.series_id / "v1.json"
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_replace = Path.replace
    fd_paths: dict[int, Path] = {}
    replace_completed = False

    def record_open(path: Path | str, flags: int, *args: int) -> int:
        fd = original_open(path, flags, *args)
        fd_paths[fd] = Path(path)
        return fd

    def record_replace(source: Path, destination: Path) -> Path:
        nonlocal replace_completed
        result = original_replace(source, destination)
        replace_completed = True
        return result

    def fail_progress_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == progress_path.parent and replace_completed:
            raise OSError(errno.ENOTSUP, "injected progress directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(Path, "replace", record_replace)
    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fail_progress_directory_fsync,
    )

    with pytest.raises(OSError, match="progress directory fsync failure"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=("notice", "practice"),
        )
    with pytest.raises(OSError, match="progress directory fsync failure"):
        store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        )

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", original_fsync)

    progress = store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )

    assert progress.completed_lesson_ids == ("notice", "practice")


def test_confirmed_catalog_template_version_and_digest_are_bound_to_its_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    ledger_path = psychology_learning_series_catalog_confirmation_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert catalog.controlled_template_version == "1"
    assert snapshot["controlled_template_version"] == "1"
    assert ledger["controlled_template_version"] == "1"
    template_registry = psychology_learning_domain._CONTROLLED_CATALOG_TEMPLATE_REGISTRY
    monkeypatch.setattr(
        psychology_learning_domain,
        "_CONTROLLED_CATALOG_TEMPLATE_REGISTRY",
        {**template_registry, "2": template_registry["1"]},
    )

    snapshot["controlled_template_version"] = "2"
    ledger["controlled_template_version"] = "2"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")
    ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

    with pytest.raises(ValueError, match="catalog revision history"):
        list_psychology_learning_series(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )

    snapshot["controlled_template_version"] = "1"
    snapshot_path.write_text(json.dumps(snapshot), encoding="utf-8")

    with pytest.raises(ValueError, match="catalog revision history"):
        list_psychology_learning_series(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )


def test_confirmed_v1_snapshot_load_uses_its_frozen_template_not_current_builder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    snapshot_bytes = snapshot_path.read_bytes()

    def future_current_builder(*_: object, **__: object) -> object:
        raise AssertionError("historic v1 loading must not use the current template builder")

    monkeypatch.setattr(
        psychology_learning_domain,
        "_build_confirmed_psychology_learning_catalog",
        future_current_builder,
    )

    listed = list_psychology_learning_series(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    resolved = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )

    assert listed == catalog.lessons
    assert resolved.catalog == catalog
    assert snapshot_path.read_bytes() == snapshot_bytes


def test_confirmed_v1_snapshot_load_does_not_use_current_copy_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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

    def future_current_compactor(*_: object, **__: object) -> str:
        raise AssertionError("historic v1 loading must not use current copy helpers")

    monkeypatch.setattr(
        psychology_learning_domain,
        "_compact_confirmed_reader_text",
        future_current_compactor,
    )

    assert list_psychology_learning_series(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ) == catalog.lessons
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).catalog == catalog


def test_confirmed_v1_snapshot_load_does_not_use_current_snapshot_schema_constant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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

    monkeypatch.setattr(
        psychology_learning_domain,
        "PSYCHOLOGY_LEARNING_CATALOG_SNAPSHOT_SCHEMA_VERSION",
        "2",
    )

    assert list_psychology_learning_series(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ) == catalog.lessons


def test_confirmed_v1_snapshot_load_does_not_use_current_digest_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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

    def future_current_digest_helper(*_: object, **__: object) -> str:
        raise AssertionError("historic v1 loading must not use current digest helpers")

    monkeypatch.setattr(
        psychology_learning_domain,
        "_stable_proposal_digest",
        future_current_digest_helper,
    )
    monkeypatch.setattr(
        psychology_learning_domain,
        "_series_id_candidate",
        future_current_digest_helper,
    )
    monkeypatch.setattr(
        psychology_learning_domain,
        "_proposal_material",
        future_current_digest_helper,
    )
    monkeypatch.setattr(
        psychology_learning_domain,
        "_confirmed_catalog_approval_id",
        future_current_digest_helper,
    )
    monkeypatch.setattr(
        psychology_learning_domain,
        "_confirmed_catalog_digest",
        future_current_digest_helper,
    )
    monkeypatch.setattr(
        psychology_learning_domain,
        "PSYCHOLOGY_LEARNING_PROPOSAL_SCHEMA_VERSION",
        "2",
    )

    assert list_psychology_learning_series(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ) == catalog.lessons
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).catalog == catalog


def test_terminal_snapshot_recovery_uses_ledger_recorded_v1_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(catalog_root=tmp_path / "series-store")
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
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    ledger_path = psychology_learning_series_catalog_confirmation_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot_path.unlink()

    def future_current_builder(*_: object, **__: object) -> object:
        raise AssertionError("terminal recovery must use the ledger template version")

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_build_confirmed_psychology_learning_catalog",
        future_current_builder,
    )

    recovered = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert recovered == catalog
    assert snapshot_path.read_bytes() == snapshot_bytes
    assert json.loads(ledger_path.read_text(encoding="utf-8"))["controlled_template_version"] == "1"
