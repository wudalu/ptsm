from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from codex_plan_runner.parser import parse_plan_tasks
from codex_plan_runner.runner import (
    CodexInvocation,
    PlanRunner,
    build_default_state_path,
    run_shell_command,
    run_subprocess_command,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="codex-plan-runner")
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument(
        "--verify-command",
        dest="verify_commands",
        action="append",
        default=[],
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--state-path", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument(
        "--full-auto",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def run_cli(
    *,
    plan_path: Path,
    verify_commands: Sequence[str],
    max_attempts: int,
    dry_run: bool,
    state_path: Path | None = None,
    resume: bool = False,
    codex_bin: str = "codex",
    sandbox: str = "workspace-write",
    full_auto: bool = True,
) -> dict[str, object]:
    tasks = parse_plan_tasks(plan_path)
    effective_state_path = state_path
    if resume and effective_state_path is None:
        raise ValueError("resume requires --state-path")
    if effective_state_path is None:
        effective_state_path = build_default_state_path(plan_path)

    def codex_exec(invocation: CodexInvocation):
        command = [
            codex_bin,
            "exec",
            "-C",
            str(Path.cwd()),
            "--skip-git-repo-check",
        ]
        if full_auto:
            command.append("--full-auto")
        if sandbox:
            command.extend(["--sandbox", sandbox])
        command.append(invocation.prompt)
        return run_subprocess_command(command)

    runner = PlanRunner(codex_exec=codex_exec, verify_exec=run_shell_command)
    result = runner.run(
        plan_path=plan_path,
        tasks=tasks,
        verify_commands=verify_commands,
        max_attempts=max_attempts,
        dry_run=dry_run,
        state_path=effective_state_path,
        resume=resume,
    )
    return result.to_dict()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_cli(
        plan_path=args.plan,
        verify_commands=args.verify_commands,
        max_attempts=args.max_attempts,
        dry_run=args.dry_run,
        state_path=args.state_path,
        resume=args.resume,
        codex_bin=args.codex_bin,
        sandbox=args.sandbox,
        full_auto=args.full_auto,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
