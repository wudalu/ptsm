from __future__ import annotations

from pathlib import Path
from typing import Any

from ptsm.config.settings import Settings, get_settings
from ptsm.application.use_cases.harness_gc import inspect_harness_state
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def run_doctor(
    *,
    settings: Settings | None = None,
    publisher: XiaohongshuMcpPublisher | None = None,
    project_root: Path | str = ".",
    now=None,
) -> dict[str, object]:
    """Collect local environment and MCP readiness checks."""
    settings = settings or get_settings()
    publisher = publisher or XiaohongshuMcpPublisher(
        server_url=settings.xhs_mcp_server_url,
        default_visibility=settings.xhs_default_visibility,
    )

    checks: list[dict[str, Any]] = [
        {
            "name": "settings",
            "status": "ok",
            "details": {
                "log_level": settings.log_level,
                "default_model_provider": settings.default_model_provider,
                "xhs_mcp_server_url": settings.xhs_mcp_server_url,
                "xhs_default_visibility": settings.xhs_default_visibility,
            },
        },
        {
            "name": "artifacts_dir",
            "status": "ok" if Path("outputs/artifacts").exists() else "missing",
            "path": "outputs/artifacts",
        },
    ]

    try:
        preflight = publisher.preflight()
        checks.append(
            {
                "name": "xhs_preflight",
                "status": str(preflight.get("status", "unknown")),
                "details": preflight,
            }
        )
    except Exception as exc:
        checks.append(
            {
                "name": "xhs_preflight",
                "status": "error",
                "error": str(exc),
            }
        )

    harness_state = inspect_harness_state(
        project_root=project_root,
        now=now,
    )
    checks.extend(harness_state["checks"])

    overall_status = "ok"
    if any(check["status"] == "error" for check in checks):
        overall_status = "error"
    elif any(check["status"] in {"missing", "warning"} for check in checks):
        overall_status = "warning"

    return {
        "status": overall_status,
        "checks": checks,
    }
