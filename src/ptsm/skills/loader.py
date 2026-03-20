from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ptsm.skills.contracts import SkillSpec
from ptsm.skills.registry import SkillRegistry


@dataclass(frozen=True)
class LoadedSkill:
    """Full skill markdown resolved from a registry entry."""

    skill: SkillSpec
    content: str
    source_path: Path


class SkillLoader:
    """Load full skill content on demand."""

    def __init__(self, registry: SkillRegistry):
        self._registry = registry

    def load(self, skill_name: str) -> LoadedSkill:
        for skill in self._registry.list_skills():
            if skill.skill_name == skill_name:
                return LoadedSkill(
                    skill=skill,
                    content=skill.source_path.read_text(encoding="utf-8"),
                    source_path=skill.source_path,
                )
        raise LookupError(f"Unknown skill: {skill_name}")
