from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.diagnose_publish import run_diagnose_publish
from ptsm.infrastructure.observability.run_store import RunStore


class FakePublisher:
    def __init__(
        self,
        *,
        preflight_payload: dict[str, object],
        status_payload: dict[str, object] | None = None,
    ) -> None:
        self.preflight_payload = preflight_payload
        self.status_payload = status_payload or {"status": "published_visible", "source": "mcp"}

    def preflight(self) -> dict[str, object]:
        return dict(self.preflight_payload)

    def check_publish_status(
        self,
        *,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> dict[str, object]:
        return {
            **self.status_payload,
            "post_id": post_id,
            "post_url": post_url,
        }


def test_run_diagnose_publish_classifies_publish_execution_error_from_run_id(
    tmp_path: Path,
) -> None:
    run_id = _write_run(
        tmp_path=tmp_path,
        artifact_payload={
            "publish_result": {
                "status": "error",
                "error": "publish failed",
            },
            "post_publish_checks": {
                "publish_status": "skipped",
            },
        },
        include_run_reference=True,
    )

    result = run_diagnose_publish(
        run_id=run_id,
        project_root=tmp_path,
        publisher=FakePublisher(preflight_payload={"status": "ready"}),
    )

    assert result["status"] == "error"
    assert result["likely_cause"] == "publish_execution_error"
    assert result["subject"]["run_id"] == run_id
    assert str(result["subject"]["artifact_path"]).endswith("artifact.json")
    assert result["artifact"]["publish_result"]["error"] == "publish failed"
    assert any("publish_result.error=publish failed" in item for item in result["evidence"])
    assert any("logs --run-id" in item for item in result["next_actions"])


def test_run_diagnose_publish_classifies_login_required(tmp_path: Path) -> None:
    artifact_path = _write_artifact(
        tmp_path,
        {
            "publish_result": {
                "status": "login_required",
            }
        },
    )

    result = run_diagnose_publish(
        artifact_path=artifact_path,
        project_root=tmp_path,
        publisher=FakePublisher(
            preflight_payload={
                "status": "login_required",
                "server_url": "http://localhost:19000/mcp",
            }
        ),
    )

    assert result["status"] == "warning"
    assert result["likely_cause"] == "login_required"
    assert any("xhs-login-qrcode" in item for item in result["next_actions"])
    assert any("xhs_preflight.status=login_required" in item for item in result["evidence"])


def test_run_diagnose_publish_classifies_publish_identifiers_missing(
    tmp_path: Path,
) -> None:
    artifact_path = _write_artifact(
        tmp_path,
        {
            "publish_result": {
                "status": "published",
            }
        },
    )

    result = run_diagnose_publish(
        artifact_path=artifact_path,
        project_root=tmp_path,
        publisher=FakePublisher(preflight_payload={"status": "ready"}),
    )

    assert result["status"] == "warning"
    assert result["likely_cause"] == "publish_identifiers_missing"
    assert result["publish_status"]["status"] == "manual_check_required"
    assert any("post_id/post_url" in item for item in result["next_actions"])


def test_run_diagnose_publish_classifies_publish_status_unsupported(
    tmp_path: Path,
) -> None:
    artifact_path = _write_artifact(
        tmp_path,
        {
            "publish_result": {
                "status": "published",
                "post_id": "note-123",
                "post_url": "https://www.xiaohongshu.com/explore/note-123",
            }
        },
    )

    result = run_diagnose_publish(
        artifact_path=artifact_path,
        project_root=tmp_path,
        publisher=FakePublisher(
            preflight_payload={"status": "ready"},
            status_payload={"status": "unsupported", "source": "mcp"},
        ),
    )

    assert result["status"] == "warning"
    assert result["likely_cause"] == "publish_status_unsupported"
    assert any("xhs-open-browser" in item for item in result["next_actions"])


def test_run_diagnose_publish_classifies_verified_publish(tmp_path: Path) -> None:
    artifact_path = _write_artifact(
        tmp_path,
        {
            "publish_result": {
                "status": "published",
                "post_id": "note-123",
                "post_url": "https://www.xiaohongshu.com/explore/note-123",
            }
        },
    )

    result = run_diagnose_publish(
        artifact_path=artifact_path,
        project_root=tmp_path,
        publisher=FakePublisher(
            preflight_payload={"status": "ready"},
            status_payload={"status": "published_visible", "source": "mcp"},
        ),
    )

    assert result["status"] == "ok"
    assert result["likely_cause"] == "publish_status_verified"
    assert result["publish_status"]["status"] == "published_visible"
    assert result["next_actions"] == ["No further action required."]


def _write_run(
    *,
    tmp_path: Path,
    artifact_payload: dict[str, object],
    include_run_reference: bool,
) -> str:
    runs_dir = tmp_path / ".ptsm" / "runs"
    artifacts_dir = tmp_path / "outputs" / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    store = RunStore(base_dir=runs_dir)
    run = store.start(
        command="run-fengkuang",
        account_id="acct-fk-local",
        platform="xiaohongshu",
        playbook_id="fengkuang_daily_post",
    )
    artifact_path = artifacts_dir / "artifact.json"
    artifact = dict(artifact_payload)
    if include_run_reference:
        artifact["run"] = {"run_id": run.run_id}
    artifact_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    store.append_event(
        run.run_id,
        event="publish_finished",
        step="publish",
        status=str(artifact_payload.get("publish_result", {}).get("status", "unknown")),
        payload={"artifact_path": str(artifact_path)},
    )
    store.finish(
        run.run_id,
        status="completed",
        payload={"artifact_path": str(artifact_path), "publish_status": "error"},
    )
    return run.run_id


def _write_artifact(tmp_path: Path, payload: dict[str, object]) -> Path:
    artifact_path = tmp_path / "outputs" / "artifacts" / "artifact.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return artifact_path
