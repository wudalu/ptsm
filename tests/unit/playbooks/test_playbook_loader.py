from __future__ import annotations

from pathlib import Path

import pytest

from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry


def test_playbook_loader_reads_yaml_and_markdown_assets() -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load("fengkuang_daily_post")

    assert playbook.definition.playbook_id == "fengkuang_daily_post"
    assert "发疯文学" in playbook.planner_prompt
    assert "普通打工人" in playbook.persona_prompt
    assert "人味" in playbook.persona_prompt
    assert "轻量正向收束" in playbook.reflection_prompt


def test_playbook_loader_reads_sushi_poetry_assets() -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load("sushi_poetry_daily_post")

    assert playbook.definition.playbook_id == "sushi_poetry_daily_post"
    assert "苏轼" in playbook.planner_prompt
    assert "读书博主" in playbook.persona_prompt
    assert "网感" in playbook.persona_prompt
    assert "#苏轼" in playbook.reflection_prompt


def test_playbook_loader_reads_human_enrichment_assets() -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load("human_enrichment_daily_post")

    assert playbook.definition.playbook_id == "human_enrichment_daily_post"
    assert "人类丰容" in playbook.planner_prompt
    assert "日常变量" in playbook.persona_prompt
    assert "3:4" in playbook.persona_prompt
    assert "#人类丰容计划" in playbook.reflection_prompt


@pytest.mark.parametrize(
    ("playbook_id", "expected_prompt_markers"),
    [
        (
            "sushi_poetry_daily_post",
            ["生活瞬间", "可收藏", "评论区", "不要讲义"],
        ),
        (
            "wuxia_character_post",
            ["当代切口", "原文", "截图", "评论区"],
        ),
        (
            "ai_tech_daily_post",
            ["3秒核心信息", "普通人影响", "收藏清单", "非投资建议"],
        ),
        (
            "daily_english_post",
            ["真实场景", "造句", "可收藏", "不要词典式"],
        ),
    ],
)
def test_remaining_domain_playbook_assets_include_quality_strategy(
    playbook_id: str,
    expected_prompt_markers: list[str],
) -> None:
    loader = PlaybookLoader(playbook_root=Path("src/ptsm/playbooks/definitions"))

    playbook = loader.load(playbook_id)
    combined_prompt = "\n".join(
        [
            playbook.planner_prompt,
            playbook.persona_prompt,
            playbook.reflection_prompt,
        ]
    )

    for marker in expected_prompt_markers:
        assert marker in combined_prompt


@pytest.mark.parametrize(
    ("playbook_id", "required_tag"),
    [
        ("sushi_poetry_daily_post", "#苏轼"),
        ("wuxia_character_post", "#金庸"),
        ("ai_tech_daily_post", "#AI资讯"),
        ("daily_english_post", "#每日英语"),
    ],
)
def test_remaining_domain_reflection_rules_block_experiment_leakage(
    playbook_id: str,
    required_tag: str,
) -> None:
    registry = PlaybookRegistry(playbook_root=Path("src/ptsm/playbooks/definitions"))
    playbook = registry.get(playbook_id)

    assert playbook.reflection["required_hashtag"] == required_tag
    forbidden = playbook.reflection["body_must_not_include_any"]
    for leaked_token in [
        "变体要求",
        "模板要求",
        "comment_chain",
        "save_tool",
        "identity_conflict",
    ]:
        assert leaked_token in forbidden
