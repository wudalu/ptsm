from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Callable, Sequence

from ptsm.plan_runner.parser import PlanTask


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class CodexInvocation:
    prompt: str
    task_title: str
    attempt: int


@dataclass(frozen=True)
class VerificationRecord:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class TaskRunResult:
    task_title: str
    attempts: int
    status: str
    verification_records: list[VerificationRecord] = field(default_factory=list)


@dataclass(frozen=True)
class PlanRunResult:
    status: str
    plan_path: str
    dry_run: bool
    state_path: str | None
    verification_artifact_path: str | None
    verify_commands: list[str]
    task_results: list[TaskRunResult]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class PlanExecutionError(RuntimeError):
    """Raised when a task cannot be completed within the allowed attempts."""


CodexExec = Callable[[CodexInvocation], CommandResult]
VerifyExec = Callable[[str], CommandResult]


class PlanRunner:
    def __init__(
        self,
        codex_exec: CodexExec,
        verify_exec: VerifyExec,
    ) -> None:
        self._codex_exec = codex_exec
        self._verify_exec = verify_exec

    def run(
        self,
        *,
        plan_path: str | Path,
        tasks: Sequence[PlanTask],
        verify_commands: Sequence[str],
        max_attempts: int,
        dry_run: bool = False,
        state_path: str | Path | None = None,
        resume: bool = False,
    ) -> PlanRunResult:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        normalized_plan_path = str(plan_path)
        normalized_verify_commands = list(verify_commands)
        normalized_state_path = Path(state_path) if state_path is not None else None
        verification_artifact_path = (
            _build_verification_artifact_path(normalized_state_path)
            if normalized_state_path is not None
            else None
        )
        if resume and normalized_state_path is None:
            raise ValueError("resume requires state_path")
        persisted_state = (
            _load_state(normalized_state_path) if resume and normalized_state_path is not None else None
        )
        task_state_map = _build_task_state_map(tasks, persisted_state)

        if dry_run:
            result = PlanRunResult(
                status=str(persisted_state.get("status", "dry-run")) if persisted_state is not None else "dry-run",
                plan_path=normalized_plan_path,
                dry_run=True,
                state_path=str(normalized_state_path) if normalized_state_path is not None else None,
                verification_artifact_path=(
                    str(verification_artifact_path)
                    if verification_artifact_path is not None
                    else None
                ),
                verify_commands=normalized_verify_commands,
                task_results=_build_task_results(tasks, task_state_map),
            )
            if normalized_state_path is not None:
                _write_state(
                    normalized_state_path,
                    plan_path=normalized_plan_path,
                    status=result.status,
                    verification_artifact_path=str(verification_artifact_path),
                    verify_commands=normalized_verify_commands,
                    max_attempts=max_attempts,
                    tasks=tasks,
                    task_state_map=task_state_map,
                )
                _write_verification_artifact(
                    verification_artifact_path,
                    plan_path=normalized_plan_path,
                    state_path=normalized_state_path,
                    status=result.status,
                    verify_commands=normalized_verify_commands,
                    tasks=tasks,
                    task_state_map=task_state_map,
                )
            return result

        if normalized_state_path is not None and persisted_state is None:
            _write_state(
                normalized_state_path,
                plan_path=normalized_plan_path,
                status="in_progress",
                verification_artifact_path=str(verification_artifact_path),
                verify_commands=normalized_verify_commands,
                max_attempts=max_attempts,
                tasks=tasks,
                task_state_map=task_state_map,
            )
            _write_verification_artifact(
                verification_artifact_path,
                plan_path=normalized_plan_path,
                state_path=normalized_state_path,
                status="in_progress",
                verify_commands=normalized_verify_commands,
                tasks=tasks,
                task_state_map=task_state_map,
            )

        for task in tasks:
            task_state = task_state_map[task.title]
            if task_state["status"] == "passed":
                continue

            effective_verify_commands = task.verify_commands or normalized_verify_commands
            effective_max_attempts = task.max_attempts or max_attempts
            last_failure = str(task_state.get("last_failure", ""))
            start_attempt = int(task_state.get("attempts", 0)) + 1

            for attempt in range(start_attempt, effective_max_attempts + 1):
                codex_result = self._codex_exec(
                    CodexInvocation(
                        prompt=_build_codex_prompt(
                            plan_path=normalized_plan_path,
                            task=task,
                            attempt=attempt,
                            verify_commands=effective_verify_commands,
                            failure_feedback=last_failure,
                        ),
                        task_title=task.title,
                        attempt=attempt,
                    )
                )

                if codex_result.exit_code != 0:
                    last_failure = _format_command_failure(
                        "Codex execution failed",
                        codex_result,
                    )
                    _append_attempt_history(
                        task_state,
                        attempt=attempt,
                        status="failed",
                        failure_stage="codex",
                        failure_reason="codex_exec_failed",
                        failure_summary=last_failure,
                        codex_result=codex_result,
                        verification_records=[],
                    )
                    task_state.update(
                        status="failed" if attempt == effective_max_attempts else "pending",
                        attempts=attempt,
                        last_failure=last_failure,
                        verification_records=[],
                    )
                    if normalized_state_path is not None:
                        _write_state(
                            normalized_state_path,
                            plan_path=normalized_plan_path,
                            status="failed" if attempt == effective_max_attempts else "in_progress",
                            verification_artifact_path=str(verification_artifact_path),
                            verify_commands=normalized_verify_commands,
                            max_attempts=max_attempts,
                            tasks=tasks,
                            task_state_map=task_state_map,
                        )
                        _write_verification_artifact(
                            verification_artifact_path,
                            plan_path=normalized_plan_path,
                            state_path=normalized_state_path,
                            status="failed" if attempt == effective_max_attempts else "in_progress",
                            verify_commands=normalized_verify_commands,
                            tasks=tasks,
                            task_state_map=task_state_map,
                        )
                    if attempt == effective_max_attempts:
                        raise PlanExecutionError(
                            f"Task '{task.title}' failed after {attempt} attempts.\n{last_failure}"
                        )
                    continue

                verification_records: list[VerificationRecord] = []
                failed_verification: VerificationRecord | None = None

                for command in effective_verify_commands:
                    verification_result = self._verify_exec(command)
                    record = VerificationRecord(
                        command=command,
                        exit_code=verification_result.exit_code,
                        stdout=verification_result.stdout,
                        stderr=verification_result.stderr,
                        started_at=verification_result.started_at,
                        finished_at=verification_result.finished_at,
                        duration_ms=verification_result.duration_ms,
                    )
                    verification_records.append(record)
                    if verification_result.exit_code != 0:
                        failed_verification = record
                        break

                if failed_verification is None:
                    _append_attempt_history(
                        task_state,
                        attempt=attempt,
                        status="passed",
                        failure_stage=None,
                        failure_reason=None,
                        failure_summary="",
                        codex_result=codex_result,
                        verification_records=verification_records,
                    )
                    task_state.update(
                        status="passed",
                        attempts=attempt,
                        last_failure="",
                        verification_records=[
                            asdict(record) for record in verification_records
                        ],
                    )
                    if normalized_state_path is not None:
                        _write_state(
                            normalized_state_path,
                            plan_path=normalized_plan_path,
                            status="in_progress",
                            verification_artifact_path=str(verification_artifact_path),
                            verify_commands=normalized_verify_commands,
                            max_attempts=max_attempts,
                            tasks=tasks,
                            task_state_map=task_state_map,
                        )
                        _write_verification_artifact(
                            verification_artifact_path,
                            plan_path=normalized_plan_path,
                            state_path=normalized_state_path,
                            status="in_progress",
                            verify_commands=normalized_verify_commands,
                            tasks=tasks,
                            task_state_map=task_state_map,
                        )
                    break

                last_failure = _format_verification_failure(failed_verification)
                _append_attempt_history(
                    task_state,
                    attempt=attempt,
                    status="failed",
                    failure_stage="verification",
                    failure_reason=_classify_verification_failure_reason(
                        failed_verification.command
                    ),
                    failure_summary=last_failure,
                    codex_result=codex_result,
                    verification_records=verification_records,
                )
                task_state.update(
                    status="failed" if attempt == effective_max_attempts else "pending",
                    attempts=attempt,
                    last_failure=last_failure,
                    verification_records=[
                        asdict(record) for record in verification_records
                    ],
                )
                if normalized_state_path is not None:
                    _write_state(
                        normalized_state_path,
                        plan_path=normalized_plan_path,
                        status="failed" if attempt == effective_max_attempts else "in_progress",
                        verification_artifact_path=str(verification_artifact_path),
                        verify_commands=normalized_verify_commands,
                        max_attempts=max_attempts,
                        tasks=tasks,
                        task_state_map=task_state_map,
                    )
                    _write_verification_artifact(
                        verification_artifact_path,
                        plan_path=normalized_plan_path,
                        state_path=normalized_state_path,
                        status="failed" if attempt == effective_max_attempts else "in_progress",
                        verify_commands=normalized_verify_commands,
                        tasks=tasks,
                        task_state_map=task_state_map,
                    )
                if attempt == effective_max_attempts:
                    raise PlanExecutionError(
                        f"Task '{task.title}' failed after {attempt} attempts.\n{last_failure}"
                    )
            else:
                raise PlanExecutionError(f"Task '{task.title}' did not complete")

        result = PlanRunResult(
            status="completed",
            plan_path=normalized_plan_path,
            dry_run=False,
            state_path=str(normalized_state_path) if normalized_state_path is not None else None,
            verification_artifact_path=(
                str(verification_artifact_path)
                if verification_artifact_path is not None
                else None
            ),
            verify_commands=normalized_verify_commands,
            task_results=_build_task_results(tasks, task_state_map),
        )
        if normalized_state_path is not None:
            _write_state(
                normalized_state_path,
                plan_path=normalized_plan_path,
                status=result.status,
                verification_artifact_path=str(verification_artifact_path),
                verify_commands=normalized_verify_commands,
                max_attempts=max_attempts,
                tasks=tasks,
                task_state_map=task_state_map,
            )
            _write_verification_artifact(
                verification_artifact_path,
                plan_path=normalized_plan_path,
                state_path=normalized_state_path,
                status=result.status,
                verify_commands=normalized_verify_commands,
                tasks=tasks,
                task_state_map=task_state_map,
            )
        return result


def _build_codex_prompt(
    *,
    plan_path: str,
    task: PlanTask,
    attempt: int,
    verify_commands: Sequence[str],
    failure_feedback: str,
) -> str:
    verify_lines = "\n".join(f"- {command}" for command in verify_commands) or "- No verification commands configured"
    failure_section = ""
    if failure_feedback:
        failure_section = (
            "\nPrevious attempt feedback:\n"
            f"{failure_feedback}\n"
            "Fix the issue before moving on.\n"
        )

    return (
        f"You are executing a task from the implementation plan at {plan_path}.\n"
        f"Current task: {task.title}\n"
        f"Attempt: {attempt}\n\n"
        "Task details:\n"
        f"{task.prompt or task.body}\n\n"
        "After implementing this task, it will be verified with:\n"
        f"{verify_lines}\n"
        f"{failure_section}"
        "Do not claim success unless the code is ready for these checks."
    )


def _format_command_failure(prefix: str, result: CommandResult) -> str:
    return (
        f"{prefix} (exit {result.exit_code})\n"
        f"STDOUT:\n{result.stdout or '<empty>'}\n"
        f"STDERR:\n{result.stderr or '<empty>'}"
    )


def _format_verification_failure(record: VerificationRecord) -> str:
    return (
        f"Verification failed for command: {record.command}\n"
        f"Exit code: {record.exit_code}\n"
        f"STDOUT:\n{record.stdout or '<empty>'}\n"
        f"STDERR:\n{record.stderr or '<empty>'}"
    )


def run_subprocess_command(command: Sequence[str]) -> CommandResult:
    started_at = _timestamp()
    started = time.perf_counter()
    completed = subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        started_at=started_at,
        finished_at=_timestamp(),
        duration_ms=round((time.perf_counter() - started) * 1000),
    )


def run_shell_command(command: str) -> CommandResult:
    started_at = _timestamp()
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        shell=True,
        executable="/bin/zsh",
    )
    return CommandResult(
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        started_at=started_at,
        finished_at=_timestamp(),
        duration_ms=round((time.perf_counter() - started) * 1000),
    )


def _load_state(state_path: Path) -> dict[str, object]:
    return json.loads(state_path.read_text(encoding="utf-8"))


def _write_state(
    state_path: Path,
    *,
    plan_path: str,
    status: str,
    verification_artifact_path: str | None,
    verify_commands: list[str],
    max_attempts: int,
    tasks: Sequence[PlanTask],
    task_state_map: dict[str, dict[str, object]],
) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "plan_path": plan_path,
        "status": status,
        "verification_artifact_path": verification_artifact_path,
        "verify_commands": verify_commands,
        "max_attempts": max_attempts,
        "tasks": [task_state_map[task.title] for task in tasks],
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_task_state_map(
    tasks: Sequence[PlanTask],
    persisted_state: dict[str, object] | None,
) -> dict[str, dict[str, object]]:
    state_map = {
        task.title: {
            "title": task.title,
            "status": "pending",
            "attempts": 0,
            "last_failure": "",
            "failure_reason": None,
            "verification_records": [],
            "attempt_history": [],
        }
        for task in tasks
    }
    if persisted_state is None:
        return state_map

    persisted_tasks = persisted_state.get("tasks", [])
    if not isinstance(persisted_tasks, list):
        raise ValueError("Persisted run state has invalid tasks payload")

    for item in persisted_tasks:
        title = str(item["title"])
        if title not in state_map:
            raise ValueError("Persisted run state does not match current plan tasks")
        state_map[title] = {
            "title": title,
            "status": str(item.get("status", "pending")),
            "attempts": int(item.get("attempts", 0)),
            "last_failure": str(item.get("last_failure", "")),
            "failure_reason": item.get("failure_reason"),
            "verification_records": list(item.get("verification_records", [])),
            "attempt_history": list(item.get("attempt_history", [])),
        }
    return state_map


def _build_task_results(
    tasks: Sequence[PlanTask],
    task_state_map: dict[str, dict[str, object]],
) -> list[TaskRunResult]:
    results: list[TaskRunResult] = []
    for task in tasks:
        item = task_state_map[task.title]
        results.append(
            TaskRunResult(
                task_title=task.title,
                attempts=int(item.get("attempts", 0)),
                status=str(item.get("status", "pending")),
                verification_records=[
                    VerificationRecord(
                        command=str(record["command"]),
                        exit_code=int(record["exit_code"]),
                        stdout=str(record.get("stdout", "")),
                        stderr=str(record.get("stderr", "")),
                    )
                    for record in item.get("verification_records", [])
                ],
            )
        )
    return results


def _append_attempt_history(
    task_state: dict[str, object],
    *,
    attempt: int,
    status: str,
    failure_stage: str | None,
    failure_reason: str | None,
    failure_summary: str,
    codex_result: CommandResult,
    verification_records: list[VerificationRecord],
) -> None:
    history = list(task_state.get("attempt_history", []))
    history.append(
        {
            "attempt": attempt,
            "status": status,
            "failure_stage": failure_stage,
            "failure_reason": failure_reason,
            "failure_summary": failure_summary,
            "codex_result": asdict(codex_result),
            "verification_records": [asdict(record) for record in verification_records],
        }
    )
    task_state["attempt_history"] = history
    task_state["failure_reason"] = failure_reason


def _build_verification_artifact_path(state_path: Path) -> Path:
    return state_path.with_suffix(".evidence.json")


def _write_verification_artifact(
    artifact_path: Path,
    *,
    plan_path: str,
    state_path: Path,
    status: str,
    verify_commands: list[str],
    tasks: Sequence[PlanTask],
    task_state_map: dict[str, dict[str, object]],
) -> None:
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1",
        "kind": "ptsm.run_plan.verification_evidence",
        "generated_at": _timestamp(),
        "plan_path": plan_path,
        "state_path": str(state_path),
        "status": status,
        "verify_commands": verify_commands,
        "tasks": [
            {
                "title": task.title,
                "status": task_state_map[task.title]["status"],
                "attempts": task_state_map[task.title]["attempts"],
                "last_failure": task_state_map[task.title]["last_failure"],
                "failure_reason": task_state_map[task.title].get("failure_reason"),
                "attempt_history": list(task_state_map[task.title]["attempt_history"]),
            }
            for task in tasks
        ],
    }
    artifact_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _classify_verification_failure_reason(command: str) -> str:
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    if "pytest" in normalized:
        return "pytest_failed"
    if re.search(r"(^| )doctor($| )", normalized):
        return "doctor_failed"
    if "run-fengkuang" in normalized:
        return "smoke_failed"
    if "xhs-check-publish" in normalized:
        return "publish_status_check_failed"
    return "verification_command_failed"
