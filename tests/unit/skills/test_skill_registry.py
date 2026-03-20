from __future__ import annotations

from pathlib import Path

from ptsm.skills.registry import SkillRegistry


def test_skill_registry_discovers_builtin_fengkuang_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = [skill.skill_name for skill in registry.list_skills()]

    assert skill_names == [
        "fengkuang_style",
        "positive_reframe",
        "xhs_hashtagging",
    ]
