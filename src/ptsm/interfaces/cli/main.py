from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Sequence
import uuid

from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.use_cases.analyze_xhs_patterns import run_analyze_xhs_patterns
from ptsm.application.use_cases.collect_xhs_patterns import run_collect_xhs_patterns
from ptsm.application.use_cases.diagnose_publish import run_diagnose_publish
from ptsm.application.use_cases.doctor import run_doctor
from ptsm.application.use_cases.eval_artifact import run_eval_artifact
from ptsm.accounts.registry import AccountRegistry
from ptsm.application.use_cases.docs_sync import run_docs_sync
from ptsm.application.use_cases.guide_post import (
    GuidePostRequest,
    PSYCHOLOGY_LANES,
    SUPPORTED_PLAYBOOK_ID,
    format_guide_post_markdown,
    resolve_psychology_lane,
    run_guide_post,
)
from ptsm.application.use_cases.harness_check import run_harness_check
from ptsm.application.use_cases.harness_evals import run_harness_evals
from ptsm.application.use_cases.harness_gc import run_harness_gc
from ptsm.application.use_cases.harness_report import run_harness_report
from ptsm.application.use_cases.install_git_hooks import install_git_hooks
from ptsm.application.use_cases.logs import run_logs
from ptsm.application.use_cases.plan_runs import run_plan_runs
from ptsm.application.use_cases.run_events import run_run_events
from ptsm.application.use_cases.runs import run_runs
from ptsm.application.use_cases.run_playbook import run_fengkuang_playbook, run_playbook
from ptsm.application.use_cases.xhs_browser import open_xhs_browser
from ptsm.application.use_cases.xhs_domain_opportunity import (
    run_xhs_domain_opportunity,
)
from ptsm.application.use_cases.xhs_login import (
    DEFAULT_XHS_LOGIN_QRCODE_PATH,
    run_xhs_login_qrcode,
    run_xhs_login_status,
)
from ptsm.application.use_cases.xhs_publish_status import check_xhs_publish_status
from ptsm.application.use_cases.topic_guidance_packs import TOPIC_GUIDANCE_PACKS
from ptsm.config.settings import Settings, get_settings
from ptsm.domain.topic_guidance import resolve_topic_lane
from ptsm.plan_runner.parser import parse_plan_tasks
from ptsm.plan_runner.runner import (
    CodexInvocation,
    PlanRunner,
    run_shell_command,
    run_subprocess_command,
)

LOCAL_IMAGE_STYLE_CHOICES = ("note_card", "iphone_notes", "wechat_chat")


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level CLI parser."""
    parser = argparse.ArgumentParser(prog="ptsm")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fengkuang = subparsers.add_parser("run-fengkuang")
    fengkuang.add_argument("--scene", default="")
    fengkuang.add_argument("--platform", default="xiaohongshu")
    fengkuang.add_argument("--account-id", default="acct-fk-local")
    fengkuang.add_argument("--thread-id")
    fengkuang.add_argument("--publish-mode")
    fengkuang.add_argument(
        "--publish-image-path",
        action="append",
        default=[],
    )
    fengkuang.add_argument(
        "--auto-generate-image",
        dest="auto_generate_image",
        action="store_true",
    )
    fengkuang.add_argument(
        "--no-auto-generate-image",
        dest="auto_generate_image",
        action="store_false",
    )
    fengkuang.set_defaults(auto_generate_image=None)
    fengkuang.add_argument("--local-image-style", choices=LOCAL_IMAGE_STYLE_CHOICES)
    fengkuang.add_argument("--publish-visibility")
    fengkuang.add_argument("--open-browser-if-needed", action="store_true")
    fengkuang.add_argument("--wait-for-publish-status", action="store_true")
    fengkuang.add_argument("--fresh-topic-research", action="store_true")
    fengkuang.add_argument("--eval", action="store_true")
    fengkuang.add_argument(
        "--login-qrcode-output",
        type=Path,
        default=DEFAULT_XHS_LOGIN_QRCODE_PATH,
    )

    run_playbook_cli = subparsers.add_parser("run-playbook")
    run_playbook_cli.add_argument("--scene", default="")
    run_playbook_cli.add_argument("--platform")
    run_playbook_cli.add_argument("--account-id", required=True)
    run_playbook_cli.add_argument("--playbook-id")
    run_playbook_cli.add_argument("--caller")
    run_playbook_cli.add_argument("--guidance-ack", action="store_true")
    run_playbook_cli.add_argument("--topic-direction-id")
    run_playbook_cli.add_argument("--thread-id")
    run_playbook_cli.add_argument("--publish-mode")
    run_playbook_cli.add_argument(
        "--publish-image-path",
        action="append",
        default=[],
    )
    run_playbook_cli.add_argument(
        "--auto-generate-image",
        dest="auto_generate_image",
        action="store_true",
    )
    run_playbook_cli.add_argument(
        "--no-auto-generate-image",
        dest="auto_generate_image",
        action="store_false",
    )
    run_playbook_cli.set_defaults(auto_generate_image=None)
    run_playbook_cli.add_argument("--local-image-style", choices=LOCAL_IMAGE_STYLE_CHOICES)
    run_playbook_cli.add_argument("--publish-visibility")
    run_playbook_cli.add_argument("--open-browser-if-needed", action="store_true")
    run_playbook_cli.add_argument("--wait-for-publish-status", action="store_true")
    run_playbook_cli.add_argument("--fresh-topic-research", action="store_true")
    run_playbook_cli.add_argument("--format-pattern-path", type=Path)
    run_playbook_cli.add_argument("--eval", action="store_true")
    run_playbook_cli.add_argument(
        "--login-qrcode-output",
        type=Path,
        default=DEFAULT_XHS_LOGIN_QRCODE_PATH,
    )

    guide_post = subparsers.add_parser("guide-post")
    guide_post.add_argument("--playbook-id", default="modern_psychology_post")
    guide_post.add_argument("--account-id", default="acct-psychology-local")
    guide_post.add_argument("--lane")
    guide_post.add_argument("--scene")
    guide_post.add_argument("--mechanism")
    guide_post.add_argument("--save-tool")
    guide_post.add_argument("--image-style", choices=LOCAL_IMAGE_STYLE_CHOICES)
    guide_post.add_argument("--comment-prompt")
    guide_post.add_argument("--non-interactive", action="store_true")
    guide_post.add_argument("--format", choices=("json", "markdown"))

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

    docs_sync = subparsers.add_parser("docs-sync")
    docs_sync.add_argument("--base-ref")
    docs_sync.add_argument("--head-ref", default="HEAD")
    docs_sync.add_argument(
        "--changed-path",
        dest="changed_paths",
        action="append",
        default=None,
    )

    harness_check = subparsers.add_parser("harness-check")
    harness_check.add_argument("--base-ref")
    harness_check.add_argument("--head-ref", default="HEAD")
    harness_check.add_argument("--strict", action="store_true")
    harness_check.add_argument(
        "--changed-path",
        dest="changed_paths",
        action="append",
        default=None,
    )

    install_hooks = subparsers.add_parser("install-git-hooks")
    install_hooks.add_argument("--base-ref", default="origin/main")
    install_hooks.add_argument("--force", action="store_true")

    accounts = subparsers.add_parser("accounts")

    gc = subparsers.add_parser("gc")
    gc.add_argument("--apply", action="store_true")
    gc.add_argument("--runs-retention-days", type=int, default=30)
    gc.add_argument("--plan-runs-retention-days", type=int, default=30)

    harness_evals = subparsers.add_parser("harness-evals")
    harness_evals.add_argument("--account-id")
    harness_evals.add_argument("--platform")
    harness_evals.add_argument("--playbook-id")
    harness_evals.add_argument("--plan-path")

    harness_report = subparsers.add_parser("harness-report")
    harness_report.add_argument("--server-url")
    harness_report.add_argument("--account-id")
    harness_report.add_argument("--platform")
    harness_report.add_argument("--playbook-id")
    harness_report.add_argument("--plan-path")
    harness_report.add_argument("--runs-retention-days", type=int, default=30)
    harness_report.add_argument("--plan-runs-retention-days", type=int, default=30)
    harness_report.add_argument("--max-stale-docs", type=int)
    harness_report.add_argument("--max-gc-candidates", type=int)
    harness_report.add_argument("--min-run-completion-rate", type=float)
    harness_report.add_argument("--min-plan-completion-rate", type=float)
    harness_report.add_argument("--fail-on-warning", action="store_true")

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

    eval_artifact_parser = subparsers.add_parser("eval-artifact")
    eval_artifact_parser.add_argument("--artifact", type=Path, required=True)

    diagnose_publish = subparsers.add_parser("diagnose-publish")
    diagnose_publish.add_argument("--artifact", type=Path)
    diagnose_publish.add_argument("--run-id")
    diagnose_publish.add_argument("--server-url")

    collect_xhs_patterns = subparsers.add_parser("collect-xhs-patterns")
    collect_xhs_patterns.add_argument("--lane", required=True)
    collect_xhs_patterns.add_argument("--keywords", required=True)
    collect_xhs_patterns.add_argument("--sample-limit-per-keyword", type=int, default=8)
    collect_xhs_patterns.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/artifacts/xhs-pattern-library"),
    )
    collect_xhs_patterns.add_argument("--dry-run", action="store_true")
    collect_xhs_patterns.add_argument("--delay-seconds", type=float, default=1.0)
    collect_xhs_patterns.add_argument("--skip-login-check", action="store_true")
    collect_xhs_patterns.add_argument("--tool-timeout-seconds", type=float)

    xhs_domain_opportunity = subparsers.add_parser("xhs-domain-opportunity")
    xhs_domain_opportunity.add_argument("--keywords", required=True)
    xhs_domain_opportunity.add_argument("--lane", default="xhs_domain_opportunity")
    xhs_domain_opportunity.add_argument("--sample-limit-per-keyword", type=int, default=5)
    xhs_domain_opportunity.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/artifacts/xhs-domain-opportunity"),
    )
    xhs_domain_opportunity.add_argument("--delay-seconds", type=float, default=0.8)
    xhs_domain_opportunity.add_argument("--skip-login-check", action="store_true")
    xhs_domain_opportunity.add_argument("--tool-timeout-seconds", type=float)

    analyze_xhs_patterns = subparsers.add_parser("analyze-xhs-patterns")
    analyze_xhs_patterns.add_argument("--sample-path", type=Path, required=True)
    analyze_xhs_patterns.add_argument("--lane", required=True)
    analyze_xhs_patterns.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/artifacts/xhs-pattern-library"),
    )

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


def _prompt_to_stderr(prompt: str) -> str:
    print(prompt, file=sys.stderr, end="")
    return input().strip()


def _print_guide_post_lane_options() -> None:
    for idx, option in enumerate(PSYCHOLOGY_LANES, 1):
        print(f"  {idx}. {option.name}", file=sys.stderr)


def _print_topic_lane_options(lanes: Sequence[object]) -> None:
    for idx, option in enumerate(lanes, 1):
        print(f"  {idx}. {option.name}", file=sys.stderr)


def _collect_guide_post_request(args: argparse.Namespace) -> GuidePostRequest:
    if args.playbook_id != SUPPORTED_PLAYBOOK_ID:
        return _collect_generic_guide_post_request(args)

    print("我们先把这条现代心理学帖子聊成一个可执行 brief。", file=sys.stderr)
    scene = args.scene
    if scene:
        print(f"1/6 具体场景：{scene}", file=sys.stderr)
    else:
        scene = _prompt_to_stderr(
            "1/6 先说一个具体瞬间，比如“看到别人周末都在聚会，自己突然很失败”： "
        )

    suggested_lane = resolve_psychology_lane(scene=scene)
    print(
        f"我会先按「{suggested_lane.name}」处理，这样更容易写成一个清楚的心理学切口。",
        file=sys.stderr,
    )

    lane = args.lane
    if lane:
        print(f"2/6 选题 lane：{lane}", file=sys.stderr)
    else:
        print("2/6 如果方向不准，可以输入编号调整；回车接受建议。", file=sys.stderr)
        _print_guide_post_lane_options()
        selected_lane = _prompt_to_stderr(f"选题 lane [默认：{suggested_lane.name}]: ")
        lane = selected_lane or suggested_lane.name

    defaults = resolve_psychology_lane(lane=lane, scene=scene)

    mechanism = args.mechanism
    if mechanism is None:
        mechanism = _prompt_to_stderr(
            f"3/6 这篇只解释一个心理机制，建议「{defaults.mechanism}」。要改就输入新机制，回车接受: "
        )

    save_tool = args.save_tool
    if save_tool is None:
        save_tool = _prompt_to_stderr(
            f"4/6 给读者一个可保存动作或小工具，建议「{defaults.save_tool}」。要改就输入，回车接受: "
        )

    image_style = args.image_style
    if image_style is None:
        image_style = _prompt_to_stderr(
            f"5/6 封面建议低密度「{defaults.image_style}」。可选 note_card / iphone_notes / wechat_chat，回车接受: "
        )

    comment_prompt = args.comment_prompt
    if comment_prompt is None:
        comment_prompt = _prompt_to_stderr(
            f"6/6 评论区要有角色认领或 A/B 入口，建议「{defaults.comment_prompt}」。要改就输入，回车接受: "
        )

    return GuidePostRequest(
        playbook_id=args.playbook_id,
        account_id=args.account_id,
        lane=lane,
        scene=scene,
        mechanism=mechanism,
        save_tool=save_tool,
        image_style=image_style,
        comment_prompt=comment_prompt,
    )


def _collect_generic_guide_post_request(args: argparse.Namespace) -> GuidePostRequest:
    pack = TOPIC_GUIDANCE_PACKS.get(args.playbook_id)
    if pack is None:
        return GuidePostRequest(
            playbook_id=args.playbook_id,
            account_id=args.account_id,
            lane=args.lane,
            scene=args.scene,
            image_style=args.image_style,
            comment_prompt=args.comment_prompt,
        )

    print("我们先把这条小红书帖子聊成一个可执行选题 brief。", file=sys.stderr)
    scene = args.scene
    if scene:
        print(f"1/3 具体场景：{scene}", file=sys.stderr)
    else:
        scene = _prompt_to_stderr("1/3 先说一个具体瞬间或想写的对象： ")

    suggested_lane = resolve_topic_lane(lanes=pack.lanes, scene=scene)
    print(
        f"我会先按「{suggested_lane.name}」处理，这样更容易写成清楚的内容切口。",
        file=sys.stderr,
    )

    lane = args.lane
    if lane:
        print(f"2/3 选题 lane：{lane}", file=sys.stderr)
    else:
        print("2/3 如果方向不准，可以输入编号调整；回车接受建议。", file=sys.stderr)
        _print_topic_lane_options(pack.lanes)
        selected_lane = _prompt_to_stderr(f"选题 lane [默认：{suggested_lane.name}]: ")
        lane = selected_lane or suggested_lane.name

    defaults = resolve_topic_lane(lanes=pack.lanes, lane=lane, scene=scene)
    comment_prompt = args.comment_prompt
    if comment_prompt is None:
        comment_prompt = _prompt_to_stderr(
            f"3/3 评论区建议「{defaults.default_comment_prompt}」。要改就输入，回车接受: "
        )

    return GuidePostRequest(
        playbook_id=args.playbook_id,
        account_id=args.account_id,
        lane=lane,
        scene=scene,
        save_tool=args.save_tool,
        image_style=args.image_style,
        comment_prompt=comment_prompt,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run-fengkuang":
        if not args.scene and not args.fresh_topic_research:
            parser.error("run-fengkuang requires --scene or --fresh-topic-research")
        result = run_fengkuang_playbook(
            FengkuangRequest(
                scene=args.scene,
                platform=args.platform,
                account_id=args.account_id,
                publish_mode=args.publish_mode,
                publish_image_paths=args.publish_image_path,
                auto_generate_images=args.auto_generate_image,
                local_image_style=args.local_image_style,
                publish_visibility=args.publish_visibility,
                login_qrcode_output_path=str(args.login_qrcode_output),
                open_browser_if_needed=args.open_browser_if_needed,
                wait_for_publish_status=args.wait_for_publish_status,
                fresh_topic_research=args.fresh_topic_research,
            ),
            thread_id=args.thread_id,
            eval_enabled=args.eval,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "run-playbook":
        if not args.scene and not args.fresh_topic_research:
            parser.error("run-playbook requires --scene or --fresh-topic-research")
        result = run_playbook(
            PlaybookRequest(
                scene=args.scene,
                platform=args.platform,
                account_id=args.account_id,
                playbook_id=args.playbook_id,
                caller=args.caller,
                guidance_ack=args.guidance_ack,
                topic_direction_id=args.topic_direction_id,
                publish_mode=args.publish_mode,
                publish_image_paths=args.publish_image_path,
                auto_generate_images=args.auto_generate_image,
                local_image_style=args.local_image_style,
                publish_visibility=args.publish_visibility,
                login_qrcode_output_path=str(args.login_qrcode_output),
                open_browser_if_needed=args.open_browser_if_needed,
                wait_for_publish_status=args.wait_for_publish_status,
                fresh_topic_research=args.fresh_topic_research,
                format_pattern_path=(
                    str(args.format_pattern_path) if args.format_pattern_path else None
                ),
            ),
            thread_id=args.thread_id,
            eval_enabled=args.eval,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "guide-post":
        request = (
            GuidePostRequest(
                playbook_id=args.playbook_id,
                account_id=args.account_id,
                lane=args.lane,
                scene=args.scene,
                mechanism=args.mechanism,
                save_tool=args.save_tool,
                image_style=args.image_style,
                comment_prompt=args.comment_prompt,
            )
            if args.non_interactive
            else _collect_guide_post_request(args)
        )
        result = run_guide_post(request)
        output_format = args.format or ("json" if args.non_interactive else "markdown")
        if output_format == "markdown":
            print(format_guide_post_markdown(result))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "collect-xhs-patterns":
        result = run_collect_xhs_patterns(
            lane=args.lane,
            keywords=args.keywords,
            sample_limit_per_keyword=args.sample_limit_per_keyword,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            delay_seconds=args.delay_seconds,
            skip_login_check=args.skip_login_check,
            tool_timeout_seconds=args.tool_timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "xhs-domain-opportunity":
        result = run_xhs_domain_opportunity(
            keywords=args.keywords,
            lane=args.lane,
            sample_limit_per_keyword=args.sample_limit_per_keyword,
            output_dir=args.output_dir,
            delay_seconds=args.delay_seconds,
            skip_login_check=args.skip_login_check,
            tool_timeout_seconds=args.tool_timeout_seconds,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "analyze-xhs-patterns":
        result = run_analyze_xhs_patterns(
            sample_path=args.sample_path,
            lane=args.lane,
            output_dir=args.output_dir,
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

    if args.command == "accounts":
        registry = AccountRegistry()
        rows = []
        for a in registry.list_accounts():
            rows.append(a.to_dict())
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if args.command == "doctor":
        result = run_doctor(
            settings=build_login_settings(server_url=args.server_url),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "docs-sync":
        result = run_docs_sync(
            changed_paths=args.changed_paths,
            base_ref=args.base_ref,
            head_ref=args.head_ref,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") != "ok":
            return 1
        return 0

    if args.command == "harness-check":
        result = run_harness_check(
            base_ref=args.base_ref,
            head_ref=args.head_ref,
            changed_paths=args.changed_paths,
            strict=args.strict,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("status") != "ok":
            return 1
        return 0

    if args.command == "install-git-hooks":
        result = install_git_hooks(
            base_ref=args.base_ref,
            force=args.force,
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

    if args.command == "harness-evals":
        result = run_harness_evals(
            account_id=args.account_id,
            platform=args.platform,
            playbook_id=args.playbook_id,
            plan_path=args.plan_path,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "harness-report":
        result = run_harness_report(
            settings=build_login_settings(server_url=args.server_url),
            account_id=args.account_id,
            platform=args.platform,
            playbook_id=args.playbook_id,
            plan_path=args.plan_path,
            runs_retention_days=args.runs_retention_days,
            plan_runs_retention_days=args.plan_runs_retention_days,
            max_stale_docs=args.max_stale_docs,
            max_gc_candidates=args.max_gc_candidates,
            min_run_completion_rate=args.min_run_completion_rate,
            min_plan_completion_rate=args.min_plan_completion_rate,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.fail_on_warning and result.get("status") in {"warning", "error"}:
            return 1
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

    if args.command == "eval-artifact":
        result = run_eval_artifact(artifact_path=args.artifact)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "diagnose-publish":
        result = run_diagnose_publish(
            artifact_path=args.artifact,
            run_id=args.run_id,
            settings=build_login_settings(server_url=args.server_url),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2
