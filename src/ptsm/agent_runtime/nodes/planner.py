from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry
from ptsm.skills.runtime_context import SkillContextResolver
from ptsm.skills.selector import SkillSelector


def build_planner_node(
    *,
    domain: str,
    playbook_id: str | None,
    playbooks: PlaybookRegistry,
    playbook_loader: PlaybookLoader,
    skills: SkillRegistry,
    skill_loader: SkillLoader,
    skill_context_resolver: SkillContextResolver | None = None,
):
    def planner(state: ExecutionState) -> ExecutionState:
        if playbook_id is not None:
            playbook = playbooks.get(playbook_id)
        else:
            playbook = playbooks.select(domain=domain, platform=state["platform"])
        surface = SkillSelector(registry=skills, loader=skill_loader).select(
            domain=domain,
            platform=state["platform"],
            playbook_id=playbook.playbook_id,
        )
        discovered = {skill.skill_name for skill in surface.list_summaries()}
        missing = [name for name in playbook.required_skills if name not in discovered]
        if missing:
            raise LookupError(f"Missing required skills: {missing}")

        loaded_skills = [surface.activate(name) for name in playbook.required_skills]
        loaded_playbook = playbook_loader.load(playbook.playbook_id)
        activated_skills = [skill.skill.skill_name for skill in loaded_skills]
        activated_skill_details = [
            {
                "skill_name": skill.skill.skill_name,
                "display_name": skill.skill.display_name,
                "resource_type": "static_skill",
                "source_path": str(skill.source_path),
            }
            for skill in loaded_skills
        ]
        runtime_skill_contexts = (
            skill_context_resolver.resolve(
                state=state,
                playbook=playbook,
                loaded_skills=loaded_skills,
            )
            if skill_context_resolver is not None
            else {}
        )
        topic_direction_context = _build_topic_direction_runtime_context(state)
        if topic_direction_context:
            runtime_skill_contexts = {
                **runtime_skill_contexts,
                "topic_direction_guidance": topic_direction_context,
            }
        runtime_skill_details = [
            {
                "skill_name": skill_name,
                "resource_type": "runtime_context",
                "resource_id": f"{skill_name}:runtime_context",
                "source_path": None,
                "content_preview": context.splitlines()[0].strip() if context.strip() else "",
            }
            for skill_name, context in runtime_skill_contexts.items()
        ]

        return {
            "planner_iterations": int(state.get("planner_iterations", 0)) + 1,
            "selected_playbook": playbook.playbook_id,
            "playbook_id": playbook.playbook_id,
            "candidate_skills": list(playbook.required_skills),
            "activated_skills": activated_skills,
            "activated_skill_details": activated_skill_details,
            "planner_prompt": loaded_playbook.planner_prompt,
            "persona_prompt": loaded_playbook.persona_prompt,
            "reflection_prompt": loaded_playbook.reflection_prompt,
            "reflection_rules": loaded_playbook.definition.reflection,
            "loaded_skill_contents": [skill.content for skill in loaded_skills],
            "runtime_skill_contents": list(runtime_skill_contexts.values()),
            "runtime_skill_details": runtime_skill_details,
        }

    return planner


def _build_topic_direction_runtime_context(state: ExecutionState) -> str:
    topic_selection = state.get("topic_selection")
    if not isinstance(topic_selection, dict):
        return ""
    direction = topic_selection.get("direction")
    if not isinstance(direction, dict):
        return ""
    format_recommendation = direction.get("format_recommendation")
    if not isinstance(format_recommendation, dict):
        format_recommendation = {}

    direction_id = str(
        topic_selection.get("topic_direction_id") or direction.get("id") or ""
    ).strip()
    lines = [
        "# XHS Topic Direction Guidance",
        "- status: confirmed_by_guide_post",
        f"- source: {_string_value(topic_selection.get('source'), default='guide-post')}",
        f"- topic_direction_id: {direction_id}",
        f"- name: {_string_value(direction.get('name'))}",
        f"- viral_hook: {_string_value(direction.get('viral_hook'))}",
        f"- content_angle: {_string_value(direction.get('content_angle'))}",
        f"- saveable_tool: {_string_value(direction.get('saveable_tool'))}",
        f"- comment_prompt: {_string_value(direction.get('comment_prompt'))}",
        f"- avoid: {_string_value(direction.get('avoid'))}",
        f"- format_archetype: {_string_value(format_recommendation.get('format_archetype'))}",
        f"- cover_role: {_string_value(format_recommendation.get('cover_role'))}",
        f"- body_shape: {_string_value(format_recommendation.get('body_shape'))}",
        (
            "- visual_evidence_need: "
            f"{_string_value(format_recommendation.get('visual_evidence_need'))}"
        ),
        (
            "- avoid_format: "
            f"{', '.join(_string_list(format_recommendation.get('avoid_format')))}"
        ),
        (
            "- drafting_constraints: Treat this as the primary selected direction; "
            "align title, cover, body structure, saveable unit, and comment handoff "
            "with the format recommendation. Do not switch to dense text poster."
        ),
    ]
    return "\n".join(lines)


def _string_value(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _string_list(value: object) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []
