from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState


def build_reflector_node(*, max_attempts: int):
    def reflector(state: ExecutionState) -> ExecutionState:
        rules = state["reflection_rules"]
        draft = state["draft_content"]
        body = str(draft["body"])
        required_hashtag = rules["required_hashtag"]
        required_phrase = rules["must_include_phrase"]
        passed = required_hashtag in draft["hashtags"] and required_phrase in body

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
                "reflection_feedback": state["reflection_prompt"],
            }

        return {
            "required_revision": True,
            "reflection_decision": "fail",
            "reflection_feedback": state["reflection_prompt"],
        }

    return reflector
