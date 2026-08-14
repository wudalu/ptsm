from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ptsm.agent_runtime.state import ExecutionState


AiTechDraftGate = Callable[[dict[str, object]], list[str]]
PsychologyLearningDraftGate = Callable[[dict[str, object]], list[str]]
PsychologyCarouselDraftGate = Callable[[dict[str, object]], list[str]]


def build_executor_node(
    *,
    drafting_agent: Any,
    ai_tech_draft_gate: AiTechDraftGate | None = None,
    psychology_learning_draft_gate: PsychologyLearningDraftGate | None = None,
    psychology_carousel_draft_gate: PsychologyCarouselDraftGate | None = None,
):
    def executor(state: ExecutionState) -> ExecutionState:
        attempt_count = int(state.get("attempt_count", 0)) + 1
        draft = drafting_agent.generate(
            scene=state["scene"],
            reflection_feedback=state.get("reflection_feedback"),
            persona_prompt=state.get("persona_prompt"),
            planner_prompt=state.get("planner_prompt"),
            skill_contents=state.get("loaded_skill_contents", []),
            runtime_skill_contents=state.get("runtime_skill_contents", []),
        )
        ai_tech_errors = (
            ai_tech_draft_gate(draft) if ai_tech_draft_gate is not None else []
        )
        psychology_learning_errors = (
            psychology_learning_draft_gate(draft)
            if psychology_learning_draft_gate is not None
            else []
        )
        psychology_carousel_errors = (
            psychology_carousel_draft_gate(draft)
            if psychology_carousel_draft_gate is not None
            and psychology_learning_draft_gate is None
            else []
        )
        if ai_tech_errors or psychology_learning_errors or psychology_carousel_errors:
            # Do not put unsafe model output into LangGraph state: state is
            # checkpointed and later returned by the generic graph API.
            # Keep only stable diagnostics for the retry loop.
            return {
                "attempt_count": attempt_count,
                "draft_content": {
                    "title": "",
                    "image_text": "",
                    "body": "",
                    "hashtags": [],
                },
                "ai_tech_executor_errors": (
                    ["AI tech draft rejected before runtime state"]
                    if ai_tech_errors
                    else []
                ),
                "psychology_learning_executor_errors": (
                    ["psychology learning draft rejected before runtime state"]
                    if psychology_learning_errors
                    else []
                ),
                "psychology_carousel_executor_errors": (
                    ["psychology carousel draft rejected before runtime state"]
                    if psychology_carousel_errors
                    else []
                ),
            }
        return {
            "attempt_count": attempt_count,
            "draft_content": draft,
            "ai_tech_executor_errors": [],
            "psychology_learning_executor_errors": [],
            "psychology_carousel_executor_errors": [],
        }

    return executor
