from __future__ import annotations

import json
from typing import Any, Mapping

from pydantic import ValidationError

from ptsm.agent_runtime.state import ExecutionState
from ptsm.domain.ai_tech_content import (
    is_ai_tech_drafting_safe_text,
    parse_ai_tech_runtime_contract,
)
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
    ai_tech_evidence: Mapping[str, Any] | None = None,
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
        has_ai_tech_evidence = ai_tech_evidence is not None
        ai_tech_evidence_context = _build_ai_tech_evidence_runtime_context(ai_tech_evidence)
        if has_ai_tech_evidence:
            # Evidence-gated AI posts must not call live context builders: their
            # raw trend headlines and source metadata are selection signals, not
            # publishable facts or hands-on records.
            runtime_skill_contexts = {
                "ai_tech_evidence_contract": (
                    ai_tech_evidence_context
                    or _raise_invalid_ai_tech_evidence_contract()
                ),
            }
        else:
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


def _build_ai_tech_evidence_runtime_context(
    evidence: Mapping[str, Any] | None,
) -> str:
    """Render only whitelisted, provenance-safe AI evidence for drafting."""
    if not isinstance(evidence, Mapping):
        return ""
    try:
        normalized = parse_ai_tech_runtime_contract(evidence)
    except ValidationError:
        return ""
    mode = _safe_runtime_text(normalized.get("mode"))
    drafting_payload = normalized.get("drafting_payload")
    requirements = normalized.get("requirements")
    if (
        mode not in {"news_brief", "hands_on", "fact_translation"}
        or not isinstance(drafting_payload, dict)
        or not isinstance(requirements, dict)
    ):
        return ""

    payload = _safe_ai_tech_drafting_payload(mode=mode, payload=drafting_payload)
    if payload is None:
        return ""
    safe_requirements = {
        "mode": mode,
        "required_sections": _safe_runtime_text_list(requirements.get("required_sections")),
        "allowed_claim_kinds": _safe_runtime_text_list(
            requirements.get("allowed_claim_kinds")
        ),
        "forbidden_claim_kinds": _safe_runtime_text_list(
            requirements.get("forbidden_claim_kinds")
        ),
        "requires_test_evidence": bool(requirements.get("requires_test_evidence")),
    }
    rendered = json.dumps(
        {
            "mode": mode,
            "drafting_payload": payload,
            "requirements": safe_requirements,
        },
        ensure_ascii=False,
        indent=2,
    )
    return (
        "# AI Tech Evidence Contract\n"
        "Use only these approved facts and recorded observations. Do not invent "
        "a personal test, performance conclusion, source title, author, feed, or URL.\n"
        f"{rendered}"
    )


def _raise_invalid_ai_tech_evidence_contract() -> str:
    raise ValueError("invalid AI tech evidence contract reached planner")


def _safe_ai_tech_drafting_payload(
    *,
    mode: str,
    payload: dict[object, object],
) -> dict[str, object] | None:
    if mode == "news_brief":
        raw_items = payload.get("news_items")
        if not isinstance(raw_items, list | tuple):
            return None
        items: list[dict[str, object]] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                return None
            label = _safe_runtime_text(raw_item.get("label"))
            facts = _safe_runtime_text_list(raw_item.get("facts"))
            if not label or not facts:
                return None
            items.append({"label": label, "facts": facts})
        return {"mode": mode, "news_items": items}

    topic = _safe_runtime_text(payload.get("topic"))
    if not topic:
        return None
    if mode == "hands_on":
        raw_record = payload.get("hands_on")
        if not isinstance(raw_record, dict):
            return None
        record: dict[str, str] = {}
        for field_name in (
            "product",
            "version",
            "tested_at",
            "task",
            "input_summary",
            "observed_output",
            "limitation",
        ):
            value = _safe_runtime_text(raw_record.get(field_name))
            if not value:
                return None
            record[field_name] = value
        return {"mode": mode, "topic": topic, "hands_on": record}

    facts = _safe_runtime_text_list(payload.get("facts"))
    raw_audience = payload.get("audience")
    if not facts or not isinstance(raw_audience, dict):
        return None
    who_should_care = _safe_runtime_text(raw_audience.get("who_should_care"))
    who_can_wait = _safe_runtime_text(raw_audience.get("who_can_wait"))
    if not who_should_care or not who_can_wait:
        return None
    return {
        "mode": mode,
        "topic": topic,
        "facts": facts,
        "audience": {
            "who_should_care": who_should_care,
            "who_can_wait": who_can_wait,
        },
    }


def _safe_runtime_text(value: object) -> str:
    if not is_ai_tech_drafting_safe_text(value):
        return ""
    assert isinstance(value, str)
    return value.strip()


def _safe_runtime_text_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [
        text
        for item in value
        if (text := _safe_runtime_text(item))
    ]


def _string_value(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _string_list(value: object) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []
