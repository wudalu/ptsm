from __future__ import annotations

from copy import deepcopy

from ptsm.agent_runtime.nodes.executor import build_executor_node
from ptsm.domain.psychology_carousel import normalize_psychology_carousel_plan
from ptsm.infrastructure.llm.factory import DeterministicDraftBackend


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


class StaticDraftingAgent:
    def __init__(self, draft: dict[str, object]) -> None:
        self.draft = draft

    def generate(self, **_kwargs: object) -> dict[str, object]:
        return deepcopy(self.draft)


def _psychology_carousel_draft() -> dict[str, object]:
    return DeterministicDraftBackend().generate(
        scene="下班后身体还在工位，需要5分钟恢复信号",
        planner_prompt="modern_psychology_post 现代心理困境观察",
        skill_contents=[
            "# Psychology Style\n#心理学，使用具体场景和低风险工具。",
            "# XHS Image Strategy\n输出 image_plan。",
        ],
    )


def _psychology_carousel_gate(
    _state: dict[str, object],
    draft: dict[str, object],
) -> list[str]:
    image_plan = draft.get("image_plan")
    if not isinstance(image_plan, dict):
        return []
    is_carousel = (
        "slides" in image_plan
        or "carousel_style" in image_plan
        or image_plan.get("style") == "psychology_text_card"
        or image_plan.get("role") == "text_carousel"
    )
    if not is_carousel:
        return []
    try:
        normalize_psychology_carousel_plan(image_plan)
    except ValueError:
        return ["invalid psychology carousel plan"]
    return []


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


def test_executor_preserves_a_valid_psychology_carousel_unchanged() -> None:
    draft = _psychology_carousel_draft()
    executor = build_executor_node(
        drafting_agent=StaticDraftingAgent(draft),
        psychology_carousel_draft_gate=lambda value: _psychology_carousel_gate({}, value),
    )

    result = executor({"scene": "下班后身体还在工位"})

    assert result["draft_content"] == draft
    assert result["psychology_carousel_executor_errors"] == []


def test_executor_rejects_an_unsafe_carousel_before_draft_state() -> None:
    draft = _psychology_carousel_draft()
    unsafe_text = "source:https://private.example/claim"
    draft["image_plan"]["slides"][1]["body_lines"][0] = unsafe_text
    executor = build_executor_node(
        drafting_agent=StaticDraftingAgent(draft),
        psychology_carousel_draft_gate=lambda value: _psychology_carousel_gate({}, value),
    )

    result = executor({"scene": "下班后身体还在工位"})

    assert result["draft_content"] == {
        "title": "",
        "image_text": "",
        "body": "",
        "hashtags": [],
    }
    assert result["psychology_carousel_executor_errors"] == [
        "psychology carousel draft rejected before runtime state: "
        "invalid psychology carousel plan"
    ]
    assert unsafe_text not in repr(result)


def test_executor_keeps_legacy_psychology_image_plan_compatible() -> None:
    draft = _psychology_carousel_draft()
    draft["image_plan"] = {
        "backend": "local_social_screenshot",
        "style": "iphone_notes",
        "role": "save_tool",
        "text_density": "low",
        "max_text_units": "3",
    }
    executor = build_executor_node(
        drafting_agent=StaticDraftingAgent(draft),
        psychology_carousel_draft_gate=lambda value: _psychology_carousel_gate({}, value),
    )

    result = executor({"scene": "下班后身体还在工位"})

    assert result["draft_content"] == draft
    assert result["psychology_carousel_executor_errors"] == []


def test_executor_rejects_a_partial_psychology_carousel_without_slides() -> None:
    draft = _psychology_carousel_draft()
    draft["image_plan"].pop("slides")
    executor = build_executor_node(
        drafting_agent=StaticDraftingAgent(draft),
        psychology_carousel_draft_gate=lambda value: _psychology_carousel_gate({}, value),
    )

    result = executor({"scene": "下班后身体还在工位"})

    assert result["psychology_carousel_executor_errors"] == [
        "psychology carousel draft rejected before runtime state: "
        "invalid psychology carousel plan"
    ]


def test_executor_keeps_gate_error_detail_for_retry_feedback() -> None:
    draft = _psychology_carousel_draft()
    draft["image_plan"]["slides"][1]["role"] = "scene"
    executor = build_executor_node(
        drafting_agent=StaticDraftingAgent(draft),
        psychology_carousel_draft_gate=lambda value: [
            "invalid psychology carousel plan: slides.1.role: "
            "Input should be 'concrete_scene'"
        ],
    )

    result = executor({"scene": "下班后身体还在工位"})

    assert result["psychology_carousel_executor_errors"] == [
        "psychology carousel draft rejected before runtime state: "
        "invalid psychology carousel plan: slides.1.role: "
        "Input should be 'concrete_scene'"
    ]
