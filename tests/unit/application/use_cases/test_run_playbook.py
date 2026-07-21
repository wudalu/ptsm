from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ptsm.accounts.registry import AccountRegistry
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.use_cases.run_playbook import (
    _build_image_generation_prompt,
    _build_note_card_image_payload,
    _build_runtime_skill_context_resolver,
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


class CapturingWorkflow(FakeWorkflow):
    def __init__(self, artifact_path: Path):
        super().__init__(artifact_path)
        self.payload: dict[str, object] | None = None

    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        self.payload = payload
        return super().invoke(payload, config)


class ResolverInvokingWorkflow(CapturingWorkflow):
    """Exercise the real dynamic resolver inside a lightweight workflow double."""

    def __init__(self, artifact_path: Path):
        super().__init__(artifact_path)
        self.skill_context_resolver = None
        self.runtime_contexts: dict[str, str] | None = None

    def invoke(self, payload: dict[str, object], config: dict[str, object] | None = None):
        self.payload = payload
        assert self.skill_context_resolver is not None
        self.runtime_contexts = self.skill_context_resolver.resolve(
            state=dict(payload),
            playbook=SimpleNamespace(
                trend_keywords=[],
                domain="发疯文学",
                playbook_id="fengkuang_daily_post",
            ),
            loaded_skills=[
                SimpleNamespace(skill=SimpleNamespace(skill_name="topic_research")),
            ],
        )
        return FakeWorkflow.invoke(self, payload, config)


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
            topic_direction_id="enrichment_desk_corner_variable",
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
    assert artifact["topic_selection"]["topic_direction_id"] == (
        "enrichment_desk_corner_variable"
    )
    assert result["topic_selection"]["topic_direction_id"] == (
        "enrichment_desk_corner_variable"
    )
    assert result["run"]["runtime_skill_details"][0]["content_preview"] == (
        "# XHS Format Pattern Library Context"
    )


def test_run_playbook_injects_selected_topic_direction_into_workflow_and_artifact(
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
    workflow = CapturingWorkflow(artifact_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: workflow,
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="把书桌改成十分钟手作角",
            account_id="acct-enrichment-local",
            playbook_id="human_enrichment_daily_post",
            topic_direction_id="enrichment_desk_corner_variable",
        ),
        publisher=SuccessfulPublisher(),
    )

    assert workflow.payload is not None
    workflow_selection = workflow.payload["topic_selection"]
    assert isinstance(workflow_selection, dict)
    assert workflow_selection["topic_direction_id"] == "enrichment_desk_corner_variable"
    assert workflow_selection["source"] == "guide-post"
    assert workflow_selection["direction"]["id"] == "enrichment_desk_corner_variable"
    assert workflow_selection["direction"]["format_recommendation"]["cover_role"] == (
        "evidence_or_scene"
    )
    assert (
        workflow_selection["direction"]["format_recommendation"]["visual_evidence_need"]
        == "high"
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert result["topic_selection"] == workflow_selection
    assert artifact["topic_selection"] == workflow_selection


def test_fresh_run_playbook_uses_public_full_scan_and_keeps_raw_provenance_out_of_scene(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "playbook-artifact.json"
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
    topic_artifact = tmp_path / "outputs" / "artifacts" / "topic-scan-2026-07-21-2.json"
    calls: list[dict[str, object]] = []
    workflow = CapturingWorkflow(artifact_path)

    async def fake_run_scan(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return SimpleNamespace(
            scan_summary="本次核心是独家原始热帖标题不能进入草稿。",
            scan_date="2026-07-21",
            platforms=[
                "xiaohongshu",
                "weibo",
                "douyin",
                "zhihu",
                "bilibili",
                "toutiao",
                "douban",
                "sspai",
            ],
            discovered_verticals=[],
            recommended_angles=[
                {
                    "vertical": "围绕原始热帖标题不能进入草稿聊聊恢复",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "围绕原始热帖标题不能进入草稿，聊聊下班后的恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "原始热帖标题不能进入草稿让人有代入感",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "原作者的下班恢复",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "https://example.test/raw-source 的恢复讨论",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "feed-secret-7 让人有代入感",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "token-secret-7 的恢复讨论",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "普通人用AI工具的恢复流程",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "小王的下班恢复",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                },
                {
                    "vertical": "人类丰容",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "angle_signature": "angle-internal-7",
                    "event_fingerprint": "event-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                    "source_title": "原始热帖标题不能进入草稿",
                    "author": "原作者",
                    "url": "https://example.test/raw-source",
                    "feed_id": "feed-secret-7",
                    "xsec_token": "token-secret-7",
                }
            ],
            noise_topics=[],
            scan_quality="partial",
            platform_errors={"weibo": "collection failed (TimeoutError)"},
            evidence=[
                {
                    "evidence_id": "evidence-internal-7",
                    "title": "原始热帖标题不能进入草稿",
                    "event_fingerprint": "event-internal-7",
                }
            ],
            raw_trending=[
                {
                    "title": "原始热帖标题不能进入草稿",
                    "author": "原作者",
                    "url": "https://example.test/raw-source",
                    "feed_id": "feed-secret-7",
                    "xsec_token": "token-secret-7",
                },
                {
                    "title": "AI工具",
                    "author": "小王",
                }
            ],
            topic_clusters=[
                {
                    "cluster_id": "cluster-internal-7",
                    "event_fingerprint": "event-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                }
            ],
            artifact_path=topic_artifact,
            report_path=tmp_path / "outputs" / "artifacts" / "topic-brief-2026-07-21-2.md",
        )

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: workflow,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="人类丰容",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            fresh_topic_research=True,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert calls == [{"output_dir": str(tmp_path / "outputs" / "artifacts")}]
    assert workflow.payload is not None
    selection = result["topic_selection"]
    assert selection["scan_quality"] == "partial"
    assert selection["platform_errors"] == {"weibo": "collection failed (TimeoutError)"}
    assert selection["artifact_path"] == str(topic_artifact)
    assert selection["cluster_id"] == "cluster-internal-7"
    assert selection["angle_signature"] == "angle-internal-7"
    assert selection["event_fingerprint"] == "event-internal-7"
    assert selection["evidence_ids"] == ["evidence-internal-7"]
    assert "scan_summary" not in selection
    assert "原始热帖标题不能进入草稿" not in json.dumps(selection, ensure_ascii=False)

    enriched_scene = str(workflow.payload["scene"])
    for secret in (
        "原始热帖标题不能进入草稿",
        "AI工具",
        "原作者",
        "小王",
        "https://example.test/raw-source",
        "feed-secret-7",
        "token-secret-7",
        "cluster-internal-7",
        "angle-internal-7",
        "event-internal-7",
        "evidence-internal-7",
    ):
        assert secret not in enriched_scene

    persisted = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert persisted["topic_selection"] == selection


def test_fresh_run_playbook_scans_once_and_skips_conflicting_runtime_topic_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "playbook-artifact.json"
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
    topic_artifact = tmp_path / "outputs" / "artifacts" / "topic-scan-2026-07-21-2.json"
    calls: list[dict[str, object]] = []
    workflow = ResolverInvokingWorkflow(artifact_path)

    async def fake_run_scan(**kwargs: object) -> object:
        calls.append(dict(kwargs))
        return SimpleNamespace(
            scan_summary="下班后的短暂恢复讨论正在升温。",
            scan_date="2026-07-21",
            platforms=["xiaohongshu", "weibo"],
            discovered_verticals=[],
            recommended_angles=[
                {
                    "vertical": "人类丰容",
                    "angle": "下班后给自己十分钟的无用恢复",
                    "why_discussion_likely": "具体、低门槛，容易评论区接龙自己的版本。",
                    "cluster_id": "cluster-internal-7",
                    "angle_signature": "angle-internal-7",
                    "event_fingerprint": "event-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                }
            ],
            noise_topics=[],
            scan_quality="partial",
            platform_errors={"weibo": "collection failed (TimeoutError)"},
            evidence=[
                {
                    "evidence_id": "evidence-internal-7",
                    "event_fingerprint": "event-internal-7",
                }
            ],
            topic_clusters=[
                {
                    "cluster_id": "cluster-internal-7",
                    "event_fingerprint": "event-internal-7",
                    "evidence_ids": ["evidence-internal-7"],
                }
            ],
            artifact_path=topic_artifact,
            report_path=tmp_path / "outputs" / "artifacts" / "topic-brief-2026-07-21-2.md",
        )

    def fake_build_fengkuang_workflow(**kwargs: object) -> ResolverInvokingWorkflow:
        workflow.skill_context_resolver = kwargs["skill_context_resolver"]
        return workflow

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        fake_build_fengkuang_workflow,
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="人类丰容",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            fresh_topic_research=True,
            format_pattern_path=str(tmp_path / "custom-pattern.json"),
        ),
        settings=Settings.model_construct(
            default_model_provider="deepseek",
            deepseek_api_key="sk-test",
            watermark_removal_enabled=False,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["status"] == "completed"
    assert calls == [{"output_dir": str(tmp_path / "outputs" / "artifacts")}]
    assert workflow.payload is not None
    assert workflow.payload["fresh_topic_research"] is False
    assert workflow.runtime_contexts == {}
    assert result["topic_selection"]["angle"] == "下班后给自己十分钟的无用恢复"


def test_fresh_run_playbook_refuses_insufficient_evidence_without_starting_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan(**_: object) -> object:
        return SimpleNamespace(
            scan_summary="",
            scan_date="2026-07-21",
            platforms=[],
            discovered_verticals=[],
            recommended_angles=[],
            noise_topics=[],
            scan_quality="insufficient_evidence",
            platform_errors={"xiaohongshu": "login required"},
            artifact_path=tmp_path / "topic-scan-2026-07-21.json",
            report_path=tmp_path / "topic-brief-2026-07-21.md",
        )

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: (_ for _ in ()).throw(AssertionError("workflow must not start")),
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="人类丰容",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            fresh_topic_research=True,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["status"] == "insufficient_evidence"
    assert result["topic_research"] == {
        "scan_quality": "insufficient_evidence",
        "platform_errors": {"xiaohongshu": "login required"},
        "artifact_path": str(tmp_path / "topic-scan-2026-07-21.json"),
        "report_path": str(tmp_path / "topic-brief-2026-07-21.md"),
    }


def test_fresh_run_playbook_refuses_vertical_without_evidence_backed_angle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan(**_: object) -> object:
        return SimpleNamespace(
            scan_summary="",
            scan_date="2026-07-21",
            platforms=["weibo"],
            discovered_verticals=[
                SimpleNamespace(
                    name="未经证实垂类",
                    keywords=["关键词"],
                    confidence=0.9,
                    discussion_density="high",
                    sample_topics=["不应进入草稿的原始标题"],
                    suggested_angles=["没有证据 ID 的建议"],
                    comment_themes=[],
                )
            ],
            recommended_angles=[],
            noise_topics=[],
            scan_quality="partial",
            platform_errors={"douyin": "collection failed (TimeoutError)"},
            artifact_path=tmp_path / "topic-scan-2026-07-21.json",
            report_path=tmp_path / "topic-brief-2026-07-21.md",
        )

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: (_ for _ in ()).throw(AssertionError("workflow must not start")),
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="人类丰容",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            fresh_topic_research=True,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["status"] == "insufficient_evidence"
    assert result["topic_research"]["scan_quality"] == "partial"


def test_run_playbook_requires_topic_guidance_for_openclaw_psychology(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    def fail_if_workflow_starts(**_: object) -> FakeWorkflow:
        raise AssertionError("workflow should not start before OpenClaw guidance ack")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        fail_if_workflow_starts,
        raising=False,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="同事临时加需求，想练一版边界句",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            caller="openclaw",
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["status"] == "topic_guidance_required"
    assert result["playbook_id"] == "modern_psychology_post"
    assert result["caller"] == "openclaw"
    direction_ids = {
        direction["id"] for direction in result["topic_guidance"]["directions"]
    }
    assert "boundary_sandwich_refusal" in direction_ids
    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert not (tmp_path / "runs").exists()


def test_run_playbook_allows_openclaw_psychology_after_guidance_ack(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: FakeWorkflow(artifact_path),
        raising=False,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="同事临时加需求，想练一版三明治拒绝法边界句",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            caller="openclaw",
            guidance_ack=True,
        ),
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "modern_psychology_post"
    assert result["publish_result"]["status"] == "dry_run"


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


def test_run_fengkuang_generated_provider_records_no_watermark_policy(
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
            scene="周六社畜躺平",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["image_generation"]["watermark_policy"]["source"] == "ptsm_generated_image"
    assert (
        result["image_generation"]["watermark_policy"]["requested"]
        == "no_provider_watermark"
    )
    assert (
        artifact["image_generation"]["watermark_policy"]
        == result["image_generation"]["watermark_policy"]
    )


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


def test_run_fengkuang_real_publish_skips_watermark_removal_for_local_generated_images(
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

    class FailingWatermarkRemover:
        def __init__(self, **_: object) -> None:
            raise AssertionError("local renderer images should not be cleaned")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.WatermarkRemover",
        FailingWatermarkRemover,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="领导18:57发来一句在吗",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
            local_image_style="wechat_chat",
        ),
        settings=Settings.model_construct(
            default_model_provider="deterministic",
            deepseek_api_key=None,
            watermark_removal_enabled=False,
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["image_generation"]["provider"] == "local_note_card"
    assert result["image_generation"]["provenance"]["source"] == "ptsm_local_renderer"
    assert publisher.received_image_paths
    assert result["watermark_removal"] == {
        "status": "skipped",
        "policy": "skipped_for_local_renderer",
        "reason": "local_renderer_trusted_no_watermark",
    }
    assert artifact["watermark_removal"] == result["watermark_removal"]


def test_run_fengkuang_real_publish_still_removes_watermark_for_provider_generated_images(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    generated_path = tmp_path / "provider-generated.png"
    cleaned_path = tmp_path / "generated_images" / "provider-generated-nowm.png"
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
                "output_path": str(cleaned_path),
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: image_backend,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.WatermarkRemover",
        FakeWatermarkRemover,
    )
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="书桌角落换一个变量",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            publish_mode="mcp-real",
        ),
        settings=Settings.model_construct(
            default_model_provider="deterministic",
            deepseek_api_key=None,
            pic_model_api_key="fake-key",
            watermark_removal_enabled=False,
        ),
        publisher=publisher,
    )

    assert calls[1]["image_path"] == str(generated_path)
    assert publisher.received_image_paths == [str(cleaned_path)]
    assert result["image_generation"]["provider"] == "bailian"
    assert result["watermark_removal"]["status"] == "completed"


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


def test_run_fengkuang_local_renderer_records_no_watermark_policy(
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

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))

    assert result["image_generation"]["provider"] == "local_note_card"
    assert result["image_generation"]["watermark_policy"]["provider"] == "local_note_card"
    assert (
        result["image_generation"]["watermark_policy"]["requested"]
        == "no_provider_watermark"
    )
    assert (
        artifact["image_generation"]["watermark_policy"]
        == result["image_generation"]["watermark_policy"]
    )


def test_run_fengkuang_generated_image_records_asset_ledger_entry(
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
    monkeypatch.chdir(tmp_path)

    result = run_fengkuang_playbook(
        FengkuangRequest(
            scene="领导18:57发来一句在吗",
            platform="xiaohongshu",
            account_id="acct-fk-local",
            auto_generate_images=True,
            local_image_style="wechat_chat",
        ),
        publisher=publisher,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    ledger = result["image_generation"]["asset_ledger"]
    ledger_path = Path(ledger["ledger_path"])
    entries = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]

    assert ledger["status"] == "recorded"
    assert artifact["image_generation"]["asset_ledger"] == ledger
    assert len(entries) == 1
    assert entries[0]["image_path"] == result["image_generation"]["generated_image_paths"][0]
    assert entries[0]["playbook_id"] == "fengkuang_daily_post"
    assert entries[0]["account_id"] == "acct-fk-local"
    assert entries[0]["provenance_source"] == "ptsm_local_renderer"


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


def test_build_note_card_image_payload_forwards_wechat_chat_options() -> None:
    payload = json.loads(
        _build_note_card_image_payload(
            scene="同事群里聊工作留痕",
            runtime_context_summary="",
            final_content={
                "title": "工作留痕后劲太大",
                "image_text": "事要留痕，但心别留疤",
                "body": "\n".join(
                    [
                        "同事：刚看见热搜",
                        "同事：工作留痕的重要性",
                        "我：我现在啥事都发文字确认",
                        "同事：我也是，口头说完还要补一句收到",
                        "我：事要留痕，但心别留疤",
                    ]
                ),
                "hashtags": ["#职场", "#工作留痕"],
                "image_plan": {
                    "backend": "local_social_screenshot",
                    "style": "wechat_chat",
                    "theme": "dark",
                    "status_time": "23:22",
                    "chat_title": "sy",
                    "show_avatars": False,
                    "chat_times": ["10:11", "10:27", "10:34"],
                    "role": "comment_prompt",
                    "text_density": "low",
                    "max_text_units": "2",
                },
            },
            local_image_style="wechat_chat",
            image_plan={
                "source": "llm_image_plan",
                "requested_backend": "local_social_screenshot",
                "selected_backend": "local_note_card",
                "requested_style": "wechat_chat",
                "role": "comment_prompt",
                "text_density": "low",
                "max_text_units": "2",
            },
        )
    )

    assert payload["style"] == "wechat_chat"
    assert payload["theme"] == "dark"
    assert payload["status_time"] == "23:22"
    assert payload["chat_title"] == "sy"
    assert payload["show_avatars"] is False
    assert payload["chat_times"] == ["10:11", "10:27", "10:34"]
    assert payload["image_plan"]["theme"] == "dark"
    assert payload["image_plan"]["status_time"] == "23:22"
    assert payload["image_plan"]["chat_title"] == "sy"
    assert payload["image_plan"]["show_avatars"] is False
    assert payload["image_plan"]["chat_times"] == ["10:11", "10:27", "10:34"]
    assert payload["body"].splitlines() == [
        "同事：刚看见热搜",
        "同事：工作留痕的重要性",
        "我：我现在啥事都发文字确认",
        "同事：我也是，口头说完还要补一句收到",
        "我：事要留痕，但心别留疤",
    ]


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


def test_build_image_generation_prompt_uses_provider_realism_policy() -> None:
    prompt = _build_image_generation_prompt(
        scene="把书桌改成一个十分钟手作角",
        persona_prompt="# Human Enrichment Persona\n真实生活角落。",
        runtime_skill_contents=[],
        final_content={
            "title": "给书桌加一个变量",
            "image_text": "今天先丰容这个角落",
            "body": "桌面、剪刀、胶带和一小块布料摊开，像刚试完一个小实验。",
            "hashtags": ["#人类丰容计划"],
        },
        image_plan={
            "requested_backend": "provider_image",
            "role": "evidence_or_scene",
            "prompt_focus": "书桌角落、材料平铺、真实手作过程",
        },
    )

    assert "手机随手拍" in prompt
    assert "自然光或室内环境光" in prompt
    assert "不完美构图" in prompt
    assert "边缘轻微裁切" in prompt
    assert "真实物件、空间或过程" in prompt
    assert "不要塑料皮肤" in prompt
    assert "不要伪造真实界面截图" in prompt


def test_build_image_generation_prompt_allows_only_short_overlay_for_cover_hook() -> None:
    prompt = _build_image_generation_prompt(
        scene="普通人看懂AI更新",
        persona_prompt="# AI Tech Persona\n像真实创作者。",
        runtime_skill_contents=[],
        final_content={
            "title": "这个AI更新被低估了",
            "image_text": "别只看参数",
            "body": "一个桌面上的手机和电脑，像刚刚试完工具。",
            "hashtags": ["#AI工具"],
        },
        image_plan={
            "requested_backend": "provider_image",
            "role": "cover_hook",
            "prompt_focus": "桌面设备场景",
        },
    )

    assert "最多一行短字" in prompt
    assert "不要做营销海报" in prompt
    assert "不要密集排版" in prompt


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
                "playbook_id": "classic_poetry_quote_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-classic-poetry-local.yaml",
        account_id="acct-classic-poetry-local",
        nickname="古诗词金句实验号",
        domain="古诗词金句",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "classic_poetry_quote_post",
        playbook_id="classic_poetry_quote_post",
        domain="古诗词金句",
        required_hashtag="#古诗词",
        required_phrase="这一句",
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
            scene="读到李白长风破浪会有时",
            account_id="acct-classic-poetry-local",
            playbook_id="classic_poetry_quote_post",
        ),
        accounts=AccountRegistry(account_root=tmp_path / "accounts"),
        playbooks=PlaybookRegistry(playbook_root=tmp_path / "playbooks"),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "classic_poetry_quote_post"
    assert captured["playbook_id"] == "classic_poetry_quote_post"
    assert captured["domain"] == "古诗词金句"


def test_run_playbook_uses_local_pattern_context_for_deterministic_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "classic_poetry_quote_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-classic-poetry-local.yaml",
        account_id="acct-classic-poetry-local",
        nickname="古诗词金句实验号",
        domain="古诗词金句",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "classic_poetry_quote_post",
        playbook_id="classic_poetry_quote_post",
        domain="古诗词金句",
        required_hashtag="#古诗词",
        required_phrase="这一句",
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
            scene="读到李白长风破浪会有时",
            account_id="acct-classic-poetry-local",
            playbook_id="classic_poetry_quote_post",
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
                "playbook_id": "classic_poetry_quote_post",
                "final_content": {"title": "旧标题"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    _write_account_definition(
        tmp_path / "accounts" / "acct-classic-poetry-local.yaml",
        account_id="acct-classic-poetry-local",
        nickname="古诗词金句实验号",
        domain="古诗词金句",
    )
    _write_playbook_definition(
        tmp_path / "playbooks" / "classic_poetry_quote_post",
        playbook_id="classic_poetry_quote_post",
        domain="古诗词金句",
        required_hashtag="#古诗词",
        required_phrase="这一句",
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
            scene="读到李白长风破浪会有时",
            account_id="acct-classic-poetry-local",
            playbook_id="classic_poetry_quote_post",
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


def test_runtime_resolver_includes_reddit_scan_for_live_deepseek_runs() -> None:
    resolver = _build_runtime_skill_context_resolver(
        Settings.model_construct(
            default_model_provider="deepseek",
            deepseek_api_key="sk-test",
            xhs_pattern_library_path="outputs/artifacts/xhs-pattern-library/current.json",
            reddit_client_id="client-id",
            reddit_client_secret="client-secret",
            reddit_user_agent="ptsm-test/0.1 (by /u/test)",
            reddit_public_json_fallback=True,
            reddit_subreddits="OpenAI,ChatGPT",
            reddit_sorts="hot,top",
            reddit_time_filter="day",
            reddit_limit_per_listing=5,
        )
    )

    assert resolver is not None
    builders = getattr(resolver, "_builders")
    assert "reddit_discussion_scan" in builders
    assert builders["reddit_discussion_scan"].__class__.__name__ == (
        "RedditDiscussionContextBuilder"
    )


def test_run_playbook_supports_classic_poetry_repo_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="读到李白长风破浪会有时，想写给低谷里的自己",
            account_id="acct-classic-poetry-local",
            playbook_id="classic_poetry_quote_post",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "classic_poetry_quote_post"
    assert result["account"]["account_id"] == "acct-classic-poetry-local"
    assert "#古诗词" in result["final_content"]["hashtags"]
    assert "#苏轼" not in result["final_content"]["hashtags"]
    assert any(
        cue in result["final_content"]["body"]
        for cue in ("长风破浪会有时", "李白", "古诗词", "金句")
    )


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
