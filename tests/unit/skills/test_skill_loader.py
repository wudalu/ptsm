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
    for compact_rule in (
        "xhs_compact_native_v1",
        "2-4 个短拍",
        "保存动作和接话口可以合在同一句自然的话里",
        "不要把正文硬拆成四段",
    ):
        assert compact_rule in loaded.content
    assert "首屏钩子 -> 领域要素 -> 可保存单元 -> 评论交接" not in loaded.content
    for title_rule in ("12-18", "22", "具体场景", "具体入口", "泛标题"):
        assert title_rule in loaded.content
    for body_rule in ("现场锚点", "真人视角", "少总述", "自然保存", "可接话结尾"):
        assert body_rule in loaded.content
    for copyable_rule in ("一个能立刻拿走的领域细节", "朋友安利", "少解释多交付"):
        assert copyable_rule in loaded.content


def test_key_xhs_style_skills_reference_viral_hook_mechanics() -> None:
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    loader = SkillLoader(registry)

    fengkuang = loader.load("fengkuang_style").content
    psychology = loader.load("psychology_style").content
    enrichment = loader.load("human_enrichment_style").content
    ai_tech = loader.load("ai_tech_style").content
    classic_poetry = loader.load("classic_poetry_style").content
    wuxia = loader.load("wuxia_commentary_style").content

    assert "高雅" in fengkuang
    assert "丝瓜汤" in fengkuang
    assert "爱你老己" in psychology
    assert "三明治拒绝法" in psychology
    assert "适我主义" in enrichment
    assert "新独居" in enrichment
    assert "AI 生活搭子" in ai_tech
    assert "古诗词" in classic_poetry
    assert "金句" in classic_poetry
    assert "老款人格" in wuxia
