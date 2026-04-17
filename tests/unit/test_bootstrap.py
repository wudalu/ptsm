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
