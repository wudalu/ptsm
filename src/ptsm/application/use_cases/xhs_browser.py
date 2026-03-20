from __future__ import annotations

import json
from pathlib import Path
from typing import Callable
import webbrowser


XHS_LOGIN_URL = "https://creator.xiaohongshu.com/login"
XHS_CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish"


def open_xhs_browser(
    *,
    target: str,
    artifact_path: Path | None = None,
    qrcode_output_path: Path | None = None,
    url: str | None = None,
    browser_opener: Callable[[str], bool] | None = None,
) -> dict[str, object]:
    """Open the most relevant XiaoHongShu page or local QR code in a browser."""
    browser_opener = browser_opener or webbrowser.open
    destination = _resolve_destination(
        target=target,
        artifact_path=artifact_path,
        qrcode_output_path=qrcode_output_path,
        url=url,
    )
    opened = bool(browser_opener(destination))
    return {
        "status": "opened" if opened else "failed",
        "target": target,
        "destination": destination,
    }


def _resolve_destination(
    *,
    target: str,
    artifact_path: Path | None,
    qrcode_output_path: Path | None,
    url: str | None,
) -> str:
    if isinstance(url, str) and url.strip():
        return url

    if target == "login":
        if qrcode_output_path is not None and qrcode_output_path.exists():
            return qrcode_output_path.resolve().as_uri()
        return XHS_LOGIN_URL

    if target == "creator":
        return XHS_CREATOR_URL

    if target == "artifact":
        artifact_destination = _resolve_artifact_destination(artifact_path)
        if artifact_destination is not None:
            return artifact_destination
        return XHS_CREATOR_URL

    raise ValueError(f"Unsupported browser target: {target}")


def _resolve_artifact_destination(artifact_path: Path | None) -> str | None:
    if artifact_path is None or not artifact_path.exists():
        return None
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    publish_result = payload.get("publish_result")
    if isinstance(publish_result, dict):
        for key in ("post_url", "url"):
            value = publish_result.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return None
