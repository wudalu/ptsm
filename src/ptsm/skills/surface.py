from __future__ import annotations

from ptsm.skills.contracts import SkillSpec
from ptsm.skills.loader import LoadedSkill, SkillLoader


class RequestSkillSurface:
    """Request-scoped view of the candidate skills for a single execution."""

    def __init__(self, *, skills: list[SkillSpec], loader: SkillLoader):
        self._skills = {skill.skill_name: skill for skill in skills}
        self._loader = loader

    def list_summaries(self) -> list[SkillSpec]:
        return list(self._skills.values())

    def activate(self, skill_name: str) -> LoadedSkill:
        if skill_name not in self._skills:
            raise LookupError(f"Skill {skill_name!r} is not available in this request surface")
        return self._loader.load(skill_name)
