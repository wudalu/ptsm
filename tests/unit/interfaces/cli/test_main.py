from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.interfaces.cli.main import main
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


def test_run_fengkuang_cli_passes_auto_generate_image_flag(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_fengkuang_playbook(
        request: FengkuangRequest,
        *,
        thread_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["request"] = request
        captured["thread_id"] = thread_id
        return {
            "status": "completed",
            "publish_result": {"status": "dry_run"},
            "post_publish_checks": {"requested": False},
        }

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_fengkuang_playbook",
        fake_run_fengkuang_playbook,
    )

    exit_code = main(
        [
            "run-fengkuang",
            "--scene",
            "周六社畜躺平",
            "--account-id",
            "acct-fk-local",
            "--auto-generate-image",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    request = captured["request"]
    assert isinstance(request, FengkuangRequest)
    assert request.auto_generate_images is True


def test_run_playbook_cli_passes_generic_request_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_playbook(
        request: PlaybookRequest,
        *,
        thread_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["request"] = request
        captured["thread_id"] = thread_id
        return {
            "status": "completed",
            "playbook_id": request.playbook_id,
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
            "--publish-image-path",
            "outputs/generated_images/cover-1.png",
            "--auto-generate-image",
            "--publish-visibility",
            "仅自己可见",
            "--open-browser-if-needed",
            "--wait-for-publish-status",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["playbook_id"] == "sushi_poetry_daily_post"
    request = captured["request"]
    assert isinstance(request, PlaybookRequest)
    assert request.scene == "夜里读到定风波"
    assert request.account_id == "acct-sushi-local"
    assert request.playbook_id == "sushi_poetry_daily_post"
    assert request.publish_mode == "dry-run"
    assert request.publish_image_paths == ["outputs/generated_images/cover-1.png"]
    assert request.auto_generate_images is True
    assert request.publish_visibility == "仅自己可见"
    assert request.open_browser_if_needed is True
    assert request.wait_for_publish_status is True
    assert captured["thread_id"] == "thread-sushi-001"


def test_run_playbook_cli_passes_openclaw_guidance_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_playbook(
        request: PlaybookRequest,
        *,
        thread_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["request"] = request
        return {
            "status": "completed",
            "playbook_id": request.playbook_id,
            "publish_result": {"status": "dry_run"},
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
            "同事临时加需求，想练一版边界句",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--caller",
            "openclaw",
            "--guidance-ack",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    request = captured["request"]
    assert isinstance(request, PlaybookRequest)
    assert request.caller == "openclaw"
    assert request.guidance_ack is True


def test_run_playbook_cli_passes_format_pattern_path(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_playbook(
        request: PlaybookRequest,
        *,
        thread_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["request"] = request
        return {"status": "completed", "format_patterns_used": {"status": "available"}}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_playbook", fake_run_playbook)

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "把书桌改成十分钟手作角",
            "--account-id",
            "acct-enrichment-local",
            "--playbook-id",
            "human_enrichment_daily_post",
            "--format-pattern-path",
            "outputs/artifacts/xhs-pattern-library/current.json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["format_patterns_used"]["status"] == "available"
    assert captured["request"].format_pattern_path == (
        "outputs/artifacts/xhs-pattern-library/current.json"
    )


def test_run_playbook_cli_passes_local_image_style(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_run_playbook(
        request: PlaybookRequest,
        *,
        thread_id: str | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        captured["request"] = request
        return {"status": "completed"}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_playbook", fake_run_playbook)

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "领导连发三个在吗",
            "--account-id",
            "acct-fk-local",
            "--playbook-id",
            "fengkuang_daily_post",
            "--auto-generate-image",
            "--local-image-style",
            "iphone_notes",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert captured["request"].local_image_style == "iphone_notes"


def test_collect_xhs_patterns_cli_dispatches_to_use_case(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_collect(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "dry_run", "samples": []}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_collect_xhs_patterns", fake_collect)

    exit_code = main(
        [
            "collect-xhs-patterns",
            "--lane",
            "human_enrichment",
            "--keywords",
            "人类丰容,家的丰容计划",
            "--sample-limit-per-keyword",
            "8",
            "--output-dir",
            "outputs/artifacts/xhs-pattern-library",
            "--dry-run",
            "--delay-seconds",
            "0",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert captured["lane"] == "human_enrichment"
    assert captured["keywords"] == "人类丰容,家的丰容计划"
    assert captured["sample_limit_per_keyword"] == 8
    assert captured["dry_run"] is True


def test_analyze_xhs_patterns_cli_dispatches_to_use_case(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_analyze(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "completed", "pattern_count": 2}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_analyze_xhs_patterns", fake_analyze)

    exit_code = main(
        [
            "analyze-xhs-patterns",
            "--sample-path",
            "outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json",
            "--lane",
            "human_enrichment",
            "--output-dir",
            "outputs/artifacts/xhs-pattern-library",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["pattern_count"] == 2
    assert captured["lane"] == "human_enrichment"
    assert captured["sample_path"] == Path(
        "outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json"
    )


def test_guide_post_cli_outputs_non_interactive_psychology_brief(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--scene",
            "睡前刷短视频停不下来，越刷越焦虑",
            "--non-interactive",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "modern_psychology_post"
    assert payload["brief"]["lane"] == "数字生活 / 信息过载"
    assert payload["brief"]["mechanism"] == "信息过载"
    assert "run-playbook --scene" in payload["run_playbook_command_text"]


def test_guide_post_cli_outputs_non_interactive_human_enrichment_brief(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            "human_enrichment_daily_post",
            "--account-id",
            "acct-enrichment-local",
            "--scene",
            "想把书桌角落改成十分钟适我主义手作位",
            "--non-interactive",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["playbook_id"] == "human_enrichment_daily_post"
    assert payload["account_id"] == "acct-enrichment-local"
    assert payload["topic_guidance"]["directions"]


@pytest.mark.parametrize(
    ("playbook_id", "account_id", "scene", "expected_prefix"),
    (
        (
            "wuxia_character_post",
            "acct-wuxia-local",
            "想用令狐冲写一种当代职场里的自由人格",
            "wuxia_",
        ),
        (
            "ai_tech_daily_post",
            "acct-ai-tech-local",
            "Google 发布 Gemini 3，想写普通人能懂的 AI 工具变化",
            "ai_",
        ),
        (
            "daily_english_post",
            "acct-daily-english-local",
            "学一个表示坚持的高级词汇，想配真实职场例句",
            "english_",
        ),
        (
            "world_cup_daily_post",
            "acct-world-cup-local",
            "阿根廷和法国决赛前，想写普通球迷看球清单",
            "worldcup_",
        ),
        (
            "reddit_curation_daily_post",
            "acct-reddit-curation-local",
            "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度",
            "reddit_",
        ),
    ),
)
def test_guide_post_cli_outputs_non_interactive_new_domain_briefs(
    playbook_id: str,
    account_id: str,
    scene: str,
    expected_prefix: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            playbook_id,
            "--account-id",
            account_id,
            "--scene",
            scene,
            "--non-interactive",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["playbook_id"] == playbook_id
    assert payload["account_id"] == account_id
    assert payload["topic_guidance"]["matched_direction_id"].startswith(expected_prefix)
    assert len(payload["topic_guidance"]["directions"]) == 4


def test_guide_post_cli_outputs_generic_markdown_for_non_psychology(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            "human_enrichment_daily_post",
            "--account-id",
            "acct-enrichment-local",
            "--scene",
            "想把书桌角落改成十分钟适我主义手作位",
            "--non-interactive",
            "--format",
            "markdown",
        ]
    )

    output = capsys.readouterr().out

    assert exit_code == 0
    assert "# Topic Guidance Brief" in output
    assert "# Psychology Guidance Brief" not in output
    assert "playbook_id: human_enrichment_daily_post" in output
    assert "trend:" in output
    assert "hook:" in output


def test_guide_post_cli_prompts_for_missing_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(
        [
            "看到别人周末都在聚会，自己突然觉得很失败",
            "",
            "",
            "",
            "",
            "你会把这句话送给哪一个瞬间？",
        ]
    )
    monkeypatch.setattr("builtins.input", lambda: next(answers))

    exit_code = main(["guide-post"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "我们先把这条现代心理学帖子聊成一个可执行 brief" in captured.err
    assert "回车接受建议" in captured.err
    assert "# Psychology Guidance Brief" in captured.out
    assert "lane: 孤独 / 比较焦虑" in captured.out
    assert "mechanism: 比较焦虑" in captured.out
    assert "comment_prompt: 你会把这句话送给哪一个瞬间？" in captured.out
