from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
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
