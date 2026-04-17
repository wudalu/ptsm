from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

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


def test_run_doctor_reports_harness_drift(tmp_path: Path) -> None:
    _write_active_doc(
        tmp_path / "docs" / "runtime.md",
        last_verified="2026-01-01",
    )
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)

    orphan_evidence = tmp_path / ".ptsm" / "plan_runs" / "demo.evidence.json"
    orphan_evidence.parent.mkdir(parents=True, exist_ok=True)
    orphan_evidence.write_text("{}", encoding="utf-8")

    malformed_run_dir = tmp_path / ".ptsm" / "runs" / "run-123"
    malformed_run_dir.mkdir(parents=True, exist_ok=True)
    (malformed_run_dir / "events.jsonl").write_text("", encoding="utf-8")

    result = run_doctor(
        settings=Settings(_env_file=None),
        publisher=FakePreflightPublisher(
            {
                "status": "ready",
                "server_url": "http://localhost:18060/mcp",
            }
        ),
        project_root=tmp_path,
        now=datetime(2026, 4, 18, tzinfo=timezone.utc),
    )

    assert result["status"] == "warning"
    checks = {check["name"]: check for check in result["checks"]}
    assert checks["harness_docs_freshness"]["status"] == "warning"
    assert checks["harness_docs_freshness"]["details"]["stale_docs"] == [
        "docs/runtime.md"
    ]
    assert checks["harness_plan_runs"]["status"] == "warning"
    assert checks["harness_plan_runs"]["details"]["orphan_evidence_paths"] == [
        ".ptsm/plan_runs/demo.evidence.json"
    ]
    assert checks["harness_run_store"]["status"] == "warning"
    assert checks["harness_run_store"]["details"]["malformed_run_dirs"] == [
        ".ptsm/runs/run-123"
    ]


def _write_active_doc(path: Path, *, last_verified: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            "title: Demo Doc\n"
            "status: active\n"
            "owner: ptsm\n"
            f"last_verified: {last_verified}\n"
            "source_of_truth: true\n"
            "related_paths:\n"
            "  - src/demo.py\n"
            "---\n\n"
            "# Demo\n"
        ),
        encoding="utf-8",
    )
