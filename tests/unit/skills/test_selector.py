from __future__ import annotations

import importlib
from pathlib import Path

from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry


def _build_selector() -> object:
    selector_module = importlib.import_module("ptsm.skills.selector")
    registry = SkillRegistry(skill_root=Path("src/ptsm/skills/builtin"))
    return selector_module.SkillSelector(
        registry=registry,
        loader=SkillLoader(registry),
    )


def test_selector_returns_request_scoped_surface() -> None:
    selector = _build_selector()

    surface = selector.select(
        domain="发疯文学",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )

    assert [item.skill_name for item in surface.list_summaries()] == [
        "fengkuang_style",
        "positive_reframe",
        "xhs_trend_scan",
        "xhs_hashtagging",
    ]
    assert "放大具体日常崩溃场景" not in surface.list_summaries()[0].short_description


def test_surface_activates_full_skill_content_on_demand() -> None:
    selector = _build_selector()

    surface = selector.select(
        domain="发疯文学",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    loaded = surface.activate("fengkuang_style")

    assert loaded.skill.skill_name == "fengkuang_style"
    assert "放大具体日常崩溃场景" in loaded.content


def test_selector_returns_sushi_poetry_scoped_surface() -> None:
    selector = _build_selector()

    surface = selector.select(
        domain="苏轼诗词赏析",
        platform="xiaohongshu",
        playbook_id="sushi_poetry_daily_post",
    )

    assert [item.skill_name for item in surface.list_summaries()] == [
        "xhs_trend_scan",
        "sushi_poetry_style",
        "xhs_poetry_hashtagging",
    ]


def test_surface_activates_sushi_poetry_skill_content_on_demand() -> None:
    selector = _build_selector()

    surface = selector.select(
        domain="苏轼诗词赏析",
        platform="xiaohongshu",
        playbook_id="sushi_poetry_daily_post",
    )
    loaded = surface.activate("sushi_poetry_style")

    assert loaded.skill.skill_name == "sushi_poetry_style"
    assert "苏轼" in loaded.content


def test_surface_activates_xhs_trend_scan_for_xiaohongshu_requests() -> None:
    selector = _build_selector()

    surface = selector.select(
        domain="发疯文学",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    loaded = surface.activate("xhs_trend_scan")

    assert loaded.skill.skill_name == "xhs_trend_scan"
    assert "热点扫描" in loaded.content
