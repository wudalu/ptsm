from __future__ import annotations

import json
from typing import Protocol

from ptsm.evaluations.contracts import EvalResult, EvalTarget


class LLMJudgeBackend(Protocol):
    def judge(self, *, prompt: str) -> str: ...


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


def _coerce_score(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return None
