from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Sequence
import uuid

from ptsm.application.models import FengkuangRequest
from ptsm.application.use_cases.doctor import run_doctor
from ptsm.application.use_cases.harness_gc import run_harness_gc
from ptsm.application.use_cases.logs import run_logs
from ptsm.application.use_cases.plan_runs import run_plan_runs
from ptsm.application.use_cases.run_events import run_run_events
from ptsm.application.use_cases.runs import run_runs
from ptsm.application.use_cases.run_playbook import run_fengkuang_playbook
from ptsm.application.use_cases.xhs_browser import open_xhs_browser
from ptsm.application.use_cases.xhs_login import (
    DEFAULT_XHS_LOGIN_QRCODE_PATH,
    run_xhs_login_qrcode,
    run_xhs_login_status,
)
from ptsm.application.use_cases.xhs_publish_status import check_xhs_publish_status
from ptsm.config.settings import Settings, get_settings
from ptsm.plan_runner.parser import parse_plan_tasks
from ptsm.plan_runner.runner import (
    CodexInvocation,
    PlanRunner,
    run_shell_command,
    run_subprocess_command,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="ptsm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fengkuang = subparsers.add_parser("run-fengkuang")
    fengkuang.add_argument("--scene", required=True)
    fengkuang.add_argument("--platform", default="xiaohongshu")
    fengkuang.add_argument("--account-id", default="acct-fk-local")
    fengkuang.add_argument("--thread-id")
    fengkuang.add_argument("--publish-mode")
    fengkuang.add_argument(
        "--publish-image-path",
        action="append",
        default=[],
    )
    fengkuang.add_argument("--publish-visibility")
    fengkuang.add_argument("--open-browser-if-needed", action="store_true")
    fengkuang.add_argument("--wait-for-publish-status", action="store_true")
    fengkuang.add_argument(
        "--login-qrcode-output",
        type=Path,
        default=DEFAULT_XHS_LOGIN_QRCODE_PATH,
    )

    xhs_login_status = subparsers.add_parser("xhs-login-status")
    xhs_login_status.add_argument("--server-url")

    xhs_login_qrcode = subparsers.add_parser("xhs-login-qrcode")
    xhs_login_qrcode.add_argument("--server-url")
    xhs_login_qrcode.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_XHS_LOGIN_QRCODE_PATH,
    )

    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--server-url")

    gc = subparsers.add_parser("gc")
    gc.add_argument("--apply", action="store_true")
    gc.add_argument("--runs-retention-days", type=int, default=30)
    gc.add_argument("--plan-runs-retention-days", type=int, default=30)

    logs = subparsers.add_parser("logs")
    logs.add_argument("--run-id")
    logs.add_argument("--artifact", type=Path)

    runs = subparsers.add_parser("runs")
    runs.add_argument("--account-id")
    runs.add_argument("--platform")
    runs.add_argument("--playbook-id")
    runs.add_argument("--status")
    runs.add_argument("--limit", type=int, default=20)

    run_events = subparsers.add_parser("run-events")
    run_events.add_argument("--account-id")
    run_events.add_argument("--platform")
    run_events.add_argument("--playbook-id")
    run_events.add_argument("--run-status")
    run_events.add_argument("--event")
    run_events.add_argument("--step")
    run_events.add_argument("--event-status")
    run_events.add_argument("--group-by")
    run_events.add_argument("--limit", type=int, default=50)

    plan_runs = subparsers.add_parser("plan-runs")
    plan_runs.add_argument("--status")
    plan_runs.add_argument("--failure-reason")
    plan_runs.add_argument("--plan-path")
    plan_runs.add_argument("--limit", type=int, default=20)

    xhs_open_browser = subparsers.add_parser("xhs-open-browser")
    xhs_open_browser.add_argument("--target", choices=["login", "creator", "artifact"], required=True)
    xhs_open_browser.add_argument("--artifact", type=Path)
    xhs_open_browser.add_argument("--url")
    xhs_open_browser.add_argument(
        "--qrcode-output",
        type=Path,
        default=DEFAULT_XHS_LOGIN_QRCODE_PATH,
    )

    xhs_check_publish = subparsers.add_parser("xhs-check-publish")
    xhs_check_publish.add_argument("--artifact", type=Path, required=True)
    xhs_check_publish.add_argument("--server-url")

    run_plan = subparsers.add_parser("run-plan")
    run_plan.add_argument("--plan", type=Path, required=True)
    run_plan.add_argument(
        "--verify-command",
        dest="verify_commands",
        action="append",
        default=[],
    )
    run_plan.add_argument("--max-attempts", type=int, default=3)
    run_plan.add_argument("--state-path", type=Path)
    run_plan.add_argument("--resume", action="store_true")
    run_plan.add_argument("--dry-run", action="store_true")
    run_plan.add_argument("--codex-bin", default="codex")
    run_plan.add_argument("--sandbox", default="workspace-write")
    run_plan.add_argument(
        "--full-auto",
        action=argparse.BooleanOptionalAction,
        default=True,
    )

    return parser


def build_default_state_path(plan_path: Path) -> Path:
    state_dir = Path.cwd() / ".ptsm" / "plan_runs"
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = uuid.uuid4().hex[:8]
    return state_dir / f"{plan_path.stem}-{timestamp}-{run_id}.json"


def build_login_settings(*, server_url: str | None) -> Settings:
    settings = get_settings()
    if not server_url:
        return settings
    return settings.model_copy(update={"xhs_mcp_server_url": server_url})


def run_plan_cli(
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
        command = [codex_bin, "exec", "-C", str(Path.cwd())]
        command.append("--skip-git-repo-check")
        if full_auto:
            command.append("--full-auto")
        if sandbox:
            command.extend(["--sandbox", sandbox])
        command.append(invocation.prompt)
        return run_subprocess_command(command)

    runner = PlanRunner(
        codex_exec=codex_exec,
        verify_exec=run_shell_command,
    )
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
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-fengkuang":
        result = run_fengkuang_playbook(
            FengkuangRequest(
                scene=args.scene,
                platform=args.platform,
                account_id=args.account_id,
                publish_mode=args.publish_mode,
                publish_image_paths=args.publish_image_path,
                publish_visibility=args.publish_visibility,
                login_qrcode_output_path=str(args.login_qrcode_output),
                open_browser_if_needed=args.open_browser_if_needed,
                wait_for_publish_status=args.wait_for_publish_status,
            ),
            thread_id=args.thread_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-plan":
        result = run_plan_cli(
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

    if args.command == "xhs-login-status":
        result = run_xhs_login_status(
            settings=build_login_settings(server_url=args.server_url)
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "xhs-login-qrcode":
        result = run_xhs_login_qrcode(
            output_path=args.output,
            settings=build_login_settings(server_url=args.server_url),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        result = run_doctor(
            settings=build_login_settings(server_url=args.server_url),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "gc":
        result = run_harness_gc(
            apply=args.apply,
            runs_retention_days=args.runs_retention_days,
            plan_runs_retention_days=args.plan_runs_retention_days,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "logs":
        result = run_logs(
            run_id=args.run_id,
            artifact_path=args.artifact,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "runs":
        result = run_runs(
            account_id=args.account_id,
            platform=args.platform,
            playbook_id=args.playbook_id,
            status=args.status,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-events":
        result = run_run_events(
            account_id=args.account_id,
            platform=args.platform,
            playbook_id=args.playbook_id,
            run_status=args.run_status,
            event=args.event,
            step=args.step,
            event_status=args.event_status,
            group_by=args.group_by,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "plan-runs":
        result = run_plan_runs(
            status=args.status,
            failure_reason=args.failure_reason,
            plan_path=args.plan_path,
            limit=args.limit,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "xhs-open-browser":
        result = open_xhs_browser(
            target=args.target,
            artifact_path=args.artifact,
            qrcode_output_path=args.qrcode_output,
            url=args.url,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "xhs-check-publish":
        result = check_xhs_publish_status(
            artifact_path=args.artifact,
            settings=build_login_settings(server_url=args.server_url),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
