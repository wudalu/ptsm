from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.accounts.registry import AccountRegistry
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.use_cases.run_playbook import (
    _build_image_generation_prompt,
    _build_note_card_image_payload,
    run_playbook,
    run_fengkuang_playbook,
)
from ptsm.config.settings import Settings
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import FileExecutionMemory
from ptsm.infrastructure.observability.run_store import RunStore
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import PublisherPreflightError
from ptsm.playbooks.registry import PlaybookRegistry


class FailingPublisher:
    def publish(self, **_: object) -> dict[str, object]:
        raise RuntimeError("publisher login required")


def test_run_fengkuang_playbook_returns_publish_error_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周一晨会开始前五分钟",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-publish-error",
        publisher=FailingPublisher(),
    )

    assert result["status"] == "completed"
    assert result["publish_result"]["status"] == "error"
    assert result["publish_result"]["platform"] == "xiaohongshu"
    assert result["publish_result"]["error"] == "publisher login required"


class FakeWorkflow:
    def __init__(self, artifact_path: Path):
        self.artifact_path = artifact_path

    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        return {
            "status": "completed",
            "artifact_path": str(self.artifact_path),
            "final_content": {
                "title": "打工人地铁生存实录",
                "image_text": "今日已疯",
                "body": f"{payload['scene']}，今天开会开到灵魂出窍，也算活着下班了。",
                "hashtags": ["#发疯文学", "#打工人日常"],
            },
            "runtime_skill_contents": [
                "# XHS Trend Scan Live Context\n"
                "- 主切口：`怎么才周四`\n"
                "- 场景张力：`下班前被新需求拽回工位`"
            ],
            "activated_skills": [
                "xhs_trend_scan",
                "fengkuang_style",
            ],
            "activated_skill_details": [
                {
                    "skill_name": "xhs_trend_scan",
                    "resource_type": "static_skill",
                    "source_path": "src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md",
                },
                {
                    "skill_name": "fengkuang_style",
                    "resource_type": "static_skill",
                    "source_path": "src/ptsm/skills/builtin/fengkuang_style/SKILL.md",
                },
            ],
            "runtime_skill_details": [
                {
                    "skill_name": "xhs_trend_scan",
                    "resource_type": "runtime_context",
                    "resource_id": "xhs_trend_scan:runtime_context",
                    "source_path": None,
                    "content_preview": "# XHS Trend Scan Live Context",
                }
            ],
        }


class PatternWorkflow(FakeWorkflow):
    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        result = super().invoke(payload, config)
        result["playbook_id"] = "human_enrichment_daily_post"
        result["final_content"] = {
            "title": "突然意识到书桌也需要丰容",
            "image_text": "今天先丰容这个角落",
            "body": "三步清单：清出空位、放一个变量、晚上观察。评论区交一个你会先试的角落。",
            "hashtags": ["#人类丰容计划", "#家的丰容计划", "#低成本生活"],
        }
        result["runtime_skill_contents"] = [
            "# XHS Format Pattern Library Context\n"
            "- status: available\n"
            "- lane: human_enrichment\n"
            "- source: outputs/artifacts/xhs-pattern-library/current.json\n"
            "- pattern_ids: human_enrichment.sudden_realization.001\n"
            "- hook_archetypes: sudden_realization\n"
            "- body_structures: ordinary friction -> one variable -> checklist -> comment\n"
            "- image_sequences: cover -> before state -> variable/material flat lay -> mini checklist -> after state -> comment invitation\n"
            "- primary_ratio: 3:4\n"
            "- 约束：借鉴结构，不要复写样本标题。"
        ]
        result["runtime_skill_details"] = [
            {
                "skill_name": "xhs_trend_scan",
                "resource_type": "runtime_context",
                "resource_id": "xhs_trend_scan:runtime_context",
                "source_path": None,
                "content_preview": "# XHS Format Pattern Library Context",
            }
        ]
        return result


class ImagePlanWorkflow(FakeWorkflow):
    def __init__(self, artifact_path: Path, image_plan: dict[str, str]):
        super().__init__(artifact_path)
        self.image_plan = image_plan

    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        result = super().invoke(payload, config)
        result["final_content"] = {
            "title": "领导18:57发在吗",
            "image_text": "收到，但灵魂已下班",
            "body": "领导：在吗\n我：收到，但灵魂已下班。",
            "hashtags": ["#发疯文学"],
            "image_plan": self.image_plan,
        }
        return result


class SuccessfulPublisher:
    def publish(self, **kwargs: object) -> dict[str, object]:
        return {
            "status": "published",
            "platform": "xiaohongshu",
            "provider": "xiaohongshu_mcp",
            "artifact_path": kwargs["artifact_path"],
        }


class CountingPublisher:
    def __init__(self) -> None:
        self.calls = 0

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.calls += 1
        return {
            "status": "published",
            "platform": "xiaohongshu",
            "provider": "xiaohongshu_mcp",
            "artifact_path": kwargs["artifact_path"],
            "post_id": "post-123",
        }


class CapturingPublisher:
    def __init__(self) -> None:
        self.received_image_paths: list[str] = []

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.received_image_paths = list(kwargs["image_paths"])
        return {
            "status": "published",
            "platform": "xiaohongshu",
            "provider": "xiaohongshu_mcp",
            "artifact_path": kwargs["artifact_path"],
        }


class CapturingImageBackend:
    def __init__(self, generated_path: Path) -> None:
        self.generated_path = generated_path
        self.prompts: list[str] = []

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        self.prompts.append(prompt)
        return {
            "provider": "bailian",
            "model": "wanx2.1-t2i-turbo",
            "generated_image_paths": [str(self.generated_path)],
            "output_dir": str(output_dir),
            "output_stem": output_stem,
        }


def _patch_passthrough_watermark_remover(monkeypatch: pytest.MonkeyPatch) -> None:
    class PassthroughWatermarkRemover:
        def __init__(self, **_: object) -> None:
            pass

        def remove(self, *, image_path: Path, output_dir: Path, output_stem: str):
            return {
                "status": "skipped",
                "reason": "test_passthrough",
                "provider": "fake-remover",
                "source_path": str(image_path),
                "output_path": str(image_path),
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.WatermarkRemover",
        PassthroughWatermarkRemover,
    )


class PreflightFailingPublisher:
    def publish(self, **_: object) -> dict[str, object]:
        raise PublisherPreflightError(
            "xiaohongshu-mcp server at http://localhost:18060/mcp is not logged in",
            preflight={
                "status": "login_required",
                "login_status": "❌ 未登录",
                "qrcode": {"timeout": "4m0s"},
            },
        )


class LoginRequiredPreflightPublisher:
    def __init__(self) -> None:
        self.publish_called = False

    def preflight(self) -> dict[str, object]:
        return {
            "status": "login_required",
            "server_url": "http://localhost:18060/mcp",
            "login_status": "❌ 未登录",
            "qrcode": {
                "text": "请扫码登录",
            },
        }

    def publish(self, **_: object) -> dict[str, object]:
        self.publish_called = True
        raise AssertionError("publish should not be called when preflight is login_required")


def test_run_fengkuang_playbook_persists_publish_result_into_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        publisher=SuccessfulPublisher(),
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["publish_result"]["status"] == "published"
    assert artifact["publish_result"]["status"] == "published"
    assert artifact["account"]["account_id"] == "acct-fk-local"
    assert artifact["publish_mode"] == "dry-run"
    assert artifact["scene"] == "周二下午会议接会议"


def test_run_fengkuang_playbook_returns_run_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["run"]["run_id"]
    assert Path(result["run"]["run_dir"]).exists()
    assert Path(result["run"]["events_path"]).exists()
    assert Path(result["run"]["summary_path"]).exists()
    assert result["run"]["activated_skills"] == [
        "xhs_trend_scan",
        "fengkuang_style",
    ]


def test_run_playbook_records_format_patterns_used_in_response_and_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "human_enrichment_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PatternWorkflow(artifact_path),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="把书桌改成十分钟手作角",
            account_id="acct-enrichment-local",
            playbook_id="human_enrichment_daily_post",
        ),
        publisher=SuccessfulPublisher(),
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["format_patterns_used"]["status"] == "available"
    assert result["format_patterns_used"]["lane"] == "human_enrichment"
    assert result["format_patterns_used"]["pattern_ids"] == [
        "human_enrichment.sudden_realization.001"
    ]
    assert artifact["format_patterns_used"] == result["format_patterns_used"]
    assert result["run"]["runtime_skill_details"][0]["content_preview"] == (
        "# XHS Format Pattern Library Context"
    )


def test_run_fengkuang_playbook_reuses_successful_publish_result_for_same_thread(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    publisher = CountingPublisher()

    first = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-ledger-001",
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )
    second = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-ledger-001",
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert publisher.calls == 1
    assert first["publish_result"] == second["publish_result"]
    assert (tmp_path / ".ptsm" / "agent_runtime" / "side-effects.json").exists()


def test_run_fengkuang_playbook_does_not_reuse_failed_publish_result(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    first = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周三工位发呆",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-ledger-002",
        publisher=FailingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    succeeding = CountingPublisher()
    second = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周三工位发呆",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        thread_id="thread-ledger-002",
        publisher=succeeding,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert first["publish_result"]["status"] == "error"
    assert succeeding.calls == 1
    assert second["publish_result"]["status"] == "published"


def test_run_fengkuang_playbook_uses_durable_runtime_state_by_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_build_fengkuang_workflow(**kwargs: object) -> FakeWorkflow:
        captured.update(kwargs)
        return FakeWorkflow(artifact_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        fake_build_fengkuang_workflow,
    )

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert isinstance(captured["memory"], FileExecutionMemory)
    assert isinstance(captured["checkpointer"], FileCheckpointSaver)
    assert captured["memory"].path == tmp_path / ".ptsm" / "agent_runtime" / "execution-memory.json"
    assert captured["checkpointer"].path == tmp_path / ".ptsm" / "agent_runtime" / "checkpoints.pkl"


def test_run_fengkuang_playbook_runs_post_publish_checks_when_requested(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
        lambda **kwargs: {
            "status": "manual_check_required",
            "artifact_path": str(kwargs["artifact_path"]),
        },
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.open_xhs_browser",
        lambda **kwargs: {
            "status": "opened",
            "destination": "https://creator.xiaohongshu.com/publish/publish",
        },
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周二下午会议接会议",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            open_browser_if_needed=True,
            wait_for_publish_status=True,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["post_publish_checks"]["requested"] is True
    assert result["post_publish_checks"]["publish_status"] == "manual_check_required"
    assert result["post_publish_checks"]["browser_opened"] is True
    assert result["post_publish_checks"]["browser_result"]["status"] == "opened"


def test_run_fengkuang_playbook_uses_retry_window_for_publish_status_wait(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    def fake_check_xhs_publish_status(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "status": "published_search_verified",
            "post_id": "note-123",
            "post_url": "https://www.xiaohongshu.com/explore/note-123",
            "source": "mcp_search",
        }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
        fake_check_xhs_publish_status,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六晚上十点半，公开发一条打工人周末快结束的发疯文学测试",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            wait_for_publish_status=True,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["post_publish_checks"]["publish_status"] == "published_search_verified"
    assert captured["search_retry_attempts"] == 4
    assert captured["search_retry_interval_seconds"] == 2.0


def test_run_fengkuang_playbook_uses_fresh_status_publisher_for_wait(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = SuccessfulPublisher()
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    def fake_check_xhs_publish_status(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"status": "manual_check_required", "artifact_path": str(kwargs["artifact_path"])}

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
        fake_check_xhs_publish_status,
    )
    monkeypatch.chdir(tmp_path)

    run_fengkuang_playbook(
        FengkuangRequest(
            scene="等回复",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            wait_for_publish_status=True,
        ),
        publisher=publisher,
    )

    assert captured["publisher"] is None


def test_run_fengkuang_playbook_returns_preflight_payload_on_login_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周三工位发呆",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        publisher=PreflightFailingPublisher(),
    )

    assert result["publish_result"]["status"] == "login_required"
    assert result["publish_result"]["preflight"]["status"] == "login_required"
    assert result["publish_result"]["preflight"]["qrcode"]["timeout"] == "4m0s"


def test_run_fengkuang_real_publish_returns_qrcode_and_skips_workflow_when_login_required(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()

    def fail_if_workflow_builds(**_: object):
        raise AssertionError("workflow should not build when real publish preflight is blocked")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        fail_if_workflow_builds,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {
            "timeout": "4m0s",
            "is_logged_in": False,
            "img": "data:image/png;base64,"
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aF9sAAAAASUVORK5CYII=",
        },
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周五下班前最后一场会",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
            login_qrcode_output_path=str(tmp_path / "xhs-login.png"),
        ),
        publisher=publisher,
    )

    qrcode_path = tmp_path / "xhs-login.png"

    assert result["status"] == "login_required"
    assert publisher.publish_called is False
    assert qrcode_path.exists()
    assert result["publish_result"]["status"] == "login_required"
    assert result["publish_result"]["preflight"]["qrcode"]["output_path"] == str(qrcode_path)
    assert str(qrcode_path) in result["publish_result"]["login_instructions"][0]
    assert "rerun" in result["publish_result"]["login_instructions"][-1]


def test_run_fengkuang_playbook_generates_image_for_real_publish_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "generated.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda settings: type(
            "FakeImageBackend",
            (),
            {
                "generate": lambda self, **kwargs: {
                    "status": "generated",
                    "provider": "bailian",
                    "model": "qwen-image-2.0-pro",
                    "prompt": kwargs["prompt"],
                    "image_paths": [str(generated_path)],
                    "generated_image_paths": [str(generated_path)],
                    "source_url": "https://example.com/generated.png",
                }
            },
        )(),
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert publisher.received_image_paths == [str(generated_path)]
    assert result["image_generation"]["provider"] == "bailian"
    assert artifact["image_generation"]["generated_image_paths"] == [str(generated_path)]


def test_run_fengkuang_playbook_prefers_manual_image_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    manual_image = tmp_path / "manual.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    def fail_build_image_backend(settings):
        raise AssertionError("image backend should not be built when manual paths are provided")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        fail_build_image_backend,
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
            publish_image_paths=[str(manual_image)],
        ),
        publisher=publisher,
    )

    assert publisher.received_image_paths == [str(manual_image)]


def test_run_fengkuang_real_publish_always_removes_watermark_for_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    manual_image = tmp_path / "manual.png"
    cleaned_image = tmp_path / "generated_images" / "manual-nowm.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    calls: list[dict[str, object]] = []

    class FakeWatermarkRemover:
        def __init__(self, **kwargs: object) -> None:
            calls.append({"init": kwargs})

        def remove(self, *, image_path: Path, output_dir: Path, output_stem: str):
            calls.append(
                {
                    "image_path": str(image_path),
                    "output_dir": str(output_dir),
                    "output_stem": output_stem,
                }
            )
            return {
                "status": "removed",
                "provider": "fake-remover",
                "source_path": str(image_path),
                "output_path": str(cleaned_image),
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.WatermarkRemover",
        FakeWatermarkRemover,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
            publish_image_paths=[str(manual_image)],
        ),
        settings=Settings.model_construct(
            default_model_provider="deterministic",
            deepseek_api_key=None,
            watermark_removal_enabled=False,
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert calls[1]["image_path"] == str(manual_image)
    assert publisher.received_image_paths == [str(cleaned_image)]
    assert result["watermark_removal"]["status"] == "completed"
    assert artifact["watermark_removal"]["status"] == "completed"


def test_run_fengkuang_playbook_skips_generation_for_dry_run_without_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )

    def fail_build_image_backend(settings):
        raise AssertionError("image backend should not be built for dry-run by default")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        fail_build_image_backend,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
        ),
        publisher=publisher,
    )

    assert publisher.received_image_paths == []
    assert result.get("image_generation") is None


def test_run_fengkuang_playbook_uses_local_note_card_when_provider_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["image_generation"]["provider"] == "local_note_card"
    assert result["image_generation"]["style"] == "xhs_note_card_v1"
    assert publisher.received_image_paths
    assert Path(publisher.received_image_paths[0]).exists()
    assert artifact["image_generation"]["provider"] == "local_note_card"


def test_run_fengkuang_playbook_uses_requested_local_image_style_when_provider_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {
                    "title": "领导连发三个在吗",
                    "image_text": "在吗？在的，但灵魂已飞行",
                    "body": "领导：在吗\n我：在的，但灵魂已进入飞行模式",
                    "hashtags": ["#发疯文学"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周一早上领导连发三个在吗",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
            local_image_style="wechat_chat",
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["image_generation"]["style"] == "wechat_chat_v1"
    assert artifact["image_generation"]["style"] == "wechat_chat_v1"
    assert publisher.received_image_paths


def test_run_fengkuang_playbook_uses_llm_local_image_plan_even_when_provider_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "provider-generated.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    image_backend = CapturingImageBackend(generated_path)

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: ImagePlanWorkflow(
            artifact_path,
            {
                "backend": "local_social_screenshot",
                "style": "wechat_chat",
                "role": "comment_prompt",
                "text_density": "low",
                "max_text_units": "2",
                "cover_text_strategy": "只保留一条触发消息和一句可复制回复",
                "reason": "聊天记录更适合本地微信截图",
            },
        ),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: image_backend,
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="领导18:57发在吗让我补材料",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert image_backend.prompts == []
    assert result["image_generation"]["provider"] == "local_note_card"
    assert result["image_generation"]["style"] == "wechat_chat_v1"
    assert result["image_generation"]["image_plan"]["source"] == "llm_image_plan"
    assert result["image_generation"]["image_plan"]["selected_backend"] == "local_note_card"
    assert result["image_generation"]["image_plan"]["requested_style"] == "wechat_chat"
    assert result["image_generation"]["image_plan"]["role"] == "comment_prompt"
    assert result["image_generation"]["image_plan"]["text_density"] == "low"
    assert result["image_generation"]["image_plan"]["max_text_units"] == "2"
    assert (
        result["image_generation"]["image_plan"]["cover_text_strategy"]
        == "只保留一条触发消息和一句可复制回复"
    )
    assert artifact["image_generation"]["image_plan"] == result["image_generation"]["image_plan"]
    assert publisher.received_image_paths
    assert Path(publisher.received_image_paths[0]).exists()


def test_run_fengkuang_playbook_uses_provider_when_image_plan_requests_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "provider-generated.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    image_backend = CapturingImageBackend(generated_path)

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: ImagePlanWorkflow(
            artifact_path,
            {
                "backend": "provider_image",
                "style": "photo_reference",
                "reason": "需要外部模型生成真实感氛围图",
            },
        ),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: image_backend,
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="领导18:57发在吗让我补材料",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
        ),
        publisher=publisher,
    )

    assert len(image_backend.prompts) == 1
    assert "provider_image" in image_backend.prompts[0]
    assert "需要外部模型生成真实感氛围图" in image_backend.prompts[0]
    assert result["image_generation"]["provider"] == "bailian"
    assert result["image_generation"]["image_plan"]["source"] == "llm_image_plan"
    assert result["image_generation"]["image_plan"]["selected_backend"] == "bailian"
    assert publisher.received_image_paths == [str(generated_path)]


def test_run_fengkuang_playbook_local_image_style_forces_local_even_when_provider_exists(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "provider-generated.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    image_backend = CapturingImageBackend(generated_path)

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: image_backend,
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周一早上领导连发三个在吗",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
            local_image_style="iphone_notes",
        ),
        publisher=publisher,
    )

    assert image_backend.prompts == []
    assert result["image_generation"]["provider"] == "local_note_card"
    assert result["image_generation"]["style"] == "iphone_notes_v1"
    assert result["image_generation"]["image_plan"]["source"] == "manual_override"
    assert result["image_generation"]["image_plan"]["selected_backend"] == "local_note_card"
    assert publisher.received_image_paths


def test_build_note_card_image_payload_includes_local_image_style() -> None:
    payload = json.loads(
        _build_note_card_image_payload(
            scene="周一早上领导连发三个在吗",
            runtime_context_summary="",
            final_content={
                "title": "领导连发三个在吗",
                "image_text": "在吗？",
                "body": "我咖啡还没打开。",
                "hashtags": ["#发疯文学"],
            },
            local_image_style="iphone_notes",
        )
    )

    assert payload["style"] == "iphone_notes"


def test_build_note_card_image_payload_clamps_low_density_tool_body() -> None:
    payload = json.loads(
        _build_note_card_image_payload(
            scene="下班路上反复复盘会议上说错的那句话",
            runtime_context_summary="",
            final_content={
                "title": "会议后反复复盘，不是你太玻璃心",
                "image_text": "先把脑内回放按暂停",
                "body": (
                    "下班地铁里，我又一次点开公司群聊，反复确认自己在会议上说错的"
                    "那句话有没有被所有人记住。越想越觉得脸发烫，甚至开始脑补明天"
                    "大家看我的眼神。\n"
                    "1. 给这件事起名：复盘漩涡\n"
                    "2. 分开事实和脑补\n"
                    "3. 给明天留一句可执行动作"
                ),
                "hashtags": ["#心理学", "#情绪管理"],
            },
            local_image_style="iphone_notes",
            image_plan={
                "source": "llm_image_plan",
                "requested_backend": "local_social_screenshot",
                "selected_backend": "local_note_card",
                "requested_style": "iphone_notes",
                "role": "save_tool",
                "text_density": "low",
                "max_text_units": "3",
                "cover_text_strategy": "封面只放一个问题和三条急救句",
                "prompt_focus": "心理复盘急救卡",
            },
        )
    )

    assert payload["image_plan"]["role"] == "save_tool"
    assert payload["image_plan"]["text_density"] == "low"
    assert payload["image_plan"]["max_text_units"] == "3"
    assert "下班地铁里" not in payload["body"]
    assert len(payload["body"]) <= 120
    assert len([line for line in payload["body"].splitlines() if line.strip()]) <= 3


def test_build_note_card_image_payload_extracts_inline_tool_lines() -> None:
    payload = json.loads(
        _build_note_card_image_payload(
            scene="下班路上反复复盘会议上说错的那句话",
            runtime_context_summary="",
            final_content={
                "title": "下班路上复盘会议，不是你在小题大做",
                "image_text": "先分清原话和脑补",
                "body": (
                    "下班路上反复复盘会议上说错的那句话，脑子还在把会议那一秒拖回进度条。\n"
                    "可以先存一个事实 / 猜测 / 下一步三栏：事实=对方实际说了什么；"
                    "猜测=我补出的评价；下一步=明天是否用一句轻确认收尾。"
                ),
                "hashtags": ["#心理学", "#情绪管理"],
            },
            local_image_style="iphone_notes",
            image_plan={
                "selected_backend": "local_note_card",
                "requested_style": "iphone_notes",
                "role": "save_tool",
                "text_density": "low",
                "max_text_units": "3",
                "prompt_focus": "做成低密度工具卡，保留标题、封面语和最多三条短句。",
            },
        )
    )

    assert "事实=对方实际说了什么" in payload["body"]
    assert "猜测=我补出的评价" in payload["body"]
    assert "下一步=明天是否用一句轻确认收尾" in payload["body"]
    assert "低密度工具卡" not in payload["body"]
    assert len([line for line in payload["body"].splitlines() if line.strip()]) == 3


def test_build_image_generation_prompt_stays_within_bailian_limit() -> None:
    prompt = _build_image_generation_prompt(
        scene="周六社畜躺平",
        persona_prompt="# Persona 普通打工人，表达要有人味和网感。",
        runtime_skill_contents=[
            "# XHS Trend Scan Live Context\n"
            "- 主切口：`怎么才周四`\n"
            "- 场景张力：`下班前被新需求拽回工位`"
        ],
        final_content={
            "title": "周六躺平失败实录：我的床好像有结界",
            "image_text": "试图在床上躺成一条咸鱼，结果被自己的焦虑反复煎烤。",
            "body": "周六躺平失败。" * 300,
            "hashtags": [
                "#发疯文学",
                "#成年人的崩溃瞬间",
                "#周末躺平计划",
                "#社畜日常",
                "#精神状态良好",
            ],
        },
    )

    assert len(prompt) <= 800
    assert "周六社畜躺平" in prompt
    assert "周六躺平失败实录" in prompt
    assert "普通打工人" in prompt
    assert "怎么才周四" in prompt
    assert "下班前被新需求拽回工位" in prompt
    assert "真人随手拍" in prompt


def test_build_image_generation_prompt_uses_image_form_review() -> None:
    prompt = _build_image_generation_prompt(
        scene="把下班后的书桌从堆满快递盒改成一个十分钟手作角",
        persona_prompt="# Human Enrichment Persona\n3:4 竖版封面，真实生活角落。",
        runtime_skill_contents=[],
        content_review={
            "image_form": {
                "primary_ratio": "3:4",
                "cover_style": "real-life creator cover",
                "recommended_sequence": [
                    "cover",
                    "before state",
                    "variable/material flat lay",
                    "mini checklist",
                    "after state",
                    "comment invitation",
                ],
            }
        },
        final_content={
            "title": "给书桌加一个零成本变量",
            "image_text": "今天先丰容这个角落",
            "body": "三步清单，评论区交一个角落。",
            "hashtags": ["#人类丰容计划"],
        },
    )

    assert "原本状态" in prompt
    assert "材料平铺" in prompt
    assert "清单" in prompt
    assert "氛围参考" in prompt
    assert "不要伪装成真实前后对比" in prompt


def test_run_fengkuang_playbook_passes_runtime_context_into_image_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "generated.png"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    image_backend = CapturingImageBackend(generated_path)

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: image_backend,
    )
    _patch_passthrough_watermark_remover(monkeypatch)
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="周四下午四点半，老板还在群里发新需求",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert len(image_backend.prompts) == 1
    assert "怎么才周四" in image_backend.prompts[0]
    assert "下班前被新需求拽回工位" in image_backend.prompts[0]
    assert result["image_generation"]["runtime_context_summary"] == (
        "主切口 怎么才周四，场景张力 下班前被新需求拽回工位"
    )
    assert artifact["image_generation"]["runtime_context_summary"] == (
        "主切口 怎么才周四，场景张力 下班前被新需求拽回工位"
    )


def test_run_playbook_supports_non_fengkuang_playbook_with_generic_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "sushi_poetry_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-sushi-local.yaml",
        account_id="acct-sushi-local",
        nickname="苏轼诗词赏析实验号",
        domain="苏轼诗词赏析",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "sushi_poetry_daily_post",
        playbook_id="sushi_poetry_daily_post",
        domain="苏轼诗词赏析",
        required_hashtag="#苏轼",
        required_phrase="苏轼",
    )
    captured: dict[str, object] = {}

    def fake_build_playbook_workflow(**kwargs: object) -> FakeWorkflow:
        captured.update(kwargs)
        return FakeWorkflow(artifact_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        fake_build_playbook_workflow,
        raising=False,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="夜里读到定风波",
            account_id="acct-sushi-local",
            playbook_id="sushi_poetry_daily_post",
        ),
        accounts=AccountRegistry(account_root=tmp_path / "accounts"),
        playbooks=PlaybookRegistry(playbook_root=tmp_path / "playbooks"),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "sushi_poetry_daily_post"
    assert captured["playbook_id"] == "sushi_poetry_daily_post"
    assert captured["domain"] == "苏轼诗词赏析"


def test_run_playbook_uses_local_pattern_context_for_deterministic_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "sushi_poetry_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-sushi-local.yaml",
        account_id="acct-sushi-local",
        nickname="苏轼诗词赏析实验号",
        domain="苏轼诗词赏析",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "sushi_poetry_daily_post",
        playbook_id="sushi_poetry_daily_post",
        domain="苏轼诗词赏析",
        required_hashtag="#苏轼",
        required_phrase="苏轼",
    )
    captured: dict[str, object] = {}

    def fake_build_playbook_workflow(**kwargs: object) -> FakeWorkflow:
        captured.update(kwargs)
        return FakeWorkflow(artifact_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        fake_build_playbook_workflow,
        raising=False,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="夜里读到定风波",
            account_id="acct-sushi-local",
            playbook_id="sushi_poetry_daily_post",
        ),
        settings=Settings.model_construct(
            default_model_provider="deterministic",
            deepseek_api_key=None,
            watermark_removal_enabled=False,
        ),
        accounts=AccountRegistry(account_root=tmp_path / "accounts"),
        playbooks=PlaybookRegistry(playbook_root=tmp_path / "playbooks"),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    resolver = captured["skill_context_resolver"]

    assert result["status"] == "completed"
    builders = getattr(resolver, "_builders")
    assert list(builders) == [
        "xhs_trend_scan",
        "topic_research",
        "reddit_discussion_scan",
    ]
    assert builders["xhs_trend_scan"].__class__.__name__ == "XhsPatternContextBuilder"
    assert builders["topic_research"].__class__.__name__ == (
        "PatternAwareTopicResearchContextBuilder"
    )
    assert builders["reddit_discussion_scan"].__class__.__name__ == (
        "RedditDiscussionContextBuilder"
    )


def test_run_playbook_uses_local_pattern_context_when_deepseek_key_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "sushi_poetry_daily_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-sushi-local.yaml",
        account_id="acct-sushi-local",
        nickname="苏轼诗词赏析实验号",
        domain="苏轼诗词赏析",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "sushi_poetry_daily_post",
        playbook_id="sushi_poetry_daily_post",
        domain="苏轼诗词赏析",
        required_hashtag="#苏轼",
        required_phrase="苏轼",
    )
    captured: dict[str, object] = {}

    def fake_build_playbook_workflow(**kwargs: object) -> FakeWorkflow:
        captured.update(kwargs)
        return FakeWorkflow(artifact_path)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        fake_build_playbook_workflow,
        raising=False,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="夜里读到定风波",
            account_id="acct-sushi-local",
            playbook_id="sushi_poetry_daily_post",
        ),
        settings=Settings.model_construct(
            default_model_provider="deepseek",
            deepseek_api_key=None,
            watermark_removal_enabled=False,
        ),
        accounts=AccountRegistry(account_root=tmp_path / "accounts"),
        playbooks=PlaybookRegistry(playbook_root=tmp_path / "playbooks"),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    resolver = captured["skill_context_resolver"]

    assert result["status"] == "completed"
    builders = getattr(resolver, "_builders")
    assert list(builders) == [
        "xhs_trend_scan",
        "topic_research",
        "reddit_discussion_scan",
    ]
    assert builders["xhs_trend_scan"].__class__.__name__ == "XhsPatternContextBuilder"
    assert builders["topic_research"].__class__.__name__ == (
        "PatternAwareTopicResearchContextBuilder"
    )
    assert builders["reddit_discussion_scan"].__class__.__name__ == (
        "RedditDiscussionContextBuilder"
    )


def test_run_playbook_supports_sushi_poetry_repo_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析",
            account_id="acct-sushi-local",
            playbook_id="sushi_poetry_daily_post",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "sushi_poetry_daily_post"
    assert result["account"]["account_id"] == "acct-sushi-local"
    assert "#苏轼" in result["final_content"]["hashtags"]


def _write_account_definition(
    path: Path,
    *,
    account_id: str,
    nickname: str,
    domain: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"account_id: {account_id}",
                f"nickname: {nickname}",
                "platform: xiaohongshu",
                f"domain: {domain}",
                "publish_mode: dry-run",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_playbook_definition(
    path: Path,
    *,
    playbook_id: str,
    domain: str,
    required_hashtag: str,
    required_phrase: str,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "playbook.yaml").write_text(
        "\n".join(
            [
                f"playbook_id: {playbook_id}",
                "version: 1",
                f"domain: {domain}",
                "platforms:",
                "  - xiaohongshu",
                "required_skills: []",
                "optional_skills: []",
                "reflection:",
                f"  must_include_phrase: {required_phrase}",
                f"  required_hashtag: \"{required_hashtag}\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (path / "planner.md").write_text("# planner\n", encoding="utf-8")
    (path / "reflection.md").write_text("# reflection\n", encoding="utf-8")
