from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState


def build_reflector_node(*, max_attempts: int):
    def reflector(state: ExecutionState) -> ExecutionState:
        rules = state["reflection_rules"]
        draft = state["draft_content"]
        body = str(draft["body"])
        missing = _missing_requirements(rules=rules, draft=draft, body=body)
        passed = not missing

        if passed:
            return {
                "required_revision": False,
                "reflection_decision": "finalize",
                "final_content": draft,
                "reflection_feedback": "",
            }

        if int(state.get("attempt_count", 0)) < max_attempts:
            return {
                "required_revision": True,
                "reflection_decision": "retry",
                "reflection_feedback": _build_feedback(state.get("reflection_prompt", ""), missing),
            }

        return {
            "required_revision": True,
            "reflection_decision": "fail",
            "reflection_feedback": _build_feedback(state.get("reflection_prompt", ""), missing),
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

    return missing


def _build_feedback(reflection_prompt: str, missing: list[str]) -> str:
    if not missing:
        return reflection_prompt
    summary = "Required reflection checks failed: " + "; ".join(missing)
    if not reflection_prompt:
        return summary
    return f"{summary}\n\n{reflection_prompt}"
