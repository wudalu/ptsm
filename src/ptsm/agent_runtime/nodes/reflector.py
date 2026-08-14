from __future__ import annotations

from collections.abc import Callable

from ptsm.agent_runtime.state import ExecutionState

ContentQualityJudge = Callable[[ExecutionState, dict[str, object]], dict[str, object]]
AiTechDraftGate = Callable[[ExecutionState, dict[str, object]], list[str]]
PsychologyLearningDraftGate = Callable[[ExecutionState, dict[str, object]], list[str]]
PsychologyCarouselDraftGate = Callable[[ExecutionState, dict[str, object]], list[str]]


def build_reflector_node(
    *,
    max_attempts: int,
    content_quality_judge: ContentQualityJudge | None = None,
    ai_tech_draft_gate: AiTechDraftGate | None = None,
    psychology_learning_draft_gate: PsychologyLearningDraftGate | None = None,
    psychology_carousel_draft_gate: PsychologyCarouselDraftGate | None = None,
):
    def reflector(state: ExecutionState) -> ExecutionState:
        rules = state["reflection_rules"]
        draft = state["draft_content"]
        body = str(draft["body"])
        catalog_managed_psychology_lesson = psychology_learning_draft_gate is not None
        # A learning-series lesson is an exact, reviewed catalog deliverable.
        # The ordinary psychology reflection contract describes open-ended
        # psychology posts, so applying it here can demand a different concept,
        # save trigger, or comment handoff than the selected lesson.  The bound
        # catalog gate is stricter for this mode and owns the entire visible
        # draft instead.
        missing = (
            []
            if catalog_managed_psychology_lesson
            else _missing_requirements(rules=rules, draft=draft, body=body)
        )
        executor_errors = state.get("ai_tech_executor_errors")
        if isinstance(executor_errors, list):
            missing.extend(
                str(error).strip() for error in executor_errors if str(error).strip()
            )
        psychology_executor_errors = state.get("psychology_learning_executor_errors")
        if isinstance(psychology_executor_errors, list):
            missing.extend(
                str(error).strip()
                for error in psychology_executor_errors
                if str(error).strip()
            )
        psychology_carousel_executor_errors = state.get(
            "psychology_carousel_executor_errors"
        )
        if isinstance(psychology_carousel_executor_errors, list):
            missing.extend(
                str(error).strip()
                for error in psychology_carousel_executor_errors
                if str(error).strip()
            )
        quality_eval: dict[str, object] | None = None
        if not missing and ai_tech_draft_gate is not None:
            missing.extend(ai_tech_draft_gate(state, draft))
        if not missing and psychology_learning_draft_gate is not None:
            missing.extend(psychology_learning_draft_gate(state, draft))
        if (
            not missing
            and psychology_carousel_draft_gate is not None
            and psychology_learning_draft_gate is None
        ):
            missing.extend(psychology_carousel_draft_gate(state, draft))
        if (
            not missing
            and content_quality_judge is not None
            and not catalog_managed_psychology_lesson
        ):
            quality_eval = content_quality_judge(state, draft)
            if quality_eval.get("status") != "passed":
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

    forbidden_hashtags = _string_list(rules.get("hashtags_must_not_include_any"))
    present_forbidden_hashtags = [tag for tag in forbidden_hashtags if tag in hashtags]
    if present_forbidden_hashtags:
        missing.append(
            "hashtags_must_not_include_any violated: "
            + ", ".join(present_forbidden_hashtags)
        )

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


def _quality_feedback(result: dict[str, object]) -> str:
    parts = [f"content quality judge failed: {result.get('reason', 'unknown')}"]
    rewrite_hint = _rewrite_hint(result)
    if rewrite_hint:
        parts.append(f"rewrite_hint: {rewrite_hint}")
    return " ".join(parts)


def _rewrite_hint(result: dict[str, object]) -> str:
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        return ""
    for item in evidence:
        if not isinstance(item, dict):
            continue
        hint = item.get("rewrite_hint")
        if isinstance(hint, str) and hint.strip():
            return hint.strip()
    return ""


def _quality_eval_state(result: dict[str, object] | None) -> dict[str, object]:
    if result is None:
        return {}
    return {"content_quality_eval": result}
