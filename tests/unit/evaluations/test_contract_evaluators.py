from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.contracts_eval import (
    contract_artifact_root_fields,
    contract_skill_details_match,
    ALL_CONTRACT_EVALUATORS,
)


def _target(**overrides):
    defaults = {
        "target_id": "t:final:ac",
        "run_id": "r",
        "playbook_id": "fengkuang_daily_post",
        "account_id": "acct",
        "phase": "final",
        "target_type": "artifact_slice",
    }
    defaults.update(overrides)
    return EvalTarget(**defaults)


class TestArtifactRootFields:
    def test_passes_with_all_required(self):
        target = _target(
            output_ref={
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "T", "body": "B", "hashtags": ["#h"]},
                "activated_skill_details": [{"skill_name": "fs"}],
                "scene": "test",
                "publish_mode": "dry-run",
            },
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "passed"

    def test_fails_with_missing_root_field(self):
        target = _target(
            output_ref={"playbook_id": "pb"},
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "failed"

    def test_skipped_without_output_ref(self):
        target = _target(output_ref=None)
        result = contract_artifact_root_fields(target)
        assert result.status == "skipped"


class TestSkillDetailsMatch:
    def test_passes_when_skills_match(self):
        target = _target(
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                    {"skill_name": "s2"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "passed"

    def test_fails_when_skill_missing_details(self):
        target = _target(
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2", "s3"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "failed"

    def test_skipped_without_output_ref(self):
        target = _target(phase="planner", target_type="node_output", output_ref=None)
        result = contract_skill_details_match(target)
        assert result.status == "skipped"


class TestAllContractEvaluators:
    def test_all_registered(self):
        assert len(ALL_CONTRACT_EVALUATORS) >= 2
