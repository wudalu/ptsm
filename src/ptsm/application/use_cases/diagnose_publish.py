from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.application.use_cases.doctor import run_doctor
from ptsm.application.use_cases.logs import run_logs
from ptsm.application.use_cases.xhs_publish_status import check_xhs_publish_status
from ptsm.config.settings import Settings
from ptsm.infrastructure.observability.run_store import RunStore
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import XiaohongshuMcpPublisher


def run_diagnose_publish(
    *,
    artifact_path: Path | str | None = None,
    run_id: str | None = None,
    settings: Settings | None = None,
    publisher: XiaohongshuMcpPublisher | None = None,
    project_root: Path | str = ".",
) -> dict[str, object]:
    if artifact_path is None and run_id is None:
        raise ValueError("diagnose_publish requires --artifact or --run-id")

    root = Path(project_root)
    resolved_artifact_path = _resolve_artifact_path(
        project_root=root,
        artifact_path=artifact_path,
        run_id=run_id,
    )
    doctor = run_doctor(
        settings=settings,
        publisher=publisher,
        project_root=root,
    )
    artifact = _read_artifact(resolved_artifact_path)
    resolved_run = _read_run(
        project_root=root,
        run_id=run_id,
        artifact_path=resolved_artifact_path,
    )
    resolved_run_id = run_id or resolved_run.get("run_id")
    publish_status = _resolve_publish_status(
        artifact_path=resolved_artifact_path,
        settings=settings,
        publisher=publisher,
    )

    status, likely_cause = _classify(
        doctor=doctor,
        artifact=artifact,
        publish_status=publish_status,
    )
    evidence = _build_evidence(
        doctor=doctor,
        artifact=artifact,
        run=resolved_run,
        publish_status=publish_status,
    )
    return {
        "status": status,
        "likely_cause": likely_cause,
        "subject": {
            "run_id": resolved_run_id,
            "artifact_path": (
                str(resolved_artifact_path) if resolved_artifact_path is not None else None
            ),
        },
        "doctor": doctor,
        "artifact": artifact,
        "run": resolved_run,
        "publish_status": publish_status,
        "evidence": evidence,
        "next_actions": _next_actions(
            likely_cause=likely_cause,
            run_id=resolved_run_id,
            artifact_path=resolved_artifact_path,
        ),
    }


def _resolve_artifact_path(
    *,
    project_root: Path,
    artifact_path: Path | str | None,
    run_id: str | None,
) -> Path | None:
    if artifact_path is not None:
        path = Path(artifact_path)
        return path if path.is_absolute() else project_root / path
    if run_id is None:
        return None
    summary = RunStore(base_dir=project_root / ".ptsm" / "runs").read_summary(run_id)
    raw_path = summary.get("artifact_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    path = Path(raw_path)
    return path if path.is_absolute() else project_root / path


def _read_artifact(artifact_path: Path | None) -> dict[str, object]:
    if artifact_path is None:
        return {
            "path": None,
            "exists": False,
            "publish_result": None,
            "post_publish_checks": None,
        }
    if not artifact_path.exists():
        return {
            "path": str(artifact_path),
            "exists": False,
            "publish_result": None,
            "post_publish_checks": None,
        }
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    publish_result = payload.get("publish_result")
    post_publish_checks = payload.get("post_publish_checks")
    return {
        "path": str(artifact_path),
        "exists": True,
        "publish_result": publish_result if isinstance(publish_result, dict) else None,
        "post_publish_checks": (
            post_publish_checks if isinstance(post_publish_checks, dict) else None
        ),
    }


def _read_run(
    *,
    project_root: Path,
    run_id: str | None,
    artifact_path: Path | None,
) -> dict[str, object]:
    try:
        logs = run_logs(
            run_id=run_id,
            artifact_path=artifact_path,
            base_dir=project_root / ".ptsm" / "runs",
        )
    except Exception:
        return {
            "run_id": run_id,
            "summary": None,
            "events": [],
        }
    events = [
        event
        for event in logs.get("events", [])
        if isinstance(event, dict)
        and (
            str(event.get("step", "")) == "publish"
            or "publish" in str(event.get("event", ""))
        )
    ]
    return {
        "run_id": logs.get("run_id"),
        "summary": logs.get("summary"),
        "events": events,
    }


def _resolve_publish_status(
    *,
    artifact_path: Path | None,
    settings: Settings | None,
    publisher: XiaohongshuMcpPublisher | None,
) -> dict[str, object] | None:
    if artifact_path is None or not artifact_path.exists():
        return None
    return check_xhs_publish_status(
        artifact_path=artifact_path,
        settings=settings,
        publisher=publisher,
    )


def _classify(
    *,
    doctor: dict[str, object],
    artifact: dict[str, object],
    publish_status: dict[str, object] | None,
) -> tuple[str, str]:
    preflight_status = _doctor_check_status(doctor, "xhs_preflight")
    if preflight_status == "login_required":
        return ("warning", "login_required")

    publish_result = artifact.get("publish_result")
    if isinstance(publish_result, dict) and publish_result.get("status") == "error":
        return ("error", "publish_execution_error")

    if publish_status is None:
        return ("error", "artifact_missing")

    publish_status_value = str(publish_status.get("status", "unknown"))
    if publish_status_value in {
        "published_visible",
        "published",
        "success",
        "published_search_verified",
    }:
        return ("ok", "publish_status_verified")
    if publish_status_value == "unsupported":
        return ("warning", "publish_status_unsupported")
    if publish_status_value == "manual_check_required":
        if publish_status.get("reason_code") == "private_missing_identifiers":
            return ("warning", "private_publish_identifiers_missing")
        if not _artifact_has_publish_identifiers(artifact):
            return ("warning", "publish_identifiers_missing")
        return ("warning", "manual_review_required")
    if publish_status_value in {"error", "failed"}:
        return ("error", "publish_status_error")
    return ("warning", "manual_review_required")


def _build_evidence(
    *,
    doctor: dict[str, object],
    artifact: dict[str, object],
    run: dict[str, object],
    publish_status: dict[str, object] | None,
) -> list[str]:
    evidence: list[str] = []
    preflight_status = _doctor_check_status(doctor, "xhs_preflight")
    if preflight_status is not None:
        evidence.append(f"xhs_preflight.status={preflight_status}")

    publish_result = artifact.get("publish_result")
    if isinstance(publish_result, dict):
        status = publish_result.get("status")
        if status is not None:
            evidence.append(f"publish_result.status={status}")
        error = publish_result.get("error")
        if isinstance(error, str) and error.strip():
            evidence.append(f"publish_result.error={error}")

    post_publish_checks = artifact.get("post_publish_checks")
    if isinstance(post_publish_checks, dict):
        status = post_publish_checks.get("publish_status")
        if status is not None:
            evidence.append(f"post_publish_checks.publish_status={status}")

    summary = run.get("summary")
    if isinstance(summary, dict):
        status = summary.get("status")
        if status is not None:
            evidence.append(f"run.summary.status={status}")

    if publish_status is not None:
        evidence.append(f"publish_status.status={publish_status.get('status', 'unknown')}")
        reason_code = publish_status.get("reason_code")
        if reason_code is not None:
            evidence.append(f"publish_status.reason_code={reason_code}")

    return evidence


def _next_actions(
    *,
    likely_cause: str,
    run_id: str | None,
    artifact_path: Path | None,
) -> list[str]:
    artifact_arg = str(artifact_path) if artifact_path is not None else "outputs/artifacts/<artifact>.json"
    run_arg = run_id or "<run_id>"

    if likely_cause == "publish_status_verified":
        return ["No further action required."]
    if likely_cause == "login_required":
        return [
            "Run `uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-login-qrcode.png`.",
            "Scan the QR code and confirm login in XiaoHongShu.",
            f"Rerun `uv run python -m ptsm.bootstrap diagnose-publish --artifact {artifact_arg}` after login.",
        ]
    if likely_cause == "publish_execution_error":
        return [
            f"Inspect `uv run python -m ptsm.bootstrap logs --run-id {run_arg}`.",
            f"Review `publish_result.error` in `{artifact_arg}`.",
            "Fix the upstream publish failure, then rerun the publish flow.",
        ]
    if likely_cause == "publish_identifiers_missing":
        return [
            f"Inspect `{artifact_arg}` and confirm `publish_result` contains post_id/post_url.",
            f"Use `uv run python -m ptsm.bootstrap xhs-open-browser --target artifact --artifact {artifact_arg}` for manual verification.",
            "If publish succeeded, update publisher metadata extraction so future artifacts keep identifiers.",
        ]
    if likely_cause == "private_publish_identifiers_missing":
        return [
            f"`{artifact_arg}` was published with `仅自己可见`, but the upstream response did not return post_id/post_url.",
            "Current tooling cannot auto-verify private posts without upstream identifiers.",
            f"Use `uv run python -m ptsm.bootstrap xhs-open-browser --target artifact --artifact {artifact_arg}` for manual verification.",
        ]
    if likely_cause == "publish_status_unsupported":
        return [
            "Check whether xiaohongshu-mcp exposes `check_publish_status` on the current server.",
            f"Use `uv run python -m ptsm.bootstrap xhs-open-browser --target artifact --artifact {artifact_arg}` for manual verification.",
            "Keep the result as manual review until the MCP status tool is available.",
        ]
    return [
        f"Inspect `uv run python -m ptsm.bootstrap logs --run-id {run_arg}`.",
        f"Run `uv run python -m ptsm.bootstrap xhs-check-publish --artifact {artifact_arg}` for the raw status probe.",
        f"Use `uv run python -m ptsm.bootstrap xhs-open-browser --target artifact --artifact {artifact_arg}` if manual verification is still needed.",
    ]


def _doctor_check_status(doctor: dict[str, object], check_name: str) -> str | None:
    checks = doctor.get("checks")
    if not isinstance(checks, list):
        return None
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") == check_name:
            status = check.get("status")
            return str(status) if status is not None else None
    return None


def _artifact_has_publish_identifiers(artifact: dict[str, object]) -> bool:
    publish_result = artifact.get("publish_result")
    if not isinstance(publish_result, dict):
        return False
    for key in ("post_id", "note_id", "id", "post_url", "url"):
        value = publish_result.get(key)
        if isinstance(value, str) and value.strip():
            return True
    return False
