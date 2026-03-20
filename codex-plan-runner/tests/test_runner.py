from __future__ import annotations

import json
from pathlib import Path

from codex_plan_runner.parser import PlanTask
from codex_plan_runner.runner import (
    CodexInvocation,
    CommandResult,
    PlanExecutionError,
    PlanRunner,
    build_default_state_path,
)


def test_plan_runner_executes_tasks_and_verifies_in_order() -> None:
    prompts: list[str] = []
    verify_commands: list[str] = []

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        prompts.append(invocation.prompt)
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    def verify_exec(command: str) -> CommandResult:
        verify_commands.append(command)
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(codex_exec=codex_exec, verify_exec=verify_exec)

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[
            PlanTask(title="Task 1: Parser", body="- create parser"),
            PlanTask(title="Task 2: Runner", body="- create runner"),
        ],
        verify_commands=["pytest -q"],
        max_attempts=2,
    )

    assert [item.task_title for item in result.task_results] == [
        "Task 1: Parser",
        "Task 2: Runner",
    ]
    assert verify_commands == ["pytest -q", "pytest -q"]
    assert "Task 1: Parser" in prompts[0]
    assert "Task 2: Runner" in prompts[1]


def test_plan_runner_uses_task_level_verify_and_max_attempts() -> None:
    verify_commands: list[str] = []
    prompts: list[str] = []

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        prompts.append(invocation.prompt)
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        verify_commands.append(command)
        return CommandResult(exit_code=1, stdout="", stderr="task-specific failure")

    runner = PlanRunner(codex_exec=codex_exec, verify_exec=verify_exec)

    try:
        runner.run(
            plan_path="docs/plans/demo.md",
            tasks=[
                PlanTask(
                    title="Task 1: Parser",
                    body="- create parser",
                    verify_commands=["uv run pytest tests/test_parser.py -q"],
                    max_attempts=1,
                )
            ],
            verify_commands=["uv run pytest tests/test_runner.py -q"],
            max_attempts=3,
        )
    except PlanExecutionError as exc:
        assert "task-specific failure" in str(exc)
    else:
        raise AssertionError("Expected PlanExecutionError")

    assert verify_commands == ["uv run pytest tests/test_parser.py -q"]
    assert len(prompts) == 1


def test_plan_runner_persists_and_resumes_state(tmp_path: Path) -> None:
    state_path = tmp_path / "run-state.json"
    codex_attempts = 0
    verify_attempts = 0

    def codex_exec(invocation: CodexInvocation) -> CommandResult:
        nonlocal codex_attempts
        codex_attempts += 1
        return CommandResult(exit_code=0, stdout="implemented", stderr="")

    def verify_exec(command: str) -> CommandResult:
        nonlocal verify_attempts
        verify_attempts += 1
        if verify_attempts == 1:
            return CommandResult(exit_code=1, stdout="", stderr="first failure")
        return CommandResult(exit_code=0, stdout="pass", stderr="")

    runner = PlanRunner(codex_exec=codex_exec, verify_exec=verify_exec)

    try:
        runner.run(
            plan_path="docs/plans/demo.md",
            tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
            verify_commands=["pytest -q"],
            max_attempts=1,
            state_path=state_path,
        )
    except PlanExecutionError:
        pass
    else:
        raise AssertionError("Expected initial run to fail")

    saved = json.loads(state_path.read_text(encoding="utf-8"))
    assert saved["status"] == "failed"
    assert saved["tasks"][0]["status"] == "failed"
    assert saved["tasks"][0]["attempts"] == 1

    result = runner.run(
        plan_path="docs/plans/demo.md",
        tasks=[PlanTask(title="Task 1: Parser", body="- create parser")],
        verify_commands=["pytest -q"],
        max_attempts=2,
        state_path=state_path,
        resume=True,
    )

    assert codex_attempts == 2
    assert result.task_results[0].status == "passed"
    assert result.task_results[0].attempts == 2


def test_build_default_state_path_uses_generic_hidden_directory(tmp_path: Path) -> None:
    state_path = build_default_state_path(
        plan_path=tmp_path / "demo.md",
        base_dir=tmp_path / ".codex-plan-runner" / "runs",
    )

    assert state_path.parent == tmp_path / ".codex-plan-runner" / "runs"
    assert state_path.name.startswith("demo-")
    assert state_path.suffix == ".json"
