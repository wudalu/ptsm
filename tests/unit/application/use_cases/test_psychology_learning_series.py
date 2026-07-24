from __future__ import annotations

import errno
import json
import os
import shutil
import stat
import threading
from pathlib import Path

import pytest

import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
import ptsm.domain.psychology_learning as psychology_learning_domain
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
    provision_psychology_learning_series_storage,
)
from ptsm.domain.psychology_learning import (
    PsychologyLearningOutlineItem,
    list_psychology_learning_series,
    psychology_learning_series_catalog_confirmation_path,
    psychology_learning_series_catalog_snapshot_path,
    psychology_learning_series_progress_sidecar_path,
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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


def test_deleting_a_flat_catalog_snapshot_preserves_its_confirmation_history(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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

    psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).unlink()

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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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

    def fail_once_for_catalog_snapshot(path, payload, **kwargs) -> None:
        nonlocal snapshot_write_failed
        if path == expected_snapshot_path and not snapshot_write_failed:
            snapshot_write_failed = True
            raise OSError("injected catalog snapshot write failure")
        original_write_new_json(path, payload, **kwargs)

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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    original_open = psychology_learning_series_use_case.os.open

    def fail_for_confirmation_record(
        path: Path | str,
        flags: int,
        *args: object,
        **kwargs: object,
    ) -> int:
        if (
            str(path) == expected_confirmation_path.name
            and flags & os.O_EXCL
            and isinstance(kwargs.get("dir_fd"), int)
        ):
            raise OSError("injected confirmation ledger write failure")
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "open",
        fail_for_confirmation_record,
    )

    with pytest.raises(OSError, match="injected confirmation ledger write failure"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert not expected_confirmation_path.exists()
    assert not expected_snapshot_path.exists()
    assert expected_confirmation_path.parent.is_dir()

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "open",
        original_open,
    )
    confirmed = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert confirmed.curriculum_version == "1"
    assert expected_confirmation_path.exists()
    assert expected_snapshot_path.exists()


def test_confirmation_uses_the_preprovisioned_flat_ledger_directory(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    assert confirmation_path.parent.is_dir()

    confirmed = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    assert confirmed.curriculum_version == "1"
    assert confirmation_path.exists()


def test_confirmation_never_attempts_online_staging_cleanup(
    tmp_path,
    monkeypatch,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    def reject_online_unlink(*args: object, **kwargs: object) -> None:
        raise AssertionError("confirmation must not clean mutable names online")

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "unlink",
        reject_online_unlink,
    )
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    ).lesson.lesson_id == "notice"


def test_custom_revision_history_fails_closed_when_a_confirmation_record_is_missing(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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


def test_public_progress_write_rejects_a_preprovisioned_progress_directory_symlink(
    tmp_path: Path,
) -> None:
    """The legacy progress API must never follow a link into catalog snapshots."""
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    snapshot_before = snapshot_path.read_bytes()
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    former_progress = tmp_path / "former-progress"
    progress_path.parent.rename(former_progress)
    progress_path.parent.symlink_to(snapshot_path.parent, target_is_directory=True)

    with pytest.raises(OSError):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=(catalog.lessons[0].lesson_id,),
        )

    assert snapshot_path.read_bytes() == snapshot_before


def test_mark_production_lesson_completed_is_idempotent_and_concurrency_safe(
    tmp_path: Path,
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
    start = threading.Barrier(2)
    failures: list[BaseException] = []

    def mark(lesson_id: str) -> None:
        try:
            start.wait(timeout=5)
            PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root).mark_production_lesson_completed(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                lesson_id=lesson_id,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    threads = [
        threading.Thread(target=mark, args=(lesson.lesson_id,))
        for lesson in catalog.lessons
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    progress = store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    assert progress.completed_lesson_ids == tuple(
        lesson.lesson_id for lesson in catalog.lessons
    )
    assert store.mark_production_lesson_completed(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        lesson_id=catalog.lessons[1].lesson_id,
    ) == progress


def test_mark_pinned_progress_is_at_least_once_when_artifact_root_rebinds_after_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A post-replace root swap fails closed but must not roll back by name."""
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
    store.mark_production_lesson_completed(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        lesson_id=catalog.lessons[0].lesson_id,
    )
    artifact_root = tmp_path / "outputs" / "artifacts"
    catalog_root = artifact_root / "psychology-learning-series"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    original_replace = os.replace
    rebound = False

    def replace_then_rebind(*args: object, **kwargs: object) -> None:
        nonlocal rebound
        original_replace(*args, **kwargs)  # type: ignore[arg-type]
        if not rebound:
            rebound = True
            artifact_root.rename(former_artifact_root)
            artifact_root.symlink_to(former_artifact_root, target_is_directory=True)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "replace",
        replace_then_rebind,
    )

    with pytest.raises(OSError, match="storage root changed"):
        store.mark_production_lesson_completed(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            lesson_id=catalog.lessons[1].lesson_id,
            catalog=catalog,
            expected_catalog_root_identity=catalog_root.stat(),
            expected_progress_identity=store._capture_pinned_progress_directory_identity(
                expected_catalog_root_identity=catalog_root.stat()
            ),
            expected_artifact_root_path=artifact_root,
            expected_artifact_root_identity=artifact_root.stat(),
        )

    assert rebound
    assert (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
        / snapshot_path.name
    ).read_bytes() == snapshot_before
    with pytest.raises(OSError, match="storage root changed"):
        store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        )
    assert PsychologyLearningSeriesStore(
        catalog_root=former_artifact_root / "psychology-learning-series"
    ).read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (
        catalog.lessons[0].lesson_id,
        catalog.lessons[1].lesson_id,
    )


@pytest.mark.parametrize(
    ("replacement_kind", "seed_existing_progress"),
    (
        ("symlink", False),
        ("hardlink", False),
        ("symlink", True),
        ("hardlink", True),
    ),
)
def test_mark_pinned_progress_leaves_a_temporary_source_swap_for_offline_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    replacement_kind: str,
    seed_existing_progress: bool,
) -> None:
    """A raced temp entry fails closed without unlinking an attacker replacement."""
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
    artifact_root = tmp_path / "outputs" / "artifacts"
    catalog_root = artifact_root / "psychology-learning-series"
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    if seed_existing_progress:
        store.mark_production_lesson_completed(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            lesson_id=catalog.lessons[0].lesson_id,
            catalog=catalog,
            expected_catalog_root_identity=catalog_root.stat(),
            expected_progress_identity=store._capture_pinned_progress_directory_identity(
                expected_catalog_root_identity=catalog_root.stat()
            ),
            expected_artifact_root_path=artifact_root,
            expected_artifact_root_identity=artifact_root.stat(),
        )
    original_replace = os.replace
    swapped = False

    def replace_after_temporary_source_swap(
        source: object,
        destination: object,
        **kwargs: object,
    ) -> None:
        nonlocal swapped
        source_name = str(source)
        source_parent_fd = kwargs.get("src_dir_fd")
        if (
            not swapped
            and source_name.endswith(".tmp")
            and isinstance(source_parent_fd, int)
        ):
            swapped = True
            os.unlink(source_name, dir_fd=source_parent_fd)
            if replacement_kind == "symlink":
                os.symlink(snapshot_path, source_name, dir_fd=source_parent_fd)
            else:
                os.link(snapshot_path, source_name, dst_dir_fd=source_parent_fd)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "replace",
        replace_after_temporary_source_swap,
    )

    with pytest.raises(OSError, match="psychology learning file changed"):
        store.mark_production_lesson_completed(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            lesson_id=(
                catalog.lessons[1].lesson_id
                if seed_existing_progress
                else catalog.lessons[0].lesson_id
            ),
            catalog=catalog,
            expected_catalog_root_identity=catalog_root.stat(),
            expected_progress_identity=store._capture_pinned_progress_directory_identity(
                expected_catalog_root_identity=catalog_root.stat()
            ),
            expected_artifact_root_path=artifact_root,
            expected_artifact_root_identity=artifact_root.stat(),
        )

    assert swapped
    if replacement_kind == "symlink":
        assert progress_path.is_symlink()
    else:
        assert progress_path.exists()
        assert os.path.samestat(progress_path.stat(), snapshot_path.stat())
    assert snapshot_path.read_bytes() == snapshot_before
    with pytest.raises((OSError, ValueError)):
        store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        )


def test_write_progress_rejects_a_hidden_temporary_payload_mutation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An attacker cannot hide a valid progress rewrite by unlinking its peer."""
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
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    peer_name = "attacker-peer.json"
    attacker_payload = psychology_learning_series_use_case._canonical_json(
        {
            "series_id": catalog.series_id,
            "curriculum_version": catalog.curriculum_version,
            "catalog_digest": catalog.catalog_digest,
            "completed_lesson_ids": [
                catalog.lessons[0].lesson_id,
                catalog.lessons[1].lesson_id,
            ],
        }
    ).encode("utf-8")
    original_replace = psychology_learning_series_use_case.os.replace
    mutated = False

    def replace_after_hidden_temporary_mutation(
        source: object,
        destination: object,
        **kwargs: object,
    ) -> None:
        nonlocal mutated
        source_name = str(source)
        source_parent_fd = kwargs.get("src_dir_fd")
        destination_parent_fd = kwargs.get("dst_dir_fd")
        if (
            not mutated
            and source_name.endswith(".tmp")
            and isinstance(source_parent_fd, int)
            and isinstance(destination_parent_fd, int)
        ):
            mutated = True
            os.link(
                source_name,
                peer_name,
                src_dir_fd=source_parent_fd,
                dst_dir_fd=destination_parent_fd,
            )
            peer_fd = os.open(
                peer_name,
                os.O_WRONLY | os.O_TRUNC,
                dir_fd=destination_parent_fd,
            )
            try:
                os.write(peer_fd, attacker_payload)
                os.fsync(peer_fd)
            finally:
                os.close(peer_fd)
            os.unlink(peer_name, dir_fd=destination_parent_fd)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "replace",
        replace_after_hidden_temporary_mutation,
    )

    with pytest.raises(OSError, match="psychology learning progress payload changed"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=(catalog.lessons[0].lesson_id,),
        )

    assert mutated
    assert progress_path.read_bytes() == attacker_payload
    assert not (progress_path.parent / peer_name).exists()


def test_write_progress_rechecks_payload_after_the_inner_replace_returns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The outer transaction closes the gap after the inner fd's final check."""
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
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    peer_name = "attacker-peer.json"
    attacker_payload = psychology_learning_series_use_case._canonical_json(
        {
            "series_id": catalog.series_id,
            "curriculum_version": catalog.curriculum_version,
            "catalog_digest": catalog.catalog_digest,
            "completed_lesson_ids": [
                catalog.lessons[0].lesson_id,
                catalog.lessons[1].lesson_id,
            ],
        }
    ).encode("utf-8")
    original_replace = psychology_learning_series_use_case._replace_pinned_regular_file
    mutated = False

    def replace_then_mutate_after_inner_check(
        *,
        parent_fd: int,
        name: str,
        payload: bytes,
        expected_identity: os.stat_result | None,
    ) -> os.stat_result:
        nonlocal mutated
        committed = original_replace(
            parent_fd=parent_fd,
            name=name,
            payload=payload,
            expected_identity=expected_identity,
        )
        mutated = True
        os.link(name, peer_name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        peer_fd = os.open(peer_name, os.O_WRONLY | os.O_TRUNC, dir_fd=parent_fd)
        try:
            os.write(peer_fd, attacker_payload)
            os.fsync(peer_fd)
        finally:
            os.close(peer_fd)
        os.unlink(peer_name, dir_fd=parent_fd)
        return committed

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_replace_pinned_regular_file",
        replace_then_mutate_after_inner_check,
    )

    with pytest.raises(OSError, match="psychology learning progress payload changed"):
        store.write_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            completed_lesson_ids=(catalog.lessons[0].lesson_id,),
        )

    assert mutated
    assert progress_path.read_bytes() == attacker_payload
    assert not (progress_path.parent / peer_name).exists()


def test_mark_pinned_progress_serializes_concurrent_marks_on_the_series_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Pinned callers share one directory flock even without a mutable lock file."""
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
    artifact_root = tmp_path / "outputs" / "artifacts"
    catalog_root = artifact_root / "psychology-learning-series"
    start = threading.Barrier(2)
    failures: list[BaseException] = []

    def mark(lesson_id: str) -> None:
        try:
            start.wait(timeout=5)
            PsychologyLearningSeriesStore(trusted_provision=True, ).mark_production_lesson_completed(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                lesson_id=lesson_id,
                catalog=catalog,
                expected_catalog_root_identity=catalog_root.stat(),
                expected_progress_identity=store._capture_pinned_progress_directory_identity(
                    expected_catalog_root_identity=catalog_root.stat()
                ),
                expected_artifact_root_path=artifact_root,
                expected_artifact_root_identity=artifact_root.stat(),
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    threads = [
        threading.Thread(target=mark, args=(lesson.lesson_id,))
        for lesson in catalog.lessons
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == tuple(lesson.lesson_id for lesson in catalog.lessons)


def test_mark_pinned_progress_shares_its_lock_with_legacy_progress_marks(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A guarded run and the public retry API cannot form separate lock domains."""
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
    artifact_root = tmp_path / "outputs" / "artifacts"
    catalog_root = artifact_root / "psychology-learning-series"
    pinned_read_entered = threading.Event()
    allow_pinned_read = threading.Event()
    legacy_read_entered = threading.Event()
    failures: list[BaseException] = []
    original_pinned_read = psychology_learning_series_use_case._read_pinned_production_progress
    original_legacy_read = PsychologyLearningSeriesStore.read_production_progress

    def pause_pinned_read(**kwargs: object):
        pinned_read_entered.set()
        assert allow_pinned_read.wait(timeout=5)
        return original_pinned_read(**kwargs)

    def record_legacy_read(
        self: PsychologyLearningSeriesStore,
        **kwargs: object,
    ):
        legacy_read_entered.set()
        return original_legacy_read(self, **kwargs)

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_read_pinned_production_progress",
        pause_pinned_read,
    )
    monkeypatch.setattr(
        PsychologyLearningSeriesStore,
        "read_production_progress",
        record_legacy_read,
    )

    def mark_pinned() -> None:
        try:
            store.mark_production_lesson_completed(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                lesson_id=catalog.lessons[0].lesson_id,
                catalog=catalog,
                expected_catalog_root_identity=catalog_root.stat(),
                expected_progress_identity=store._capture_pinned_progress_directory_identity(
                    expected_catalog_root_identity=catalog_root.stat()
                ),
                expected_artifact_root_path=artifact_root,
                expected_artifact_root_identity=artifact_root.stat(),
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    def mark_legacy() -> None:
        try:
            PsychologyLearningSeriesStore(trusted_provision=True, ).mark_production_lesson_completed(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                lesson_id=catalog.lessons[1].lesson_id,
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    pinned_thread = threading.Thread(target=mark_pinned)
    pinned_thread.start()
    assert pinned_read_entered.wait(timeout=5)
    legacy_thread = threading.Thread(target=mark_legacy)
    legacy_thread.start()

    # The legacy reader may not enter while the pinned writer owns the same
    # series-directory flock. A separate `.lock` file would fail this check.
    assert not legacy_read_entered.wait(timeout=0.25)
    allow_pinned_read.set()
    pinned_thread.join(timeout=10)
    legacy_thread.join(timeout=10)

    assert not failures
    assert not pinned_thread.is_alive()
    assert not legacy_thread.is_alive()
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == tuple(lesson.lesson_id for lesson in catalog.lessons)


def test_custom_catalog_resolution_fails_closed_until_matching_retry_and_for_tampered_snapshots(
    tmp_path,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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

    tampered_store = PsychologyLearningSeriesStore(trusted_provision=True,
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

    missing_proposal_store = PsychologyLearningSeriesStore(trusted_provision=True,
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


@pytest.mark.parametrize("storage_directory", ("proposals", "confirmations", "catalogs"))
def test_immutable_catalog_writes_reject_a_symlinked_storage_directory(
    tmp_path: Path,
    storage_directory: str,
) -> None:
    root = tmp_path / "series-store"
    outside = tmp_path / "outside"
    outside.mkdir()
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )

    if storage_directory == "proposals":
        (root / storage_directory).rmdir()
        (root / storage_directory).symlink_to(outside, target_is_directory=True)
        with pytest.raises(OSError, match="symlink|directory|storage"):
            store.persist_proposal(proposal)
    else:
        store.persist_proposal(proposal)
        (root / storage_directory).rmdir()
        (root / storage_directory).symlink_to(outside, target_is_directory=True)
        with pytest.raises(OSError, match="symlink|directory|storage"):
            store.confirm(
                proposal_id=proposal.proposal_id,
                proposal_fingerprint=proposal.proposal_fingerprint,
            )

    assert not tuple(outside.iterdir())


def test_immutable_proposal_snapshot_rejects_a_hard_link(
    tmp_path: Path,
) -> None:
    root = tmp_path / "series-store"
    outside = tmp_path / "outside-proposal.json"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    target = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=root,
    )
    outside.write_text(
        json.dumps(proposal.model_dump(mode="json"), ensure_ascii=False),
        encoding="utf-8",
    )
    os.link(outside, target)

    with pytest.raises(OSError, match="private regular file"):
        store.persist_proposal(proposal)

    assert outside.stat().st_nlink == 2


def test_immutable_proposal_write_rejects_a_target_replacement_after_file_sync(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A direct O_EXCL target is never cleaned up after an attacker swaps it."""
    root = tmp_path / "series-store"
    outside = tmp_path / "outside.json"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    target = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=root,
    )
    outside.write_text('{"attacker":true}', encoding="utf-8")
    original_fsync = psychology_learning_series_use_case.os.fsync
    swapped = False

    def fsync_then_swap_target(fd: int) -> None:
        nonlocal swapped
        original_fsync(fd)
        if (
            not swapped
            and target.exists()
            and stat.S_ISREG(os.fstat(fd).st_mode)
        ):
            swapped = True
            outside.replace(target)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", fsync_then_swap_target)

    with pytest.raises(OSError):
        store.persist_proposal(proposal)

    assert swapped
    assert target.read_text(encoding="utf-8") == '{"attacker":true}'
    with pytest.raises((OSError, ValueError)):
        store.read_proposal(proposal_id=proposal.proposal_id)


def test_immutable_proposal_write_preserves_an_existing_private_collision(
    tmp_path: Path,
) -> None:
    """A pre-existing name is never overwritten by an immutable retry."""
    root = tmp_path / "series-store"
    outside = tmp_path / "outside.json"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    target = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=root,
    )
    outside.write_text('{"attacker":true}', encoding="utf-8")
    outside.replace(target)

    with pytest.raises((OSError, ValueError)):
        store.persist_proposal(proposal)

    assert target.read_text(encoding="utf-8") == '{"attacker":true}'


def test_immutable_proposal_write_rejects_a_hidden_content_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    target = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=root,
    )
    peer_path = root / "proposals" / "attacker-peer.json"
    attacker_bytes = b'{"attacker":true}'
    original_fsync = psychology_learning_series_use_case.os.fsync
    mutated = False

    def fsync_then_mutate_hidden_peer(fd: int) -> None:
        nonlocal mutated
        original_fsync(fd)
        if (
            not mutated
            and target.exists()
            and stat.S_ISREG(os.fstat(fd).st_mode)
        ):
            mutated = True
            os.link(target, peer_path)
            peer_fd = os.open(peer_path, os.O_WRONLY | os.O_TRUNC)
            try:
                os.write(peer_fd, attacker_bytes)
                original_fsync(peer_fd)
            finally:
                os.close(peer_fd)
            peer_path.unlink()

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fsync_then_mutate_hidden_peer,
    )

    with pytest.raises(OSError, match="immutable snapshot source changed"):
        store.persist_proposal(proposal)

    assert mutated
    assert target.read_bytes() == attacker_bytes
    assert not peer_path.exists()


def test_proposal_persistence_rejects_a_proposals_directory_rebind_after_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "series-store"
    former_proposals = tmp_path / "former-proposals"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    proposal_path = psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=root,
    )
    original_fsync = psychology_learning_series_use_case.os.fsync
    rebound = False

    def fsync_then_rebind_proposals(fd: int) -> None:
        nonlocal rebound
        original_fsync(fd)
        if (
            not rebound
            and proposal_path.exists()
            and stat.S_ISREG(os.fstat(fd).st_mode)
        ):
            rebound = True
            (root / "proposals").rename(former_proposals)
            (root / "proposals").mkdir()

    monkeypatch.setattr(
        psychology_learning_series_use_case.os,
        "fsync",
        fsync_then_rebind_proposals,
    )

    with pytest.raises(OSError, match="storage (root|directory) changed"):
        store.persist_proposal(proposal)

    assert rebound
    assert not proposal_path.exists()
    assert (former_proposals / proposal_path.name).exists()
    with pytest.raises(ValueError, match="unknown psychology learning proposal"):
        store.read_proposal(proposal_id=proposal.proposal_id)


def test_proposal_persistence_rejects_a_missing_provisioned_directory(
    tmp_path: Path,
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
    (root / "proposals").rmdir()

    with pytest.raises(OSError, match="storage is not provisioned"):
        store.persist_proposal(proposal)

    assert not (root / "proposals").exists()


def test_proposal_persistence_requires_trusted_provisioning(tmp_path: Path) -> None:
    """A content mutation never creates an unpinned storage directory."""
    root = tmp_path / "series-store"
    store = PsychologyLearningSeriesStore(catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    with pytest.raises(OSError, match="storage is not provisioned"):
        store.persist_proposal(proposal)

    provisioned_root = provision_psychology_learning_series_storage(catalog_root=root)
    persisted = PsychologyLearningSeriesStore(
        catalog_root=provisioned_root
    ).persist_proposal(proposal)

    assert persisted == proposal
    assert psychology_learning_series_proposal_snapshot_path(
        proposal_id=proposal.proposal_id,
        catalog_root=provisioned_root,
    ).is_file()


def test_confirmation_rejects_a_catalog_root_rebind_after_proposal_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "series-store"
    former_root = tmp_path / "former-series-store"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    original_sync = store._sync_existing_catalog_history
    rebound = False

    def sync_then_rebind(*, series_id: str) -> None:
        nonlocal rebound
        original_sync(series_id=series_id)
        if not rebound:
            rebound = True
            root.rename(former_root)
            root.mkdir()

    monkeypatch.setattr(store, "_sync_existing_catalog_history", sync_then_rebind)

    with pytest.raises(OSError, match="storage root changed"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert rebound
    assert not tuple(root.iterdir())
    assert (
        former_root / "proposals" / f"{proposal.proposal_id}.json"
    ).is_file()


def test_confirmation_rejects_a_catalog_child_rebind_between_commits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "series-store"
    former_catalogs = tmp_path / "former-catalogs"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    original_persist_record = store._persist_confirmation_record
    rebound = False

    def persist_record_then_rebind(
        catalog,
        *,
        mutation_scope,
    ) -> None:
        nonlocal rebound
        original_persist_record(catalog, mutation_scope=mutation_scope)
        if not rebound:
            rebound = True
            (root / "catalogs").rename(former_catalogs)
            (root / "catalogs").mkdir()

    monkeypatch.setattr(store, "_persist_confirmation_record", persist_record_then_rebind)

    with pytest.raises(OSError, match="storage (root|directory) changed"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )

    assert rebound
    assert not tuple((root / "catalogs").iterdir())
    assert not tuple(former_catalogs.iterdir())


def test_confirmation_rejects_a_directory_entry_in_flat_catalog_storage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    original_sync = store._sync_existing_catalog_history

    def sync_then_create_series_directory(*, series_id: str) -> None:
        original_sync(series_id=series_id)
        (root / "catalogs" / series_id).mkdir()

    monkeypatch.setattr(
        store,
        "_sync_existing_catalog_history",
        sync_then_create_series_directory,
    )

    with pytest.raises(ValueError, match="catalog revision history"):
        store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )


def test_write_new_json_syncs_file_and_destination_directory_after_direct_create(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "proposals" / "proposal.json"
    path.parent.mkdir(parents=True)
    events: list[str] = []
    original_fsync = psychology_learning_series_use_case.os.fsync

    def record_fsync(fd: int) -> None:
        kind = "directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"
        events.append(f"{kind}-fsync")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "fsync", record_fsync)

    psychology_learning_series_use_case._write_new_json(path, {"value": "one"})

    file_sync_index = events.index("file-fsync")
    assert any(
        index > file_sync_index and event == "directory-fsync"
        for index, event in enumerate(events)
    )
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "one"}


def test_write_new_json_file_sync_failure_leaves_immutable_target_for_offline_cleanup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "series-store" / "proposals" / "proposal.json"
    path.parent.mkdir(parents=True)
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

    assert path.exists()
    assert json.loads(path.read_text(encoding="utf-8")) == {"value": "one"}


def test_domain_custom_catalog_reads_reject_visible_snapshot_until_directory_sync_retries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    original_dup = psychology_learning_series_use_case.os.dup
    original_fsync = psychology_learning_series_use_case.os.fsync
    fd_paths: dict[int, Path] = {}

    def record_open(
        opened_path: Path | str,
        flags: int,
        *args: int,
        **kwargs: object,
    ) -> int:
        fd = original_open(opened_path, flags, *args, **kwargs)
        parent_fd = kwargs.get("dir_fd")
        parent_path = fd_paths.get(parent_fd) if isinstance(parent_fd, int) else None
        fd_paths[fd] = (
            parent_path / str(opened_path)
            if parent_path is not None
            else Path(opened_path)
        )
        return fd

    def record_dup(fd: int) -> int:
        duplicate = original_dup(fd)
        if fd in fd_paths:
            fd_paths[duplicate] = fd_paths[fd]
        return duplicate

    def fail_snapshot_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == snapshot_path.parent and snapshot_path.exists():
            raise OSError(errno.ENOTSUP, "injected snapshot directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(psychology_learning_series_use_case.os, "dup", record_dup)
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    proposal_directory_identity = os.stat(path.parent)
    original_fsync = psychology_learning_series_use_case.os.fsync

    def fail_destination_directory_fsync(fd: int) -> None:
        if os.path.samestat(os.fstat(fd), proposal_directory_identity):
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


def test_confirmation_retries_a_directory_sync_failure_without_rewriting_its_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    original_dup = psychology_learning_series_use_case.os.dup
    original_fsync = psychology_learning_series_use_case.os.fsync
    fd_paths: dict[int, Path] = {}

    def record_open(
        opened_path: Path | str,
        flags: int,
        *args: int,
        **kwargs: object,
    ) -> int:
        fd = original_open(opened_path, flags, *args, **kwargs)
        parent_fd = kwargs.get("dir_fd")
        parent_path = fd_paths.get(parent_fd) if isinstance(parent_fd, int) else None
        fd_paths[fd] = (
            parent_path / str(opened_path)
            if parent_path is not None
            else Path(opened_path)
        )
        return fd

    def record_dup(fd: int) -> int:
        duplicate = original_dup(fd)
        if fd in fd_paths:
            fd_paths[duplicate] = fd_paths[fd]
        return duplicate

    def fail_confirmation_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == confirmation_path.parent and confirmation_path.exists():
            raise OSError(errno.ENOTSUP, "injected confirmation directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(psychology_learning_series_use_case.os, "dup", record_dup)
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_replace = psychology_learning_series_use_case.os.replace
    fd_paths: dict[int, Path] = {}
    replace_completed = False

    def record_open(
        path: Path | str,
        flags: int,
        *args: int,
        **kwargs: object,
    ) -> int:
        fd = original_open(path, flags, *args, **kwargs)
        parent_fd = kwargs.get("dir_fd")
        parent_path = fd_paths.get(parent_fd) if isinstance(parent_fd, int) else None
        fd_paths[fd] = (parent_path / str(path)) if parent_path is not None else Path(path)
        return fd

    def record_replace(source: object, destination: object, **kwargs: object) -> None:
        nonlocal replace_completed
        result = original_replace(source, destination, **kwargs)
        replace_completed = True
        return result

    def fail_progress_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == progress_path.parent and replace_completed:
            raise OSError(errno.ENOTSUP, "injected progress directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(psychology_learning_series_use_case.os, "replace", record_replace)
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=store.catalog_root,
    )
    original_open = psychology_learning_series_use_case.os.open
    original_fsync = psychology_learning_series_use_case.os.fsync
    original_replace = psychology_learning_series_use_case.os.replace
    fd_paths: dict[int, Path] = {}
    replace_completed = False

    def record_open(
        path: Path | str,
        flags: int,
        *args: int,
        **kwargs: object,
    ) -> int:
        fd = original_open(path, flags, *args, **kwargs)
        parent_fd = kwargs.get("dir_fd")
        parent_path = fd_paths.get(parent_fd) if isinstance(parent_fd, int) else None
        fd_paths[fd] = (parent_path / str(path)) if parent_path is not None else Path(path)
        return fd

    def record_replace(source: object, destination: object, **kwargs: object) -> None:
        nonlocal replace_completed
        result = original_replace(source, destination, **kwargs)
        replace_completed = True
        return result

    def fail_progress_directory_fsync(fd: int) -> None:
        if fd_paths.get(fd) == progress_path.parent and replace_completed:
            raise OSError(errno.ENOTSUP, "injected progress directory fsync failure")
        original_fsync(fd)

    monkeypatch.setattr(psychology_learning_series_use_case.os, "open", record_open)
    monkeypatch.setattr(psychology_learning_series_use_case.os, "replace", record_replace)
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=tmp_path / "series-store")
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
