from __future__ import annotations

from pathlib import Path

from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry


def test_skill_loader_reads_full_skill_markdown() -> None:
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    loader = SkillLoader(registry)

    loaded = loader.load("fengkuang_style")

    assert loaded.skill.skill_name == "fengkuang_style"
    assert loaded.skill.platform_tags == ["xiaohongshu"]
    assert "评论区接一句" in loaded.content
    assert "具体日常崩溃瞬间" in loaded.content
    assert loaded.source_path.name == "SKILL.md"


def test_skill_loader_reads_shared_xhs_human_voice_skill() -> None:
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    loader = SkillLoader(registry)

    loaded = loader.load("xhs_human_voice")

    assert loaded.skill.skill_name == "xhs_human_voice"
    assert loaded.skill.platform_tags == ["xiaohongshu"]
    assert "温暖" in loaded.content
    assert "真人" in loaded.content
    assert "不格式化" in loaded.content
    assert "具体场景" in loaded.content
    for rule in ("首屏钩子", "领域要素", "可保存单元", "评论交接"):
        assert rule in loaded.content
    for title_rule in ("12-18", "22", "冲突", "反差", "戏剧", "身份", "工具", "泛标题"):
        assert title_rule in loaded.content
    for body_rule in ("现场锚点", "真人视角", "少总述", "自然保存", "可接话结尾"):
        assert body_rule in loaded.content


def test_key_xhs_style_skills_reference_viral_hook_mechanics() -> None:
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    loader = SkillLoader(registry)

    fengkuang = loader.load("fengkuang_style").content
    psychology = loader.load("psychology_style").content
    enrichment = loader.load("human_enrichment_style").content
    ai_tech = loader.load("ai_tech_style").content
    sushi = loader.load("sushi_poetry_style").content
    wuxia = loader.load("wuxia_commentary_style").content

    assert "高雅" in fengkuang
    assert "丝瓜汤" in fengkuang
    assert "爱你老己" in psychology
    assert "三明治拒绝法" in psychology
    assert "适我主义" in enrichment
    assert "新独居" in enrichment
    assert "AI 生活搭子" in ai_tech
    assert "文化力" in sushi
    assert "老款人格" in wuxia
