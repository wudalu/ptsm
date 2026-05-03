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
        "xhs_trend_scan",
        "xhs_hashtagging",
        "sushi_poetry_style",
        "xhs_poetry_hashtagging",
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


def test_skill_registry_parses_scope_tags_for_sushi_poetry_skill() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = next(
        skill for skill in registry.list_skills() if skill.skill_name == "sushi_poetry_style"
    )

    assert spec.domain_tags == ["苏轼诗词赏析"]
    assert spec.platform_tags == ["xiaohongshu"]
    assert spec.playbook_tags == ["sushi_poetry_daily_post"]


def test_skill_registry_parses_platform_scoped_xhs_trend_skill() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = next(
        skill for skill in registry.list_skills() if skill.skill_name == "xhs_trend_scan"
    )

    assert spec.domain_tags == []
    assert spec.platform_tags == ["xiaohongshu"]
    assert spec.playbook_tags == []
    assert spec.token_budget_hint == 180
    assert spec.assets_present is False
