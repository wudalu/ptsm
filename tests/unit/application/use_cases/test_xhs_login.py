from __future__ import annotations

import base64
from pathlib import Path

from ptsm.application.use_cases.xhs_login import (
    fetch_xhs_login_qrcode_via_api,
    run_xhs_login_qrcode,
    run_xhs_login_status,
)


class FakePreflightPublisher:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def preflight(self) -> dict[str, object]:
        return self.payload


def test_run_xhs_login_status_returns_preflight_payload() -> None:
    result = run_xhs_login_status(
        publisher=FakePreflightPublisher(
            {
                "status": "ready",
                "server_url": "http://localhost:18060/mcp",
                "login_status": "✅ 已登录",
                "available_tools": ["check_login_status", "publish_content"],
            }
        )
    )

    assert result["status"] == "ready"
    assert result["login_status"] == "✅ 已登录"
    assert result["available_tools"] == ["check_login_status", "publish_content"]


def test_run_xhs_login_qrcode_writes_png_file(tmp_path: Path) -> None:
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
    )
    output_path = tmp_path / "xhs-login.png"

    result = run_xhs_login_qrcode(
        output_path=output_path,
        publisher=FakePreflightPublisher(
            {
                "status": "login_required",
                "server_url": "http://localhost:18060/mcp",
                "login_status": "❌ 未登录",
                "qrcode": {
                    "timeout": "4m0s",
                    "is_logged_in": False,
                    "img": "data:image/png;base64,"
                    + base64.b64encode(raw).decode("ascii"),
                },
            }
        ),
    )

    assert output_path.exists()
    assert output_path.read_bytes() == raw
    assert result["status"] == "login_required"
    assert result["qrcode"]["output_path"] == str(output_path)
    assert result["qrcode"]["timeout"] == "4m0s"


def test_run_xhs_login_qrcode_falls_back_to_http_api_when_mcp_lacks_img(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    raw = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII="
    )
    output_path = tmp_path / "xhs-login-fallback.png"
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {
            "timeout": "4m0s",
            "is_logged_in": False,
            "img": "data:image/png;base64," + base64.b64encode(raw).decode("ascii"),
        },
    )

    result = run_xhs_login_qrcode(
        output_path=output_path,
        publisher=FakePreflightPublisher(
            {
                "status": "login_required",
                "server_url": "http://localhost:18061/mcp",
                "login_status": "❌ 未登录",
                "qrcode": {"text": "请扫码登录"},
            }
        ),
    )

    assert output_path.exists()
    assert output_path.read_bytes() == raw
    assert result["qrcode"]["output_path"] == str(output_path)
    assert result["qrcode"]["timeout"] == "4m0s"


def test_fetch_xhs_login_qrcode_via_api_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_timeout(*_: object, **__: object) -> object:
        raise TimeoutError("timed out")

    monkeypatch.setattr("ptsm.application.use_cases.xhs_login.urlopen", raise_timeout)

    assert fetch_xhs_login_qrcode_via_api("http://localhost:18061/mcp") is None
