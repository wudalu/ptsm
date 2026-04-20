from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.agent_runtime import runtime as runtime_module
from ptsm.agent_runtime.runtime import build_fengkuang_workflow
from ptsm.application.models import FengkuangRequest
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import FileExecutionMemory, InMemoryExecutionMemory


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


def test_fengkuang_workflow_revises_once_and_persists_memory() -> None:
    memory = InMemoryExecutionMemory()
    workflow = build_fengkuang_workflow(memory=memory)

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
    assert result["attempt_count"] == 2
    assert "周一早高峰地铁通勤" in result["final_content"]["body"]
    assert "也算" in result["final_content"]["body"]

    lessons = memory.search(namespace=("accounts", "acct-fk-001", "lessons"))
    assert len(lessons) == 1
    assert lessons[0]["playbook_id"] == "fengkuang_daily_post"


def test_fengkuang_workflow_writes_final_artifact(tmp_path: Path) -> None:
    workflow = build_fengkuang_workflow(
        artifact_store=FileArtifactStore(base_dir=tmp_path),
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


def test_fengkuang_workflow_persists_checkpoint_with_file_backed_saver(
    tmp_path: Path,
) -> None:
    checkpoint_path = tmp_path / "checkpoints.pkl"
    workflow = build_fengkuang_workflow(
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=FileCheckpointSaver(path=checkpoint_path),
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


class NeverImprovingDraftingAgent:
    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "title": "一直在疯",
            "image_text": "还在疯",
            "body": f"{scene}，今天只有崩溃，没有缓冲。",
            "hashtags": ["#发疯文学"],
        }


def test_fengkuang_workflow_stops_after_max_attempts() -> None:
    workflow = build_fengkuang_workflow(
        drafting_agent=NeverImprovingDraftingAgent(),
        max_attempts=3,
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
