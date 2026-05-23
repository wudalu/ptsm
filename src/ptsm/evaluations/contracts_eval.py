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
    if isinstance(title, str):
        forbidden_titles = _string_list(constraints.get("title_must_not_equal_any"))
        if title in forbidden_titles:
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": f"title_must_not_equal_any violated: {title}",
                }
            )
        required_title_terms = _string_list(constraints.get("title_must_include_any"))
        if required_title_terms and not any(term in title for term in required_title_terms):
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": (
                        "title_must_include_any violated: "
                        f"missing one of {required_title_terms}"
                    ),
                }
            )

    image_text = payload.get("image_text")
    if isinstance(image_text, str):
        forbidden_image_texts = _string_list(
            constraints.get("image_text_must_not_equal_any")
        )
        if image_text in forbidden_image_texts:
            failures.append(
                {
                    "path": _field_path(target, "image_text"),
                    "value_preview": image_text,
                    "observation": (
                        "image_text_must_not_equal_any violated: "
                        f"{image_text}"
                    ),
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
        required_any = _string_list(constraints.get("hashtags_must_include_any"))
        if required_any and not any(tag in hashtags for tag in required_any):
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": (
                        "hashtags_must_include_any violated: "
                        f"missing one of {required_any}"
                    ),
                }
            )
        forbidden_any = _string_list(constraints.get("hashtags_must_not_include_any"))
        present_forbidden = [tag for tag in forbidden_any if tag in hashtags]
        if present_forbidden:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": (
                        "hashtags_must_not_include_any violated: "
                        f"found {present_forbidden}"
                    ),
                }
            )

    body = payload.get("body")
    if isinstance(body, str):
        body_min_chars = constraints.get("body_min_chars")
        if isinstance(body_min_chars, int) and len(body) < body_min_chars:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_min_chars violated: "
                        f"{len(body)} < {body_min_chars}"
                    ),
                }
            )

        body_max_chars = constraints.get("body_max_chars")
        if isinstance(body_max_chars, int) and len(body) > body_max_chars:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_max_chars violated: "
                        f"{len(body)} > {body_max_chars}"
                    ),
                }
            )

        include_any = _string_list(constraints.get("body_must_include_any"))
        if include_any and not any(term in body for term in include_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_any violated: "
                        f"missing one of {include_any}"
                    ),
                }
            )

        include_all = _string_list(constraints.get("body_must_include_all"))
        missing_all = [term for term in include_all if term not in body]
        if missing_all:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_all violated: "
                        f"missing {missing_all}"
                    ),
                }
            )

        comment_prompt_any = _string_list(
            constraints.get("body_must_include_comment_prompt_any")
        )
        if comment_prompt_any and not any(term in body for term in comment_prompt_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_comment_prompt_any violated: "
                        f"missing one of {comment_prompt_any}"
                    ),
                }
            )

        save_trigger_any = _string_list(
            constraints.get("body_must_include_save_trigger_any")
        )
        if save_trigger_any and not any(term in body for term in save_trigger_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_save_trigger_any violated: "
                        f"missing one of {save_trigger_any}"
                    ),
                }
            )

        forbidden = _string_list(constraints.get("body_must_not_include_any"))
        present = [term for term in forbidden if term in body]
        if present:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_not_include_any violated: "
                        f"found {present}"
                    ),
                }
            )
    combined_forbidden = _string_list(constraints.get("combined_must_not_include_any"))
    if combined_forbidden:
        combined_text = "\n".join(
            value
            for value in (title, image_text, body)
            if isinstance(value, str)
        )
        present = [term for term in combined_forbidden if term in combined_text]
        if present:
            failures.append(
                {
                    "path": (
                        "final_content.title/image_text/body"
                        if target.phase == "executor"
                        else "title/image_text/body"
                    ),
                    "value_preview": combined_text[:120],
                    "observation": (
                        "combined_must_not_include_any violated: "
                        f"found {present}"
                    ),
                }
            )
    return failures


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


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
