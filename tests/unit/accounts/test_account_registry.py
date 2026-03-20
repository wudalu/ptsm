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
