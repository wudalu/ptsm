from __future__ import annotations

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
