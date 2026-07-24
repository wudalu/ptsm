from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
import pytest

import ptsm.agent_runtime.runtime as psychology_learning_runtime
from ptsm.agent_runtime.runtime import (
    _resolve_verified_psychology_learning_catalog_contract,
    build_playbook_workflow,
)
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.config.settings import Settings
from ptsm.domain.psychology_learning import (
    PsychologyLearningBundle,
    _build_confirmed_psychology_learning_catalog,
    build_psychology_learning_catalog_receipt,
    list_psychology_learning_series,
    render_psychology_learning_draft,
    require_sealed_psychology_learning_preflight_bundle,
    resolve_psychology_learning_selection,
    seal_psychology_learning_preflight_bundle,
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


def test_runtime_contract_requires_an_exact_custom_catalog_receipt(
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
        lesson_id=catalog.lessons[0].lesson_id,
        curriculum_version=catalog.curriculum_version,
    )

    assert bundle.catalog is not None
    receipt = build_psychology_learning_catalog_receipt(bundle)
    assert receipt is not None
    with pytest.raises(
        ValueError,
        match="custom psychology learning catalog requires a receipt",
    ):
        _resolve_verified_psychology_learning_catalog_contract(
            contract=bundle.runtime_contract,
            manifest=bundle.manifest,
        )
    verified_contract, verified_manifest, verified_receipt = (
        _resolve_verified_psychology_learning_catalog_contract(
            contract=bundle.runtime_contract,
            manifest=bundle.manifest,
            catalog_receipt=receipt,
        )
    )
    assert verified_contract == bundle.runtime_contract
    assert verified_manifest == bundle.manifest
    assert verified_receipt == receipt

    tampered_receipt = deepcopy(receipt)
    tampered_receipt["catalog_digest"] = "catalog:tampered"
    with pytest.raises(
        ValueError,
        match="custom psychology learning catalog receipt does not match",
    ):
        _resolve_verified_psychology_learning_catalog_contract(
            contract=bundle.runtime_contract,
            manifest=bundle.manifest,
            catalog_receipt=tampered_receipt,
        )


def test_runtime_rejects_an_unconfirmed_custom_bundle_as_trust_proof() -> None:
    """A controlled catalog built from a proposal is not a runnable authority."""
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    unconfirmed_catalog = _build_confirmed_psychology_learning_catalog(
        proposal,
        curriculum_version="1",
    )
    unconfirmed_bundle = PsychologyLearningBundle(
        lesson=unconfirmed_catalog.lessons[0],
        lessons=unconfirmed_catalog.lessons,
        catalog=unconfirmed_catalog,
    )
    receipt = build_psychology_learning_catalog_receipt(unconfirmed_bundle)
    assert receipt is not None

    with pytest.raises(ValueError, match="preflight"):
        _resolve_verified_psychology_learning_catalog_contract(
            contract=unconfirmed_bundle.runtime_contract,
            manifest=unconfirmed_bundle.manifest,
            catalog_receipt=receipt,
            psychology_learning_preflight_capability=unconfirmed_bundle,
        )


def test_runtime_rejects_a_sealed_bundle_copied_onto_an_unconfirmed_catalog() -> None:
    """A preflight marker is bound to the exact selection, not merely the object."""
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    unconfirmed_catalog = _build_confirmed_psychology_learning_catalog(
        proposal,
        curriculum_version="1",
    )
    capability = seal_psychology_learning_preflight_bundle(_bundle())
    forged_bundle = require_sealed_psychology_learning_preflight_bundle(
        capability
    ).model_copy(
        update={
            "lesson": unconfirmed_catalog.lessons[0],
            "lessons": unconfirmed_catalog.lessons,
            "catalog": unconfirmed_catalog,
        }
    )
    receipt = build_psychology_learning_catalog_receipt(forged_bundle)
    assert receipt is not None

    with pytest.raises(ValueError, match="preflight"):
        _resolve_verified_psychology_learning_catalog_contract(
            contract=forged_bundle.runtime_contract,
            manifest=forged_bundle.manifest,
            catalog_receipt=receipt,
            psychology_learning_preflight_capability=forged_bundle,
        )


def test_runtime_rejects_a_preflight_capability_after_its_bound_bundle_is_mutated() -> None:
    """The capability snapshots its exact preflight selection, not a marker."""
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    unconfirmed_catalog = _build_confirmed_psychology_learning_catalog(
        proposal,
        curriculum_version="1",
    )
    capability = seal_psychology_learning_preflight_bundle(_bundle())
    bound_bundle = require_sealed_psychology_learning_preflight_bundle(capability)
    object.__setattr__(bound_bundle, "lesson", unconfirmed_catalog.lessons[0])
    object.__setattr__(bound_bundle, "lessons", unconfirmed_catalog.lessons)
    object.__setattr__(bound_bundle, "catalog", unconfirmed_catalog)
    receipt = build_psychology_learning_catalog_receipt(bound_bundle)
    assert receipt is not None

    with pytest.raises(ValueError, match="preflight"):
        _resolve_verified_psychology_learning_catalog_contract(
            contract=bound_bundle.runtime_contract,
            manifest=bound_bundle.manifest,
            catalog_receipt=receipt,
            psychology_learning_preflight_capability=capability,
        )


def test_confirmed_custom_catalog_runtime_reuses_preflight_bundle_and_keeps_goal_out_of_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Only the exact opaque receipt may cross into a custom lesson runtime."""
    monkeypatch.chdir(tmp_path)
    private_goal = "确认前私有目标，不得进入运行时、草稿或制品"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {
                "id": "notice",
                "title": "先识别重复时刻",
                "goal": private_goal,
            },
            {
                "id": "practice",
                "title": "练习一个小步骤",
                "goal": "确认前的第二个私有目标",
            },
        ),
    )
    store = PsychologyLearningSeriesStore(trusted_provision=True, )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    capability = seal_psychology_learning_preflight_bundle(
        resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
        )
    )
    bundle = require_sealed_psychology_learning_preflight_bundle(capability)
    receipt = build_psychology_learning_catalog_receipt(bundle)
    assert receipt is not None

    def reject_catalog_reresolution(**_: object) -> object:
        pytest.fail("guarded runtime must reuse the preflight psychology learning bundle")

    monkeypatch.setattr(
        psychology_learning_runtime,
        "resolve_psychology_learning_selection",
        reject_catalog_reresolution,
    )

    checkpointer = InMemorySaver()
    memory = InMemoryExecutionMemory()
    drafting_agent = CapturingLearningDraftAgent(
        render_psychology_learning_draft(bundle.runtime_contract)
    )
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
        psychology_learning_catalog_receipt=receipt,
        psychology_learning_preflight_capability=capability,
    )
    config = {"configurable": {"thread_id": "custom-learning-boundary"}}
    result = workflow.invoke(
        {
            "scene": f"operator supplied: {private_goal}",
            "platform": "xiaohongshu",
            "account_id": "acct-psychology-local",
            "topic_selection": {"proposal_goal": private_goal},
        },
        config=config,
    )

    assert result["status"] == "completed"
    assert len(drafting_agent.calls) == 1
    runtime_context = "\n".join(
        drafting_agent.calls[0]["runtime_skill_contents"]  # type: ignore[index]
    )
    artifact = json.loads(Path(str(result["artifact_path"])).read_text(encoding="utf-8"))
    assert artifact["psychology_learning_catalog_receipt"] == receipt
    snapshots = json.dumps(
        [snapshot.values for snapshot in workflow.get_state_history(config)],
        ensure_ascii=False,
        default=str,
    )
    serialized_memory = json.dumps(memory._storage, ensure_ascii=False, default=str)
    for forbidden in (private_goal, proposal.proposal_id, str(store.catalog_root)):
        assert forbidden not in runtime_context
        assert forbidden not in snapshots
        assert forbidden not in json.dumps(artifact, ensure_ascii=False)
        assert forbidden not in serialized_memory


def test_learning_finalize_rejects_a_rebound_artifact_root_before_first_write(
    tmp_path: Path,
) -> None:
    """A frozen learning root must constrain the finalizer's first artifact write."""
    bundle = _bundle()
    artifact_root = tmp_path / "artifacts"
    artifact_root.mkdir()
    expected_artifact_root_identity = artifact_root.stat()
    former_artifact_root = tmp_path / "former-artifacts"
    workflow = build_playbook_workflow(
        playbook_id="modern_psychology_post",
        domain="现代心理困境观察",
        settings=_settings(),
        drafting_agent=CapturingLearningDraftAgent(_valid_draft()),  # type: ignore[arg-type]
        max_attempts=0,
        artifact_store=FileArtifactStore(base_dir=artifact_root),
        psychology_learning_contract=bundle.runtime_contract,
        psychology_learning_manifest=bundle.manifest,
        expected_artifact_root_identity=expected_artifact_root_identity,
    )
    artifact_root.rename(former_artifact_root)
    artifact_root.mkdir()

    with pytest.raises(OSError, match="artifact parent changed"):
        workflow.invoke(
            {
                "scene": "ignored",
                "platform": "xiaohongshu",
                "account_id": "acct-psychology-local",
            },
            config={"configurable": {"thread_id": "rebound-learning-root"}},
        )

    assert not tuple(artifact_root.iterdir())
    assert not tuple(former_artifact_root.iterdir())


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


def test_confirmed_catalog_reconstruction_keeps_proposal_metadata_out_of_runtime_contract(
    tmp_path: Path,
) -> None:
    root = tmp_path / "series-store"
    store = PsychologyLearningSeriesStore(trusted_provision=True, catalog_root=root)
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )

    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
        catalog_root=root,
    )

    assert bundle.catalog is not None
    assert bundle.catalog.catalog_digest == catalog.catalog_digest
    assert bundle.catalog.publication_plan == catalog.publication_plan
    assert "proposal" not in bundle.runtime_contract
    assert "approval" not in bundle.runtime_contract
    assert "source_refs" not in bundle.runtime_contract
