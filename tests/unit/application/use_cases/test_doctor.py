from __future__ import annotations

from ptsm.application.use_cases.doctor import run_doctor
from ptsm.config.settings import Settings


class FakePreflightPublisher:
    def __init__(self, payload: dict[str, object]):
        self.payload = payload

    def preflight(self) -> dict[str, object]:
        return self.payload


def test_run_doctor_reports_settings_and_mcp_status() -> None:
    result = run_doctor(
        settings=Settings(_env_file=None),
        publisher=FakePreflightPublisher(
            {
                "status": "ready",
                "server_url": "http://localhost:18060/mcp",
                "login_status": "✅ 已登录",
                "available_tools": ["check_login_status", "publish_content"],
            }
        ),
    )

    assert result["status"] == "ok"
    assert result["checks"][0]["name"] == "settings"
    assert result["checks"][0]["status"] == "ok"
    assert result["checks"][1]["name"] == "artifacts_dir"
    assert result["checks"][1]["status"] == "ok"
    assert result["checks"][2]["name"] == "xhs_preflight"
    assert result["checks"][2]["status"] == "ready"
