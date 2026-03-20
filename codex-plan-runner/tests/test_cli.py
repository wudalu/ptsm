from __future__ import annotations

from pathlib import Path

from codex_plan_runner.cli import build_parser, main, run_cli
from codex_plan_runner.runner import CodexInvocation, CommandResult


def test_build_parser_supports_generic_run_options() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "--plan",
            "docs/plans/demo.md",
            "--verify-command",
            "pytest -q",
            "--max-attempts",
            "4",
            "--state-path",
            ".codex-plan-runner/runs/demo.json",
            "--resume",
            "--dry-run",
        ]
    )

    assert args.plan == Path("docs/plans/demo.md")
    assert args.verify_commands == ["pytest -q"]
    assert args.max_attempts == 4
    assert args.state_path == Path(".codex-plan-runner/runs/demo.json")
    assert args.resume is True
    assert args.dry_run is True


def test_run_cli_generates_default_state_path(monkeypatch, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")
    expected_state_path = tmp_path / ".codex-plan-runner" / "runs" / "generated.json"
    captured: dict[str, object] = {}

    class DummyResult:
        def to_dict(self) -> dict[str, object]:
            return {"status": "dry-run", "state_path": str(expected_state_path)}

    class DummyRunner:
        def __init__(self, *, codex_exec, verify_exec) -> None:
            captured["codex_exec"] = codex_exec
            captured["verify_exec"] = verify_exec

        def run(self, **kwargs):
            captured.update(kwargs)
            return DummyResult()

    monkeypatch.setattr(
        "codex_plan_runner.cli.build_default_state_path",
        lambda plan_path_arg: expected_state_path,
    )
    monkeypatch.setattr("codex_plan_runner.cli.PlanRunner", DummyRunner)

    result = run_cli(
        plan_path=plan_path,
        verify_commands=["pytest -q"],
        max_attempts=3,
        dry_run=True,
    )

    assert captured["state_path"] == expected_state_path
    assert result["state_path"] == str(expected_state_path)


def test_main_prints_json_result(monkeypatch, tmp_path: Path, capsys) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")

    def fake_run_cli(**kwargs):
        return {"status": "dry-run", "state_path": "state.json", "tasks": 1}

    monkeypatch.setattr("codex_plan_runner.cli.run_cli", fake_run_cli)

    exit_code = main(["--plan", str(plan_path), "--dry-run"])

    assert exit_code == 0
    assert '"status": "dry-run"' in capsys.readouterr().out


def test_run_cli_allows_running_codex_outside_git_repo(
    monkeypatch, tmp_path: Path
) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")
    captured: dict[str, object] = {}

    class DummyResult:
        def to_dict(self) -> dict[str, object]:
            return {"status": "completed"}

    class DummyRunner:
        def __init__(self, *, codex_exec, verify_exec) -> None:
            captured["codex_exec"] = codex_exec
            captured["verify_exec"] = verify_exec

        def run(self, **kwargs):
            captured.update(kwargs)
            codex_exec = captured["codex_exec"]
            assert callable(codex_exec)
            codex_exec(
                CodexInvocation(
                    prompt="implement task",
                    task_title="Task 1: Parser",
                    attempt=1,
                )
            )
            return DummyResult()

    def fake_run_subprocess_command(command):
        captured["command"] = list(command)
        return CommandResult(exit_code=0, stdout="ok", stderr="")

    monkeypatch.setattr("codex_plan_runner.cli.PlanRunner", DummyRunner)
    monkeypatch.setattr(
        "codex_plan_runner.cli.run_subprocess_command",
        fake_run_subprocess_command,
    )

    run_cli(
        plan_path=plan_path,
        verify_commands=[],
        max_attempts=1,
        dry_run=False,
        codex_bin="codex",
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
