from __future__ import annotations

from typing import Any
from typing_extensions import Literal, TypedDict

ReflectionDecision = Literal["continue", "retry", "replan", "finalize", "fail"]


class ExecutionState(TypedDict, total=False):
    scene: str
    platform: str
    account_id: str
    status: str
    selected_playbook: str
    playbook_id: str
    candidate_skills: list[str]
    activated_skills: list[str]
    activated_skill_details: list[dict[str, Any]]
    draft_content: dict[str, Any]
    final_content: dict[str, Any]
    reflection_feedback: str
    reflection_decision: ReflectionDecision
    required_revision: bool
    replanned: bool
    attempt_count: int
    planner_iterations: int
    drafting_provider: str
    planner_prompt: str
    persona_prompt: str
    reflection_prompt: str
    reflection_rules: dict[str, Any]
    loaded_skill_contents: list[str]
    runtime_skill_contents: list[str]
    runtime_skill_details: list[dict[str, Any]]
    topic_selection: dict[str, Any]
    artifact_path: str
    memory_hits: list[dict[str, Any]]
    content_quality_eval: dict[str, Any]
    content_review: dict[str, Any]
    ai_tech_executor_errors: list[str]
    psychology_learning_executor_errors: list[str]
    psychology_carousel_executor_errors: list[str]
