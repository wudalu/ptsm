from __future__ import annotations

from pathlib import Path

from ptsm.interfaces.cli.main import build_default_state_path, run_plan_cli
from ptsm.plan_runner.runner import CodexInvocation, CommandResult


def test_run_plan_cli_allows_non_git_directories(monkeypatch, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")

    captured: dict[str, object] = {}

    class DummyResult:
        def __init__(self, state_path: Path | None) -> None:
            self.state_path = state_path

        def to_dict(self) -> dict[str, object]:
            return {
                "status": "dry-run",
                "verification_artifact_path": (
                    str(self.state_path.with_suffix(".evidence.json"))
                    if self.state_path is not None
                    else None
                ),
            }

    class DummyRunner:
        def __init__(self, *, codex_exec, verify_exec) -> None:
            captured["codex_exec"] = codex_exec
            captured["verify_exec"] = verify_exec

        def run(self, **kwargs):
            captured.update(kwargs)
            return DummyResult(kwargs.get("state_path"))

    def fake_run_subprocess_command(command: list[str]) -> CommandResult:
        captured["command"] = command
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("ptsm.interfaces.cli.main.PlanRunner", DummyRunner)
    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_subprocess_command",
        fake_run_subprocess_command,
    )

    run_plan_cli(
        plan_path=plan_path,
        verify_commands=["uv run pytest -q"],
        max_attempts=3,
        dry_run=False,
    )

    codex_exec = captured["codex_exec"]
    assert callable(codex_exec)
    codex_exec(
        CodexInvocation(
            prompt="implement task",
            task_title="Task 1: Parser",
            attempt=1,
        )
    )

    assert captured["command"] == [
        "codex",
        "exec",
        "-C",
        str(Path.cwd()),
        "--skip-git-repo-check",
        "--full-auto",
        "--sandbox",
        "workspace-write",
        "implement task",
    ]


def test_run_plan_cli_returns_verification_artifact_path(
    monkeypatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")
    state_path = tmp_path / "state.json"

    class DummyResult:
        def to_dict(self) -> dict[str, object]:
            return {
                "status": "completed",
                "verification_artifact_path": str(
                    state_path.with_suffix(".evidence.json")
                ),
            }

    class DummyRunner:
        def __init__(self, *, codex_exec, verify_exec) -> None:
            pass

        def run(self, **kwargs):
            return DummyResult()

    monkeypatch.setattr("ptsm.interfaces.cli.main.PlanRunner", DummyRunner)

    result = run_plan_cli(
        plan_path=plan_path,
        verify_commands=["uv run pytest -q"],
        max_attempts=3,
        dry_run=False,
        state_path=state_path,
    )

    assert result["verification_artifact_path"] == str(
        state_path.with_suffix(".evidence.json")
    )


def test_build_default_state_path_uses_plan_runs_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    state_path = build_default_state_path(Path("docs/plans/demo.md"))

    assert state_path.parent == tmp_path / ".ptsm" / "plan_runs"
    assert state_path.name.startswith("demo-")
    assert state_path.suffix == ".json"
