from __future__ import annotations

from pathlib import Path

from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry


def test_skill_loader_reads_full_skill_markdown() -> None:
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    loader = SkillLoader(registry)

    loaded = loader.load("fengkuang_style")

    assert loaded.skill.skill_name == "fengkuang_style"
    assert "放大具体日常崩溃场景" in loaded.content
    assert loaded.source_path.name == "SKILL.md"
