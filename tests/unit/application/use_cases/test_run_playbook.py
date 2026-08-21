from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import ptsm.domain.psychology_learning as psychology_learning_domain
import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
import ptsm.evaluations.contracts_eval as contracts_eval
from ptsm.accounts.registry import AccountProfile, AccountRegistry
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.services.image_carousel_transaction import (
    ImageCarouselTransaction,
    ImageCarouselTransactionError,
)
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.application.use_cases.run_playbook import (
    _build_image_generation_prompt,
    _build_note_card_image_payload,
    _build_runtime_skill_context_resolver,
    _capture_psychology_learning_artifact_scope,
    _owned_psychology_learning_artifact_path,
    _remove_owned_unsafe_psychology_learning_artifact,
    _resolve_psychology_learning_preflight,
    _sanitize_psychology_learning_image_generation,
    run_playbook,
    run_fengkuang_playbook,
)
from ptsm.config.settings import Settings
from ptsm.domain.psychology_learning import (
    build_psychology_learning_catalog_receipt,
    psychology_learning_series_catalog_snapshot_path,
    psychology_learning_series_progress_sidecar_path,
    render_psychology_learning_draft,
    require_sealed_psychology_learning_preflight_bundle,
    resolve_psychology_learning_selection,
)
from ptsm.domain.psychology_carousel import psychology_carousel_inner_pages_fingerprint
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.images.image_file_evidence import ImageFileEvidenceError
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import (
    ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER,
    FileExecutionMemory,
    InMemoryExecutionMemory,
)
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


def _ordinary_psychology_carousel_content() -> dict[str, object]:
    return {
        "title": "下班后，脑子还在替会议加班",
        "image_text": "人走了，会议还没散",
        "body": (
            "人已经离开会议室，脑子还在反复回放那句话。"
            "可以先分开事实、猜测和下一步；如果持续影响生活，请寻求专业帮助。"
        ),
        "hashtags": ["#心理学", "#情绪管理", "#反刍思维"],
        "image_plan": {
            "backend": "local_social_screenshot",
            "style": "psychology_text_card",
            "role": "text_carousel",
            "text_density": "medium",
            "max_text_units": "4",
            "cover_text_strategy": "封面只放一个生活化钩子",
            "reason": "同一主题按场景、机制、工具和边界逐页展开",
            "prompt_focus": "只排版已审核文字",
            "carousel_style": "psychology_text_card_v1",
            "slides": [
                {
                    "slide_id": "cover",
                    "order": 1,
                    "role": "cover_hook",
                    "headline": "人走了，会议还没散",
                    "body_lines": ["下班后脑子还在替那句话加班"],
                },
                {
                    "slide_id": "scene",
                    "order": 2,
                    "role": "concrete_scene",
                    "headline": "身体离开了会议室",
                    "body_lines": ["脑子却在反复给那句话加字幕"],
                },
                {
                    "slide_id": "mechanism",
                    "order": 3,
                    "role": "light_mechanism",
                    "headline": "回放不等于复盘",
                    "body_lines": ["反复检查，常是在找回一点控制感"],
                },
                {
                    "slide_id": "tool",
                    "order": 4,
                    "role": "save_tool",
                    "headline": "先写这三栏",
                    "body_lines": ["事实：对方原话", "猜测：我补出的评价", "下一步：是否需要确认"],
                },
                {
                    "slide_id": "boundary",
                    "order": 5,
                    "role": "professional_boundary",
                    "headline": "一张卡片不是全部支持",
                    "body_lines": ["如果持续影响生活，请寻求专业帮助"],
                },
                {
                    "slide_id": "comment",
                    "order": 6,
                    "role": "comment_prompt",
                    "headline": "会后回放时，你是哪一派？",
                    "body_lines": ["A.写完又删", "B.发完重看"],
                },
            ],
        },
    }


class PsychologyCarouselWorkflow:
    def __init__(self, artifact_path: Path, final_content: dict[str, object]) -> None:
        self.artifact_path = artifact_path
        self.final_content = final_content

    def invoke(
        self,
        payload: dict[str, object],
        config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            "status": "completed",
            "artifact_path": str(self.artifact_path),
            "final_content": self.final_content,
            "content_review": {"image_plan": self.final_content["image_plan"]},
            "runtime_skill_contents": [],
            "activated_skills": [],
            "activated_skill_details": [],
            "runtime_skill_details": [],
        }


class StoreBackedCarouselReservation:
    """Exercise the private runtime handoff without exposing its token in state."""

    def __init__(
        self,
        *,
        memory: InMemoryExecutionMemory,
        namespace: tuple[str, ...],
        fingerprint: str,
        reservation_id: str,
        lesson: dict[str, object],
        events: list[str],
    ) -> None:
        self.memory = memory
        self.namespace = namespace
        self.fingerprint = fingerprint
        self.reservation_id = reservation_id
        self.lesson = lesson
        self.events = events
        self._settled = False

    def commit(self) -> bool:
        if self._settled:
            return False
        self.events.append("commit")
        committed = self.memory.commit_psychology_carousel_inner_fingerprint(
            namespace=self.namespace,
            fingerprint=self.fingerprint,
            reservation_id=self.reservation_id,
            item=self.lesson,
        )
        self._settled = True
        return committed

    def release(self) -> None:
        if self._settled:
            return
        self.events.append("release")
        self.memory.release_psychology_carousel_inner_fingerprint(
            namespace=self.namespace,
            fingerprint=self.fingerprint,
            reservation_id=self.reservation_id,
        )
        self._settled = True


class NoopCarouselReservation:
    def commit(self) -> bool:
        return True

    def release(self) -> None:
        return None


class HandoffPsychologyCarouselWorkflow(PsychologyCarouselWorkflow):
    def __init__(
        self,
        artifact_path: Path,
        final_content: dict[str, object],
        *,
        reservation_sink: object,
        reservation: object,
    ) -> None:
        super().__init__(artifact_path, final_content)
        self._reservation_sink = reservation_sink
        self._reservation = reservation

    def invoke(
        self,
        payload: dict[str, object],
        config: dict[str, object] | None = None,
    ) -> dict[str, object]:
        assert callable(self._reservation_sink)
        self._reservation_sink(self._reservation)
        return super().invoke(payload, config)


def _reserved_carousel_lifecycle(
    final_content: dict[str, object],
) -> tuple[
    InMemoryExecutionMemory,
    tuple[str, ...],
    dict[str, object],
    StoreBackedCarouselReservation,
]:
    memory = InMemoryExecutionMemory()
    namespace = ("accounts", "acct-psychology-local", "lessons")
    fingerprint = psychology_carousel_inner_pages_fingerprint(final_content["image_plan"])
    lesson = {
        "playbook_id": "modern_psychology_post",
        "psychology_carousel_inner_fingerprint": fingerprint,
        ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER: True,
    }
    reservation_id = memory.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=fingerprint,
        item=lesson,
    )
    assert reservation_id is not None
    reservation = StoreBackedCarouselReservation(
        memory=memory,
        namespace=namespace,
        fingerprint=fingerprint,
        reservation_id=reservation_id,
        lesson=lesson,
        events=[],
    )
    return memory, namespace, lesson, reservation


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
        self.received_image_evidence: list[dict[str, object]] | None = None

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.received_image_paths = list(kwargs["image_paths"])
        raw_evidence = kwargs.get("image_evidence")
        self.received_image_evidence = (
            [dict(page) for page in raw_evidence]  # type: ignore[union-attr]
            if raw_evidence is not None
            else None
        )
        return {
            "status": "published",
            "platform": "xiaohongshu",
            "provider": "xiaohongshu_mcp",
            "artifact_path": kwargs["artifact_path"],
        }


class EvidenceRejectingPublisher:
    def __init__(self) -> None:
        self.calls = 0
        self.received_image_evidence: list[dict[str, object]] | None = None

    def publish(self, **kwargs: object) -> dict[str, object]:
        self.calls += 1
        raw_evidence = kwargs.get("image_evidence")
        self.received_image_evidence = (
            [dict(page) for page in raw_evidence]  # type: ignore[union-attr]
            if raw_evidence is not None
            else None
        )
        raise ImageFileEvidenceError("image_file_hash_mismatch")


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
        self.generated_path.write_bytes(b"fake-provider-image")
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


def test_run_playbook_keeps_explicit_psychology_single_image_direction_format(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "psychology-single-image-artifact.json"
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
    workflow = CapturingWorkflow(artifact_path)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: workflow,
    )
    monkeypatch.chdir(tmp_path)

    run_playbook(
        PlaybookRequest(
            scene="同事临时加需求，想练一版边界句",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            topic_direction_id="boundary_sandwich_refusal",
            local_image_style="iphone_notes",
            auto_generate_images=False,
        ),
        publisher=SuccessfulPublisher(),
    )

    assert workflow.payload is not None
    selection = workflow.payload["topic_selection"]
    assert isinstance(selection, dict)
    recommendation = selection["direction"]["format_recommendation"]
    assert recommendation["format_archetype"] == "note_card"
    assert recommendation["cover_role"] == "save_tool"


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
    guidance = result["topic_guidance"]
    assert guidance["image_recommendation"]["format_archetype"] == "text_carousel"
    assert guidance["image_recommendation"]["role"] == "text_carousel"
    assert all(
        direction["format_recommendation"]["format_archetype"]
        == "text_carousel"
        for direction in guidance["directions"]
    )
    direction_ids = {
        direction["id"] for direction in guidance["directions"]
    }
    assert "boundary_sandwich_refusal" in direction_ids
    serialized = json.dumps(result, ensure_ascii=False)
    assert "open_scene_watch_checklist_" not in serialized
    assert "open_scene_tool_handoff_" not in serialized
    assert "看球搭子" not in serialized
    assert "AI 工具生活化" not in serialized
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert not (tmp_path / "runs").exists()


def test_openclaw_psychology_preflight_preserves_explicit_single_image_style(
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
            local_image_style="iphone_notes",
        ),
        publisher=SuccessfulPublisher(),
    )

    assert result["status"] == "topic_guidance_required"
    guidance = result["topic_guidance"]
    assert guidance["image_recommendation"]["local_style"] == "iphone_notes"
    assert "format_archetype" not in guidance["image_recommendation"]
    assert all(
        direction["format_recommendation"]["format_archetype"]
        != "text_carousel"
        for direction in guidance["directions"]
    )
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

    def generate_provider_image(self: object, **kwargs: object) -> dict[str, object]:
        generated_path.write_bytes(b"fake-provider-image")
        return {
            "status": "generated",
            "provider": "bailian",
            "model": "qwen-image-2.0-pro",
            "prompt": kwargs["prompt"],
            "image_paths": [str(generated_path)],
            "generated_image_paths": [str(generated_path)],
            "source_url": "https://example.com/generated.png",
        }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_fengkuang_workflow",
        lambda **_: FakeWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda settings: type(
            "FakeImageBackend",
            (),
            {"generate": generate_provider_image},
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


def test_run_playbook_publishes_complete_psychology_carousel_in_manifest_order(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "psychology-carousel.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()

    def build_workflow(**kwargs: object) -> HandoffPsychologyCarouselWorkflow:
        return HandoffPsychologyCarouselWorkflow(
            artifact_path,
            final_content,
            reservation_sink=kwargs["ordinary_psychology_carousel_reservation_sink"],
            reservation=NoopCarouselReservation(),
        )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    generation = result["image_generation"]
    assert result["status"] == "completed"
    assert generation["status"] == "committed"
    assert generation["carousel_style"] == "psychology_text_card_v1"
    assert generation["image_count"] == 6
    assert [page["order"] for page in generation["pages"]] == [1, 2, 3, 4, 5, 6]
    assert publisher.received_image_paths == generation["generated_image_paths"]
    assert publisher.received_image_evidence == generation["pages"]
    assert all(Path(path).is_file() for path in publisher.received_image_paths)
    assert Path(generation["manifest_path"]).is_file()
    assert result["watermark_removal"] == {
        "status": "skipped",
        "policy": "skipped_for_local_renderer",
        "reason": "local_renderer_trusted_no_watermark",
    }
    assert generation["asset_ledger"]["entry_count"] == 6
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["image_generation"]["manifest_sha256"] == generation[
        "manifest_sha256"
    ]


def test_run_playbook_commits_carousel_memory_only_after_ledger_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "handoff-carousel.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    memory, namespace, lesson, reservation = _reserved_carousel_lifecycle(final_content)

    def build_workflow(**kwargs: object) -> HandoffPsychologyCarouselWorkflow:
        return HandoffPsychologyCarouselWorkflow(
            artifact_path,
            final_content,
            reservation_sink=kwargs["ordinary_psychology_carousel_reservation_sink"],
            reservation=reservation,
        )

    def append_ledger(**_: object) -> dict[str, object]:
        reservation.events.append("ledger")
        assert memory.search(namespace=namespace) == []
        return {"entry_count": 6}

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.append_generated_image_assets",
        append_ledger,
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
        ),
        memory=memory,
        publisher=CapturingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert reservation.events == ["ledger", "commit"]
    assert memory.search(namespace=namespace) == [lesson]
    serialized_result = json.dumps(result, ensure_ascii=False)
    serialized_artifact = artifact_path.read_text(encoding="utf-8")
    assert reservation.reservation_id not in serialized_result
    assert reservation.reservation_id not in serialized_artifact


def test_run_playbook_carousel_renderer_failure_finishes_without_publish_side_effects(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "failed-carousel.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.setattr(
        ImageCarouselTransaction,
        "generate",
        lambda self, **kwargs: (_ for _ in ()).throw(
            ImageCarouselTransactionError("renderer failed on page 3: private path")
        ),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert result["image_generation"] == {
        "status": "failed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 6,
        "reason": "psychology_carousel_generation_failed",
    }
    assert result["watermark_removal"] is None
    assert result["publish_result"] is None
    assert result["run"]["status"] == "psychology_carousel_generation_failed"
    assert publisher.calls == 0
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["image_generation"] == result["image_generation"]
    assert "private path" not in json.dumps(result, ensure_ascii=False)
    assert not (
        tmp_path / "outputs" / "artifacts" / "generated-image-assets" / "assets.jsonl"
    ).exists()


def test_run_playbook_carousel_ledger_failure_keeps_set_but_skips_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "ledger-failed-carousel.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.append_generated_image_assets",
        lambda **_: (_ for _ in ()).throw(OSError("ledger contains private path")),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert result["image_generation"]["status"] == "committed"
    assert result["image_generation"]["image_count"] == 6
    assert all(
        Path(path).is_file()
        for path in result["image_generation"]["generated_image_paths"]
    )
    assert result["watermark_removal"] is None
    assert result["publish_result"] is None
    assert publisher.calls == 0
    assert "ledger contains private path" not in json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize("failure_step", ("renderer", "verification", "ledger"))
def test_run_playbook_releases_carousel_memory_reservation_after_rendering_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    failure_step: str,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / f"{failure_step}-handoff.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    memory, namespace, lesson, reservation = _reserved_carousel_lifecycle(final_content)

    def build_workflow(**kwargs: object) -> HandoffPsychologyCarouselWorkflow:
        return HandoffPsychologyCarouselWorkflow(
            artifact_path,
            final_content,
            reservation_sink=kwargs["ordinary_psychology_carousel_reservation_sink"],
            reservation=reservation,
        )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    if failure_step == "renderer":
        monkeypatch.setattr(
            ImageCarouselTransaction,
            "generate",
            lambda self, **kwargs: (_ for _ in ()).throw(
                ImageCarouselTransactionError("renderer failure")
            ),
        )
    elif failure_step == "verification":
        monkeypatch.setattr(
            "ptsm.application.use_cases.run_playbook.verify_committed_carousel_set",
            lambda **_: (_ for _ in ()).throw(
                ImageCarouselTransactionError("verification failure")
            ),
        )
    else:
        monkeypatch.setattr(
            "ptsm.application.use_cases.run_playbook.append_generated_image_assets",
            lambda **_: (_ for _ in ()).throw(OSError("ledger failure")),
        )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
        ),
        memory=memory,
        publisher=CountingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert reservation.events == ["release"]
    assert memory.search(namespace=namespace) == []
    retry_reservation_id = memory.reserve_psychology_carousel_inner_fingerprint(
        namespace=namespace,
        fingerprint=reservation.fingerprint,
        item=lesson,
    )
    assert retry_reservation_id is not None
    serialized_result = json.dumps(result, ensure_ascii=False)
    serialized_artifact = artifact_path.read_text(encoding="utf-8")
    assert reservation.reservation_id not in serialized_result
    assert reservation.reservation_id not in serialized_artifact


@pytest.mark.parametrize(
    ("auto_generate_images", "publish_image_paths", "local_image_style"),
    (
        (False, [], None),
        (True, ["provided-carousel.png"], None),
        (True, [], "legacy_note_card"),
    ),
)
def test_run_playbook_releases_carousel_memory_when_no_local_carousel_is_rendered(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    auto_generate_images: bool,
    publish_image_paths: list[str],
    local_image_style: str | None,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "unrendered-handoff.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    memory, namespace, _, reservation = _reserved_carousel_lifecycle(final_content)

    def build_workflow(**kwargs: object) -> HandoffPsychologyCarouselWorkflow:
        return HandoffPsychologyCarouselWorkflow(
            artifact_path,
            final_content,
            reservation_sink=kwargs["ordinary_psychology_carousel_reservation_sink"],
            reservation=reservation,
        )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _settings: None,
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="下班后还在回放会议里的那句话",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=auto_generate_images,
            publish_image_paths=publish_image_paths,
            local_image_style=local_image_style,
        ),
        memory=memory,
        publisher=CountingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert reservation.events == ["release"]
    assert memory.search(namespace=namespace) == []


def test_run_playbook_releases_carousel_reservation_on_unhandled_post_workflow_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _ordinary_psychology_carousel_content()
    artifact_path = tmp_path / "outputs" / "artifacts" / "post-workflow-error.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    memory, namespace, lesson, reservation = _reserved_carousel_lifecycle(final_content)

    def build_workflow(**kwargs: object) -> HandoffPsychologyCarouselWorkflow:
        return HandoffPsychologyCarouselWorkflow(
            artifact_path,
            final_content,
            reservation_sink=kwargs["ordinary_psychology_carousel_reservation_sink"],
            reservation=reservation,
        )

    def fail_merge(self: FileArtifactStore, *args: object, **kwargs: object) -> None:
        del self, args, kwargs
        raise OSError("post-workflow artifact merge failed")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.setattr(FileArtifactStore, "merge", fail_merge)
    monkeypatch.chdir(tmp_path)
    run_store = RunStore(base_dir=tmp_path / "runs")

    with pytest.raises(OSError, match="post-workflow artifact merge failed") as error:
        run_playbook(
            PlaybookRequest(
                scene="下班后还在回放会议里的那句话",
                account_id="acct-psychology-local",
                playbook_id="modern_psychology_post",
                auto_generate_images=False,
            ),
            memory=memory,
            publisher=CountingPublisher(),
            run_store=run_store,
        )

    assert reservation.events == ["release"]
    assert memory.search(namespace=namespace) == []
    assert (
        memory.reserve_psychology_carousel_inner_fingerprint(
            namespace=namespace,
            fingerprint=reservation.fingerprint,
            item=lesson,
        )
        is not None
    )
    serialized_artifact = artifact_path.read_text(encoding="utf-8")
    serialized_events = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tmp_path / "runs").glob("*/events.jsonl")
    )
    assert reservation.reservation_id not in str(error.value)
    assert reservation.reservation_id not in serialized_artifact
    assert reservation.reservation_id not in serialized_events


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


def test_run_playbook_requires_ai_evidence_before_starting_a_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            scene="Kimi K3 更新",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "ai_tech_evidence_required"
    assert result["playbook_id"] == "ai_tech_daily_post"


def test_run_playbook_does_not_echo_free_text_scene_in_ai_preflight_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_scene = "Example 原始标题 https://example.com/release by Example Author"
    result = run_playbook(
        PlaybookRequest(
            scene=raw_scene,
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
        ),
        run_store=RunStore(),
    )

    serialized = json.dumps(result, ensure_ascii=False)

    assert result["status"] == "ai_tech_evidence_required"
    assert raw_scene not in serialized
    assert "https://example.com/release" not in serialized


def test_run_playbook_never_runs_or_renders_fresh_radar_inside_ai_evidence_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook._run_topic_radar_scan",
        lambda **_: pytest.fail("AI evidence mode must not run Topic Radar inline"),
    )
    raw_scene = "Example 原始标题 https://example.com/release by Example Author"

    result = run_playbook(
        PlaybookRequest(
            scene=raw_scene,
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            fresh_topic_research=True,
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    serialized = json.dumps(result, ensure_ascii=False)

    assert result["status"] == "ai_tech_fresh_research_separate"
    assert raw_scene not in serialized
    assert "https://example.com/release" not in serialized


@pytest.mark.parametrize(
    ("ai_content_mode", "ai_evidence_bundle"),
    (("news_brief", {"mode": "news_brief", "news_items": []}),),
)
def test_run_playbook_rejects_invalid_or_mismatched_ai_evidence_before_starting_a_run(
    monkeypatch: pytest.MonkeyPatch,
    ai_content_mode: str,
    ai_evidence_bundle: dict[str, object],
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            scene="Kimi K3 更新",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode=ai_content_mode,
            ai_evidence_bundle=ai_evidence_bundle,
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "ai_tech_evidence_invalid"
    assert result["playbook_id"] == "ai_tech_daily_post"


def test_run_playbook_rejects_mismatched_valid_ai_evidence_before_starting_a_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            scene="Kimi K3 更新",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="hands_on",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "ai_tech_evidence_invalid"
    assert result["diagnostic"] == "content_mode_mismatch"


def test_run_playbook_validates_ai_evidence_without_passing_raw_bundle_to_workflow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = {
        "title": "AI 科技三条更新",
        "image_text": "今天该看哪三件事",
        "body": (
            "模型发布：产品发布了新的推理模型。\n"
            "开发者工具：开发者工具新增了批量处理能力。\n"
            "行业应用：功能面向团队协作场景开放。"
        ),
        "hashtags": ["#AI资讯"],
    }
    artifact_path = tmp_path / "outputs" / "artifacts" / "artifact.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "ai_tech_daily_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    class ValidAiWorkflow(CapturingWorkflow):
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            result = super().invoke(payload, config)
            result["final_content"] = final_content
            return result

    workflow = ValidAiWorkflow(artifact_path)
    workflow_build_arguments: dict[str, object] = {}

    def build_workflow(**kwargs: object) -> ValidAiWorkflow:
        workflow_build_arguments.update(kwargs)
        return workflow

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="Raw release title https://example.com/release by Example Author",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            ai_evidence_file_path="inputs/ai-evidence.json",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert workflow.payload is not None
    assert "ai_evidence_bundle" not in workflow.payload
    assert "ai_content_mode" not in workflow.payload
    assert "ai_evidence_file_path" not in workflow.payload
    assert "ai_tech_evidence" not in workflow.payload
    assert set(workflow_build_arguments["ai_tech_evidence"]) == {
        "mode",
        "drafting_payload",
        "requirements",
    }
    assert workflow_build_arguments["ai_tech_evidence_manifest"] == {
        "source_refs": [
            "official-release-001",
            "official-release-002",
            "official-release-003",
        ],
        "test_evidence_refs": [],
        "event_fingerprints": [
            "event-model-release-001",
            "event-developer-tools-002",
            "event-industry-use-003",
        ],
        "trend_support": [],
    }
    assert workflow_build_arguments["ai_tech_evidence"]["mode"] == "news_brief"
    assert "https://example.com/release" not in str(workflow.payload["scene"])
    assert "Example Author" not in str(workflow.payload["scene"])
    assert "产品发布了新的推理模型。" in json.dumps(
        workflow_build_arguments["ai_tech_evidence"], ensure_ascii=False
    )
    assert "official-release-001" not in json.dumps(
        workflow_build_arguments["ai_tech_evidence"], ensure_ascii=False
    )
    assert "ai_tech_evidence" not in result

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["ai_tech_evidence_manifest"]["source_refs"] == [
        "official-release-001",
        "official-release-002",
        "official-release-003",
    ]
    assert "ai_tech_evidence" not in artifact
    assert result["ai_tech_evidence_manifest"] == artifact["ai_tech_evidence_manifest"]
    assert artifact["ai_tech_content_mode"] == "news_brief"
    assert artifact["ai_tech_evidence_gate"] == {
        "status": "passed",
        "mode": "news_brief",
        "validator": "ai_tech_draft_contract",
        "validator_version": "1",
        "errors": [],
    }
    assert result["ai_tech_evidence_gate"] == artifact["ai_tech_evidence_gate"]
    serialized_artifact = json.dumps(artifact, ensure_ascii=False)
    assert "https://example.com/release" not in serialized_artifact
    assert "Example Author" not in serialized_artifact


def test_run_playbook_blocks_ai_publish_when_workflow_did_not_write_an_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class MissingArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(tmp_path / "missing-artifact.json"),
                "final_content": {
                    "title": "AI 科技三条更新",
                    "image_text": "今天该看哪三件事",
                    "body": (
                        "模型发布：产品发布了新的推理模型。\n"
                        "开发者工具：开发者工具新增了批量处理能力。\n"
                        "行业应用：功能面向团队协作场景开放。"
                    ),
                    "hashtags": ["#AI资讯"],
                },
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: MissingArtifactWorkflow(),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _: pytest.fail("image generation must not be reached"),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="Raw release title https://example.com/release by Example Author",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            auto_generate_images=True,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "ai_tech_artifact_required"
    assert publisher.calls == 0


def test_run_playbook_blocks_unsafe_ai_custom_workflow_before_image_or_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class UnsafeAiWorkflow(CapturingWorkflow):
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            self.payload = payload
            return {
                "status": "completed",
                "artifact_path": str(self.artifact_path),
                "final_content": {
                    "title": "今天的 AI 更新",
                    "image_text": "别只看参数",
                    "body": "我实测后发现，这次速度提升明显。",
                    "hashtags": ["#AI资讯"],
                },
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps({"playbook_id": "ai_tech_daily_post"}, ensure_ascii=False),
        encoding="utf-8",
    )
    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: UnsafeAiWorkflow(artifact_path),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda _: pytest.fail("image generation must not be reached"),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            auto_generate_images=True,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "ai_tech_draft_invalid"
    assert result["publish_result"] is None
    assert publisher.calls == 0
    assert "我实测" in result["ai_tech_draft_validation"]["errors"]


def test_ai_login_rerun_preserves_evidence_file_arguments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()
    evidence_path = tmp_path / "ai evidence.json"
    evidence_path.write_text(json.dumps(_valid_ai_news_brief_bundle()), encoding="utf-8")
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

    result = run_playbook(
        PlaybookRequest(
            scene="Raw release title https://example.com/release by Example Author",
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            publish_mode="mcp-real",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            ai_evidence_file_path=str(evidence_path),
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    rerun_instruction = result["publish_result"]["login_instructions"][-1]

    assert result["status"] == "login_required"
    assert "--ai-content-mode news_brief" in rerun_instruction
    assert "--ai-evidence-file" in rerun_instruction
    assert str(evidence_path) in rerun_instruction
    assert "--scene" not in rerun_instruction
    assert "https://example.com/release" not in rerun_instruction
    assert "https://example.com/release" not in result["scene"]


def test_psychology_learning_login_rerun_preserves_catalog_selection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {"timeout": "4m0s", "is_logged_in": False},
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="operator-only scene https://example.com/should-not-leak",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            publish_mode="mcp-real",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    rerun_instruction = result["publish_result"]["login_instructions"][-1]

    assert result["status"] == "login_required"
    assert "--psychology-content-mode learning_series" in rerun_instruction
    assert "--psychology-series-id after_work_rumination" in rerun_instruction
    assert "--psychology-lesson-id notice_the_loop" in rerun_instruction
    assert "--psychology-curriculum-version 1" in rerun_instruction
    assert (
        "--topic-direction-id psychology_learning_after_work_rumination_notice_the_loop"
        in rerun_instruction
    )
    assert "--scene" not in rerun_instruction
    assert "https://example.com/should-not-leak" not in rerun_instruction


def test_ai_login_without_evidence_file_uses_api_recovery_instruction(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {"timeout": "4m0s", "is_logged_in": False},
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            publish_mode="mcp-real",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    recovery_instruction = result["publish_result"]["login_instructions"][-1]

    assert result["status"] == "login_required"
    assert "original API request" in recovery_instruction
    assert "ai_evidence_bundle" in recovery_instruction
    assert "Then rerun:" not in recovery_instruction


def test_ai_login_rerun_uses_equals_form_for_leading_dash_evidence_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {"timeout": "4m0s", "is_logged_in": False},
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            publish_mode="mcp-real",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            ai_evidence_file_path="-ai-evidence.json",
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    rerun_instruction = result["publish_result"]["login_instructions"][-1]

    assert "--ai-evidence-file=-ai-evidence.json" in rerun_instruction


def test_non_ai_login_rerun_ignores_unrelated_ai_evidence_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    publisher = LoginRequiredPreflightPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.xhs_login.fetch_xhs_login_qrcode_via_api",
        lambda server_url: {"timeout": "4m0s", "is_logged_in": False},
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            scene="读到李白长风破浪会有时",
            account_id="acct-classic-poetry-local",
            playbook_id="classic_poetry_quote_post",
            publish_mode="mcp-real",
            ai_content_mode="news_brief",
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    rerun_instruction = result["publish_result"]["login_instructions"][-1]

    assert "Then rerun:" in rerun_instruction
    assert "--ai-content-mode" not in rerun_instruction


def _valid_ai_news_brief_bundle() -> dict[str, object]:
    return {
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
    }


def _psychology_learning_bundle():
    return resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id="notice_the_loop",
    )


def _valid_psychology_learning_draft() -> dict[str, object]:
    return render_psychology_learning_draft(_psychology_learning_bundle().runtime_contract)


def test_psychology_learning_carousel_receipt_keeps_only_safe_set_evidence() -> None:
    receipt = _sanitize_psychology_learning_image_generation(
        {
            "status": "committed",
            "provider": "local_note_card",
            "style": "psychology_text_card_v1",
            "carousel_style": "psychology_text_card_v1",
            "image_count": 7,
            "manifest_sha256": "a" * 64,
            "manifest_path": "/private/generated/set/manifest.json",
            "generated_image_paths": ["/private/generated/set/page-01.png"],
            "pages": [{"headline": "catalog-only text"}],
            "provenance": {"source": "ptsm_local_renderer"},
        },
        controlled_template_version="2",
    )

    assert receipt == {
        "status": "committed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "manifest_sha256": "a" * 64,
    }
    assert _sanitize_psychology_learning_image_generation(
        {
            **receipt,
            "provider": "local_note_card",
            "provenance": {"source": "ptsm_local_renderer"},
            "manifest_sha256": "/tmp/not-a-hash",
        },
        controlled_template_version="2",
    ) is None
    assert _sanitize_psychology_learning_image_generation(
        {
            "status": "failed",
            "renderer": "ptsm_local_renderer",
            "carousel_style": "psychology_text_card_v1",
            "image_count": 7,
            "reason": "psychology_carousel_generation_failed",
            "private_error": "/tmp/page-03.png failed",
        },
        controlled_template_version="2",
    ) == {
        "status": "failed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "reason": "psychology_carousel_generation_failed",
    }


def _prepare_custom_learning_carousel_case(
    tmp_path: Path,
) -> tuple[PsychologyLearningSeriesStore, object, object, Path, dict[str, object]]:
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True)
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "learning-carousel.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return store, catalog, bundle, artifact_path, final_content


def test_learning_requested_carousel_advances_only_after_complete_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    store, catalog, bundle, artifact_path, final_content = (
        _prepare_custom_learning_carousel_case(tmp_path)
    )
    publisher = CapturingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["image_generation"] == {
        "status": "committed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "manifest_sha256": result["image_generation"]["manifest_sha256"],
    }
    assert len(publisher.received_image_paths) == 7
    assert publisher.received_image_evidence is not None
    assert [page["order"] for page in publisher.received_image_evidence] == list(
        range(1, 8)
    )
    assert all(Path(path).is_file() for path in publisher.received_image_paths)
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (bundle.lesson_id,)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["image_generation"] == result["image_generation"]
    assert "manifest_path" not in artifact["image_generation"]
    assert "generated_image_paths" not in artifact["image_generation"]
    assert "pages" not in artifact["image_generation"]
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [row["page_order"] for row in ledger_rows] == list(range(1, 8))
    assert [row["image_path"] for row in ledger_rows] == publisher.received_image_paths


def test_historic_v1_requested_image_keeps_single_card_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    store = PsychologyLearningSeriesStore(trusted_provision=True)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)

    def build_v1(proposal_value, *, curriculum_version: str):
        return psychology_learning_domain._build_confirmed_psychology_learning_catalog_for_template(
            proposal_value,
            curriculum_version=curriculum_version,
            controlled_template_version="1",
        )

    monkeypatch.setattr(
        psychology_learning_series_use_case,
        "_build_confirmed_psychology_learning_catalog",
        build_v1,
    )
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "historic-v1-card.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = CapturingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert bundle.runtime_contract["controlled_template_version"] == "1"
    assert "slides" not in final_content["image_plan"]
    assert result["status"] == "completed"
    assert result["image_generation"] == {
        "status": "generated",
        "renderer": "ptsm_local_renderer",
    }
    assert len(publisher.received_image_paths) == 1
    assert publisher.received_image_evidence is None
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["image_generation"] == result["image_generation"]


def test_learning_requested_carousel_failure_does_not_advance_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    store, catalog, bundle, artifact_path, final_content = (
        _prepare_custom_learning_carousel_case(tmp_path)
    )
    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )
    monkeypatch.setattr(
        ImageCarouselTransaction,
        "generate",
        lambda self, **kwargs: (_ for _ in ()).throw(
            ImageCarouselTransactionError("page 3 failed at /private/catalog.png")
        ),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert result["image_generation"] == {
        "status": "failed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": 7,
        "reason": "psychology_carousel_generation_failed",
    }
    assert publisher.calls == 0
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["image_generation"] == result["image_generation"]
    assert "/private/catalog.png" not in json.dumps(result, ensure_ascii=False)


def test_learning_requested_carousel_ledger_failure_does_not_advance_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    store, catalog, bundle, artifact_path, final_content = (
        _prepare_custom_learning_carousel_case(tmp_path)
    )
    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.append_generated_image_assets",
        lambda **_: (_ for _ in ()).throw(
            OSError("ledger failed at /private/generated/assets.jsonl")
        ),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert result["image_generation"]["status"] == "committed"
    assert set(result["image_generation"]) == {
        "status",
        "renderer",
        "carousel_style",
        "image_count",
        "manifest_sha256",
    }
    assert publisher.calls == 0
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    assert "/private/generated" not in json.dumps(result, ensure_ascii=False)


def test_learning_requested_carousel_publish_evidence_failure_does_not_advance_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    store, catalog, bundle, artifact_path, final_content = (
        _prepare_custom_learning_carousel_case(tmp_path)
    )
    publisher = EvidenceRejectingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: PsychologyCarouselWorkflow(artifact_path, final_content),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            auto_generate_images=True,
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_carousel_generation_failed"
    assert result["publish_result"] is None
    assert result["image_generation"]["status"] == "committed"
    assert set(result["image_generation"]) == {
        "status",
        "renderer",
        "carousel_style",
        "image_count",
        "manifest_sha256",
    }
    assert publisher.calls == 1
    assert publisher.received_image_evidence is not None
    assert [page["order"] for page in publisher.received_image_evidence] == list(
        range(1, 8)
    )
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    assert result["run"]["status"] == "psychology_carousel_generation_failed"
    assert "hash_mismatch" not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_requires_complete_psychology_learning_selection_before_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            scene="operator supplied https://example.com/raw-scene",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    serialized = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "psychology_learning_required"
    assert "https://example.com/raw-scene" not in serialized


def test_run_playbook_requires_an_explicit_psychology_learning_curriculum_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "psychology_learning_required"


def test_run_playbook_rejects_psychology_learning_flags_for_other_playbooks_before_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    raw_scene = "operator supplied https://example.com/free-claim"
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            scene=raw_scene,
            account_id="acct-daily-english-local",
            playbook_id="daily_english_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "psychology_learning_playbook_invalid"
    assert raw_scene not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_rejects_mismatched_psychology_learning_direction_before_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
                psychology_content_mode="learning_series",
                psychology_series_id="after_work_rumination",
                psychology_lesson_id="notice_the_loop",
                psychology_curriculum_version="1",
                topic_direction_id="psychology_learning_after_work_rumination_close_the_replay",
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "psychology_learning_topic_direction_invalid"


@pytest.mark.parametrize(
    "overrides",
    (
        {"local_image_style": "Smith_2024_Rumination_MetaAnalysis"},
        {
            "publish_image_paths": [
                "outputs/generated_images/Smith_2024_Rumination_MetaAnalysis.png"
            ]
        },
    ),
    ids=("local_style", "manual_image"),
)
def test_psychology_learning_preflight_rejects_operator_image_overrides(
    overrides: dict[str, object],
) -> None:
    request = PlaybookRequest(
        account_id="acct-psychology-local",
        playbook_id="modern_psychology_post",
        psychology_content_mode="learning_series",
        psychology_series_id="after_work_rumination",
        psychology_lesson_id="notice_the_loop",
        psychology_curriculum_version="1",
        topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        **overrides,
    )

    bundle, failure = _resolve_psychology_learning_preflight(
        request=request,
        platform="xiaohongshu",
        playbook_id="modern_psychology_post",
    )

    assert bundle is None
    assert failure == {
        "scene": "心理学学习专题",
        "platform": "xiaohongshu",
        "account_id": "acct-psychology-local",
        "playbook_id": "modern_psychology_post",
        "status": "psychology_learning_image_override_invalid",
        "diagnostic": "learning_series_uses_the_catalog_image_plan_only",
    }


def test_run_playbook_accepts_confirmed_custom_catalog_at_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    proposal_goal = "写下一次下班后的具体时刻"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "notice",
                "title": "先识别重复时刻",
                "goal": proposal_goal,
            },
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id=catalog.lessons[0].lesson_id,
        curriculum_version=catalog.curriculum_version,
    )
    assert bundle.catalog is not None
    request = PlaybookRequest(
        account_id="acct-psychology-local",
        playbook_id="modern_psychology_post",
        psychology_content_mode="learning_series",
        psychology_series_id=bundle.series_id,
        psychology_lesson_id=bundle.lesson_id,
        psychology_curriculum_version=catalog.curriculum_version,
        topic_direction_id=bundle.direction_id,
    )

    preflight_capability, failure = _resolve_psychology_learning_preflight(
        request=request,
        platform="xiaohongshu",
        playbook_id="modern_psychology_post",
    )

    assert preflight_capability is not None
    preflight_bundle = require_sealed_psychology_learning_preflight_bundle(
        preflight_capability
    )
    assert preflight_bundle == bundle
    assert failure is None
    assert proposal_goal not in json.dumps(preflight_bundle.model_dump(), ensure_ascii=False)


@pytest.mark.parametrize(
    "reserved_relative_path",
    (
        "proposals/proposal.json",
        "catalogs/series--v1.json",
        "confirmations/series--v1.json",
        "progress/series--v1.json",
        "progress/.series--v1.json.lock",
        "progress/.v1.json.pending.tmp",
    ),
)
def test_psychology_learning_artifact_ownership_excludes_every_catalog_store_descendant(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    reserved_relative_path: str,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact_store = FileArtifactStore()
    reserved_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "psychology-learning-series"
        / reserved_relative_path
    )
    reserved_path.parent.mkdir(parents=True, exist_ok=True)
    reserved_path.write_text("reserved", encoding="utf-8")

    assert _owned_psychology_learning_artifact_path(
        artifact_store=artifact_store,
        artifact_path=str(reserved_path),
    ) is None


def test_psychology_learning_artifact_ownership_rejects_missing_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    missing_path = tmp_path / "outputs" / "artifacts" / "not-created-yet.json"

    assert _owned_psychology_learning_artifact_path(
        artifact_store=FileArtifactStore(),
        artifact_path=str(missing_path),
    ) is None


def test_psychology_learning_artifact_ownership_preserves_parent_traversal_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact_store = FileArtifactStore()
    ordinary_path = tmp_path / "outputs" / "artifacts" / "ordinary.json"
    ordinary_path.parent.mkdir(parents=True, exist_ok=True)
    ordinary_path.write_text("{}", encoding="utf-8")
    inside_spelling = ordinary_path.parent / "nested" / ".." / ordinary_path.name
    outside_path = tmp_path / "outputs" / "outside.json"
    outside_path.write_text("{}", encoding="utf-8")
    outside_spelling = ordinary_path.parent / ".." / outside_path.name

    assert _owned_psychology_learning_artifact_path(
        artifact_store=artifact_store,
        artifact_path=str(inside_spelling),
    ) == ordinary_path
    assert _owned_psychology_learning_artifact_path(
        artifact_store=artifact_store,
        artifact_path=str(outside_spelling),
    ) is None


def test_psychology_learning_artifact_scope_prepares_fresh_builtin_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A first builtin lesson can freeze an artifact root before its workflow."""
    monkeypatch.chdir(tmp_path)

    scope = _capture_psychology_learning_artifact_scope(
        artifact_store=FileArtifactStore(),
    )

    assert scope is not None
    assert (tmp_path / "outputs" / "artifacts").is_dir()
    assert scope.reserved_catalog_root_identity is None


def test_psychology_learning_artifact_scope_rejects_catalog_created_after_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An absent catalog root is frozen too; it cannot appear mid-workflow."""
    monkeypatch.chdir(tmp_path)
    artifact_store = FileArtifactStore()
    scope = _capture_psychology_learning_artifact_scope(
        artifact_store=artifact_store,
    )
    assert scope is not None
    artifact_path = tmp_path / "outputs" / "artifacts" / "ordinary.json"
    artifact_path.write_text("{}", encoding="utf-8")
    (tmp_path / "outputs" / "artifacts" / "psychology-learning-series").mkdir()

    assert _owned_psychology_learning_artifact_path(
        artifact_store=artifact_store,
        artifact_path=str(artifact_path),
        scope=scope,
    ) is None


def test_psychology_learning_rejection_leaves_a_rebound_artifact_root_untouched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Rejected artifacts must not re-authorize a catalog after the root moves."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    artifact_store = FileArtifactStore()
    scope = _capture_psychology_learning_artifact_scope(
        artifact_store=artifact_store,
    )
    assert scope is not None
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    artifact_root.rename(former_artifact_root)
    catalog_parent = (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
    )
    former_snapshot_path = catalog_parent / snapshot_path.name
    artifact_root.symlink_to(catalog_parent, target_is_directory=True)
    rebound_artifact_path = artifact_root / snapshot_path.name

    _remove_owned_unsafe_psychology_learning_artifact(
        artifact_store=artifact_store,
        artifact_path=str(rebound_artifact_path),
        scope=scope,
    )

    assert former_snapshot_path.read_bytes() == snapshot_before


def test_psychology_learning_rejection_leaves_a_recreated_artifact_root_untouched(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A matching-looking replacement root cannot inherit old authority."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    artifact_store = FileArtifactStore()
    scope = _capture_psychology_learning_artifact_scope(
        artifact_store=artifact_store,
    )
    assert scope is not None
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    artifact_root.rename(former_artifact_root)
    artifact_root.mkdir()
    rebound_artifact_path = artifact_root / snapshot_path.name
    rebound_artifact_path.write_bytes(snapshot_before)

    _remove_owned_unsafe_psychology_learning_artifact(
        artifact_store=artifact_store,
        artifact_path=str(rebound_artifact_path),
        scope=scope,
    )

    assert rebound_artifact_path.read_bytes() == snapshot_before
    assert (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
        / snapshot_path.name
    ).read_bytes() == snapshot_before


def test_psychology_learning_rejection_fails_closed_on_rebound_root_symlink_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A looped artifact root cannot crash rejection or reach a catalog snapshot."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    artifact_store = FileArtifactStore()
    scope = _capture_psychology_learning_artifact_scope(
        artifact_store=artifact_store,
    )
    assert scope is not None
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    artifact_root.rename(former_artifact_root)
    artifact_root.symlink_to(artifact_root.name, target_is_directory=True)

    _remove_owned_unsafe_psychology_learning_artifact(
        artifact_store=artifact_store,
        artifact_path=str(artifact_root / snapshot_path.name),
        scope=scope,
    )

    assert (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
        / snapshot_path.name
    ).read_bytes() == snapshot_before


def test_run_playbook_draft_rejection_refuses_rebound_artifact_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An untrusted workflow cannot turn draft rejection into catalog deletion."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    catalog_parent = (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
    )

    class RebindingInvalidDraftWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            artifact_root.rename(former_artifact_root)
            artifact_root.symlink_to(catalog_parent, target_is_directory=True)
            return {
                "status": "completed",
                "artifact_path": str(artifact_root / snapshot_path.name),
                "final_content": {"title": "not the controlled learning draft"},
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: RebindingInvalidDraftWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_draft_invalid"
    assert (catalog_parent / snapshot_path.name).read_bytes() == snapshot_before


def test_builtin_learning_draft_rejection_refuses_rebound_root_with_custom_catalog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Builtin lessons share the custom catalog root and need the same guard."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    catalog_parent = (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
    )

    class RebindingBuiltinDraftWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            artifact_root.rename(former_artifact_root)
            artifact_root.symlink_to(catalog_parent, target_is_directory=True)
            return {
                "status": "completed",
                "artifact_path": str(artifact_root / snapshot_path.name),
                "final_content": {"title": "not the controlled learning draft"},
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: RebindingBuiltinDraftWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id=(
                "psychology_learning_after_work_rumination_notice_the_loop"
            ),
        ),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_draft_invalid"
    assert (catalog_parent / snapshot_path.name).read_bytes() == snapshot_before


@pytest.mark.parametrize(
    "swap_stage",
    ("initial_seal", "artifact_update", "post_publish_checks"),
)
def test_run_playbook_refuses_root_rebind_at_each_learning_artifact_stage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    swap_stage: str,
) -> None:
    """A root rebind cannot make catalog ``v1.json`` an artifact at any stage."""
    monkeypatch.chdir(tmp_path)
    private_goal = f"{swap_stage} 时不可泄露或删除的确认前学习目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    catalog_parent = (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
    )
    former_snapshot_path = catalog_parent / snapshot_path.name
    artifact_path = artifact_root / snapshot_path.name
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rebound = False

    def rebind_artifact_root() -> None:
        nonlocal rebound
        assert not rebound
        rebound = True
        artifact_root.rename(former_artifact_root)
        artifact_root.symlink_to(catalog_parent, target_is_directory=True)

    class RootRebindingWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            if swap_stage == "initial_seal":
                rebind_artifact_root()
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    class RootRebindingPublisher:
        def publish(self, **kwargs: object) -> dict[str, object]:
            if swap_stage == "artifact_update":
                rebind_artifact_root()
            return {
                "status": "published",
                "platform": "xiaohongshu",
                "provider": "root-rebinding-publisher",
                "artifact_path": kwargs["artifact_path"],
            }

    if swap_stage == "post_publish_checks":
        def check_then_rebind(**_: object) -> dict[str, object]:
            rebind_artifact_root()
            return {"status": "published", "source": "mcp"}

        monkeypatch.setattr(
            "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
            check_then_rebind,
        )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: RootRebindingWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            wait_for_publish_status=swap_stage == "post_publish_checks",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=RootRebindingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert rebound
    assert result["status"] == "psychology_learning_artifact_invalid"
    assert former_snapshot_path.read_bytes() == snapshot_before
    assert PsychologyLearningSeriesStore(
        catalog_root=former_artifact_root / "psychology-learning-series"
    ).read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized
    assert snapshot_before.decode("utf-8") not in serialized


def test_run_playbook_does_not_mark_custom_progress_after_eval_rebinds_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A scope change during eval invalidates the run before progress is written."""
    monkeypatch.chdir(tmp_path)
    private_goal = "eval 重绑根目录时不能推进的确认前学习目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    artifact_path = artifact_root / "eval-rebind.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    rebound = False

    def eval_then_rebind(**kwargs: object) -> dict[str, object]:
        nonlocal rebound
        eval_artifact_payload = kwargs.get("artifact_payload")
        assert isinstance(eval_artifact_payload, dict)
        assert private_goal not in json.dumps(eval_artifact_payload, ensure_ascii=False)
        assert not rebound
        rebound = True
        artifact_root.rename(former_artifact_root)
        artifact_root.symlink_to(former_artifact_root, target_is_directory=True)
        return {"status": "passed"}

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook._run_eval_on_artifact",
        eval_then_rebind,
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
        eval_enabled=True,
    )

    assert rebound
    assert result["status"] == "psychology_learning_artifact_invalid"
    assert (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
        / snapshot_path.name
    ).read_bytes() == snapshot_before
    with pytest.raises(OSError, match="storage root changed"):
        store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        )
    assert PsychologyLearningSeriesStore(
        catalog_root=former_artifact_root / "psychology-learning-series"
    ).read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    assert private_goal not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_custom_learning_uses_preflight_bundle_after_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Post-publish strict checks, eval, and progress reuse the frozen bundle."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "frozen-bundle.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    resolver_frozen = False

    def reject_catalog_resolution(**_: object) -> object:
        pytest.fail("post-preflight code must not resolve the mutable catalog path")

    class ResolverFreezingPublisher:
        def publish(self, **kwargs: object) -> dict[str, object]:
            nonlocal resolver_frozen
            assert not resolver_frozen
            resolver_frozen = True
            monkeypatch.setattr(
                psychology_learning_domain,
                "resolve_psychology_learning_selection",
                reject_catalog_resolution,
            )
            monkeypatch.setattr(
                contracts_eval,
                "resolve_psychology_learning_selection",
                reject_catalog_resolution,
            )
            return {
                "status": "dry_run",
                "platform": "xiaohongshu",
                "provider": "frozen-bundle-publisher",
                "artifact_path": kwargs["artifact_path"],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=ResolverFreezingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
        eval_enabled=True,
    )

    assert resolver_frozen
    assert result["eval"] is not None
    assert result["status"] == "completed", result
    assert result["eval"]["status"] == "passed", result["eval"]
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (bundle.lesson_id,)


def test_run_playbook_does_not_mark_progress_when_storage_rebinds_at_mark(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The progress store must recheck the frozen roots at its own entrypoint."""
    monkeypatch.chdir(tmp_path)
    private_goal = "写入进度前重绑目录时不可推进的确认前学习目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    artifact_path = artifact_root / "progress-rebind.json"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    original_mark = PsychologyLearningSeriesStore.mark_production_lesson_completed
    rebound = False

    def rebind_then_mark(
        self: PsychologyLearningSeriesStore,
        **kwargs: object,
    ) -> object:
        nonlocal rebound
        assert not rebound
        rebound = True
        artifact_root.rename(former_artifact_root)
        artifact_root.symlink_to(former_artifact_root, target_is_directory=True)
        return original_mark(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )
    monkeypatch.setattr(
        PsychologyLearningSeriesStore,
        "mark_production_lesson_completed",
        rebind_then_mark,
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert rebound
    assert result["status"] == "psychology_learning_progress_persist_failed"
    assert (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
        / snapshot_path.name
    ).read_bytes() == snapshot_before
    with pytest.raises(OSError, match="storage root changed"):
        store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        )
    assert PsychologyLearningSeriesStore(
        catalog_root=former_artifact_root / "psychology-learning-series"
    ).read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    assert private_goal not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_rejects_a_progress_directory_rebind_after_preflight(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A protected run must not reopen a replacement progress directory."""
    monkeypatch.chdir(tmp_path)
    private_goal = "预检后重绑进度目录时不可推进的确认前学习目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True)
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=("practice",),
    )
    artifact_root = tmp_path / "outputs" / "artifacts"
    catalog_root = artifact_root / "psychology-learning-series"
    progress_path = psychology_learning_series_progress_sidecar_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        catalog_root=catalog_root,
    )
    former_progress_directory = tmp_path / "former-progress"
    artifact_path = artifact_root / "progress-directory-rebind.json"
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    rebound = False

    class ProgressRebindingWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            nonlocal rebound
            assert not rebound
            rebound = True
            (catalog_root / "progress").rename(former_progress_directory)
            (catalog_root / "progress").mkdir(mode=0o700)
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ProgressRebindingWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert rebound
    assert result["status"] == "psychology_learning_progress_persist_failed"
    assert not progress_path.exists()
    former_progress_path = former_progress_directory / progress_path.name
    assert former_progress_path.is_file()
    assert json.loads(former_progress_path.read_text(encoding="utf-8"))["completed_lesson_ids"] == [
        "practice"
    ]
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized


def test_learning_post_publish_helpers_use_only_in_memory_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Learning helpers must not reopen a mutable artifact after publication."""
    monkeypatch.chdir(tmp_path)
    artifact_path = tmp_path / "outputs" / "artifacts" / "v1.json"
    artifact_path.parent.mkdir(parents=True)
    final_content = _valid_psychology_learning_draft()
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    class NonMappingPublisher:
        def publish(self, **_: object) -> object:
            return None

    status_calls: list[dict[str, object]] = []
    browser_calls: list[dict[str, object]] = []

    def capture_status(**kwargs: object) -> dict[str, object]:
        status_calls.append(dict(kwargs))
        return {"status": "manual_check_required", "source": "mcp"}

    def capture_browser(**kwargs: object) -> dict[str, object]:
        browser_calls.append(dict(kwargs))
        return {
            "status": "opened",
            "target": kwargs["target"],
            "destination": "https://creator.xiaohongshu.com/publish/publish",
        }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidLearningWorkflow(),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
        capture_status,
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.open_xhs_browser",
        capture_browser,
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            wait_for_publish_status=True,
            open_browser_if_needed=True,
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        publisher=NonMappingPublisher(),  # type: ignore[arg-type]
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert status_calls[0]["publish_result"] == {}
    assert browser_calls[0]["target"] == "creator"
    assert "artifact_path" not in browser_calls[0]


def test_builtin_learning_evaluates_before_run_summary_can_rebind_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Builtin eval must complete while its frozen root is still intact."""
    monkeypatch.chdir(tmp_path)
    private_goal = "builtin eval 不得读取的确认前学习目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    catalog_store = PsychologyLearningSeriesStore(trusted_provision=True, )
    catalog_store.persist_proposal(proposal)
    catalog = catalog_store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    bundle = resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id="notice_the_loop",
        curriculum_version="1",
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_root = tmp_path / "outputs" / "artifacts"
    former_artifact_root = tmp_path / "outputs" / "former-artifacts"
    catalog_parent = (
        former_artifact_root
        / "psychology-learning-series"
        / "catalogs"
    )
    artifact_path = artifact_root / snapshot_path.name
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidBuiltinLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    run_store = RunStore(base_dir=tmp_path / "runs")
    original_finish = run_store.finish
    rebound = False

    def finish_then_rebind(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal rebound
        summary = original_finish(*args, **kwargs)
        if not rebound:
            rebound = True
            artifact_root.rename(former_artifact_root)
            artifact_root.symlink_to(catalog_parent, target_is_directory=True)
        return summary

    eval_called = False
    eval_saw_rebound: bool | None = None

    def eval_before_rebind(**kwargs: object) -> dict[str, object]:
        nonlocal eval_called, eval_saw_rebound
        eval_artifact_payload = kwargs.get("artifact_payload")
        assert isinstance(eval_artifact_payload, dict)
        assert private_goal not in json.dumps(eval_artifact_payload, ensure_ascii=False)
        eval_called = True
        eval_saw_rebound = rebound
        return {"status": "passed"}

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidBuiltinLearningWorkflow(),
    )
    monkeypatch.setattr(run_store, "finish", finish_then_rebind)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook._run_eval_on_artifact",
        eval_before_rebind,
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id=(
                "psychology_learning_after_work_rumination_notice_the_loop"
            ),
        ),
        publisher=SuccessfulPublisher(),
        run_store=run_store,
        eval_enabled=True,
    )

    assert rebound
    assert result["status"] == "completed"
    assert eval_called
    assert eval_saw_rebound is False
    assert (catalog_parent / snapshot_path.name).read_bytes() == snapshot_before
    assert private_goal not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_preserves_custom_catalog_snapshot_when_workflow_returns_it_as_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An immutable catalog snapshot is never an owned workflow artifact."""
    monkeypatch.chdir(tmp_path)
    private_goal = "确认前私有目标，不得在失败响应中泄露"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)

    class SnapshotReturningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(snapshot_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: SnapshotReturningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_artifact_invalid"
    assert result["psychology_learning_artifact_validation"] == {
        "error": "learning artifact failed ownership or provenance validation"
    }
    assert snapshot_path.read_bytes() == snapshot_before
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    ) == bundle
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized
    assert snapshot_before.decode("utf-8") not in serialized


def test_run_playbook_leaves_an_unsafe_symlink_for_offline_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A rejected learning symlink remains for offline cleanup without touching its target."""
    monkeypatch.chdir(tmp_path)
    private_goal = "普通 artifact 目标中的私有目标不得被读取或删除"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    ordinary_artifact_path = tmp_path / "outputs" / "artifacts" / "ordinary-artifact.json"
    ordinary_artifact_path.parent.mkdir(parents=True, exist_ok=True)
    ordinary_artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
                "private_goal": private_goal,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ordinary_before = ordinary_artifact_path.read_bytes()
    artifact_path = tmp_path / "outputs" / "artifacts" / "learning-artifact.json"
    artifact_path.symlink_to(ordinary_artifact_path.resolve())

    class SymlinkReturningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: SymlinkReturningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_artifact_invalid"
    assert ordinary_artifact_path.read_bytes() == ordinary_before
    assert artifact_path.is_symlink()
    assert snapshot_path.read_bytes() == snapshot_before
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    ) == bundle
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized


def test_run_playbook_preserves_custom_catalog_snapshot_through_case_alias(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Case-insensitive filesystems must not turn the store into an artifact."""
    monkeypatch.chdir(tmp_path)
    private_goal = "大小写别名不得泄露确认前私有目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    alias_parts = list(snapshot_path.parts)
    alias_parts[alias_parts.index("psychology-learning-series")] = (
        "PSYCHOLOGY-LEARNING-SERIES"
    )
    alias_snapshot_path = Path(*alias_parts)
    try:
        alias_is_snapshot = alias_snapshot_path.exists() and os.path.samefile(
            alias_snapshot_path,
            snapshot_path,
        )
    except OSError:
        alias_is_snapshot = False
    if not alias_is_snapshot:
        pytest.skip("filesystem does not resolve a case-varied catalog-store alias")

    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)

    class AliasSnapshotReturningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(alias_snapshot_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: AliasSnapshotReturningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_artifact_invalid"
    assert snapshot_path.read_bytes() == snapshot_before
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    ) == bundle
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert snapshot_before.decode("utf-8") not in serialized


def test_run_playbook_rechecks_ownership_before_replacing_learning_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A post-read symlink swap cannot redirect envelope replacement to the store."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "replace-target.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class NormalArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    original_read_with_identity = FileArtifactStore.read_with_identity
    original_artifact_path = artifact_path.resolve()
    swapped = False

    def read_then_swap(
        self: FileArtifactStore,
        path: Path | str,
        *,
        expected_parent_identity: os.stat_result | None = None,
    ) -> tuple[dict[str, object], object]:
        nonlocal swapped
        payload = original_read_with_identity(
            self,
            path,
            expected_parent_identity=expected_parent_identity,
        )
        if not swapped and Path(path).resolve() == original_artifact_path:
            swapped = True
            artifact_path.unlink()
            artifact_path.symlink_to(snapshot_path.resolve())
        return payload

    monkeypatch.setattr(FileArtifactStore, "read_with_identity", read_then_swap)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: NormalArtifactWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert swapped
    assert result["status"] == "psychology_learning_artifact_invalid"
    assert snapshot_path.read_bytes() == snapshot_before
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    ) == bundle
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()


def test_run_playbook_rejects_catalog_swap_at_learning_artifact_replace_entry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A swap after ownership recheck still cannot seal over a catalog snapshot."""
    monkeypatch.chdir(tmp_path)
    private_goal = "replace 入口换链时也不能泄露确认前私有目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "replace-entry-target.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class NormalArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    original_replace = FileArtifactStore.replace
    swapped = False

    def replace_then_swap(
        self: FileArtifactStore,
        path: Path | str,
        payload: dict[str, object],
        **kwargs: object,
    ) -> Path:
        nonlocal swapped
        if not swapped and Path(path) == artifact_path:
            swapped = True
            artifact_path.unlink()
            artifact_path.symlink_to(snapshot_path.resolve())
        return original_replace(self, path, payload, **kwargs)

    monkeypatch.setattr(FileArtifactStore, "replace", replace_then_swap)
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: NormalArtifactWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert swapped
    assert result["status"] == "psychology_learning_artifact_invalid"
    assert snapshot_path.read_bytes() == snapshot_before
    assert resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    ) == bundle
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized
    assert snapshot_before.decode("utf-8") not in serialized


@pytest.mark.parametrize(
    ("swap_stage", "link_kind"),
    (
        ("artifact_update", "symlink"),
        ("post_publish_checks", "symlink"),
        ("artifact_update", "hardlink"),
    ),
)
def test_run_playbook_rejects_catalog_swap_before_each_post_publish_learning_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    swap_stage: str,
    link_kind: str,
) -> None:
    """Neither post-publish receipt update may read or write a catalog snapshot."""
    monkeypatch.chdir(tmp_path)
    private_goal = f"{swap_stage}-{link_kind} 换链时也不能泄露确认前私有目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_path = psychology_learning_series_catalog_snapshot_path(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    snapshot_before = snapshot_path.read_bytes()
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = (
        tmp_path / "outputs" / "artifacts" / f"{swap_stage}-{link_kind}-target.json"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class NormalArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    swapped = False

    def swap_artifact_to_snapshot() -> None:
        nonlocal swapped
        assert not swapped
        swapped = True
        artifact_path.unlink()
        if link_kind == "symlink":
            artifact_path.symlink_to(snapshot_path.resolve())
        else:
            os.link(snapshot_path, artifact_path)

    class PostPublishSwappingPublisher:
        def publish(self, **kwargs: object) -> dict[str, object]:
            if swap_stage == "artifact_update":
                swap_artifact_to_snapshot()
            return {
                "status": "published",
                "platform": "xiaohongshu",
                "provider": "post-publish-swapper",
                "artifact_path": kwargs["artifact_path"],
            }

    if swap_stage == "post_publish_checks":
        def check_then_swap(**_: object) -> dict[str, object]:
            swap_artifact_to_snapshot()
            return {"status": "published", "source": "mcp"}

        monkeypatch.setattr(
            "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
            check_then_swap,
        )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: NormalArtifactWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            wait_for_publish_status=swap_stage == "post_publish_checks",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=PostPublishSwappingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert swapped
    assert result["status"] == "psychology_learning_artifact_invalid"
    assert snapshot_path.read_bytes() == snapshot_before
    if link_kind == "hardlink":
        # Runtime cleanup is deliberately forbidden: the unsafe hard link stays
        # for a trusted offline operator, and its second link makes the immutable
        # catalog fail closed until that operator removes the residue.
        assert artifact_path.exists()
        assert os.path.samestat(artifact_path.stat(), snapshot_path.stat())
        with pytest.raises(ValueError, match="catalog revision history"):
            resolve_psychology_learning_selection(
                series_id=catalog.series_id,
                lesson_id="notice",
                curriculum_version=catalog.curriculum_version,
            )
        with pytest.raises(ValueError, match="catalog revision history"):
            store.read_production_progress(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
            )
    else:
        assert resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
        ) == bundle
        assert store.read_production_progress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
        ).completed_lesson_ids == ()
    serialized = json.dumps(result, ensure_ascii=False)
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized
    assert snapshot_before.decode("utf-8") not in serialized


def test_run_playbook_completes_a_confirmed_custom_lesson_and_marks_production_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    private_goal = "只在第一次确认前可见的私人目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "notice",
                "title": "先识别重复时刻",
                "goal": private_goal,
            },
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    expected_catalog_receipt = build_psychology_learning_catalog_receipt(bundle)
    assert expected_catalog_receipt is not None
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "custom-learning-artifact.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    workflow_arguments: dict[str, object] = {}

    def build_workflow(**kwargs: object) -> ValidCustomLearningWorkflow:
        workflow_arguments.update(kwargs)
        return ValidCustomLearningWorkflow()

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )

    result = run_playbook(
        PlaybookRequest(
            scene="operator supplied scene must not be used",
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert workflow_arguments["psychology_learning_catalog_receipt"] == expected_catalog_receipt
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["psychology_learning_catalog_receipt"] == expected_catalog_receipt
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (bundle.lesson_id,)
    serialized = json.dumps(
        {"artifact": artifact, "response": result, "workflow": workflow_arguments},
        ensure_ascii=False,
        default=str,
    )
    assert private_goal not in serialized
    assert proposal.proposal_id not in serialized
    assert str(store.catalog_root) not in serialized


def test_run_playbook_rejects_a_post_envelope_tampered_custom_lesson_without_progress(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The final strict check is authoritative even when offline eval is disabled."""
    monkeypatch.chdir(tmp_path)
    private_goal = "只在确认前可见的私人目标"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "notice",
                "title": "先识别重复时刻",
                "goal": private_goal,
            },
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "tampered-custom-learning.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    class PostEnvelopeMutatingPublisher:
        def publish(self, **kwargs: object) -> dict[str, object]:
            persisted_path = Path(str(kwargs["artifact_path"]))
            artifact = json.loads(persisted_path.read_text(encoding="utf-8"))
            artifact["psychology_learning_mode"] = "not-learning-series"
            artifact["psychology_learning_gate"] = {
                **artifact["psychology_learning_gate"],
                "status": "failed",
            }
            persisted_path.write_text(
                json.dumps(artifact, ensure_ascii=False),
                encoding="utf-8",
            )
            return {
                "status": "published",
                "platform": "xiaohongshu",
                "provider": "post-envelope-mutator",
                "artifact_path": str(persisted_path),
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=PostEnvelopeMutatingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_artifact_invalid"
    assert result["psychology_learning_artifact_validation"] == {
        "error": "learning artifact failed final provenance validation"
    }
    assert artifact_path.exists()
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()
    assert private_goal not in json.dumps(result, ensure_ascii=False)


def test_run_playbook_does_not_mark_custom_progress_when_eval_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "custom-learning-eval.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook._run_eval_on_artifact",
        lambda **_: {"status": "failed", "gate": {"required_failed": 1}},
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
        eval_enabled=True,
    )

    assert result["status"] == "psychology_learning_eval_failed"
    assert result["eval"] == {"status": "failed", "gate": {"required_failed": 1}}
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == ()


def test_run_playbook_marks_custom_progress_after_a_sanitized_publish_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Publishing is not the production-completion authority for a safe lesson."""
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "custom-learning-publish.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id=bundle.series_id,
            psychology_lesson_id=bundle.lesson_id,
            psychology_curriculum_version=catalog.curriculum_version,
            topic_direction_id=bundle.direction_id,
        ),
        publisher=FailingPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "completed"
    assert result["publish_result"] == {"status": "error"}
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (bundle.lesson_id,)
    serialized = json.dumps(result, ensure_ascii=False)
    assert "publisher login required" not in serialized


def test_run_playbook_retries_a_custom_progress_mark_after_storage_recovers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    final_content = render_psychology_learning_draft(bundle.runtime_contract)
    artifact_path = tmp_path / "outputs" / "artifacts" / "custom-learning-retry.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidCustomLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    original_mark = PsychologyLearningSeriesStore.mark_production_lesson_completed
    attempts = 0

    def fail_once_then_mark(
        self: PsychologyLearningSeriesStore,
        **kwargs: object,
    ):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise OSError("private progress storage failure")
        return original_mark(self, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidCustomLearningWorkflow(),
    )
    monkeypatch.setattr(
        PsychologyLearningSeriesStore,
        "mark_production_lesson_completed",
        fail_once_then_mark,
    )
    request = PlaybookRequest(
        account_id="acct-psychology-local",
        playbook_id="modern_psychology_post",
        psychology_content_mode="learning_series",
        psychology_series_id=bundle.series_id,
        psychology_lesson_id=bundle.lesson_id,
        psychology_curriculum_version=catalog.curriculum_version,
        topic_direction_id=bundle.direction_id,
    )

    first = run_playbook(
        request,
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs-first"),
    )
    second = run_playbook(
        request,
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs-second"),
    )

    assert first["status"] == "psychology_learning_progress_persist_failed"
    assert first["psychology_learning_progress"] == {
        "status": "not_recorded",
        "reason": "production_progress_persist_failed",
    }
    assert "private progress storage failure" not in json.dumps(first, ensure_ascii=False)
    assert second["status"] == "completed"
    assert attempts == 2
    assert store.read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    ).completed_lesson_ids == (bundle.lesson_id,)


def test_run_playbook_binds_psychology_learning_contract_without_free_scene_or_sources(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    final_content = _valid_psychology_learning_draft()
    artifact_path = tmp_path / "outputs" / "artifacts" / "learning-artifact.json"
    artifact_path.parent.mkdir(parents=True)
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
                "activated_skill_details": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidLearningWorkflow:
        def __init__(self) -> None:
            self.payload: dict[str, object] | None = None

        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            self.payload = payload
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    workflow = ValidLearningWorkflow()
    workflow_build_arguments: dict[str, object] = {}

    def build_workflow(**kwargs: object) -> ValidLearningWorkflow:
        workflow_build_arguments.update(kwargs)
        return workflow

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        build_workflow,
    )
    monkeypatch.chdir(tmp_path)
    raw_scene = "operator supplied https://example.com/raw-scene by Example Author"

    result = run_playbook(
        PlaybookRequest(
            scene=raw_scene,
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
                psychology_content_mode="learning_series",
                psychology_series_id="after_work_rumination",
                psychology_lesson_id="notice_the_loop",
                psychology_curriculum_version="1",
                topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        publisher=SuccessfulPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    bundle = _psychology_learning_bundle()
    assert result["status"] == "completed"
    assert workflow.payload is not None
    assert raw_scene not in json.dumps(workflow.payload, ensure_ascii=False)
    assert "psychology_content_mode" not in workflow.payload
    assert "psychology_series_id" not in workflow.payload
    assert "psychology_lesson_id" not in workflow.payload
    assert workflow_build_arguments["psychology_learning_contract"] == bundle.runtime_contract
    assert workflow_build_arguments["psychology_learning_manifest"] == bundle.manifest
    assert "source_refs" not in json.dumps(
        workflow_build_arguments["psychology_learning_contract"], ensure_ascii=False
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["psychology_learning_series_id"] == "after_work_rumination"
    assert artifact["psychology_learning_lesson_id"] == "notice_the_loop"
    assert artifact["psychology_learning_evidence_manifest"] == bundle.manifest
    assert raw_scene not in json.dumps(artifact, ensure_ascii=False)


def test_run_playbook_leaves_an_unsafe_psychology_learning_artifact_for_offline_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "outputs" / "artifacts" / "unsafe-learning-artifact.json"
    artifact_path.parent.mkdir(parents=True)
    raw_url = "https://private.example.com/psychology-source"
    final_content = _valid_psychology_learning_draft()
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
                "source_url": raw_url,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class UnsafeLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: UnsafeLearningWorkflow(),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-local",
            playbook_id="modern_psychology_post",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "psychology_learning_artifact_invalid"
    assert publisher.calls == 0
    assert artifact_path.exists()


def test_run_playbook_persists_only_sanitized_learning_publish_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "outputs" / "artifacts" / "learning-artifact.json"
    artifact_path.parent.mkdir(parents=True)
    final_content = _valid_psychology_learning_draft()
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "final_content": final_content,
                "activated_skill_details": [],
                "provider_message": "Untrusted custom workflow message",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class ValidLearningWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": final_content,
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    class RawMetadataPublisher:
        def publish(self, **_: object) -> dict[str, object]:
            return {
                "status": "Smith_2024_Rumination_MetaAnalysis",
                "platform": "xiaohongshu",
                "provider": "xiaohongshu_mcp",
                "post_id": "note-123",
                "post_url": "https://www.xiaohongshu.com/explore/note-123",
                "server_url": "http://127.0.0.1:18060/mcp",
                "raw_response": "APA Rumination Study by Author",
                "preflight": {"tools": ["publish_content"], "login_status": "ready"},
                "platform_payload": {"title": "untrusted provider payload"},
            }

    class AccountWithPublisherEndpoint:
        def get(self, account_id: str) -> AccountProfile:
            assert account_id == "acct-psychology-learning"
            return AccountProfile(
                account_id=account_id,
                nickname="心理学习实验号",
                platform="xiaohongshu",
                domain="现代心理困境观察",
                publish_mode="mcp-real",
                publisher_server_url="http://127.0.0.1:18060/mcp",
            )

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ValidLearningWorkflow(),
    )
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.check_xhs_publish_status",
        lambda **_: {
            "status": "Smith_2024_Rumination_MetaAnalysis",
            "source": "mcp_search",
            "post_id": "note-123",
            "post_url": "https://www.xiaohongshu.com/explore/note-123",
            "xsec_token": "private-status-token",
        },
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-psychology-learning",
            playbook_id="modern_psychology_post",
            publish_mode="mcp-real",
            auto_generate_images=False,
            wait_for_publish_status=True,
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
            psychology_curriculum_version="1",
            topic_direction_id="psychology_learning_after_work_rumination_notice_the_loop",
        ),
        accounts=AccountWithPublisherEndpoint(),  # type: ignore[arg-type]
        publisher=RawMetadataPublisher(),
        run_store=RunStore(base_dir=tmp_path / "runs"),
        eval_enabled=True,
    )

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    serialized_artifact = json.dumps(artifact, ensure_ascii=False)
    serialized_response = json.dumps(result, ensure_ascii=False)
    serialized_run_summary = json.dumps(result["run"], ensure_ascii=False)
    serialized_run_events = (Path(result["run"]["events_path"])).read_text(
        encoding="utf-8"
    )
    serialized_side_effect_ledger = (
        tmp_path / ".ptsm" / "agent_runtime" / "side-effects.json"
    ).read_text(encoding="utf-8")

    assert result["status"] == "completed"
    assert result["publish_result"] == {"status": "unknown"}
    assert result["post_publish_checks"] == {
        "requested": True,
        "browser_opened": False,
        "publish_status": "unknown",
        "status_result": {
            "status": "unknown",
            "source": "mcp_search",
        },
    }
    assert result["eval"]["status"] == "passed"
    assert artifact["account"] == {
        "account_id": "acct-psychology-learning",
        "platform": "xiaohongshu",
    }
    assert artifact["topic_selection"] == {
        "source": "psychology-learning-series",
        "psychology_learning": {
            "series_id": "after_work_rumination",
            "curriculum_version": "1",
            "lesson_id": "notice_the_loop",
            "lesson_number": 1,
        },
    }
    assert artifact["publish_result"] == {
        "status": "unknown",
    }
    assert artifact["post_publish_checks"] == {
        "requested": True,
        "browser_opened": False,
        "publish_status": "unknown",
        "status_result": {
            "status": "unknown",
            "source": "mcp_search",
        },
    }
    for raw_value in (
        "127.0.0.1:18060",
        "APA Rumination Study by Author",
        "Smith_2024_Rumination_MetaAnalysis",
        "private-status-token",
        "untrusted provider payload",
        "Untrusted custom workflow message",
    ):
        assert raw_value not in serialized_artifact
        assert raw_value not in serialized_response
        assert raw_value not in serialized_run_summary
        assert raw_value not in serialized_run_events
        assert raw_value not in serialized_side_effect_ledger


@pytest.mark.parametrize(
    "topic_direction_id",
    ("missing-ai-direction", "ai_prompt_context_card"),
)
def test_run_playbook_rejects_unknown_or_wrong_mode_ai_topic_direction_before_starting(
    monkeypatch: pytest.MonkeyPatch,
    topic_direction_id: str,
) -> None:
    class NoRunStart:
        def start(self, **_: object) -> object:
            raise AssertionError("RunStore.start must not be called")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: pytest.fail("workflow must not be built"),
    )

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
            topic_direction_id=topic_direction_id,
        ),
        run_store=NoRunStart(),  # type: ignore[arg-type]
    )

    assert result["status"] == "ai_tech_topic_direction_invalid"
    assert result["diagnostic"] == "unknown_or_mode_mismatched_topic_direction"


def test_run_playbook_rejects_custom_ai_artifact_with_raw_provenance_before_merge_or_publish(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "outputs" / "artifacts" / "foreign-ai-artifact.json"
    artifact_path.parent.mkdir(parents=True)
    raw_url = "https://example.com/release"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "ai_tech_daily_post",
                "raw_source_url": raw_url,
                "source_title": "Example 模型发布原始标题",
                "author": "Example Author",
                "feed_id": "feed-secret-7",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class UnsafeArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(artifact_path),
                "final_content": {
                    "title": "AI 科技三条更新",
                    "image_text": "今天该看哪三件事",
                    "body": (
                        "模型发布：产品发布了新的推理模型。\n"
                        "开发者工具：开发者工具新增了批量处理能力。\n"
                        "行业应用：功能面向团队协作场景开放。"
                    ),
                    "hashtags": ["#AI资讯"],
                },
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: UnsafeArtifactWorkflow(),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "ai_tech_artifact_invalid"
    assert publisher.calls == 0
    persisted = artifact_path.read_text(encoding="utf-8")
    assert raw_url in persisted
    assert "ai_tech_evidence_manifest" not in persisted


def test_run_playbook_rejects_custom_ai_artifact_outside_owned_artifact_store(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    foreign_artifact_path = tmp_path / "foreign-ai-artifact.json"
    foreign_artifact_path.write_text(
        json.dumps({"playbook_id": "ai_tech_daily_post"}, ensure_ascii=False),
        encoding="utf-8",
    )

    class ForeignArtifactWorkflow:
        def invoke(
            self,
            payload: dict[str, object],
            config: dict[str, object] | None = None,
        ) -> dict[str, object]:
            return {
                "status": "completed",
                "artifact_path": str(foreign_artifact_path),
                "final_content": {
                    "title": "AI 科技三条更新",
                    "image_text": "今天该看哪三件事",
                    "body": (
                        "模型发布：产品发布了新的推理模型。\n"
                        "开发者工具：开发者工具新增了批量处理能力。\n"
                        "行业应用：功能面向团队协作场景开放。"
                    ),
                    "hashtags": ["#AI资讯"],
                },
                "runtime_skill_contents": [],
                "activated_skills": [],
                "activated_skill_details": [],
                "runtime_skill_details": [],
            }

    publisher = CountingPublisher()
    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_playbook_workflow",
        lambda **_: ForeignArtifactWorkflow(),
    )
    monkeypatch.chdir(tmp_path)

    result = run_playbook(
        PlaybookRequest(
            account_id="acct-ai-tech-local",
            playbook_id="ai_tech_daily_post",
            ai_content_mode="news_brief",
            ai_evidence_bundle=_valid_ai_news_brief_bundle(),
        ),
        publisher=publisher,
        run_store=RunStore(base_dir=tmp_path / "runs"),
    )

    assert result["status"] == "ai_tech_artifact_invalid"
    assert publisher.calls == 0
    assert "ai_tech_evidence_manifest" not in foreign_artifact_path.read_text(
        encoding="utf-8"
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
