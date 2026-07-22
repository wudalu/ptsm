from __future__ import annotations

import json
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ptsm.agent_runtime.runtime import build_playbook_workflow
from ptsm.config.settings import Settings
from ptsm.domain.ai_tech_content import parse_ai_tech_evidence_bundle
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.memory.store import InMemoryExecutionMemory


class CapturingDraftAgent:
    provider_name = "capturing"

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return {
            "title": "AI 科技三条更新",
            "image_text": "今天该看哪三件事",
            "body": (
                "模型发布：产品发布了新的推理模型。\n"
                "开发者工具：开发者工具新增了批量处理能力。\n"
                "行业应用：功能面向团队协作场景开放。"
            ),
            "hashtags": ["#AI资讯"],
        }


def _settings() -> Settings:
    return Settings.model_construct(
        default_model_provider="deterministic",
        default_model="deterministic",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
        xhs_mcp_server_url="http://localhost:18060/mcp",
    )


def _news_contract() -> dict[str, object]:
    return parse_ai_tech_evidence_bundle(
        {
            "mode": "news_brief",
            "news_items": [
                {
                    "label": "模型发布",
                    "event_fingerprint": "event-model-001",
                    "facts": ["产品发布了新的推理模型。"],
                    "source_refs": ["official-001"],
                },
                {
                    "label": "开发者工具",
                    "event_fingerprint": "event-tools-002",
                    "facts": ["开发者工具新增了批量处理能力。"],
                    "source_refs": ["official-002"],
                },
                {
                    "label": "行业应用",
                    "event_fingerprint": "event-industry-003",
                    "facts": ["功能面向团队协作场景开放。"],
                    "source_refs": ["official-003"],
                },
            ],
        }
    ).runtime_contract


def _news_manifest() -> dict[str, object]:
    return parse_ai_tech_evidence_bundle(
        {
            "mode": "news_brief",
            "news_items": [
                {
                    "label": "模型发布",
                    "event_fingerprint": "event-model-001",
                    "facts": ["产品发布了新的推理模型。"],
                    "source_refs": ["official-001"],
                },
                {
                    "label": "开发者工具",
                    "event_fingerprint": "event-tools-002",
                    "facts": ["开发者工具新增了批量处理能力。"],
                    "source_refs": ["official-002"],
                },
                {
                    "label": "行业应用",
                    "event_fingerprint": "event-industry-003",
                    "facts": ["功能面向团队协作场景开放。"],
                    "source_refs": ["official-003"],
                },
            ],
        }
    ).manifest.model_dump(mode="json")


def test_ai_workflow_requires_a_valid_bound_evidence_contract() -> None:
    with pytest.raises(ValueError, match="requires a normalized AI evidence contract"):
        build_playbook_workflow(
            playbook_id="ai_tech_daily_post",
            domain="AI科技资讯",
            settings=_settings(),
        )

    with pytest.raises(ValueError, match="invalid normalized AI evidence contract"):
        build_playbook_workflow(
            playbook_id="ai_tech_daily_post",
            domain="AI科技资讯",
            settings=_settings(),
            ai_tech_evidence={"mode": "news_brief"},
            ai_tech_evidence_manifest=_news_manifest(),
        )

    with pytest.raises(ValueError, match="requires an opaque AI evidence manifest"):
        build_playbook_workflow(
            playbook_id="ai_tech_daily_post",
            domain="AI科技资讯",
            settings=_settings(),
            ai_tech_evidence=_news_contract(),
        )


def test_ai_workflow_drops_unbound_input_evidence_before_checkpoint_and_executor(
    tmp_path: Path,
) -> None:
    checkpointer = InMemorySaver()
    memory = InMemoryExecutionMemory()
    drafting_agent = CapturingDraftAgent()
    workflow = build_playbook_workflow(
        playbook_id="ai_tech_daily_post",
        domain="AI科技资讯",
        settings=_settings(),
        drafting_agent=drafting_agent,  # type: ignore[arg-type]
        max_attempts=0,
        memory=memory,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=checkpointer,
        ai_tech_evidence=_news_contract(),
        ai_tech_evidence_manifest=_news_manifest(),
    )
    config = {"configurable": {"thread_id": "ai-evidence-boundary"}}
    raw_url = "https://example.com/release"

    result = workflow.invoke(
        {
            "scene": "AI 科技资讯简报",
            "platform": "xiaohongshu",
            "account_id": "acct-ai-tech-local",
            "ai_tech_evidence": {
                "raw_source_url": raw_url,
                "author": "Example Author",
            },
        },
        config=config,
    )

    assert result["status"] == "completed"
    assert len(drafting_agent.calls) == 1
    runtime_context = "\n".join(
        drafting_agent.calls[0]["runtime_skill_contents"]  # type: ignore[index]
    )
    assert "产品发布了新的推理模型。" in runtime_context
    assert raw_url not in runtime_context
    assert "Example Author" not in runtime_context
    assert "Recent Account Memory" not in runtime_context

    snapshots = list(workflow.get_state_history(config))
    serialized_snapshots = json.dumps(
        [snapshot.values for snapshot in snapshots],
        ensure_ascii=False,
        default=str,
    )
    assert raw_url not in serialized_snapshots
    assert "Example Author" not in serialized_snapshots
    assert all("ai_tech_evidence" not in snapshot.values for snapshot in snapshots)
    serialized_memory = json.dumps(
        memory.search(namespace=("accounts", "acct-ai-tech-local", "lessons")),
        ensure_ascii=False,
    )
    assert raw_url not in serialized_memory
    assert "Example Author" not in serialized_memory


def test_ai_workflow_allowlists_all_direct_input_before_langgraph_checkpoints(
    tmp_path: Path,
) -> None:
    checkpointer = InMemorySaver()
    drafting_agent = CapturingDraftAgent()
    workflow = build_playbook_workflow(
        playbook_id="ai_tech_daily_post",
        domain="AI科技资讯",
        settings=_settings(),
        drafting_agent=drafting_agent,  # type: ignore[arg-type]
        max_attempts=0,
        memory=InMemoryExecutionMemory(),
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=checkpointer,
        ai_tech_evidence=_news_contract(),
        ai_tech_evidence_manifest=_news_manifest(),
    )
    config = {"configurable": {"thread_id": "ai-evidence-allowlist"}}
    raw_url = "https://example.com/release"
    raw_title = "Example 模型发布原始标题"
    raw_author = "Example Author"
    raw_feed = "feed:example-news"

    result = workflow.invoke(
        {
            "scene": f"{raw_title} {raw_url}",
            "platform": "xiaohongshu",
            "account_id": "acct-ai-tech-local",
            "reflection_feedback": f"{raw_author} {raw_feed}",
            "topic_selection": {
                "raw_source_title": raw_title,
                "author": raw_author,
                "feed": raw_feed,
                "source_url": raw_url,
            },
            "content_quality_eval": {"reason": f"{raw_title} {raw_url}"},
            "final_content": {"body": raw_title},
        },
        config=config,
    )

    assert len(drafting_agent.calls) == 1
    assert drafting_agent.calls[0]["scene"] == "AI 科技资讯简报：模型发布 / 开发者工具 / 行业应用"
    serialized_result = json.dumps(result, ensure_ascii=False, default=str)
    snapshots = list(workflow.get_state_history(config))
    serialized_snapshots = json.dumps(
        [snapshot.values for snapshot in snapshots],
        ensure_ascii=False,
        default=str,
    )
    for raw_value in (raw_url, raw_title, raw_author, raw_feed):
        assert raw_value not in serialized_result
        assert raw_value not in serialized_snapshots


def test_ai_workflow_rejects_unsafe_model_output_before_state_or_checkpoint(
    tmp_path: Path,
) -> None:
    class UnsafeDraftAgent:
        provider_name = "unsafe"

        def generate(self, **_: object) -> dict[str, object]:
            return {
                "title": "AI 科技三条更新",
                "image_text": "今天该看哪三件事",
                "body": (
                    "模型发布：产品发布了新的推理模型。\n"
                    "开发者工具：开发者工具新增了批量处理能力。\n"
                    "行业应用：https://example.com/release"
                ),
                "hashtags": ["#AI资讯"],
            }

    checkpointer = InMemorySaver()
    memory = InMemoryExecutionMemory()
    workflow = build_playbook_workflow(
        playbook_id="ai_tech_daily_post",
        domain="AI科技资讯",
        settings=_settings(),
        drafting_agent=UnsafeDraftAgent(),  # type: ignore[arg-type]
        max_attempts=0,
        memory=memory,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=checkpointer,
        ai_tech_evidence=_news_contract(),
        ai_tech_evidence_manifest=_news_manifest(),
    )
    config = {"configurable": {"thread_id": "ai-unsafe-output"}}
    raw_url = "https://example.com/release"

    result = workflow.invoke(
        {
            "platform": "xiaohongshu",
            "account_id": "acct-ai-tech-local",
        },
        config=config,
    )

    snapshots = list(workflow.get_state_history(config))
    serialized_snapshots = json.dumps(
        [snapshot.values for snapshot in snapshots],
        ensure_ascii=False,
        default=str,
    )
    assert result["status"] == "failed"
    assert raw_url not in json.dumps(result, ensure_ascii=False, default=str)
    assert raw_url not in serialized_snapshots
    assert memory.search(namespace=("accounts", "acct-ai-tech-local", "lessons")) == []
