from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def check_xhs_publish_status(
    *,
    artifact_path: Path,
    settings: Settings | None = None,
    publisher: Any | None = None,
    search_retry_attempts: int = 1,
    search_retry_interval_seconds: float = 0.0,
    sleep: Callable[[float], None] = time.sleep,
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
    platform_payload = publish_result.get("platform_payload")
    title = _first_string(platform_payload, "title") if isinstance(platform_payload, dict) else None
    body = _first_string(platform_payload, "content", "body") if isinstance(platform_payload, dict) else None
    visibility = (
        _first_string(platform_payload, "visibility") if isinstance(platform_payload, dict) else None
    )

    if post_id or post_url:
        publisher = publisher or _build_publisher(settings)
        check_method = getattr(publisher, "check_publish_status", None)
        if callable(check_method):
            return check_method(post_id=post_id, post_url=post_url)

    publisher = publisher or _build_publisher(settings)
    if (
        visibility is not None
        and visibility != "仅自己可见"
        and title is not None
        and body is not None
    ):
        finder = getattr(publisher, "find_published_note", None)
        if callable(finder):
            located = _retry_public_search_lookup(
                finder=finder,
                title=title,
                body=body,
                search_retry_attempts=search_retry_attempts,
                search_retry_interval_seconds=search_retry_interval_seconds,
                sleep=sleep,
            )
            if isinstance(located, dict):
                return {
                    "status": "published_search_verified",
                    **located,
                }

    if visibility == "仅自己可见":
        return {
            "status": "manual_check_required",
            "reason_code": "private_missing_identifiers",
            "reason": (
                "artifact does not include post_id or post_url, and 仅自己可见 posts "
                "cannot be auto-verified under the current upstream tooling contract"
            ),
            "artifact_path": str(artifact_path),
            "post_id": post_id,
            "post_url": post_url,
            "visibility": visibility,
        }

    return {
        "status": "manual_check_required",
        "reason_code": "missing_identifiers",
        "reason": "artifact does not include post_id or post_url for automated verification",
        "artifact_path": str(artifact_path),
        "post_id": post_id,
        "post_url": post_url,
        "visibility": visibility,
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


def _retry_public_search_lookup(
    *,
    finder: Callable[..., dict[str, object] | None],
    title: str,
    body: str,
    search_retry_attempts: int,
    search_retry_interval_seconds: float,
    sleep: Callable[[float], None],
) -> dict[str, object] | None:
    attempts = max(1, search_retry_attempts)
    interval = max(0.0, search_retry_interval_seconds)

    for attempt in range(attempts):
        located = finder(title=title, body=body)
        if isinstance(located, dict):
            return located
        if attempt < attempts - 1 and interval > 0:
            sleep(interval)
    return None
