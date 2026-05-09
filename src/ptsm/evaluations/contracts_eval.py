from __future__ import annotations

from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget
from ptsm.evaluations.rules import _result  # noqa: F401
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract


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


def contract_playbook_node_contract(
    target: EvalTarget,
    playbook_contract: PlaybookEvalContract,
) -> EvalResult:
    evaluator_id = "playbook.node_contract"
    node_contract = playbook_contract.node_contracts.get(target.phase)
    if not isinstance(node_contract, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason=f"no playbook node contract for phase {target.phase}",
        )

    payload = _node_payload(target)
    if payload is None:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )

    failures: list[dict[str, object]] = []
    required_fields = node_contract.get("required_fields", [])
    if isinstance(required_fields, list):
        for field in required_fields:
            field_name = str(field)
            value = payload.get(field_name)
            if field_name not in payload or value is None or value == "":
                failures.append(
                    {
                        "path": _field_path(target, field_name),
                        "value_preview": str(value),
                        "observation": "missing required field",
                    }
                )

    constraints = node_contract.get("constraints", {})
    if isinstance(constraints, dict):
        failures.extend(_constraint_failures(target=target, payload=payload, constraints=constraints))

    if failures:
        reasons = [f"{item['path']}: {item['observation']}" for item in failures]
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="failed",
            reason="; ".join(reasons),
            score=0.0,
            evidence=failures,
        )

    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status="passed",
        reason=f"playbook node contract satisfied for phase {target.phase}",
        score=1.0,
    )


def _node_payload(target: EvalTarget) -> dict | None:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return None
    if target.phase == "executor" and isinstance(ref.get("final_content"), dict):
        return ref["final_content"]
    return ref


def _field_path(target: EvalTarget, field_name: str) -> str:
    if target.phase == "executor":
        return f"final_content.{field_name}"
    return field_name


def _constraint_failures(
    *,
    target: EvalTarget,
    payload: dict,
    constraints: dict,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    title = payload.get("title")
    title_max_chars = constraints.get("title_max_chars")
    if isinstance(title, str) and isinstance(title_max_chars, int):
        if len(title) > title_max_chars:
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": f"title_max_chars exceeded: {len(title)} > {title_max_chars}",
                }
            )

    hashtags = payload.get("hashtags")
    if isinstance(hashtags, list):
        min_count = constraints.get("hashtags_min_count")
        max_count = constraints.get("hashtags_max_count")
        if isinstance(min_count, int) and len(hashtags) < min_count:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": f"hashtags_min_count violated: {len(hashtags)} < {min_count}",
                }
            )
        if isinstance(max_count, int) and len(hashtags) > max_count:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": f"hashtags_max_count violated: {len(hashtags)} > {max_count}",
                }
            )
    return failures


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
