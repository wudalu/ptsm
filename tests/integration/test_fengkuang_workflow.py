from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.agent_runtime import runtime as runtime_module
from ptsm.agent_runtime.runtime import build_fengkuang_workflow
from ptsm.application.models import FengkuangRequest
from ptsm.config.settings import Settings
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import FileExecutionMemory, InMemoryExecutionMemory


class FakeTrendContextResolver:
    def resolve(self, *, state, playbook, loaded_skills) -> dict[str, str]:
        return {
            "xhs_trend_scan": (
                "# XHS Trend Scan Live Context\n"
                "- 主切口：`怎么才周四`\n"
                "- 场景张力：`下班前被新需求拽回工位`"
            )
        }


def _deterministic_settings() -> Settings:
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


def test_build_fengkuang_workflow_uses_generic_runtime_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_build_execution_graph(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        runtime_module,
        "build_execution_graph",
        fake_build_execution_graph,
        raising=False,
    )

    workflow = runtime_module.build_fengkuang_workflow()

    assert workflow is sentinel
    assert callable(captured["ingest"])
    assert callable(captured["planner"])
    assert callable(captured["executor"])
    assert callable(captured["reflector"])
    assert callable(captured["finalize"])


def test_build_fengkuang_workflow_delegates_to_build_playbook_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel = object()
    captured: dict[str, object] = {}

    def fake_build_playbook_workflow(**kwargs: object) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        runtime_module,
        "build_playbook_workflow",
        fake_build_playbook_workflow,
        raising=False,
    )

    workflow = runtime_module.build_fengkuang_workflow()

    assert workflow is sentinel
    assert captured["playbook_id"] == "fengkuang_daily_post"
    assert captured["domain"] == runtime_module.DOMAIN_FENGKUANG


def test_fengkuang_workflow_finalizes_without_required_ye_suan_and_persists_memory() -> None:
    memory = InMemoryExecutionMemory()
    workflow = build_fengkuang_workflow(
        memory=memory,
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="周一早高峰地铁通勤",
            platform="xiaohongshu",
            account_id="acct-fk-001",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-001"}},
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "fengkuang_daily_post"
    assert result["attempt_count"] == 1
    assert "周一早高峰地铁通勤" in result["final_content"]["body"]
    assert "#发疯文学" in result["final_content"]["hashtags"]
    assert "精神病" not in result["final_content"]["body"]
    assert "心理医生" not in result["final_content"]["body"]

    lessons = memory.search(namespace=("accounts", "acct-fk-001", "lessons"))
    assert len(lessons) == 1
    assert lessons[0]["playbook_id"] == "fengkuang_daily_post"


def test_fengkuang_workflow_writes_final_artifact(tmp_path: Path) -> None:
    workflow = build_fengkuang_workflow(
        artifact_store=FileArtifactStore(base_dir=tmp_path),
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="周五下班前最后一场会",
            platform="xiaohongshu",
            account_id="acct-fk-003",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-003"}},
    )

    artifact_path = Path(result["artifact_path"])
    assert artifact_path.exists()

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact["playbook_id"] == "fengkuang_daily_post"
    assert artifact["final_content"]["hashtags"][0] == "#发疯文学"
    assert "怎么才周四" in artifact["final_content"]["title"]
    assert "runtime_skill_contents" in artifact
    assert artifact["activated_skill_details"][0]["skill_name"] == "xhs_trend_scan"
    assert artifact["activated_skill_details"][0]["resource_type"] == "static_skill"
    assert artifact["runtime_skill_details"] == [
        {
            "skill_name": "xhs_trend_scan",
            "resource_type": "runtime_context",
            "resource_id": "xhs_trend_scan:runtime_context",
            "source_path": None,
            "content_preview": "# XHS Trend Scan Live Context",
        }
    ]


def test_fengkuang_workflow_persists_checkpoint_with_file_backed_saver(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "checkpoints.pkl"
    workflow = build_fengkuang_workflow(
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=FileCheckpointSaver(path=checkpoint_path),
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="周三工位发呆",
            platform="xiaohongshu",
            account_id="acct-fk-004",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-004"}},
    )

    reloaded = FileCheckpointSaver(path=checkpoint_path)
    saved = reloaded.get_tuple(
        {"configurable": {"thread_id": "thread-fk-004", "checkpoint_ns": ""}}
    )

    assert result["status"] == "completed"
    assert checkpoint_path.exists()
    assert saved is not None


def test_fengkuang_workflow_persists_lessons_with_file_backed_memory(
    tmp_path: Path,
) -> None:
    memory_path = tmp_path / "execution-memory.json"
    workflow = build_fengkuang_workflow(
        memory=FileExecutionMemory(path=memory_path),
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="周四下班前最后一场会",
            platform="xiaohongshu",
            account_id="acct-fk-005",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-005"}},
    )

    reloaded = FileExecutionMemory(path=memory_path)
    lessons = reloaded.search(namespace=("accounts", "acct-fk-005", "lessons"))

    assert result["status"] == "completed"
    assert memory_path.exists()
    assert len(lessons) == 1
    assert lessons[0]["playbook_id"] == "fengkuang_daily_post"


def test_fengkuang_workflow_reads_recent_account_memory_before_drafting() -> None:
    memory = InMemoryExecutionMemory()
    memory.record(
        namespace=("accounts", "acct-fk-memory", "lessons"),
        item={
            "playbook_id": "fengkuang_daily_post",
            "scene": "昨天领导18:57发在吗",
            "title": "领导18:57发在吗，我的工牌先疯了",
            "final_body": "评论区接一句工牌背面的疯话。至少先让工牌替我发言。",
        },
    )
    workflow = build_fengkuang_workflow(
        memory=memory,
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="今天领导18:59又发在吗",
            platform="xiaohongshu",
            account_id="acct-fk-memory",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-memory"}},
    )

    assert result["status"] == "completed"
    assert result["memory_hits"]
    runtime_context = "\n".join(result["runtime_skill_contents"])
    assert "Avoid repeating recent account posts" in runtime_context
    assert "领导18:57发在吗，我的工牌先疯了" in runtime_context


class NeverImprovingDraftingAgent:
    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        persona_prompt: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
        runtime_skill_contents: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "title": "一直在疯",
            "image_text": "还在疯",
            "body": f"{scene}，今天只有崩溃，没有缓冲。",
            "hashtags": ["#打工人"],
        }


class SequenceJudgeBackend:
    def __init__(self, responses: list[dict[str, object]]) -> None:
        self.responses = responses
        self.calls = 0

    def judge(self, *, prompt: str) -> str:
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return json.dumps(response, ensure_ascii=False)


class FeedbackAwareDraftingAgent:
    def __init__(self) -> None:
        self.feedback_seen: list[str | None] = []

    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        persona_prompt: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
        runtime_skill_contents: list[str] | None = None,
    ) -> dict[str, object]:
        self.feedback_seen.append(reflection_feedback)
        if reflection_feedback:
            return {
                "title": "领导18:57发「在吗」那一秒",
                "image_text": "我的工牌先替我发疯",
                "body": (
                    f"{scene}，群聊弹出来那一秒，工牌先替我深呼吸。"
                    "可复制疯话：收到，但我的电量不支持热更新。"
                    "评论区接一句你最想写在工牌背面的疯话。"
                ),
                "hashtags": ["#发疯文学", "#打工人日常"],
            }
        return {
            "title": "领导18:57发「在吗」那一秒",
            "image_text": "我的工牌先替我发疯",
            "body": (
                f"{scene}，群聊弹出来那一秒，工牌先替我深呼吸。"
                "评论区接一句你最想写在工牌背面的疯话。"
            ),
            "hashtags": ["#发疯文学", "#打工人日常"],
        }


def test_fengkuang_workflow_stops_after_max_attempts() -> None:
    workflow = build_fengkuang_workflow(
        drafting_agent=NeverImprovingDraftingAgent(),
        max_attempts=3,
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="周二工位开会",
            platform="xiaohongshu",
            account_id="acct-fk-002",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-002"}},
    )

    assert result["status"] == "failed"
    assert result["attempt_count"] == 3


def test_fengkuang_workflow_regenerates_when_content_quality_judge_fails() -> None:
    drafting_agent = FeedbackAwareDraftingAgent()
    judge_backend = SequenceJudgeBackend(
        [
            {
                "score": 0.45,
                "labels": {
                    "hook_specificity": "pass",
                    "save_trigger": "fail",
                    "comment_trigger": "pass",
                    "platform_native_format": "warn",
                    "persona_fit": "pass",
                    "safety": "pass",
                },
                "reason": "missing saveable line",
                "rewrite_hint": "Add one reusable copyable line.",
            },
            {
                "score": 0.86,
                "labels": {
                    "hook_specificity": "pass",
                    "save_trigger": "pass",
                    "comment_trigger": "pass",
                    "platform_native_format": "pass",
                    "persona_fit": "pass",
                    "safety": "pass",
                },
                "reason": "ready for human review",
                "rewrite_hint": "",
            },
        ]
    )
    workflow = build_fengkuang_workflow(
        drafting_agent=drafting_agent,
        content_quality_judge_backend=judge_backend,
        max_attempts=3,
        settings=_deterministic_settings(),
        skill_context_resolver=FakeTrendContextResolver(),
    )

    result = workflow.invoke(
        FengkuangRequest(
            scene="领导18:57突然发来一句在吗，明天早会还要我补材料",
            platform="xiaohongshu",
            account_id="acct-fk-judge",
        ).model_dump(mode="python"),
        config={"configurable": {"thread_id": "thread-fk-judge"}},
    )

    assert result["status"] == "completed"
    assert result["attempt_count"] == 2
    assert judge_backend.calls == 2
    assert "Add one reusable copyable line." in str(drafting_agent.feedback_seen[1])
    assert "可复制疯话" in result["final_content"]["body"]
    assert result["content_quality_eval"]["status"] == "passed"
    assert result["content_quality_eval"]["gate_level"] == "required"
