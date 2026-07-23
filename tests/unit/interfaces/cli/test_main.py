from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
)
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
            "读到李白长风破浪会有时",
            "--account-id",
            "acct-classic-poetry-local",
            "--playbook-id",
            "classic_poetry_quote_post",
            "--thread-id",
            "thread-classic-poetry-001",
            "--publish-mode",
            "dry-run",
            "--publish-image-path",
            "outputs/generated_images/cover-1.png",
            "--auto-generate-image",
            "--publish-visibility",
            "仅自己可见",
            "--open-browser-if-needed",
            "--wait-for-publish-status",
            "--topic-direction-id",
            "classic_tang_resilience_quote",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["playbook_id"] == "classic_poetry_quote_post"
    request = captured["request"]
    assert isinstance(request, PlaybookRequest)
    assert request.scene == "读到李白长风破浪会有时"
    assert request.account_id == "acct-classic-poetry-local"
    assert request.playbook_id == "classic_poetry_quote_post"
    assert request.publish_mode == "dry-run"
    assert request.publish_image_paths == ["outputs/generated_images/cover-1.png"]
    assert request.auto_generate_images is True
    assert request.publish_visibility == "仅自己可见"
    assert request.open_browser_if_needed is True
    assert request.wait_for_publish_status is True
    assert request.topic_direction_id == "classic_tang_resilience_quote"
    assert captured["thread_id"] == "thread-classic-poetry-001"


def test_run_playbook_cli_loads_ai_evidence_file_without_scene(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}
    evidence_path = tmp_path / "ai-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "mode": "news_brief",
                "news_items": [
                    {
                        "label": "模型发布",
                        "event_fingerprint": "event-model-release-001",
                        "facts": ["产品发布了新的推理模型。"],
                        "source_refs": ["official-release-001"],
                    },
                    {
                        "label": "开发者工具",
                        "event_fingerprint": "event-developer-tools-002",
                        "facts": ["开发者工具新增了批量处理能力。"],
                        "source_refs": ["official-release-002"],
                    },
                    {
                        "label": "行业应用",
                        "event_fingerprint": "event-industry-use-003",
                        "facts": ["功能面向团队协作场景开放。"],
                        "source_refs": ["official-release-003"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def fake_run_playbook(
        request: PlaybookRequest,
        **_: object,
    ) -> dict[str, object]:
        captured["request"] = request
        return {"status": "completed", "playbook_id": request.playbook_id}

    monkeypatch.setattr("ptsm.interfaces.cli.main.run_playbook", fake_run_playbook)

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
            "--ai-content-mode",
            "news_brief",
            "--ai-evidence-file",
            str(evidence_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    request = captured["request"]
    assert isinstance(request, PlaybookRequest)
    assert request.scene == ""
    assert request.ai_content_mode == "news_brief"
    assert request.ai_evidence_bundle["mode"] == "news_brief"
    assert request.ai_evidence_file_path == str(evidence_path)


def test_run_playbook_cli_reports_malformed_ai_evidence_json_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_path = tmp_path / "bad-ai-evidence.json"
    evidence_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-playbook",
                "--scene",
                "AI 更新",
                "--account-id",
                "acct-ai-tech-local",
                "--playbook-id",
                "ai_tech_daily_post",
                "--ai-content-mode",
                "news_brief",
                "--ai-evidence-file",
                str(evidence_path),
            ]
        )

    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "ai evidence file" in captured.err


def test_run_playbook_cli_allows_ai_request_without_scene_to_reach_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ai_tech_evidence_required"


def test_run_playbook_cli_resolves_default_ai_playbook_before_scene_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-ai-tech-local",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["playbook_id"] == "ai_tech_daily_post"
    assert payload["status"] == "ai_tech_evidence_required"


def test_run_playbook_cli_keeps_scene_requirement_for_non_ai_evidence_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    evidence_path = tmp_path / "ai-evidence.json"
    evidence_path.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-playbook",
                "--account-id",
                "acct-classic-poetry-local",
                "--playbook-id",
                "classic_poetry_quote_post",
                "--ai-evidence-file",
                str(evidence_path),
            ]
        )

    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "requires --scene" in captured.err


def test_run_playbook_cli_reports_non_utf8_ai_evidence_cleanly(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    evidence_path = tmp_path / "bad-ai-evidence.json"
    evidence_path.write_bytes(b"\xff\xfe")

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "run-playbook",
                "--scene",
                "AI 更新",
                "--account-id",
                "acct-ai-tech-local",
                "--playbook-id",
                "ai_tech_daily_post",
                "--ai-evidence-file",
                str(evidence_path),
            ]
        )

    captured = capsys.readouterr()

    assert exc_info.value.code == 2
    assert "ai evidence file" in captured.err


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


def test_xhs_record_metrics_cli_passes_fields(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_record_xhs_post_metrics(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "recorded", "record": {"interaction_score": 244}}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.record_xhs_post_metrics",
        fake_record_xhs_post_metrics,
        raising=False,
    )

    exit_code = main(
        [
            "xhs-record-metrics",
            "--artifact",
            "outputs/artifacts/psychology.json",
            "--checkpoint",
            "24h",
            "--views",
            "1000",
            "--likes",
            "80",
            "--collects",
            "60",
            "--comments",
            "8",
            "--shares",
            "2",
            "--output-path",
            "outputs/artifacts/xhs-post-metrics/metrics.jsonl",
            "--decision",
            "keep",
            "--notes",
            "collects close to likes",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "recorded"
    assert captured["artifact_path"] == Path("outputs/artifacts/psychology.json")
    assert captured["checkpoint"] == "24h"
    assert captured["views"] == 1000
    assert captured["likes"] == 80
    assert captured["collects"] == 60
    assert captured["comments"] == 8
    assert captured["shares"] == 2
    assert captured["output_path"] == Path("outputs/artifacts/xhs-post-metrics/metrics.jsonl")
    assert captured["decision"] == "keep"
    assert captured["notes"] == "collects close to likes"


def test_xhs_metrics_report_cli_passes_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_summarize_xhs_post_metrics(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "ok", "groups": [{"group": "sleep_recovery_shutdown_card"}]}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.summarize_xhs_post_metrics",
        fake_summarize_xhs_post_metrics,
        raising=False,
    )

    exit_code = main(
        [
            "xhs-metrics-report",
            "--input-path",
            "outputs/artifacts/xhs-post-metrics/metrics.jsonl",
            "--playbook-id",
            "modern_psychology_post",
            "--account-id",
            "acct-psychology-local",
            "--checkpoint",
            "24h",
            "--group-by",
            "topic_direction_id",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ok"
    assert captured["input_path"] == Path("outputs/artifacts/xhs-post-metrics/metrics.jsonl")
    assert captured["playbook_id"] == "modern_psychology_post"
    assert captured["account_id"] == "acct-psychology-local"
    assert captured["checkpoint"] == "24h"
    assert captured["group_by"] == "topic_direction_id"


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
            "--skip-login-check",
            "--tool-timeout-seconds",
            "70",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "dry_run"
    assert captured["lane"] == "human_enrichment"
    assert captured["keywords"] == "人类丰容,家的丰容计划"
    assert captured["sample_limit_per_keyword"] == 8
    assert captured["dry_run"] is True
    assert captured["skip_login_check"] is True
    assert captured["tool_timeout_seconds"] == 70.0


def test_xhs_domain_opportunity_cli_dispatches_to_use_case(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_scan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "completed", "recommendations": []}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_xhs_domain_opportunity",
        fake_scan,
    )

    exit_code = main(
        [
            "xhs-domain-opportunity",
            "--keywords",
            "睡眠恢复,轻养生,人类丰容",
            "--sample-limit-per-keyword",
            "5",
            "--output-dir",
            "outputs/artifacts/xhs-domain-opportunity",
            "--delay-seconds",
            "0",
            "--skip-login-check",
            "--tool-timeout-seconds",
            "70",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert captured["keywords"] == "睡眠恢复,轻养生,人类丰容"
    assert captured["sample_limit_per_keyword"] == 5
    assert captured["delay_seconds"] == 0
    assert captured["skip_login_check"] is True
    assert captured["tool_timeout_seconds"] == 70.0


def test_hotspot_discovery_cli_dispatches_without_direction_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, object] = {}

    def fake_discovery(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "partial", "hotspots": []}

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.run_hotspot_discovery",
        fake_discovery,
    )

    exit_code = main(
        [
            "hotspot-discovery",
            "--output-dir",
            "outputs/artifacts/hotspot-discovery-test",
            "--max-hotspots",
            "5",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {"status": "partial", "hotspots": []}
    assert captured == {
        "output_dir": Path("outputs/artifacts/hotspot-discovery-test"),
        "max_hotspots": 5,
    }


def test_hotspot_discovery_cli_rejects_non_positive_display_limit() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["hotspot-discovery", "--max-hotspots", "0"])

    assert exc_info.value.code == 2


def test_xhs_domain_opportunity_cli_rejects_separator_only_keywords() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["xhs-domain-opportunity", "--keywords", "，"])

    assert exc_info.value.code == 2


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
    assert payload["topic_guidance"]["selection_policy"] == "dynamic_scene_diversity_rerank"
    assert payload["topic_guidance"]["open_direction_id"]
    assert payload["topic_guidance"]["open_direction_ids"]
    open_count = sum(
        1
        for direction in payload["topic_guidance"]["directions"]
        if direction["direction_type"] == "open_scene"
    )
    assert open_count >= 1
    assert payload["topic_guidance"]["direction_type_counts"]["open_scene"] == open_count
    checklist_items = {item["item"] for item in payload["quality_checklist"]}
    assert "角色认领评论" in checklist_items
    assert "例子型评论" not in checklist_items
    assert (
        payload["topic_guidance"]["open_direction_id"]
        == payload["topic_guidance"]["open_direction_ids"][0]
    )
    image_recommendation = payload["topic_guidance"]["image_recommendation"]
    assert image_recommendation["status"] == "available"
    assert (
        image_recommendation["decision_stage"]
        == "after_topic_direction_confirmation"
    )
    assert image_recommendation["recommended_backend"] in {
        "local_social_screenshot",
        "provider_image",
    }
    assert image_recommendation["command_hint"]
    for direction in payload["topic_guidance"]["directions"]:
        assert direction["format_recommendation"]["format_archetype"] in {
            "note_card",
            "carousel",
            "chat_screenshot",
            "provider_scene",
        }
        assert direction["format_recommendation"]["cover_role"]
        assert direction["format_recommendation"]["body_shape"]
    open_direction = next(
        direction
        for direction in payload["topic_guidance"]["directions"]
        if direction["direction_type"] == "open_scene"
    )
    assert open_direction["format_recommendation"]["avoid_format"]
    assert "run-playbook --scene" in payload["run_playbook_command_text"]


def test_guide_post_cli_outputs_catalog_psychology_learning_series(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            "modern_psychology_post",
            "--account-id",
            "acct-psychology-local",
            "--psychology-content-mode",
            "learning_series",
            "--psychology-series-id",
            "after_work_rumination",
            "--psychology-lesson-id",
            "notice_the_loop",
            "--non-interactive",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["brief"]["content_mode"] == "learning_series"
    assert payload["series"]["series_id"] == "after_work_rumination"
    assert len(payload["series"]["roadmap"]) == 6
    assert payload["topic_guidance"]["selection_policy"] == "catalog_learning_series"
    assert all(
        direction["direction_type"] == "learning_series_lesson"
        for direction in payload["topic_guidance"]["directions"]
    )
    assert "source_refs" not in json.dumps(payload, ensure_ascii=False)


def test_guide_post_cli_lists_learning_lessons_before_one_is_selected(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            "modern_psychology_post",
            "--account-id",
            "acct-psychology-local",
            "--psychology-content-mode",
            "learning_series",
            "--psychology-series-id",
            "after_work_rumination",
            "--non-interactive",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "selection_required"
    assert len(payload["series"]["roadmap"]) == 6
    assert "run_playbook_command" not in payload


@pytest.mark.parametrize("command", ("run-playbook", "guide-post"))
def test_cli_rejects_psychology_learning_flags_for_other_playbooks(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    arguments = [
        command,
        "--playbook-id",
        "daily_english_post",
        "--account-id",
        "acct-daily-english-local",
        "--psychology-content-mode",
        "learning_series",
        "--psychology-series-id",
        "after_work_rumination",
        "--psychology-lesson-id",
        "notice_the_loop",
    ]
    if command == "guide-post":
        arguments.append("--non-interactive")

    with pytest.raises(SystemExit) as exc_info:
        main(arguments)

    assert exc_info.value.code == 2
    assert "only support modern_psychology_post" in capsys.readouterr().err


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
    assert (
        payload["topic_guidance"]["image_recommendation"]["recommended_backend"]
        == "provider_image"
    )
    first_direction = payload["topic_guidance"]["directions"][0]
    assert first_direction["format_recommendation"]["cover_role"] == "evidence_or_scene"
    assert first_direction["format_recommendation"]["visual_evidence_need"] == "high"


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
    assert "open_scene" in output
    assert "trend:" in output
    assert "hook:" in output
    assert "## Image Recommendation" in output
    assert "provider_image" in output


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
    assert "评论区要让用户给例子" not in captured.err
    assert "角色认领或 A/B 入口" in captured.err
    assert "# Psychology Guidance Brief" in captured.out
    assert "lane: 孤独 / 比较焦虑" in captured.out
    assert "mechanism: 比较焦虑" in captured.out
    assert "comment_prompt: 你会把这句话送给哪一个瞬间？" in captured.out


def test_guide_post_cli_requires_and_forwards_ai_evidence_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "guide-post",
                "--playbook-id",
                "ai_tech_daily_post",
                "--account-id",
                "acct-ai-tech-local",
                "--scene",
                "今天想做一条 AI 科技热点快讯",
                "--non-interactive",
            ]
        )

    assert exc_info.value.code == 2
    assert "--ai-content-mode" in capsys.readouterr().err

    exit_code = main(
        [
            "guide-post",
            "--playbook-id",
            "ai_tech_daily_post",
            "--account-id",
            "acct-ai-tech-local",
            "--scene",
            "今天想做一条 AI 科技热点快讯",
            "--ai-content-mode",
            "news_brief",
            "--ai-evidence-file",
            "inputs/ai-evidence.json",
            "--non-interactive",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["brief"]["content_mode"] == "news_brief"
    assert payload["run_playbook_command"][-1] == "note_card" or "--local-image-style" in payload["run_playbook_command"]
    assert "--ai-evidence-file inputs/ai-evidence.json" in payload["run_playbook_command_text"]


def _patch_cli_psychology_series_store(
    monkeypatch: pytest.MonkeyPatch,
    root: Path,
) -> PsychologyLearningSeriesStore:
    class TempPsychologyLearningSeriesStore(PsychologyLearningSeriesStore):
        def __init__(self) -> None:
            super().__init__(catalog_root=root)

    monkeypatch.setattr(
        "ptsm.interfaces.cli.main.PsychologyLearningSeriesStore",
        TempPsychologyLearningSeriesStore,
    )
    return TempPsychologyLearningSeriesStore()


def test_plan_psychology_series_cli_persists_a_nonrunnable_topic_only_proposal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _patch_cli_psychology_series_store(monkeypatch, tmp_path / "series-store")

    exit_code = main(
        [
            "plan-psychology-series",
            "--topic",
            "下班后的脑内回放",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    persisted = store.read_proposal(proposal_id=payload["proposal_id"])

    assert exit_code == 0
    assert payload["status"] == "proposal_ready_for_confirmation"
    assert payload["runnable"] is False
    assert payload["proposal_fingerprint"] == persisted.proposal_fingerprint
    assert payload["series"]["series_id"] == persisted.catalog.series_id
    assert len(payload["series"]["lessons"]) == 4
    assert payload["publication_plan"]["items"][0]["publication_order"] == 1
    assert "confirm-psychology-series" in payload["next_step"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "source_refs" not in serialized
    assert "approval" not in serialized
    assert "series-store" not in serialized
    assert not (store.catalog_root / "catalogs").exists()


def test_plan_psychology_series_cli_accepts_a_safe_json_outline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _patch_cli_psychology_series_store(monkeypatch, tmp_path / "series-store")
    outline_path = tmp_path / "outline.json"
    outline_path.write_text(
        json.dumps(
            [
                {"id": "review", "title": "回顾已有线索", "goal": "整理一个发现"},
                {"id": "notice", "title": "先识别触发时刻", "goal": "看见一个瞬间"},
                {"id": "practice", "title": "练习一个小动作", "goal": "今天尝试一次"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "plan-psychology-series",
            "--topic",
            "下班后的脑内回放",
            "--curriculum-outline-file",
            str(outline_path),
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    persisted = store.read_proposal(proposal_id=payload["proposal_id"])

    assert exit_code == 0
    assert [item["lesson_id"] for item in payload["series"]["lessons"]] == [
        "review",
        "notice",
        "practice",
    ]
    assert [item["lesson_id"] for item in payload["publication_plan"]["items"]] == [
        "notice",
        "practice",
        "review",
    ]
    assert payload["series"]["lessons"][0]["goal"] == "整理一个发现"
    assert persisted.catalog.lessons[0].goal == "整理一个发现"


@pytest.mark.parametrize(
    ("contents", "expected_error"),
    (
        (b'{"title":"not a list"}', "JSON list"),
        (b'[{"title":"https://example.com"}]', "proposal"),
        (b"[" + b" " * (64 * 1024) + b"]", "too large"),
    ),
)
def test_plan_psychology_series_cli_rejects_invalid_outline_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    contents: bytes,
    expected_error: str,
) -> None:
    store = _patch_cli_psychology_series_store(monkeypatch, tmp_path / "series-store")
    outline_path = tmp_path / "outline.json"
    outline_path.write_bytes(contents)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "plan-psychology-series",
                "--topic",
                "下班后的脑内回放",
                "--curriculum-outline-file",
                str(outline_path),
                "--format",
                "json",
            ]
        )

    assert exc_info.value.code == 2
    assert expected_error in capsys.readouterr().err
    assert not (store.catalog_root / "proposals").exists()
    assert not (store.catalog_root / "catalogs").exists()


def test_plan_psychology_series_cli_rejects_deeply_nested_json_before_persisting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _patch_cli_psychology_series_store(monkeypatch, tmp_path / "series-store")
    outline_path = tmp_path / "outline.json"
    outline_path.write_bytes(b"[" * 30_000 + b"0" + b"]" * 30_000)

    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "plan-psychology-series",
                "--topic",
                "下班后的脑内回放",
                "--curriculum-outline-file",
                str(outline_path),
                "--format",
                "json",
            ]
        )

    assert exc_info.value.code == 2
    assert "could not parse psychology series outline file" in capsys.readouterr().err
    assert not (store.catalog_root / "proposals").exists()


def test_confirm_psychology_series_cli_requires_exact_receipt_and_confirmation_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    store = _patch_cli_psychology_series_store(monkeypatch, tmp_path / "series-store")
    outline_path = tmp_path / "outline.json"
    outline_path.write_text(
        json.dumps(
            [
                {
                    "id": "notice",
                    "title": "先识别触发时刻",
                    "goal": "确认前用于审核的目标",
                },
                {
                    "id": "practice",
                    "title": "练习一个小动作",
                    "goal": "今天尝试一次",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    assert main(
        [
            "plan-psychology-series",
            "--topic",
            "下班后的脑内回放",
            "--curriculum-outline-file",
            str(outline_path),
            "--format",
            "json",
        ]
    ) == 0
    proposal_payload = json.loads(capsys.readouterr().out)
    assert proposal_payload["series"]["lessons"][0]["goal"] == "确认前用于审核的目标"

    base_arguments = [
        "confirm-psychology-series",
        "--proposal-id",
        proposal_payload["proposal_id"],
        "--proposal-fingerprint",
        proposal_payload["proposal_fingerprint"],
    ]
    with pytest.raises(SystemExit) as missing_confirm:
        main(base_arguments)
    assert missing_confirm.value.code == 2
    assert not (store.catalog_root / "catalogs").exists()
    capsys.readouterr()

    with pytest.raises(SystemExit) as wrong_fingerprint:
        main(
            [
                *base_arguments[:5],
                "proposal:not-the-persisted-fingerprint",
                "--confirm",
            ]
        )
    assert wrong_fingerprint.value.code == 2
    assert not (store.catalog_root / "catalogs").exists()
    capsys.readouterr()

    exit_code = main([*base_arguments, "--confirm"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "confirmed"
    assert payload["series"]["series_id"] == proposal_payload["series"]["series_id"]
    assert payload["series"]["origin"] == "user_confirmed"
    assert payload["series"]["curriculum_version"] == "1"
    assert len(payload["series"]["roadmap"]) == 2
    assert payload["series"]["publication_plan"]["items"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "approval" not in serialized
    assert "proposal_fingerprint" not in serialized
    assert "catalog_digest" not in serialized
    assert "source_refs" not in serialized
    assert "确认前用于审核的目标" not in serialized
