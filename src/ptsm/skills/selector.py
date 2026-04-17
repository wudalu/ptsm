from __future__ import annotations

from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry
from ptsm.skills.surface import RequestSkillSurface


class SkillSelector:
    """Rule-based selector for request-scoped skill candidates."""

    def __init__(self, *, registry: SkillRegistry, loader: SkillLoader):
        self._registry = registry
        self._loader = loader

    def select(
        self,
        *,
        domain: str | None = None,
        platform: str | None = None,
        playbook_id: str | None = None,
    ) -> RequestSkillSurface:
        selected = [
            skill
            for skill in self._registry.list_skills()
            if _matches(skill.domain_tags, domain)
            and _matches(skill.platform_tags, platform)
            and _matches(skill.playbook_tags, playbook_id)
        ]
        return RequestSkillSurface(skills=selected, loader=self._loader)


def _matches(tags: list[str], value: str | None) -> bool:
    if value is None or not tags:
        return True
    return value in tags
