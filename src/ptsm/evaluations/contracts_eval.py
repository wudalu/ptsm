from __future__ import annotations

from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget
from ptsm.evaluations.rules import _result  # noqa: F401


def contract_artifact_root_fields(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:artifact.root_fields",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="artifact.root_fields",
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )
    required = [
        "playbook_id", "final_content", "activated_skill_details",
        "scene", "publish_mode",
    ]
    missing = [f for f in required if f not in ref]
    if missing:
        return EvalResult(
            eval_result_id=f"{target.target_id}:artifact.root_fields",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="artifact.root_fields",
            evaluator_version="1",
            status="failed",
            reason=f"missing required root fields: {missing}",
            score=0.0,
        )
    return EvalResult(
        eval_result_id=f"{target.target_id}:artifact.root_fields",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id="artifact.root_fields",
        evaluator_version="1",
        status="passed",
        reason="all required root fields present",
        score=1.0,
    )


def contract_skill_details_match(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )
    activated = ref.get("activated_skills")
    details = ref.get("activated_skill_details", [])
    if not isinstance(activated, list) or not isinstance(details, list):
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="skipped",
            reason="activated_skills or activated_skill_details not lists",
        )
    detail_names = {
        d.get("skill_name")
        for d in details
        if isinstance(d, dict) and d.get("skill_name")
    }
    missing = [s for s in activated if s not in detail_names]
    if missing:
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="failed",
            reason=f"activated skills missing details: {missing}",
            score=0.0,
        )
    return EvalResult(
        eval_result_id=f"{target.target_id}:skill_activation.details_match",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id="skill_activation.details_match",
        evaluator_version="1",
        status="passed",
        reason=f"all {len(activated)} skills have details",
        score=1.0,
    )


ALL_CONTRACT_EVALUATORS: list[EvaluatorSpec] = [
    EvaluatorSpec(
        "artifact.root_fields", "1", "contract", "shared observability",
        {"phases": ["final"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "skill_activation.details_match", "1", "contract", "shared skill/runtime",
        {"phases": ["planner"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
]
