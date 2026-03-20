from __future__ import annotations

from ptsm.config.settings import Settings
from ptsm.infrastructure.publishers.contracts import Publisher
from ptsm.infrastructure.publishers.xiaohongshu_adapter import XiaohongshuAdapter
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def build_publisher(*, platform: str, publish_mode: str, settings: Settings) -> Publisher:
    """Build the concrete publisher for a platform/mode pair."""
    if platform != "xiaohongshu":
        raise ValueError(f"Unsupported platform for publisher factory: {platform}")

    if publish_mode == "dry-run":
        return XiaohongshuAdapter()

    if publish_mode == "mcp-real":
        return XiaohongshuMcpPublisher(
            server_url=settings.xhs_mcp_server_url,
            default_visibility=settings.xhs_default_visibility,
        )

    raise ValueError(f"unsupported publish mode for {platform}: {publish_mode}")
