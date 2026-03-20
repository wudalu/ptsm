from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher

DEFAULT_XHS_LOGIN_QRCODE_PATH = Path("/tmp/xhs-login-qrcode.png")


def run_xhs_login_status(
    *,
    settings: Settings | None = None,
    publisher: XiaohongshuMcpPublisher | None = None,
) -> dict[str, object]:
    """Return the current XiaoHongShu MCP login preflight payload."""
    publisher = publisher or _build_publisher(settings)
    return publisher.preflight()


def run_xhs_login_qrcode(
    *,
    output_path: Path = DEFAULT_XHS_LOGIN_QRCODE_PATH,
    settings: Settings | None = None,
    publisher: XiaohongshuMcpPublisher | None = None,
) -> dict[str, object]:
    """Fetch XiaoHongShu login preflight and persist QR image when available."""
    publisher = publisher or _build_publisher(settings)
    return materialize_xhs_login_qrcode(publisher.preflight(), output_path=output_path)


def materialize_xhs_login_qrcode(
    preflight: dict[str, Any],
    *,
    output_path: Path = DEFAULT_XHS_LOGIN_QRCODE_PATH,
) -> dict[str, Any]:
    qrcode = preflight.get("qrcode")
    if isinstance(qrcode, dict):
        if not isinstance(qrcode.get("img"), str):
            server_url = preflight.get("server_url")
            if isinstance(server_url, str):
                fallback_qrcode = fetch_xhs_login_qrcode_via_api(server_url)
                if isinstance(fallback_qrcode, dict):
                    qrcode = {**qrcode, **fallback_qrcode}
        image_data = qrcode.get("img")
        if isinstance(image_data, str) and image_data.startswith("data:image/"):
            saved_path = _write_data_uri_image(image_data, output_path)
            qrcode = {**qrcode, "output_path": str(saved_path)}
            preflight = {**preflight, "qrcode": qrcode}
    return preflight


def build_xhs_login_instructions(
    *,
    qrcode_output_path: str | None,
    rerun_command: str,
) -> list[str]:
    instructions: list[str] = []
    if qrcode_output_path:
        instructions.append(f"Open {qrcode_output_path} and scan it with XiaoHongShu.")
    else:
        instructions.append("Run `ptsm xhs-login-qrcode` to generate a XiaoHongShu login QR code.")
    instructions.append("Confirm login in the XiaoHongShu app.")
    instructions.append(f"Then rerun: {rerun_command}")
    return instructions


def _build_publisher(settings: Settings | None) -> XiaohongshuMcpPublisher:
    resolved_settings = settings or get_settings()
    return XiaohongshuMcpPublisher(
        server_url=resolved_settings.xhs_mcp_server_url,
        default_visibility=resolved_settings.xhs_default_visibility,
    )


def fetch_xhs_login_qrcode_via_api(server_url: str) -> dict[str, Any] | None:
    parsed = urlparse(server_url)
    if not parsed.scheme or not parsed.netloc:
        return None

    path = parsed.path.rstrip("/")
    if path.endswith("/mcp"):
        path = path[: -len("/mcp")]
    api_url = parsed._replace(
        path=f"{path}/api/v1/login/qrcode" or "/api/v1/login/qrcode",
        params="",
        query="",
        fragment="",
    ).geturl()

    try:
        with urlopen(api_url, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict):
            return None
    except Exception:
        return None

    data = payload.get("data")
    return data if isinstance(data, dict) else None


def _write_data_uri_image(data_uri: str, output_path: Path) -> Path:
    prefix, encoded = data_uri.split(",", 1)
    if ";base64" not in prefix:
        raise ValueError("Unsupported QR code image format")

    raw = base64.b64decode(encoded)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)
    return output_path
