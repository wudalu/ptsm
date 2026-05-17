from __future__ import annotations

from ptsm.agent_runtime.runtime import _playbook_requires_content_quality_judge


def test_quality_judge_required_by_eval_contract_for_ai_tech() -> None:
    assert _playbook_requires_content_quality_judge("ai_tech_daily_post") is True


def test_quality_judge_not_required_when_eval_contract_is_missing() -> None:
    assert _playbook_requires_content_quality_judge("missing_playbook") is False
