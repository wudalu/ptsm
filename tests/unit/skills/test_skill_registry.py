from __future__ import annotations

from pathlib import Path

from ptsm.skills.registry import SkillRegistry


def test_skill_registry_discovers_builtin_fengkuang_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}

    assert "fengkuang_style" in skill_names
    assert "positive_reframe" in skill_names
    assert "xhs_hashtagging" in skill_names
    assert "xhs_trend_scan" in skill_names
    assert "xhs_image_strategy" in skill_names
    assert "classic_poetry_style" in skill_names
    assert "xhs_classic_poetry_hashtagging" in skill_names


def test_skill_registry_parses_scope_tags_from_front_matter() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = registry.list_skills()[0]

    assert spec.domain_tags == ["发疯文学"]
    assert spec.platform_tags == ["xiaohongshu"]
    assert "fengkuang_daily_post" in spec.playbook_tags
    assert spec.token_budget_hint == 360
    assert spec.assets_present is False


def test_skill_registry_parses_scope_tags_for_classic_poetry_skill() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = next(
        skill for skill in registry.list_skills() if skill.skill_name == "classic_poetry_style"
    )

    assert spec.domain_tags == ["古诗词金句"]
    assert spec.platform_tags == ["xiaohongshu"]
    assert spec.playbook_tags == ["classic_poetry_quote_post"]


def test_registry_discovers_wuxia_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}
    assert "wuxia_commentary_style" in skill_names
    assert "xhs_wuxia_hashtagging" in skill_names


def test_wuxia_skills_have_correct_tags() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    commentary = skills["wuxia_commentary_style"]
    assert "武侠人物评述" in commentary.domain_tags
    assert "wuxia_character_post" in commentary.playbook_tags


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


def test_skill_registry_parses_platform_scoped_xhs_image_strategy_skill() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = next(
        skill for skill in registry.list_skills() if skill.skill_name == "xhs_image_strategy"
    )

    assert spec.domain_tags == []
    assert spec.platform_tags == ["xiaohongshu"]
    assert spec.playbook_tags == []
    assert spec.token_budget_hint == 220
    assert spec.assets_present is False


def test_registry_discovers_daily_english_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}
    assert "daily_english_style" in skill_names
    assert "daily_english_hashtagging" in skill_names


def test_daily_english_skills_have_correct_tags() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    style = skills["daily_english_style"]
    assert "每日英语学习" in style.domain_tags
    assert "xiaohongshu" in style.platform_tags

    hashtagging = skills["daily_english_hashtagging"]
    assert "每日英语学习" in hashtagging.domain_tags
    assert "xiaohongshu" in hashtagging.platform_tags


def test_skill_registry_discovers_topic_research_skill() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    spec = next(
        skill for skill in registry.list_skills() if skill.skill_name == "topic_research"
    )

    assert spec.domain_tags == []
    assert spec.platform_tags == ["xiaohongshu"]
    assert spec.playbook_tags == []
    assert spec.token_budget_hint == 200
    assert spec.assets_present is False


def test_registry_discovers_modern_psychology_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}

    assert "psychology_style" in skill_names
    assert "psychology_safety" in skill_names
    assert "xhs_psychology_hashtagging" in skill_names


def test_modern_psychology_skills_have_correct_tags() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    for skill_name in [
        "psychology_style",
        "psychology_safety",
        "xhs_psychology_hashtagging",
    ]:
        skill = skills[skill_name]
        assert "现代心理困境观察" in skill.domain_tags
        assert "xiaohongshu" in skill.platform_tags
        assert "modern_psychology_post" in skill.playbook_tags


def test_registry_discovers_human_enrichment_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}

    assert "human_enrichment_style" in skill_names
    assert "xhs_enrichment_visuals" in skill_names
    assert "xhs_enrichment_hashtagging" in skill_names


def test_human_enrichment_skills_have_correct_tags() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    for skill_name in [
        "human_enrichment_style",
        "xhs_enrichment_visuals",
        "xhs_enrichment_hashtagging",
    ]:
        skill = skills[skill_name]
        assert "人类丰容实验" in skill.domain_tags
        assert "xiaohongshu" in skill.platform_tags
        assert "human_enrichment_daily_post" in skill.playbook_tags


def test_registry_discovers_world_cup_skills() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skill_names = {skill.skill_name for skill in registry.list_skills()}

    assert "world_cup_style" in skill_names
    assert "xhs_world_cup_visuals" in skill_names
    assert "xhs_world_cup_hashtagging" in skill_names


def test_world_cup_skills_have_correct_tags() -> None:
    registry = SkillRegistry(
        skill_root=Path("src/ptsm/skills/builtin"),
    )

    skills = {skill.skill_name: skill for skill in registry.list_skills()}
    for skill_name in [
        "world_cup_style",
        "xhs_world_cup_visuals",
        "xhs_world_cup_hashtagging",
    ]:
        skill = skills[skill_name]
        assert "世界杯主题" in skill.domain_tags
        assert "xiaohongshu" in skill.platform_tags
        assert "world_cup_daily_post" in skill.playbook_tags


def test_world_cup_style_encodes_safe_xhs_mechanics() -> None:
    content = (
        Path("src/ptsm/skills/builtin/world_cup_style/SKILL.md")
        .read_text(encoding="utf-8")
    )

    for marker in ["普通球迷", "赛事情绪", "看球清单", "禁止赌球", "不写预测比分"]:
        assert marker in content


def test_remaining_domain_style_skills_encode_xhs_quality_mechanics() -> None:
    skill_root = Path("src/ptsm/skills/builtin")
    expected_markers = {
        "classic_poetry_style": ["古诗词", "金句", "可收藏", "不伪造出处"],
        "wuxia_commentary_style": ["当代切口", "原文", "截图", "评论区"],
        "ai_tech_style": ["3秒核心信息", "普通人影响", "收藏清单", "非投资建议"],
        "daily_english_style": ["真实场景", "造句", "可收藏", "不要词典式"],
    }

    for skill_name, markers in expected_markers.items():
        content = (skill_root / skill_name / "SKILL.md").read_text(encoding="utf-8")
        for marker in markers:
            assert marker in content


def test_human_enrichment_style_mentions_pattern_library_hooks() -> None:
    content = (
        Path("src/ptsm/skills/builtin/human_enrichment_style/SKILL.md")
        .read_text(encoding="utf-8")
    )

    for marker in [
        "突然意识到",
        "人，你该",
        "before vs after",
        "低成本变量清单",
        "不要复写样本标题",
    ]:
        assert marker in content
