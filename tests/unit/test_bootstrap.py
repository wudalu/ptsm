from __future__ import annotations

import json
import logging
from pathlib import Path

import ptsm.bootstrap as bootstrap
from ptsm.bootstrap import build_parser
from ptsm.interfaces.cli.main import main, run_plan_cli


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_build_parser_supports_fengkuang_dry_run() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-fengkuang",
            "--scene",
            "周一早高峰地铁通勤",
            "--login-qrcode-output",
            "/tmp/xhs-login-qrcode.png",
        ]
    )

    assert args.command == "run-fengkuang"
    assert args.scene == "周一早高峰地铁通勤"
    assert args.thread_id is None
    assert args.login_qrcode_output == Path("/tmp/xhs-login-qrcode.png")


def test_build_parser_supports_post_publish_flags() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-fengkuang",
            "--scene",
            "周一早高峰地铁通勤",
            "--open-browser-if-needed",
            "--wait-for-publish-status",
        ]
    )

    assert args.command == "run-fengkuang"
    assert args.open_browser_if_needed is True
    assert args.wait_for_publish_status is True


def test_build_parser_supports_run_playbook() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-playbook",
            "--scene",
            "夜里读到定风波",
            "--account-id",
            "acct-sushi-local",
            "--playbook-id",
            "sushi_poetry_daily_post",
            "--thread-id",
            "thread-sushi-001",
            "--publish-mode",
            "dry-run",
            "--publish-image-path",
            "outputs/generated_images/cover-1.png",
            "--publish-image-path",
            "outputs/generated_images/cover-2.png",
            "--auto-generate-image",
            "--publish-visibility",
            "仅自己可见",
            "--open-browser-if-needed",
            "--wait-for-publish-status",
            "--login-qrcode-output",
            "/tmp/xhs-login-qrcode.png",
        ]
    )

    assert args.command == "run-playbook"
    assert args.scene == "夜里读到定风波"
    assert args.account_id == "acct-sushi-local"
    assert args.playbook_id == "sushi_poetry_daily_post"
    assert args.thread_id == "thread-sushi-001"
    assert args.publish_mode == "dry-run"
    assert args.publish_image_path == [
        "outputs/generated_images/cover-1.png",
        "outputs/generated_images/cover-2.png",
    ]
    assert args.auto_generate_image is True
    assert args.publish_visibility == "仅自己可见"
    assert args.open_browser_if_needed is True
    assert args.wait_for_publish_status is True
    assert args.login_qrcode_output == Path("/tmp/xhs-login-qrcode.png")


def test_build_parser_supports_run_plan() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-plan",
            "--plan",
            "docs/plans/demo.md",
            "--verify-command",
            "pytest -q",
            "--max-attempts",
            "4",
            "--state-path",
            ".ptsm/plan_runs/demo.json",
            "--resume",
            "--dry-run",
        ]
    )

    assert args.command == "run-plan"
    assert args.plan == Path("docs/plans/demo.md")
    assert args.verify_commands == ["pytest -q"]
    assert args.max_attempts == 4
    assert args.state_path == Path(".ptsm/plan_runs/demo.json")
    assert args.resume is True
    assert args.dry_run is True


def test_build_parser_supports_xhs_login_qrcode() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "xhs-login-qrcode",
            "--output",
            "/tmp/demo-qrcode.png",
        ]
    )

    assert args.command == "xhs-login-qrcode"
    assert args.output == Path("/tmp/demo-qrcode.png")


def test_build_parser_supports_xhs_login_status() -> None:
    parser = build_parser()

    args = parser.parse_args(["xhs-login-status"])

    assert args.command == "xhs-login-status"


def test_build_parser_supports_doctor() -> None:
    parser = build_parser()

    args = parser.parse_args(["doctor"])

    assert args.command == "doctor"


def test_build_parser_supports_docs_sync() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "docs-sync",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--changed-path",
            "src/ptsm/interfaces/cli/main.py",
            "--changed-path",
            "docs/operations.md",
        ]
    )

    assert args.command == "docs-sync"
    assert args.base_ref == "origin/main"
    assert args.head_ref == "HEAD"
    assert args.changed_paths == [
        "src/ptsm/interfaces/cli/main.py",
        "docs/operations.md",
    ]


def test_build_parser_supports_harness_check() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "harness-check",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--strict",
            "--changed-path",
            "src/ptsm/interfaces/cli/main.py",
        ]
    )

    assert args.command == "harness-check"
    assert args.base_ref == "origin/main"
    assert args.head_ref == "HEAD"
    assert args.strict is True
    assert args.changed_paths == ["src/ptsm/interfaces/cli/main.py"]


def test_build_parser_supports_install_git_hooks() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "install-git-hooks",
            "--base-ref",
            "origin/main",
            "--force",
        ]
    )

    assert args.command == "install-git-hooks"
    assert args.base_ref == "origin/main"
    assert args.force is True


def test_build_parser_supports_logs() -> None:
    parser = build_parser()

    args = parser.parse_args(["logs", "--run-id", "run-123"])

    assert args.command == "logs"
    assert args.run_id == "run-123"


def test_build_parser_supports_runs() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "runs",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--status",
            "completed",
            "--limit",
            "5",
        ]
    )

    assert args.command == "runs"
    assert args.account_id == "acct-fk-local"
    assert args.platform == "xiaohongshu"
    assert args.status == "completed"
    assert args.limit == 5


def test_build_parser_supports_run_events() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "run-events",
            "--account-id",
            "acct-fk-local",
            "--run-status",
            "completed",
            "--event",
            "publish_finished",
            "--step",
            "publish",
            "--event-status",
            "completed",
            "--group-by",
            "status",
            "--limit",
            "5",
        ]
    )

    assert args.command == "run-events"
    assert args.account_id == "acct-fk-local"
    assert args.run_status == "completed"
    assert args.event == "publish_finished"
    assert args.step == "publish"
    assert args.event_status == "completed"
    assert args.group_by == "status"
    assert args.limit == 5


def test_build_parser_supports_plan_runs() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "plan-runs",
            "--status",
            "failed",
            "--failure-reason",
            "pytest_failed",
            "--plan-path",
            "demo",
            "--limit",
            "5",
        ]
    )

    assert args.command == "plan-runs"
    assert args.status == "failed"
    assert args.failure_reason == "pytest_failed"
    assert args.plan_path == "demo"
    assert args.limit == 5


def test_build_parser_supports_gc() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "gc",
            "--apply",
            "--runs-retention-days",
            "14",
            "--plan-runs-retention-days",
            "7",
        ]
    )

    assert args.command == "gc"
    assert args.apply is True
    assert args.runs_retention_days == 14
    assert args.plan_runs_retention_days == 7


def test_build_parser_supports_harness_evals() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "harness-evals",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--playbook-id",
            "fengkuang_daily_post",
            "--plan-path",
            "demo",
        ]
    )

    assert args.command == "harness-evals"
    assert args.account_id == "acct-fk-local"
    assert args.platform == "xiaohongshu"
    assert args.playbook_id == "fengkuang_daily_post"
    assert args.plan_path == "demo"


def test_build_parser_supports_harness_report() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "harness-report",
            "--server-url",
            "http://localhost:19000/mcp",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--playbook-id",
            "fengkuang_daily_post",
            "--plan-path",
            "docs/plans/demo.md",
            "--runs-retention-days",
            "14",
            "--plan-runs-retention-days",
            "7",
            "--max-stale-docs",
            "0",
            "--max-gc-candidates",
            "1",
            "--min-run-completion-rate",
            "0.8",
            "--min-plan-completion-rate",
            "0.9",
            "--fail-on-warning",
        ]
    )

    assert args.command == "harness-report"
    assert args.server_url == "http://localhost:19000/mcp"
    assert args.account_id == "acct-fk-local"
    assert args.platform == "xiaohongshu"
    assert args.playbook_id == "fengkuang_daily_post"
    assert args.plan_path == "docs/plans/demo.md"
    assert args.runs_retention_days == 14
    assert args.plan_runs_retention_days == 7
    assert args.max_stale_docs == 0
    assert args.max_gc_candidates == 1
    assert args.min_run_completion_rate == 0.8
    assert args.min_plan_completion_rate == 0.9
    assert args.fail_on_warning is True


def test_build_parser_supports_xhs_open_browser() -> None:
    parser = build_parser()

    args = parser.parse_args(["xhs-open-browser", "--target", "creator"])

    assert args.command == "xhs-open-browser"
    assert args.target == "creator"


def test_build_parser_supports_xhs_check_publish() -> None:
    parser = build_parser()

    args = parser.parse_args(["xhs-check-publish", "--artifact", "outputs/artifacts/demo.json"])

    assert args.command == "xhs-check-publish"
    assert args.artifact == Path("outputs/artifacts/demo.json")


def test_build_parser_supports_diagnose_publish() -> None:
    parser = build_parser()

    args = parser.parse_args(
        [
            "diagnose-publish",
            "--run-id",
            "run-123",
            "--artifact",
            "outputs/artifacts/demo.json",
            "--server-url",
            "http://localhost:19000/mcp",
        ]
    )

    assert args.command == "diagnose-publish"
    assert args.run_id == "run-123"
    assert args.artifact == Path("outputs/artifacts/demo.json")
    assert args.server_url == "http://localhost:19000/mcp"


def test_scaffold_files_pin_python_runtime() -> None:
    assert (PROJECT_ROOT / ".env.example").is_file()
    assert (PROJECT_ROOT / "README.md").is_file()
    assert (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"


def test_bootstrap_main_configures_logging_before_running_cli(monkeypatch) -> None:
    configured: list[tuple[str, object]] = []
    settings = object()

    monkeypatch.setattr(bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(
        bootstrap,
        "configure_logging",
        lambda configured_settings: configured.append(("logging", configured_settings)),
    )
    monkeypatch.setattr(
        bootstrap,
        "run_cli",
        lambda argv=None: configured.append(("cli", argv)) or 7,
    )

    exit_code = bootstrap.main(["run-plan", "--plan", "docs/plans/demo.md"])

    assert exit_code == 7
    assert configured == [
        ("logging", settings),
        ("cli", ["run-plan", "--plan", "docs/plans/demo.md"]),
    ]


def test_configure_logging_emits_structured_json(capsys) -> None:
    from ptsm.config.logging import configure_logging, get_logger

    configure_logging(log_level="DEBUG")
    get_logger("ptsm.test").info("bootstrap ready", component="test")

    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["event"] == "bootstrap ready"
    assert payload["component"] == "test"
    assert payload["logger"] == "ptsm.test"


def test_configure_logging_suppresses_httpx_info_noise(capsys) -> None:
    from ptsm.config.logging import configure_logging

    configure_logging(log_level="INFO")
    logging.getLogger("httpx").info("noise that should stay hidden")

    assert capsys.readouterr().out.strip() == ""


def test_main_dispatches_run_plan(monkeypatch, tmp_path: Path, capsys) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")
    state_path = tmp_path / "state.json"
    captured: dict[str, object] = {}

    def fake_run_plan(**kwargs):
        captured.update(kwargs)
        return {"status": "dry-run", "tasks": 1}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_plan_cli", fake_run_plan)

    exit_code = main(
        [
            "run-plan",
            "--plan",
            str(plan_path),
            "--verify-command",
            "pytest -q",
            "--state-path",
            str(state_path),
            "--resume",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert captured["plan_path"] == plan_path
    assert captured["verify_commands"] == ["pytest -q"]
    assert captured["state_path"] == state_path
    assert captured["resume"] is True
    assert captured["dry_run"] is True
    assert '"status": "dry-run"' in capsys.readouterr().out


def test_main_dispatches_runs(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_runs(**kwargs):
        captured.update(kwargs)
        return {"count": 1, "runs": [{"run_id": "run-123"}]}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_runs", fake_run_runs)

    exit_code = main(
        [
            "runs",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--status",
            "completed",
            "--limit",
            "5",
        ]
    )

    assert exit_code == 0
    assert captured["account_id"] == "acct-fk-local"
    assert captured["platform"] == "xiaohongshu"
    assert captured["status"] == "completed"
    assert captured["limit"] == 5
    assert '"run_id": "run-123"' in capsys.readouterr().out


def test_main_dispatches_run_events(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_run_events(**kwargs):
        captured.update(kwargs)
        return {
            "count": 1,
            "events": [{"run_id": "run-123", "event": "publish_finished"}],
            "group_by": "status",
            "totals": {"completed": 1},
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_run_events",
        fake_run_run_events,
    )

    exit_code = main(
        [
            "run-events",
            "--account-id",
            "acct-fk-local",
            "--run-status",
            "completed",
            "--event",
            "publish_finished",
            "--step",
            "publish",
            "--event-status",
            "completed",
            "--group-by",
            "status",
            "--limit",
            "5",
        ]
    )

    assert exit_code == 0
    assert captured["account_id"] == "acct-fk-local"
    assert captured["run_status"] == "completed"
    assert captured["event"] == "publish_finished"
    assert captured["step"] == "publish"
    assert captured["event_status"] == "completed"
    assert captured["group_by"] == "status"
    assert captured["limit"] == 5
    assert '"publish_finished"' in capsys.readouterr().out


def test_main_dispatches_plan_runs(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_plan_runs(**kwargs):
        captured.update(kwargs)
        return {"count": 1, "runs": [{"artifact_path": ".ptsm/plan_runs/demo.evidence.json"}]}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_plan_runs",
        fake_run_plan_runs,
    )

    exit_code = main(
        [
            "plan-runs",
            "--status",
            "failed",
            "--failure-reason",
            "pytest_failed",
            "--plan-path",
            "demo",
            "--limit",
            "5",
        ]
    )

    assert exit_code == 0
    assert captured["status"] == "failed"
    assert captured["failure_reason"] == "pytest_failed"
    assert captured["plan_path"] == "demo"
    assert captured["limit"] == 5
    assert ".evidence.json" in capsys.readouterr().out


def test_main_dispatches_gc(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_harness_gc(**kwargs):
        captured.update(kwargs)
        return {"status": "applied", "removed_count": 1, "candidates": []}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_harness_gc",
        fake_run_harness_gc,
    )

    exit_code = main(
        [
            "gc",
            "--apply",
            "--runs-retention-days",
            "14",
            "--plan-runs-retention-days",
            "7",
        ]
    )

    assert exit_code == 0
    assert captured["apply"] is True
    assert captured["runs_retention_days"] == 14
    assert captured["plan_runs_retention_days"] == 7
    assert '"removed_count": 1' in capsys.readouterr().out


def test_main_dispatches_harness_evals(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_harness_evals(**kwargs):
        captured.update(kwargs)
        return {"runs": {"total": 2}, "plan_runs": {"total": 1}, "recent_failures": []}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_harness_evals",
        fake_run_harness_evals,
    )

    exit_code = main(
        [
            "harness-evals",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--playbook-id",
            "fengkuang_daily_post",
            "--plan-path",
            "demo",
        ]
    )

    assert exit_code == 0
    assert captured["account_id"] == "acct-fk-local"
    assert captured["platform"] == "xiaohongshu"
    assert captured["playbook_id"] == "fengkuang_daily_post"
    assert captured["plan_path"] == "demo"
    assert '"total": 2' in capsys.readouterr().out


def test_main_dispatches_harness_report_and_can_fail_on_warning(
    monkeypatch, capsys
) -> None:
    captured: dict[str, object] = {}

    def fake_run_harness_report(**kwargs):
        captured.update(kwargs)
        return {
            "status": "warning",
            "thresholds": {"configured": {"max_stale_docs": 0}, "violations": []},
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_harness_report",
        fake_run_harness_report,
    )

    exit_code = main(
        [
            "harness-report",
            "--server-url",
            "http://localhost:19000/mcp",
            "--account-id",
            "acct-fk-local",
            "--platform",
            "xiaohongshu",
            "--playbook-id",
            "fengkuang_daily_post",
            "--plan-path",
            "docs/plans/demo.md",
            "--runs-retention-days",
            "14",
            "--plan-runs-retention-days",
            "7",
            "--max-stale-docs",
            "0",
            "--max-gc-candidates",
            "1",
            "--min-run-completion-rate",
            "0.8",
            "--min-plan-completion-rate",
            "0.9",
            "--fail-on-warning",
        ]
    )

    assert exit_code == 1
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert captured["account_id"] == "acct-fk-local"
    assert captured["platform"] == "xiaohongshu"
    assert captured["playbook_id"] == "fengkuang_daily_post"
    assert captured["plan_path"] == "docs/plans/demo.md"
    assert captured["runs_retention_days"] == 14
    assert captured["plan_runs_retention_days"] == 7
    assert captured["max_stale_docs"] == 0
    assert captured["max_gc_candidates"] == 1
    assert captured["min_run_completion_rate"] == 0.8
    assert captured["min_plan_completion_rate"] == 0.9
    assert '"status": "warning"' in capsys.readouterr().out


def test_main_dispatches_xhs_login_qrcode(monkeypatch, tmp_path: Path, capsys) -> None:
    output_path = tmp_path / "qrcode.png"
    captured: dict[str, object] = {}

    def fake_run_xhs_login_qrcode(**kwargs):
        captured.update(kwargs)
        return {"status": "login_required", "qrcode": {"output_path": str(output_path)}}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_xhs_login_qrcode",
        fake_run_xhs_login_qrcode,
    )

    exit_code = main(
        [
            "xhs-login-qrcode",
            "--server-url",
            "http://localhost:19000/mcp",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert captured["output_path"] == output_path
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert '"output_path"' in capsys.readouterr().out


def test_main_dispatches_xhs_login_status(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_xhs_login_status(**kwargs):
        captured.update(kwargs)
        return {"status": "ready", "login_status": "✅ 已登录"}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_xhs_login_status",
        fake_run_xhs_login_status,
    )

    exit_code = main(["xhs-login-status", "--server-url", "http://localhost:19000/mcp"])

    assert exit_code == 0
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert '"status": "ready"' in capsys.readouterr().out


def test_main_dispatches_doctor(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_doctor(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "checks": []}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_doctor",
        fake_run_doctor,
    )

    exit_code = main(["doctor", "--server-url", "http://localhost:19000/mcp"])

    assert exit_code == 0
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert '"status": "ok"' in capsys.readouterr().out


def test_main_dispatches_run_playbook(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_playbook(request, *, thread_id: str | None = None):
        captured["request"] = request
        captured["thread_id"] = thread_id
        return {
            "status": "completed",
            "playbook_id": "sushi_poetry_daily_post",
            "publish_result": {"status": "dry_run"},
            "post_publish_checks": {"requested": True},
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_playbook",
        fake_run_playbook,
        raising=False,
    )

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "夜里读到定风波",
            "--account-id",
            "acct-sushi-local",
            "--playbook-id",
            "sushi_poetry_daily_post",
            "--thread-id",
            "thread-sushi-001",
            "--publish-mode",
            "dry-run",
        ]
    )

    assert exit_code == 0
    assert captured["thread_id"] == "thread-sushi-001"
    assert captured["request"].scene == "夜里读到定风波"
    assert captured["request"].account_id == "acct-sushi-local"
    assert captured["request"].playbook_id == "sushi_poetry_daily_post"
    assert '"playbook_id": "sushi_poetry_daily_post"' in capsys.readouterr().out


def test_main_dispatches_docs_sync_and_fails_on_error(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_docs_sync(**kwargs):
        captured.update(kwargs)
        return {
            "status": "error",
            "missing_updates": [
                {
                    "changed_path": "src/ptsm/interfaces/cli/main.py",
                    "candidate_docs": [{"doc": "docs/operations.md"}],
                }
            ],
            "unmapped_changes": [],
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_docs_sync",
        fake_run_docs_sync,
    )

    exit_code = main(
        [
            "docs-sync",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--changed-path",
            "src/ptsm/interfaces/cli/main.py",
        ]
    )

    assert exit_code == 1
    assert captured["base_ref"] == "origin/main"
    assert captured["head_ref"] == "HEAD"
    assert captured["changed_paths"] == ["src/ptsm/interfaces/cli/main.py"]
    assert '"status": "error"' in capsys.readouterr().out


def test_main_dispatches_harness_check_and_fails_on_error(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_run_harness_check(**kwargs):
        captured.update(kwargs)
        return {"status": "error", "docs_sync": {"status": "error"}}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_harness_check",
        fake_run_harness_check,
    )

    exit_code = main(
        [
            "harness-check",
            "--base-ref",
            "origin/main",
            "--head-ref",
            "HEAD",
            "--strict",
            "--changed-path",
            "src/ptsm/interfaces/cli/main.py",
        ]
    )

    assert exit_code == 1
    assert captured["base_ref"] == "origin/main"
    assert captured["head_ref"] == "HEAD"
    assert captured["strict"] is True
    assert captured["changed_paths"] == ["src/ptsm/interfaces/cli/main.py"]
    assert '"status": "error"' in capsys.readouterr().out


def test_main_dispatches_install_git_hooks(monkeypatch, capsys) -> None:
    captured: dict[str, object] = {}

    def fake_install_git_hooks(**kwargs):
        captured.update(kwargs)
        return {"status": "installed", "hook_path": ".git/hooks/pre-push"}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.install_git_hooks",
        fake_install_git_hooks,
    )

    exit_code = main(["install-git-hooks", "--base-ref", "origin/main", "--force"])

    assert exit_code == 0
    assert captured["base_ref"] == "origin/main"
    assert captured["force"] is True
    assert '"status": "installed"' in capsys.readouterr().out


def test_main_dispatches_logs(monkeypatch, capsys, tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    captured: dict[str, object] = {}

    def fake_run_logs(**kwargs):
        captured.update(kwargs)
        return {"run_id": "run-123", "events": [], "summary": {"status": "completed"}}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_logs",
        fake_run_logs,
    )

    exit_code = main(["logs", "--artifact", str(artifact_path)])

    assert exit_code == 0
    assert captured["artifact_path"] == artifact_path
    assert '"run_id": "run-123"' in capsys.readouterr().out


def test_main_dispatches_xhs_open_browser(monkeypatch, capsys, tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    captured: dict[str, object] = {}

    def fake_open_xhs_browser(**kwargs):
        captured.update(kwargs)
        return {"status": "opened", "destination": "https://creator.xiaohongshu.com"}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.open_xhs_browser",
        fake_open_xhs_browser,
    )

    exit_code = main(["xhs-open-browser", "--target", "artifact", "--artifact", str(artifact_path)])

    assert exit_code == 0
    assert captured["artifact_path"] == artifact_path
    assert '"status": "opened"' in capsys.readouterr().out


def test_main_dispatches_xhs_check_publish(monkeypatch, capsys, tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    captured: dict[str, object] = {}

    def fake_check_xhs_publish_status(**kwargs):
        captured.update(kwargs)
        return {"status": "published_visible", "source": "mcp"}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.check_xhs_publish_status",
        fake_check_xhs_publish_status,
    )

    exit_code = main(
        [
            "xhs-check-publish",
            "--server-url",
            "http://localhost:19000/mcp",
            "--artifact",
            str(artifact_path),
        ]
    )

    assert exit_code == 0
    assert captured["artifact_path"] == artifact_path
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert '"status": "published_visible"' in capsys.readouterr().out


def test_main_dispatches_diagnose_publish(monkeypatch, capsys, tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"
    captured: dict[str, object] = {}

    def fake_run_diagnose_publish(**kwargs):
        captured.update(kwargs)
        return {
            "status": "warning",
            "likely_cause": "publish_identifiers_missing",
            "next_actions": ["Inspect artifact metadata."],
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_diagnose_publish",
        fake_run_diagnose_publish,
    )

    exit_code = main(
        [
            "diagnose-publish",
            "--run-id",
            "run-123",
            "--artifact",
            str(artifact_path),
            "--server-url",
            "http://localhost:19000/mcp",
        ]
    )

    assert exit_code == 0
    assert captured["run_id"] == "run-123"
    assert captured["artifact_path"] == artifact_path
    assert captured["settings"].xhs_mcp_server_url == "http://localhost:19000/mcp"
    assert '"likely_cause": "publish_identifiers_missing"' in capsys.readouterr().out


def test_run_plan_cli_generates_default_state_path(monkeypatch, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text("# Demo\n\n### Task 1: Parser\n\n- create parser\n", encoding="utf-8")
    expected_state_path = tmp_path / "generated-state.json"
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
        "ptsm.interfaces.cli.main.build_default_state_path",
        lambda plan_path_arg: expected_state_path,
    )
    monkeypatch.setattr("ptsm.interfaces.cli.main.PlanRunner", DummyRunner)

    result = run_plan_cli(
        plan_path=plan_path,
        verify_commands=["pytest -q"],
        max_attempts=3,
        dry_run=True,
    )

    assert captured["state_path"] == expected_state_path
    assert result["state_path"] == str(expected_state_path)
