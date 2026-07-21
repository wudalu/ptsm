from __future__ import annotations

import json
from typing import Protocol

from ptsm.evaluations.contracts import EvalResult, EvalTarget


class LLMJudgeBackend(Protocol):
    def judge(self, *, prompt: str) -> str: ...


CONTENT_QUALITY_LABELS = (
    "hook_specificity",
    "save_trigger",
    "comment_trigger",
    "platform_native_format",
    "persona_fit",
    "safety",
)
CONTENT_QUALITY_ALLOWED_LABEL_VALUES = {"pass", "warn", "fail"}
CONTENT_QUALITY_RUBRIC = (
    "Evaluate content quality for Xiaohongshu. Return strict JSON only with keys: "
    "score, labels, reason, rewrite_hint. "
    "labels must contain hook_specificity, save_trigger, comment_trigger, "
    "platform_native_format, persona_fit, safety, each set to pass, warn, or fail. "
    "Check whether the hook is specific, there is a save/share trigger, there is a "
    "comment/example prompt, the format feels platform-native, persona fits the "
    "playbook, and safety risks are absent. Reward compact Xiaohongshu rhythm: "
    "2-4 short beats, a concrete lived detail, one usable takeaway, and a natural "
    "rather than template-like ending. Do not add a new deterministic hard gate; "
    "use this only as a qualitative signal. Do not judge virality."
)


def run_content_quality_judge(
    target: EvalTarget,
    *,
    backend: LLMJudgeBackend,
    evaluator_id: str = "llm.executor.content_quality",
    threshold: float = 0.7,
    gate_level: str = "required",
) -> EvalResult:
    prompt = _build_prompt(target=target, rubric=CONTENT_QUALITY_RUBRIC)
    raw_response = backend.judge(prompt=prompt)
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        return _warning_error_result(
            target=target,
            evaluator_id=evaluator_id,
            reason=f"invalid JSON from content quality judge: {exc.msg}",
            gate_level=gate_level,
        )

    if not isinstance(payload, dict):
        return _warning_error_result(
            target=target,
            evaluator_id=evaluator_id,
            reason="invalid JSON from content quality judge: expected object",
            gate_level=gate_level,
        )

    labels = _content_quality_labels(payload.get("labels"))
    if labels is None:
        return _warning_error_result(
            target=target,
            evaluator_id=evaluator_id,
            reason="invalid JSON from content quality judge: labels missing or invalid",
            gate_level=gate_level,
        )

    score = _coerce_score(payload.get("score"))
    has_failed_label = any(value == "fail" for value in labels.values())
    status = (
        "passed"
        if score is not None and score >= threshold and not has_failed_label
        else "failed"
    )
    rewrite_hint = str(payload.get("rewrite_hint") or "")

    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status=status,
        reason=str(payload.get("reason") or "content quality judge completed"),
        score=score,
        label="content_quality",
        evidence=[{"labels": labels, "rewrite_hint": rewrite_hint}],
        gate_level=gate_level,
    )


def run_llm_judge(
    target: EvalTarget,
    *,
    evaluator_id: str,
    rubric: str,
    backend: LLMJudgeBackend,
    threshold: float = 0.7,
) -> EvalResult:
    prompt = _build_prompt(target=target, rubric=rubric)
    raw_response = backend.judge(prompt=prompt)
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="error",
            reason=f"invalid JSON from LLM judge: {exc.msg}",
            gate_level="warning",
        )

    if not isinstance(payload, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="error",
            reason="invalid JSON from LLM judge: expected object",
            gate_level="warning",
        )

    score = _coerce_score(payload.get("score"))
    status = "passed" if score is not None and score >= threshold else "failed"
    evidence = payload.get("evidence")
    if not isinstance(evidence, list):
        evidence = []
    confidence = _coerce_score(payload.get("confidence"))
    label = payload.get("label")

    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status=status,
        reason=str(payload.get("reason") or "LLM judge completed"),
        score=score,
        label=str(label) if label is not None else None,
        evidence=evidence,
        confidence=confidence,
        gate_level="warning",
    )


def _build_prompt(*, target: EvalTarget, rubric: str) -> str:
    output = target.output_ref if target.output_ref is not None else {}
    output_json = json.dumps(output, ensure_ascii=False, sort_keys=True)
    return (
        "You are a PTSM evaluation judge. Return strict JSON only with keys "
        "score, label, reason, evidence, confidence.\n"
        f"Playbook: {target.playbook_id}\n"
        f"Phase: {target.phase}\n"
        f"Rubric: {rubric}\n"
        f"Output JSON: {output_json}"
    )


def _content_quality_labels(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    labels: dict[str, str] = {}
    for key in CONTENT_QUALITY_LABELS:
        raw_label = value.get(key)
        if raw_label not in CONTENT_QUALITY_ALLOWED_LABEL_VALUES:
            return None
        labels[key] = str(raw_label)
    return labels


def _warning_error_result(
    *, target: EvalTarget, evaluator_id: str, reason: str, gate_level: str
) -> EvalResult:
    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status="error",
        reason=reason,
        gate_level=gate_level,
    )


def _coerce_score(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return None
