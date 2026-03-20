from __future__ import annotations

import pytest

from ptsm.config.settings import Settings
from ptsm.infrastructure.publishers.factory import build_publisher
from ptsm.infrastructure.publishers.xiaohongshu_adapter import XiaohongshuAdapter
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def test_build_publisher_returns_dry_run_adapter_for_xiaohongshu() -> None:
    publisher = build_publisher(
        platform="xiaohongshu",
        publish_mode="dry-run",
        settings=Settings(_env_file=None),
    )

    assert isinstance(publisher, XiaohongshuAdapter)


def test_build_publisher_returns_mcp_adapter_with_settings_url(monkeypatch) -> None:
    monkeypatch.setenv("XHS_MCP_SERVER_URL", "http://localhost:18060/mcp")
    settings = Settings(_env_file=None)

    publisher = build_publisher(
        platform="xiaohongshu",
        publish_mode="mcp-real",
        settings=settings,
    )

    assert isinstance(publisher, XiaohongshuMcpPublisher)
    assert publisher.server_url == "http://localhost:18060/mcp"


def test_build_publisher_rejects_unknown_publish_mode() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        build_publisher(
            platform="xiaohongshu",
            publish_mode="surprise-mode",
            settings=Settings(_env_file=None),
        )
