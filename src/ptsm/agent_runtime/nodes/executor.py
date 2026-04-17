from __future__ import annotations

from typing import Any

from ptsm.agent_runtime.state import ExecutionState


def build_executor_node(*, drafting_agent: Any):
    def executor(state: ExecutionState) -> ExecutionState:
        attempt_count = int(state.get("attempt_count", 0)) + 1
        draft = drafting_agent.generate(
            scene=state["scene"],
            reflection_feedback=state.get("reflection_feedback"),
            planner_prompt=state.get("planner_prompt"),
            skill_contents=state.get("loaded_skill_contents", []),
        )
        return {
            "attempt_count": attempt_count,
            "draft_content": draft,
        }

    return executor
