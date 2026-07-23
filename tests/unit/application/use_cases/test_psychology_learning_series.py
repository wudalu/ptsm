from __future__ import annotations

from collections.abc import Sequence

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


def test_plan_psychology_learning_series_rejects_oversized_outline_before_iteration() -> None:
    class OversizedOutline(Sequence[dict[str, str]]):
        def __len__(self) -> int:
            return 7

        def __getitem__(self, index: int) -> dict[str, str]:
            raise AssertionError(f"outline should not be materialized: {index}")

    with pytest.raises(ValueError, match="outline must contain between 2 and 6 lessons"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=OversizedOutline(),
        )


def test_plan_psychology_learning_series_does_not_consume_non_sequence_outline() -> None:
    def unbounded_outline():
        raise AssertionError("outline should not be consumed")
        yield {"title": "never reached"}

    with pytest.raises(TypeError, match="outline must be a sized sequence"):
        plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=unbounded_outline(),  # type: ignore[arg-type]
        )
