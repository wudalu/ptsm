from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
import pytest

from ptsm.agent_runtime.runtime import build_playbook_workflow
from ptsm.config.settings import Settings
from ptsm.domain.psychology_learning import (
    list_psychology_learning_series,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
)
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.memory.store import InMemoryExecutionMemory


class CapturingLearningDraftAgent:
    provider_name = "capturing"

    def __init__(self, draft: dict[str, object]) -> None:
        self._draft = draft
        self.calls: list[dict[str, object]] = []

    def generate(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        return dict(self._draft)


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


def _bundle():
    return resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id="notice_the_loop",
    )


def _valid_draft() -> dict[str, object]:
    return render_psychology_learning_draft(_bundle().runtime_contract)


def test_learning_workflow_requires_a_bound_catalog_contract() -> None:
    try:
        build_playbook_workflow(
            playbook_id="modern_psychology_post",
            domain="现代心理困境观察",
            settings=_settings(),
            psychology_learning_contract={"mode": "learning_series"},
        )
    except ValueError as exc:
        assert "psychology learning" in str(exc)
    else:
        raise AssertionError("invalid learning contract must be rejected")


def test_learning_workflow_rejects_a_well_formed_but_tampered_catalog_contract() -> None:
    bundle = _bundle()
    tampered_contract = deepcopy(bundle.runtime_contract)
    tampered_contract["approved_explanation"] = "这是一条目录外的心理学解释。"

    with pytest.raises(ValueError, match="catalog"):
        build_playbook_workflow(
            playbook_id="modern_psychology_post",
            domain="现代心理困境观察",
            settings=_settings(),
            psychology_learning_contract=tampered_contract,
            psychology_learning_manifest=bundle.manifest,
        )


def test_learning_workflow_isolates_reused_thread_history_from_ordinary_psychology(
    tmp_path: Path,
) -> None:
    checkpointer = InMemorySaver()
    thread_config = {"configurable": {"thread_id": "reused-psychology-thread"}}
    raw_url = "https://example.com/ordinary-psychology-scene"
    ordinary_workflow = build_playbook_workflow(
        playbook_id="modern_psychology_post",
        domain="现代心理困境观察",
        settings=_settings(),
        drafting_agent=CapturingLearningDraftAgent(_valid_draft()),  # type: ignore[arg-type]
        max_attempts=0,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "ordinary-artifacts"),
        checkpointer=checkpointer,
    )
    ordinary_workflow.invoke(
        {
            "scene": raw_url,
            "platform": "xiaohongshu",
            "account_id": "acct-psychology-local",
        },
        config=thread_config,
    )

    bundle = _bundle()
    learning_workflow = build_playbook_workflow(
        playbook_id="modern_psychology_post",
        domain="现代心理困境观察",
        settings=_settings(),
        drafting_agent=CapturingLearningDraftAgent(_valid_draft()),  # type: ignore[arg-type]
        max_attempts=0,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "learning-artifacts"),
        checkpointer=checkpointer,
        psychology_learning_contract=bundle.runtime_contract,
        psychology_learning_manifest=bundle.manifest,
    )
    result = learning_workflow.invoke(
        {
            "scene": "ignored",
            "platform": "xiaohongshu",
            "account_id": "acct-psychology-local",
        },
        config=thread_config,
    )

    assert result["status"] == "completed"
    history = json.dumps(
        [snapshot.values for snapshot in learning_workflow.get_state_history(thread_config)],
        ensure_ascii=False,
        default=str,
    )
    assert raw_url not in history


def test_learning_workflow_drops_free_input_and_sources_before_checkpoint_and_drafting(
    tmp_path: Path,
) -> None:
    bundle = _bundle()
    checkpointer = InMemorySaver()
    memory = InMemoryExecutionMemory()
    drafting_agent = CapturingLearningDraftAgent(_valid_draft())
    workflow = build_playbook_workflow(
        playbook_id="modern_psychology_post",
        domain="现代心理困境观察",
        settings=_settings(),
        drafting_agent=drafting_agent,  # type: ignore[arg-type]
        max_attempts=0,
        memory=memory,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
        checkpointer=checkpointer,
        psychology_learning_contract=bundle.runtime_contract,
        psychology_learning_manifest=bundle.manifest,
    )
    config = {"configurable": {"thread_id": "psychology-learning-boundary"}}
    raw_url = "https://example.com/free-operator-scene"
    raw_author = "Example Author"

    result = workflow.invoke(
        {
            "scene": f"{raw_author} {raw_url}",
            "platform": "xiaohongshu",
            "account_id": "acct-psychology-local",
            "topic_selection": {"source_url": raw_url, "author": raw_author},
            "psychology_learning_contract": {"source_refs": ["source:leaked"]},
        },
        config=config,
    )

    assert result["status"] == "completed"
    assert len(drafting_agent.calls) == 1
    runtime_context = "\n".join(
        drafting_agent.calls[0]["runtime_skill_contents"]  # type: ignore[index]
    )
    assert bundle.runtime_contract["approved_explanation"] in runtime_context
    assert raw_url not in runtime_context
    assert raw_author not in runtime_context
    assert "source:" not in runtime_context
    assert "Recent Account Memory" not in runtime_context

    snapshots = list(workflow.get_state_history(config))
    serialized_snapshots = json.dumps(
        [snapshot.values for snapshot in snapshots],
        ensure_ascii=False,
        default=str,
    )
    assert raw_url not in serialized_snapshots
    assert raw_author not in serialized_snapshots
    assert "source:apa-rumination-2023" not in serialized_snapshots
    assert all("psychology_learning_contract" not in snapshot.values for snapshot in snapshots)

    artifact = json.loads(Path(str(result["artifact_path"])).read_text(encoding="utf-8"))
    assert artifact["psychology_learning_evidence_manifest"] == bundle.manifest
    assert raw_url not in json.dumps(artifact, ensure_ascii=False)
    assert raw_author not in json.dumps(artifact, ensure_ascii=False)


@pytest.mark.parametrize(
    "lesson_id",
    [
        lesson.lesson_id
        for lesson in list_psychology_learning_series(
            series_id="after_work_rumination"
        )
    ],
)
def test_every_catalog_lesson_completes_with_the_bound_runtime(
    lesson_id: str,
    tmp_path: Path,
) -> None:
    """A catalog lesson must not retry forever against ordinary-post rules."""
    bundle = resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id=lesson_id,
    )
    workflow = build_playbook_workflow(
        playbook_id="modern_psychology_post",
        domain="现代心理困境观察",
        settings=_settings(),
        artifact_store=FileArtifactStore(base_dir=tmp_path / lesson_id),
        psychology_learning_contract=bundle.runtime_contract,
        psychology_learning_manifest=bundle.manifest,
    )

    result = workflow.invoke(
        {
            "scene": "operator input must be ignored",
            "platform": "xiaohongshu",
            "account_id": "acct-psychology-local",
        },
        config={"configurable": {"thread_id": f"catalog-{lesson_id}"}},
    )

    assert result["status"] == "completed"
