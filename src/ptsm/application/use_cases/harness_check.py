from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from typing import Sequence

from ptsm.application.use_cases.docs_sync import run_docs_sync
from ptsm.application.use_cases.harness_report import run_harness_report
from ptsm.config.settings import Settings


DEFAULT_PYTEST_COMMAND = ("uv", "run", "pytest", "-q")


class _SkippedPreflightPublisher:
    def preflight(self) -> dict[str, object]:
        return {
            "status": "skipped",
            "reason": "harness_check_skip_preflight",
        }


def run_harness_check(
    *,
    project_root: Path | str = ".",
    base_ref: str | None = None,
    head_ref: str = "HEAD",
    changed_paths: Sequence[str] | None = None,
    pytest_command: Sequence[str] = DEFAULT_PYTEST_COMMAND,
    strict: bool = False,
) -> dict[str, object]:
    root = Path(project_root)
    current_time = datetime.now(timezone.utc)

    docs_sync = run_docs_sync(
        project_root=root,
        changed_paths=changed_paths,
        base_ref=base_ref,
        head_ref=head_ref,
    )
    harness_report = run_harness_report(
        settings=Settings(_env_file=None),
        publisher=_SkippedPreflightPublisher(),
        project_root=root,
        now=current_time,
    )
    pytest_result = _run_pytest(command=pytest_command, project_root=root)

    return {
        "generated_at": current_time.isoformat(),
        "status": _overall_status(
            docs_sync=docs_sync,
            harness_report=harness_report,
            pytest_result=pytest_result,
            strict=strict,
        ),
        "base_ref": base_ref,
        "head_ref": head_ref,
        "strict": strict,
        "docs_sync": docs_sync,
        "harness_report": harness_report,
        "pytest": pytest_result,
    }


def _run_pytest(*, command: Sequence[str], project_root: Path) -> dict[str, object]:
    env = os.environ.copy()
    env["DEFAULT_LLM_PROVIDER"] = "deterministic"
    env["DEEPSEEK_API_KEY"] = ""

    completed = subprocess.run(
        list(command),
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "command": list(command),
        "returncode": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _overall_status(
    *,
    docs_sync: dict[str, object],
    harness_report: dict[str, object],
    pytest_result: dict[str, object],
    strict: bool,
) -> str:
    if docs_sync.get("status") != "ok":
        return "error"
    if strict:
        if harness_report.get("status") != "ok":
            return "error"
    elif _local_harness_gate_failed(harness_report):
        return "error"
    if pytest_result.get("status") != "ok":
        return "error"
    return "ok"


def _tail(text: str, *, lines: int = 40) -> list[str]:
    payload = [line for line in text.splitlines() if line.strip()]
    return payload[-lines:]


def _local_harness_gate_failed(harness_report: dict[str, object]) -> bool:
    doctor = harness_report.get("doctor")
    if not isinstance(doctor, dict):
        return False
    checks = doctor.get("checks")
    if not isinstance(checks, list):
        return False
    for check in checks:
        if not isinstance(check, dict):
            continue
        if check.get("name") != "harness_docs_freshness":
            continue
        return check.get("status") != "ok"
    return False
