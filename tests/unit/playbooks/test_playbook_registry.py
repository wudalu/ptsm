from __future__ import annotations

from pathlib import Path

from ptsm.accounts.registry import AccountRegistry
from ptsm.playbooks.registry import PlaybookRegistry


def test_playbook_registry_selects_fengkuang_daily_post() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.select(domain="发疯文学", platform="xiaohongshu")

    assert playbook.playbook_id == "fengkuang_daily_post"
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "fengkuang_style",
        "positive_reframe",
        "xhs_hashtagging",
    ]


def test_playbook_registry_selects_by_account_domain_and_platform() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-fk-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "fengkuang_daily_post"


def test_playbook_registry_loads_sushi_poetry_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("sushi_poetry_daily_post")

    assert playbook.domain == "苏轼诗词赏析"
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "sushi_poetry_style",
        "xhs_poetry_hashtagging",
    ]


def test_playbook_registry_selects_sushi_poetry_by_account_domain_and_platform() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-sushi-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "sushi_poetry_daily_post"


def test_registry_loads_wuxia_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("wuxia_character_post")

    assert playbook.domain == "武侠人物评述"
    assert "xiaohongshu" in playbook.platforms
    assert "wuxia_commentary_style" in playbook.required_skills
    assert "xhs_wuxia_hashtagging" in playbook.required_skills
    assert playbook.trend_keywords == [
        "金庸群侠",
        "武侠人物",
        "令狐冲 性格分析",
        "射雕英雄传 人物",
    ]


def test_registry_selects_wuxia_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-wuxia-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "wuxia_character_post"
