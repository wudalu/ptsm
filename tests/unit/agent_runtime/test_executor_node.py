from __future__ import annotations

from ptsm.agent_runtime.nodes.executor import build_executor_node


class CapturingDraftingAgent:
    def __init__(self) -> None:
        self.kwargs: dict[str, object] = {}

    def generate(self, **kwargs: object) -> dict[str, object]:
        self.kwargs = kwargs
        return {
            "title": "像真人发的日常",
            "image_text": "今天又被热梗创到",
            "body": "正文",
            "hashtags": ["#发疯文学"],
        }


def test_executor_passes_persona_prompt_to_drafting_agent() -> None:
    drafting_agent = CapturingDraftingAgent()
    executor = build_executor_node(drafting_agent=drafting_agent)

    result = executor(
        {
            "scene": "周六社畜躺平",
            "persona_prompt": "# Persona\n普通打工人，表达要有人味。",
            "planner_prompt": "# Planner",
            "loaded_skill_contents": ["# Skill"],
            "runtime_skill_contents": ["# XHS Trend Scan Live Context\n主切口：怎么才周四"],
        }
    )

    assert result["attempt_count"] == 1
    assert drafting_agent.kwargs["persona_prompt"] == "# Persona\n普通打工人，表达要有人味。"
    assert drafting_agent.kwargs["runtime_skill_contents"] == [
        "# XHS Trend Scan Live Context\n主切口：怎么才周四"
    ]
