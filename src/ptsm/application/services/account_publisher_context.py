"""Resolve per-account publisher execution context."""

from __future__ import annotations

from dataclasses import dataclass

from ptsm.accounts.registry import AccountProfile
from ptsm.config.settings import Settings


@dataclass(frozen=True)
class PublisherContext:
    cookie_profile_id: str
    cookie_path: str
    server_url: str
    visibility: str
    resolution_source: str  # "account" | "settings" | "cli_override"


def resolve_publisher_context(
    account: AccountProfile,
    settings: Settings,
    server_url_override: str | None = None,
    visibility_override: str | None = None,
) -> PublisherContext:
    """Build execution context: account cookie profile > settings defaults > overrides."""
    if account.has_cookie_profile:
        server_url = server_url_override or account.publisher_server_url or settings.xhs_mcp_server_url
        return PublisherContext(
            cookie_profile_id=account.cookie_profile_id,
            cookie_path=account.cookie_path,
            server_url=server_url,
            visibility=visibility_override or account.publisher_visibility or settings.xhs_default_visibility,
            resolution_source="account",
        )

    # No account cookie profile — use settings with optional override
    return PublisherContext(
        cookie_profile_id="",
        cookie_path="",
        server_url=server_url_override or settings.xhs_mcp_server_url,
        visibility=visibility_override or settings.xhs_default_visibility,
        resolution_source="settings",
    )
