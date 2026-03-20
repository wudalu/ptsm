from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def check_xhs_publish_status(
    *,
    artifact_path: Path,
    settings: Settings | None = None,
    publisher: Any | None = None,
) -> dict[str, object]:
    """Resolve publish status from artifact metadata and MCP publisher capabilities."""
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    publish_result = payload.get("publish_result")
    if not isinstance(publish_result, dict):
        return {
            "status": "manual_check_required",
            "reason": "artifact does not contain publish_result metadata",
            "artifact_path": str(artifact_path),
        }

    post_id = _first_string(publish_result, "post_id", "note_id", "id")
    post_url = _first_string(publish_result, "post_url", "url")

    if post_id or post_url:
        publisher = publisher or _build_publisher(settings)
        check_method = getattr(publisher, "check_publish_status", None)
        if callable(check_method):
            return check_method(post_id=post_id, post_url=post_url)

    return {
        "status": "manual_check_required",
        "reason": "artifact does not include post_id or post_url for automated verification",
        "artifact_path": str(artifact_path),
        "post_id": post_id,
        "post_url": post_url,
    }


def _build_publisher(settings: Settings | None) -> XiaohongshuMcpPublisher:
    resolved_settings = settings or get_settings()
    return XiaohongshuMcpPublisher(
        server_url=resolved_settings.xhs_mcp_server_url,
        default_visibility=resolved_settings.xhs_default_visibility,
    )


def _first_string(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None
