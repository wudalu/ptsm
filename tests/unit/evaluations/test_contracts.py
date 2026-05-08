from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget, EvalResult, EvaluatorSpec, EvalSuite


class TestEvalTarget:
    def test_roundtrip_to_dict(self):
        target = EvalTarget(
            target_id="run-1:executor:final_content",
            run_id="run-1",
            artifact_path="outputs/artifacts/a.json",
            playbook_id="fengkuang_daily_post",
            account_id="acct-fk-local",
            platform="xiaohongshu",
            phase="executor",
            target_type="artifact_slice",
            metadata={"skill_names": ["fengkuang_style"]},
        )
        d = target.to_dict()
        assert d["target_id"] == "run-1:executor:final_content"
        assert d["phase"] == "executor"
        assert d["metadata"]["skill_names"] == ["fengkuang_style"]

    def test_minimal_target(self):
        target = EvalTarget(
            target_id="r:p:n",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="planner",
            target_type="node_output",
        )
        assert target.artifact_path is None
        assert target.platform is None

    def test_none_fields_excluded_from_dict(self):
        target = EvalTarget(
            target_id="r:p:n",
            run_id="r",
            playbook_id="pb",
            account_id="acct",
            phase="planner",
            target_type="node_output",
        )
        d = target.to_dict()
        assert "artifact_path" not in d
        assert "platform" not in d


class TestEvalResult:
    def test_passed_result(self):
        result = EvalResult(
            eval_result_id="er-1",
            eval_run_id="evrun-1",
            target_id="t-1",
            evaluator_id="artifact_schema.required",
            evaluator_version="1",
            status="passed",
            reason="all required fields present",
        )
        assert result.status == "passed"
        assert result.score is None

    def test_failed_result_with_evidence(self):
        result = EvalResult(
            eval_result_id="er-2",
            eval_run_id="evrun-1",
            target_id="t-2",
            evaluator_id="final_content.hashtags_present",
            evaluator_version="1",
            status="failed",
            score=0.0,
            reason="hashtags list is empty",
            evidence=[
                {
                    "path": "final_content.hashtags",
                    "value_preview": "[]",
                    "observation": "hashtags must be non-empty",
                },
            ],
        )
        d = result.to_dict()
        assert d["status"] == "failed"
        assert len(d["evidence"]) == 1

    def test_to_dict_excludes_none(self):
        result = EvalResult(
            eval_result_id="er-3",
            eval_run_id="evrun-1",
            target_id="t-3",
            evaluator_id="e-1",
            evaluator_version="1",
            status="passed",
            reason="ok",
        )
        d = result.to_dict()
        assert "score" not in d
        assert "label" not in d


class TestEvaluatorSpec:
    def test_rule_evaluator(self):
        spec = EvaluatorSpec(
            evaluator_id="artifact_schema.required",
            version="1",
            type="rule",
            owner="shared evaluation",
            applies_to={"phases": ["finalize"], "playbook_ids": [], "platforms": []},
            threshold=0.8,
            gate_level="required",
        )
        assert spec.type == "rule"
        assert spec.gate_level == "required"

    def test_llm_judge_warning(self):
        spec = EvaluatorSpec(
            evaluator_id="style.judge",
            version="1",
            type="llm_judge",
            owner="playbook",
            gate_level="warning",
        )
        assert spec.gate_level == "warning"
        assert spec.threshold == 0.8  # default


class TestEvalSuite:
    def test_suite_binds_evaluators(self):
        suite = EvalSuite(
            suite_id="fengkuang_daily_post.default",
            scope={"playbook_id": "fengkuang_daily_post", "platform": "xiaohongshu"},
            evaluators=["artifact_schema.required", "final_content.hashtags_present"],
        )
        assert len(suite.evaluators) == 2
        assert suite.scope["playbook_id"] == "fengkuang_daily_post"
