from __future__ import annotations

from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget


def _make_eval_id(target_id: str, evaluator_id: str) -> str:
    return f"{target_id}:{evaluator_id}"


def _result(
    target_id: str,
    evaluator_id: str,
    status: str,
    reason: str,
    score: float | None = None,
    evidence: list[dict] | None = None,
) -> EvalResult:
    return EvalResult(
        eval_result_id=_make_eval_id(target_id, evaluator_id),
        eval_run_id="",
        target_id=target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status=status,
        reason=reason,
        score=score,
        evidence=evidence or [],
    )


def _get_final_content(target: EvalTarget) -> dict | None:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return None
    fc = ref.get("final_content")
    if isinstance(fc, dict):
        return fc
    return None


def rule_final_content_fields(target: EvalTarget) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(
            target.target_id,
            "final_content.required_fields",
            "skipped",
            "final_content not found in target",
        )
    required = ["title", "body", "hashtags"]
    missing = [f for f in required if not fc.get(f)]
    if missing:
        return _result(
            target.target_id,
            "final_content.required_fields",
            "failed",
            f"missing required fields: {missing}",
            score=0.0,
            evidence=[
                {"path": f"final_content.{f}", "value_preview": str(fc.get(f)),
                 "observation": "missing"}
                for f in missing
            ],
        )
    return _result(
        target.target_id,
        "final_content.required_fields",
        "passed",
        "all required fields present",
        score=1.0,
    )


def rule_hashtags_non_empty(target: EvalTarget) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(
            target.target_id, "hashtags.non_empty", "skipped", "no final_content"
        )
    hashtags = fc.get("hashtags")
    if not isinstance(hashtags, list) or not hashtags:
        return _result(
            target.target_id,
            "hashtags.non_empty",
            "failed",
            "hashtags list is empty or missing",
            score=0.0,
            evidence=[
                {
                    "path": "final_content.hashtags",
                    "value_preview": str(hashtags),
                    "observation": "empty",
                }
            ],
        )
    return _result(
        target.target_id,
        "hashtags.non_empty",
        "passed",
        f"found {len(hashtags)} hashtags",
        score=1.0,
    )


def rule_hashtags_bounded(
    target: EvalTarget, max_hashtags: int = 8
) -> EvalResult:
    fc = _get_final_content(target)
    if fc is None:
        return _result(
            target.target_id, "hashtags.bounded", "skipped", "no final_content"
        )
    hashtags = fc.get("hashtags", [])
    if not isinstance(hashtags, list):
        return _result(
            target.target_id, "hashtags.bounded", "skipped", "hashtags not a list"
        )
    if len(hashtags) > max_hashtags:
        return _result(
            target.target_id,
            "hashtags.bounded",
            "failed",
            f"hashtags count {len(hashtags)} exceeds max {max_hashtags}",
            score=0.0,
        )
    return _result(
        target.target_id,
        "hashtags.bounded",
        "passed",
        f"hashtags count {len(hashtags)} within limit {max_hashtags}",
        score=1.0,
    )


def rule_publish_mode_valid(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(
            target.target_id, "publish_mode.valid", "skipped", "no output ref"
        )
    mode = ref.get("publish_mode")
    valid = {"dry-run", "mcp-real"}
    if mode not in valid:
        return _result(
            target.target_id,
            "publish_mode.valid",
            "failed",
            f"invalid publish_mode: {mode}",
            score=0.0,
        )
    return _result(
        target.target_id,
        "publish_mode.valid",
        "passed",
        f"valid publish_mode: {mode}",
        score=1.0,
    )


def rule_no_real_publish_in_dry_run(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return _result(
            target.target_id,
            "publish.dry_run_safety",
            "skipped",
            "no output ref",
        )
    publish_mode = ref.get("publish_mode", "dry-run")
    publish_result = ref.get("publish_result")
    if publish_mode == "dry-run":
        if isinstance(publish_result, dict) and publish_result.get(
            "status"
        ) not in ("dry_run", None):
            return _result(
                target.target_id,
                "publish.dry_run_safety",
                "failed",
                "real publish detected in dry-run mode",
                score=0.0,
            )
    return _result(
        target.target_id,
        "publish.dry_run_safety",
        "passed",
        "dry-run safety ok",
        score=1.0,
    )


ALL_RULE_EVALUATORS: list[EvaluatorSpec] = [
    EvaluatorSpec(
        "final_content.required_fields", "1", "rule", "shared evaluation",
        {"phases": ["executor"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "hashtags.non_empty", "1", "rule", "shared evaluation",
        {"phases": ["executor"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "hashtags.bounded", "1", "rule", "shared evaluation",
        {"phases": ["executor"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "publish_mode.valid", "1", "rule", "shared evaluation",
        {"phases": ["final"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "publish.dry_run_safety", "1", "rule", "shared evaluation",
        {"phases": ["final"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
]
