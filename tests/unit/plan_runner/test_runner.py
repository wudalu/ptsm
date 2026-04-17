from __future__ import annotations

import json
from pathlib import Path

from ptsm.plan_runner.parser import PlanTask
from ptsm.plan_runner.runner import (
    CodexInvocation,
    CommandResult,
    PlanExecutionError,
    PlanRunner,
)


def test_plan_runner_executes_tasks_in_order() -> None:
    prompts: list[str] = []
    verify_commands: list[str] = []

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        prompts.append(invocation.prompt)
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    def verify_exec(command: str) -> CommandResult:
        verify_commands.append(command)
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[
            PlanTask(title="Task 1: Parser", body="- create parser"),
            PlanTask(title="Task 2: Runner", body="- create runner"),
        ],
        verify_commands=["pytest tests/unit -q"],
        max_attempts=2,
    )

    assert [item.task_title for item in result.task_results] == [
        "Task 1: Parser",
        "Task 2: Runner",
    ]
    assert verify_commands == ["pytest tests/unit -q", "pytest tests/unit -q"]
    assert "Task 1: Parser" in prompts[0]
    assert "Task 2: Runner" in prompts[1]


def test_plan_runner_retries_with_verification_feedback() -> None:
    prompts: list[str] = []
    verification_attempts = 0

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        prompts.append(invocation.prompt)
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        nonlocal verification_attempts
        verification_attempts += 1
        if verification_attempts == 1:
            return CommandResult(exit_code=1, stdout="", stderr="tests failed")
        return CommandResult(exit_code=0, stdout="tests passed", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
        verify_commands=["pytest tests/unit -q"],
        max_attempts=2,
    )

    assert len(prompts) == 2
    assert "Verification failed" in prompts[1]
    assert "tests failed" in prompts[1]


def test_plan_runner_raises_after_exhausting_attempts() -> None:
    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        return CommandResult(exit_code=1, stdout="", stderr="still failing")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    try:
        runner.run(
            plan_path="docs/plans/demo.md",
            tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
            verify_commands=["pytest tests/unit -q"],
            max_attempts=2,
        )
    except PlanExecutionError as exc:
        assert "Task 1: Parser" in str(exc)
        assert "still failing" in str(exc)
    else:
        raise AssertionError("Expected PlanExecutionError")


def test_plan_runner_uses_task_level_verify_and_max_attempts() -> None:
    prompts: list[str] = []
    verify_commands: list[str] = []

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        prompts.append(invocation.prompt)
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        verify_commands.append(command)
        return CommandResult(exit_code=1, stdout="", stderr="task-specific failure")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    try:
        runner.run(
            plan_path="docs/plans/demo.md",
            tasks=[
                PlanTask(
                    title="Task 1: Parser",
                    body="- create parser",
                    verify_commands=["uv run pytest tests/unit/plan_runner/test_parser.py -q"],
                    max_attempts=1,
                )
            ],
            verify_commands=["uv run pytest tests/unit/plan_runner/test_runner.py -q"],
            max_attempts=3,
        )
    except PlanExecutionError as exc:
        assert "task-specific failure" in str(exc)
    else:
        raise AssertionError("Expected PlanExecutionError")

    assert verify_commands == ["uv run pytest tests/unit/plan_runner/test_parser.py -q"]
    assert len(prompts) == 1


def test_plan_runner_persists_state_file(tmp_path: Path) -> None:
    state_path = tmp_path / "run-state.json"

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    def verify_exec(command: str) -> CommandResult:
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
        verify_commands=["uv run pytest tests/unit -q"],
        max_attempts=2,
        state_path=state_path,
    )

    saved = json.loads(state_path.read_text(encoding="utf-8"))

    assert result.verification_artifact_path == str(
        state_path.with_suffix(".evidence.json")
    )
    assert saved["status"] == "completed"
    assert saved["verification_artifact_path"] == str(
        state_path.with_suffix(".evidence.json")
    )
    assert saved["tasks"][0]["title"] == "Task 1: Parser"
    assert saved["tasks"][0]["status"] == "passed"
    assert saved["tasks"][0]["attempts"] == 1


def test_plan_runner_writes_verification_evidence_with_attempt_history(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "run-state.json"
    verify_attempts = 0

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        nonlocal verify_attempts
        verify_attempts += 1
        if verify_attempts == 1:
            return CommandResult(exit_code=1, stdout="nope", stderr="first failure")
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
        verify_commands=["uv run pytest tests/unit -q"],
        max_attempts=2,
        state_path=state_path,
    )

    evidence_path = state_path.with_suffix(".evidence.json")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))

    assert result.verification_artifact_path == str(evidence_path)
    assert evidence["status"] == "completed"
    assert evidence["state_path"] == str(state_path)
    assert evidence["tasks"][0]["title"] == "Task 1: Parser"
    assert evidence["tasks"][0]["attempt_history"][0]["attempt"] == 1
    assert evidence["tasks"][0]["attempt_history"][0]["status"] == "failed"
    assert evidence["tasks"][0]["attempt_history"][0]["verification_records"][0][
        "stderr"
    ] == "first failure"
    assert evidence["tasks"][0]["attempt_history"][1]["attempt"] == 2
    assert evidence["tasks"][0]["attempt_history"][1]["status"] == "passed"


def test_plan_runner_resumes_and_skips_completed_tasks(tmp_path: Path) -> None:
    state_path = tmp_path / "run-state.json"
    state_path.write_text(
        json.dumps(
            {
                "plan_path": "docs/plans/demo.md",
                "status": "in_progress",
                "verify_commands": ["uv run pytest tests/unit -q"],
                "max_attempts": 3,
                "tasks": [
                    {
                        "title": "Task 1: Parser",
                        "status": "passed",
                        "attempts": 1,
                        "last_failure": "",
                        "verification_records": [],
                    },
                    {
                        "title": "Task 2: Runner",
                        "status": "pending",
                        "attempts": 0,
                        "last_failure": "",
                        "verification_records": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    executed_titles: list[str] = []

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        executed_titles.append(invocation.task_title)
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    def verify_exec(command: str) -> CommandResult:
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[
            PlanTask(title="Task 1: Parser", body="- create parser"),
            PlanTask(title="Task 2: Runner", body="- create runner"),
        ],
        verify_commands=["uv run pytest tests/unit -q"],
        max_attempts=3,
        state_path=state_path,
        resume=True,
    )

    assert executed_titles == ["Task 2: Runner"]
    assert [item.task_title for item in result.task_results] == [
        "Task 1: Parser",
        "Task 2: Runner",
    ]


def test_plan_runner_persists_failed_task_state_for_real_resume(tmp_path: Path) -> None:
    state_path = tmp_path / "run-state.json"
    codex_attempts = 0

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        nonlocal codex_attempts
        codex_attempts += 1
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    verify_attempts = 0

    def verify_exec(command: str) -> CommandResult:
        nonlocal verify_attempts
        verify_attempts += 1
        if verify_attempts == 1:
            return CommandResult(exit_code=1, stdout="", stderr="first failure")
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=verify_exec,
    )

    try:
        runner.run(
            plan_path="docs/plans/demo.md",
            tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
            verify_commands=["uv run pytest tests/unit -q"],
            max_attempts=1,
            state_path=state_path,
        )
    except PlanExecutionError:
        pass
    else:
        raise AssertionError("Expected initial run to fail")

    failed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert failed_state["status"] == "failed"
    assert failed_state["tasks"][0]["title"] == "Task 1: Parser"
    assert failed_state["tasks"][0]["status"] == "failed"
    assert failed_state["tasks"][0]["attempts"] == 1
    assert "first failure" in failed_state["tasks"][0]["last_failure"]

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
        verify_commands=["uv run pytest tests/unit -q"],
        max_attempts=2,
        state_path=state_path,
        resume=True,
    )

    assert codex_attempts == 2
    assert result.task_results[0].status == "passed"
    assert result.task_results[0].attempts == 2
