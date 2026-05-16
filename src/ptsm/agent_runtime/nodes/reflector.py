from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState
from ptsm.evaluations.contracts import EvalResult, EvalTarget
from ptsm.evaluations.llm_judge import LLMJudgeBackend, run_content_quality_judge


def build_reflector_node(
    *, max_attempts: int, content_quality_backend: LLMJudgeBackend | None = None
):
    def reflector(state: ExecutionState) -> ExecutionState:
        rules = state["reflection_rules"]
        draft = state["draft_content"]
        body = str(draft["body"])
        missing = _missing_requirements(rules=rules, draft=draft, body=body)
        quality_eval: EvalResult | None = None
        if not missing and content_quality_backend is not None:
            quality_eval = run_content_quality_judge(
                _build_content_quality_target(state=state, draft=draft),
                backend=content_quality_backend,
                gate_level="required",
            )
            if quality_eval.status != "passed":
                missing.append(_quality_feedback(quality_eval))

        passed = not missing

        if passed:
            return {
                "required_revision": False,
                "reflection_decision": "finalize",
                "final_content": draft,
                "reflection_feedback": "",
                **_quality_eval_state(quality_eval),
            }

        if int(state.get("attempt_count", 0)) < max_attempts:
            return {
                "required_revision": True,
                "reflection_decision": "retry",
                "reflection_feedback": _build_feedback(state.get("reflection_prompt", ""), missing),
                **_quality_eval_state(quality_eval),
            }

        return {
            "required_revision": True,
            "reflection_decision": "fail",
            "reflection_feedback": _build_feedback(state.get("reflection_prompt", ""), missing),
            **_quality_eval_state(quality_eval),
        }

    return reflector


def _missing_requirements(
    *, rules: dict[str, object], draft: dict[str, object], body: str
) -> list[str]:
    missing: list[str] = []
    hashtags = draft.get("hashtags", [])
    if not isinstance(hashtags, list):
        hashtags = []

    required_hashtag = str(rules.get("required_hashtag", "")).strip()
    if required_hashtag and required_hashtag not in hashtags:
        missing.append(f"missing required hashtag {required_hashtag}")

    required_phrase = str(rules.get("must_include_phrase", "")).strip()
    if required_phrase and required_phrase not in body:
        missing.append(f"missing required phrase {required_phrase}")

    title = str(draft.get("title", "")).strip()
    forbidden_titles = _string_list(rules.get("title_must_not_equal_any"))
    if title and title in forbidden_titles:
        missing.append(f"title_must_not_equal_any violated: {title}")

    body_required_any = _string_list(rules.get("body_must_include_any"))
    if body_required_any and not any(term in body for term in body_required_any):
        missing.append(
            "body_must_include_any violated: "
            + ", ".join(body_required_any)
        )

    body_forbidden = _string_list(rules.get("body_must_not_include_any"))
    present_forbidden = [term for term in body_forbidden if term in body]
    if present_forbidden:
        missing.append(
            "body_must_not_include_any violated: "
            + ", ".join(present_forbidden)
        )

    return missing


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _build_feedback(reflection_prompt: str, missing: list[str]) -> str:
    if not missing:
        return reflection_prompt
    summary = "Required reflection checks failed: " + "; ".join(missing)
    if not reflection_prompt:
        return summary
    return f"{summary}\n\n{reflection_prompt}"


def _build_content_quality_target(
    *, state: ExecutionState, draft: dict[str, object]
) -> EvalTarget:
    attempt_count = int(state.get("attempt_count", 0))
    playbook_id = str(state.get("playbook_id", ""))
    account_id = str(state.get("account_id", ""))
    return EvalTarget(
        target_id=f"{account_id}:{playbook_id}:executor:attempt-{attempt_count}",
        run_id=str(state.get("thread_id", "")),
        playbook_id=playbook_id,
        account_id=account_id,
        platform=str(state.get("platform", "")),
        phase="executor",
        target_type="artifact_slice",
        output_ref={"final_content": draft},
    )


def _quality_feedback(result: EvalResult) -> str:
    parts = [f"content quality judge failed: {result.reason}"]
    rewrite_hint = _rewrite_hint(result)
    if rewrite_hint:
        parts.append(f"rewrite_hint: {rewrite_hint}")
    return " ".join(parts)


def _rewrite_hint(result: EvalResult) -> str:
    for item in result.evidence or []:
        hint = item.get("rewrite_hint")
        if isinstance(hint, str) and hint.strip():
            return hint.strip()
    return ""


def _quality_eval_state(result: EvalResult | None) -> dict[str, object]:
    if result is None:
        return {}
    return {"content_quality_eval": result.to_dict()}
