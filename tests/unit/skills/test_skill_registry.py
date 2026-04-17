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


def test_skill_registry_parses_scope_tags_from_front_matter() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = registry.list_skills()[0]

    assert spec.domain_tags == ["发疯文学"]
    assert spec.platform_tags == ["xiaohongshu"]
    assert "fengkuang_daily_post" in spec.playbook_tags
    assert spec.token_budget_hint == 200
    assert spec.assets_present is False
