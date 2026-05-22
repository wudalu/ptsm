from __future__ import annotations

import pytest

from ptsm.accounts.registry import AccountRegistry


def test_account_registry_loads_local_fengkuang_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-fk-local")

    assert account.account_id == "acct-fk-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "发疯文学"
    assert account.nickname == "发疯文学实验号"


def test_account_registry_raises_for_unknown_account() -> None:
    registry = AccountRegistry()

    with pytest.raises(LookupError, match="missing-acct"):
        registry.get("missing-acct")


def test_account_registry_loads_daily_english_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-daily-english-local")

    assert account.account_id == "acct-daily-english-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "每日英语学习"
    assert account.nickname == "英语学习日记实验号"


def test_account_registry_loads_modern_psychology_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-psychology-local")

    assert account.account_id == "acct-psychology-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "现代心理困境观察"
    assert account.nickname == "心理观察手记实验号"


def test_account_registry_loads_human_enrichment_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-enrichment-local")

    assert account.account_id == "acct-enrichment-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "人类丰容实验"
    assert account.nickname == "日常丰容实验号"


def test_account_registry_loads_world_cup_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-world-cup-local")

    assert account.account_id == "acct-world-cup-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "世界杯主题"
    assert account.nickname == "世界杯看球手记实验号"


def test_account_registry_loads_reddit_curation_account() -> None:
    registry = AccountRegistry()

    account = registry.get("acct-reddit-curation-local")

    assert account.account_id == "acct-reddit-curation-local"
    assert account.platform == "xiaohongshu"
    assert account.domain == "Reddit英文讨论转译"
    assert account.nickname == "Reddit英文精选实验号"


def test_account_profile_to_dict_exposes_routing_fields() -> None:
    account = AccountRegistry().get("acct-fk-local")

    payload = account.to_dict()

    assert payload["account_id"] == "acct-fk-local"
    assert payload["platform"] == "xiaohongshu"
    assert payload["domain"] == "发疯文学"
