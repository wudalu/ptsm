from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry
from ptsm.skills.selector import SkillSelector


def build_planner_node(
    *,
    domain: str,
    playbook_id: str | None,
    playbooks: PlaybookRegistry,
    playbook_loader: PlaybookLoader,
    skills: SkillRegistry,
    skill_loader: SkillLoader,
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

        return {
            "planner_iterations": int(state.get("planner_iterations", 0)) + 1,
            "selected_playbook": playbook.playbook_id,
            "playbook_id": playbook.playbook_id,
            "candidate_skills": list(playbook.required_skills),
            "activated_skills": activated_skills,
            "planner_prompt": loaded_playbook.planner_prompt,
            "reflection_prompt": loaded_playbook.reflection_prompt,
            "reflection_rules": loaded_playbook.definition.reflection,
            "loaded_skill_contents": [skill.content for skill in loaded_skills],
        }

    return planner
