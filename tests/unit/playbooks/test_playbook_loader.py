from __future__ import annotations

from pathlib import Path

from ptsm.playbooks.loader import PlaybookLoader


def test_playbook_loader_reads_yaml_and_markdown_assets() -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load("fengkuang_daily_post")

    assert playbook.definition.playbook_id == "fengkuang_daily_post"
    assert "发疯文学" in playbook.planner_prompt
    assert "普通打工人" in playbook.persona_prompt
    assert "人味" in playbook.persona_prompt
    assert "也算" in playbook.reflection_prompt


def test_playbook_loader_reads_sushi_poetry_assets() -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load("sushi_poetry_daily_post")

    assert playbook.definition.playbook_id == "sushi_poetry_daily_post"
    assert "苏轼" in playbook.planner_prompt
    assert "读书博主" in playbook.persona_prompt
    assert "网感" in playbook.persona_prompt
    assert "#苏轼" in playbook.reflection_prompt
