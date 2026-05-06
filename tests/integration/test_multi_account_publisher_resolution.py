from __future__ import annotations

from pathlib import Path

from ptsm.accounts.registry import AccountRegistry
from ptsm.application.services.account_publisher_context import (
    resolve_publisher_context,
    PublisherContext,
)
from ptsm.config.settings import Settings, get_settings


def test_different_accounts_resolve_different_contexts() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    settings = Settings()

    fk = registry.get("acct-fk-local")
    sushi = registry.get("acct-sushi-local")

    ctx_fk = resolve_publisher_context(fk, settings)
    ctx_sushi = resolve_publisher_context(sushi, settings)

    assert ctx_fk.cookie_profile_id == "fk-local-cookie"
    assert ctx_sushi.cookie_profile_id == "sushi-local-cookie"
    assert ctx_fk.cookie_profile_id != ctx_sushi.cookie_profile_id
    assert ctx_fk.resolution_source == "account"
    assert ctx_sushi.resolution_source == "account"


def test_account_without_cookie_falls_back_to_settings() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    settings = Settings()

    wuxia = registry.get("acct-wuxia-local")
    ctx = resolve_publisher_context(wuxia, settings)

    assert ctx.cookie_profile_id == ""
    assert ctx.resolution_source == "settings"
    assert ctx.server_url == settings.xhs_mcp_server_url


def test_server_url_override_takes_priority() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    settings = Settings()

    fk = registry.get("acct-fk-local")
    ctx = resolve_publisher_context(fk, settings, server_url_override="http://custom:9999/mcp")

    assert ctx.server_url == "http://custom:9999/mcp"
    assert ctx.cookie_profile_id == "fk-local-cookie"
    assert ctx.resolution_source == "account"


def test_visibility_override() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    settings = Settings()

    sushi = registry.get("acct-sushi-local")
    ctx = resolve_publisher_context(sushi, settings, visibility_override="公开")

    assert ctx.visibility == "公开"


def test_account_dict_includes_cookie_summary() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    fk = registry.get("acct-fk-local")
    d = fk.to_dict()

    assert d["account_id"] == "acct-fk-local"
    assert d["cookie_profile_id"] == "fk-local-cookie"
    assert d["cookie_path"] == "cookies/fk-local.json"


def test_account_without_cookie_omits_cookie_fields() -> None:
    registry = AccountRegistry(
        account_root=Path("src/ptsm/accounts/definitions"),
    )
    wuxia = registry.get("acct-wuxia-local")
    d = wuxia.to_dict()

    assert "cookie_profile_id" not in d
    assert d["account_id"] == "acct-wuxia-local"


def test_ptsm_accounts_command(capsys) -> None:
    from ptsm.interfaces.cli.main import main
    import sys

    sys.argv = ["ptsm", "accounts"]
    try:
        main()
    except SystemExit as e:
        assert e.code == 0

    captured = capsys.readouterr()
    import json
    rows = json.loads(captured.out)
    assert isinstance(rows, list)
    assert len(rows) >= 3

    fk = next(r for r in rows if r["account_id"] == "acct-fk-local")
    assert fk["cookie_profile_id"] == "fk-local-cookie"
