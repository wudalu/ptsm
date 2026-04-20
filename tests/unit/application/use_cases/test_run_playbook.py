from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.accounts.registry import AccountRegistry
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.use_cases.run_playbook import (
    _build_image_generation_prompt,
    run_playbook,
    run_fengkuang_playbook,
)
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
        }


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


def test_build_image_generation_prompt_stays_within_bailian_limit() -> None:
    prompt = _build_image_generation_prompt(
        scene="周六社畜躺平",
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
