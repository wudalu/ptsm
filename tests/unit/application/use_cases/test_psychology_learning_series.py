from __future__ import annotations

import pytest

from ptsm.application.use_cases.psychology_learning_series import (
    plan_psychology_learning_series,
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


def test_plan_psychology_learning_series_rejects_oversized_concrete_outline() -> None:
    with pytest.raises(ValueError, match="outline must contain between 2 and 6 lessons"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=[{"title": "只做数量检查"}] * 7,
        )
