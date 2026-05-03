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
    reflection_rules: dict[str, str]
    loaded_skill_contents: list[str]
    runtime_skill_contents: list[str]
    artifact_path: str
    memory_hits: list[dict[str, Any]]
