from __future__ import annotations

from pathlib import Path

from ptsm.playbooks.registry import PlaybookRegistry


def test_playbook_registry_selects_fengkuang_daily_post() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.select(domain="发疯文学", platform="xiaohongshu")

    assert playbook.playbook_id == "fengkuang_daily_post"
    assert playbook.required_skills == [
        "fengkuang_style",
        "positive_reframe",
        "xhs_hashtagging",
    ]
