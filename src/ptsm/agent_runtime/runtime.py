from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import re
from threading import Event, RLock, Thread, current_thread
from typing import Any, Callable, Mapping

from langgraph.checkpoint.memory import InMemorySaver
from pydantic import ValidationError

from ptsm.agent_runtime.agents import FengkuangDraftingAgent
from ptsm.agent_runtime.graph.builder import build_execution_graph
from ptsm.agent_runtime.nodes.executor import build_executor_node
from ptsm.agent_runtime.nodes.ingest import build_ingest_node
from ptsm.agent_runtime.nodes.memory import build_memory_node
from ptsm.agent_runtime.nodes.planner import build_planner_node
from ptsm.agent_runtime.nodes.reflector import build_reflector_node
from ptsm.agent_runtime.state import ExecutionState
from ptsm.config.settings import Settings, get_settings
from ptsm.domain.ai_tech_content import (
    AiTechEvidenceManifest,
    parse_ai_tech_runtime_contract,
    validate_ai_tech_draft_contract,
)
from ptsm.domain.psychology_carousel import (
    normalize_psychology_carousel_plan,
    psychology_carousel_inner_pages_fingerprint,
)
from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
    PsychologyLearningEvidenceManifest,
    _PsychologyLearningPreflightCapability,
    parse_psychology_learning_runtime_contract,
    require_sealed_psychology_learning_preflight_bundle,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
    verify_psychology_learning_catalog_receipt,
)
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.evaluations.content_quality_gate import (
    build_content_quality_judge_gate,
)
from ptsm.infrastructure.llm.factory import build_drafting_backend, build_llm_judge_backend
from ptsm.infrastructure.memory.checkpoint import FileCheckpointSaver
from ptsm.infrastructure.memory.store import (
    ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER,
    ExecutionMemoryStore,
    FileExecutionMemory,
    InMemoryExecutionMemory,
)
from ptsm.evaluations.playbook_contracts import load_playbook_eval_contract
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry
from ptsm.skills.runtime_context import SkillContextResolver, build_skill_context_resolver

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
SKILL_ROOT = PACKAGE_ROOT / "skills" / "builtin"
DOMAIN_FENGKUANG = "发疯文学"
AI_TECH_PLAYBOOK_ID = "ai_tech_daily_post"
MODERN_PSYCHOLOGY_PLAYBOOK_ID = "modern_psychology_post"
DEFAULT_RUNTIME_STATE_DIR = Path(".ptsm") / "agent_runtime"
_SAFE_AI_RUNTIME_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
_INNER_CAROUSEL_FINGERPRINT_PATTERN = re.compile(r"^[0-9a-f]{64}$")
PsychologyCarouselDraftGate = Callable[
    [ExecutionState, dict[str, object]],
    list[str],
]
_ORDINARY_PSYCHOLOGY_CAROUSEL_HEARTBEAT_INTERVAL_SECONDS = 60.0
_ORDINARY_PSYCHOLOGY_CAROUSEL_HEARTBEAT_JOIN_TIMEOUT_SECONDS = 1.0


@dataclass
class OrdinaryPsychologyCarouselMemoryReservation:
    """Opaque, process-local capability for the post-render memory commit."""

    _execution_memory: ExecutionMemoryStore
    _namespace: tuple[str, ...]
    _fingerprint: str
    _reservation_id: str
    _item: dict[str, object]
    _heartbeat_interval_seconds: float = (
        _ORDINARY_PSYCHOLOGY_CAROUSEL_HEARTBEAT_INTERVAL_SECONDS
    )
    _settled: bool = False
    _receipt_intent: dict[str, object] | None = None
    _heartbeat_started: bool = False
    _heartbeat_healthy: bool = True
    _heartbeat_stop: Event = field(default_factory=Event, init=False, repr=False)
    _heartbeat_thread: Thread | None = field(default=None, init=False, repr=False)
    _lock: Any = field(default_factory=RLock, init=False, repr=False)

    def start_heartbeat(self) -> bool:
        """Renew the owner-fenced lease until this capability settles."""
        with self._lock:
            if self._settled:
                return False
            if self._heartbeat_started:
                return self._heartbeat_healthy
            self._heartbeat_started = True
        if not self._renew():
            with self._lock:
                self._heartbeat_healthy = False
            return False
        with self._lock:
            if self._settled:
                return False
            thread = Thread(
                target=self._heartbeat_loop,
                name="ptsm-psychology-carousel-lease",
                daemon=True,
            )
            self._heartbeat_thread = thread
        try:
            thread.start()
        except RuntimeError:
            with self._lock:
                self._heartbeat_thread = None
                self._heartbeat_healthy = False
            return False
        return True

    def heartbeat_is_healthy(self) -> bool:
        with self._lock:
            return self._heartbeat_healthy

    def persist_receipt_intent(self, receipt_intent: dict[str, object]) -> bool:
        """Persist a pre-ledger recovery identity without stopping the lease."""
        with self._lock:
            if self._settled or self._receipt_intent is not None:
                return False
        try:
            persisted = (
                self._execution_memory.persist_psychology_carousel_inner_fingerprint_receipt_intent(
                    namespace=self._namespace,
                    fingerprint=self._fingerprint,
                    reservation_id=self._reservation_id,
                    item=self._item,
                    receipt_intent=receipt_intent,
                )
            )
        except Exception:
            return False
        if persisted:
            with self._lock:
                self._receipt_intent = dict(receipt_intent)
        return persisted

    def commit_receipt_intent(self, receipt_intent: dict[str, object]) -> bool:
        with self._lock:
            if self._settled or self._receipt_intent != receipt_intent:
                return False
        committed = self._execution_memory.commit_psychology_carousel_inner_fingerprint_receipt_intent(
            namespace=self._namespace,
            fingerprint=self._fingerprint,
            reservation_id=self._reservation_id,
            item=self._item,
            receipt_intent=receipt_intent,
        )
        if committed:
            with self._lock:
                self._settled = True
            self._stop_heartbeat()
        return committed

    def abort_receipt_intent(self) -> bool:
        """Owner-only abort for a known pre-ledger failure."""
        with self._lock:
            if self._settled or self._receipt_intent is None:
                return False
        try:
            aborted = (
                self._execution_memory.abort_psychology_carousel_inner_fingerprint_receipt_intent(
                    namespace=self._namespace,
                    fingerprint=self._fingerprint,
                    reservation_id=self._reservation_id,
                )
            )
        except Exception:
            return False
        if aborted:
            with self._lock:
                self._settled = True
            self._stop_heartbeat()
        return aborted

    def release(self) -> None:
        with self._lock:
            if self._settled:
                return
            receipt_intent = self._receipt_intent
        self._stop_heartbeat()
        if receipt_intent is not None:
            # The caller explicitly aborts known pre-ledger failures. Any
            # remaining intent may already have a durable ledger and must stay
            # for expiry-based verification rather than being released.
            with self._lock:
                self._settled = True
            return
        try:
            self._execution_memory.release_psychology_carousel_inner_fingerprint(
                namespace=self._namespace,
                fingerprint=self._fingerprint,
                reservation_id=self._reservation_id,
            )
        finally:
            with self._lock:
                self._settled = True

    def _renew(self) -> bool:
        try:
            return bool(
                self._execution_memory.renew_psychology_carousel_inner_fingerprint(
                    namespace=self._namespace,
                    fingerprint=self._fingerprint,
                    reservation_id=self._reservation_id,
                )
            )
        except Exception:
            return False

    def _heartbeat_loop(self) -> None:
        while not self._heartbeat_stop.wait(self._heartbeat_interval_seconds):
            with self._lock:
                if self._settled:
                    return
            if self._renew():
                continue
            with self._lock:
                self._heartbeat_healthy = False
            return

    def _stop_heartbeat(self) -> None:
        with self._lock:
            self._heartbeat_stop.set()
            thread = self._heartbeat_thread
            self._heartbeat_thread = None
        if thread is not None and thread is not current_thread():
            thread.join(
                timeout=_ORDINARY_PSYCHOLOGY_CAROUSEL_HEARTBEAT_JOIN_TIMEOUT_SECONDS
            )


OrdinaryPsychologyCarouselReservationSink = Callable[
    [OrdinaryPsychologyCarouselMemoryReservation],
    None,
]


class _BoundAiTechWorkflow:
    """Expose an AI workflow only through a pre-checkpoint input boundary.

    LangGraph records its input before the first node executes, so ingest-time
    cleanup cannot protect checkpoint history.  This facade deliberately does
    not proxy the compiled graph's generic invocation methods: every AI
    invocation starts from a fresh, minimal state built from the bound evidence
    contract and safe execution identifiers.
    """

    def __init__(self, *, workflow: Any, contract: Mapping[str, Any]) -> None:
        self._workflow = workflow
        self._contract = contract

    def invoke(
        self,
        input: Mapping[str, Any] | None,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        safe_input = _build_ai_tech_workflow_input(
            contract=self._contract,
            supplied=input or {},
        )
        result = self._workflow.invoke(
            safe_input,
            config=_sanitize_ai_tech_workflow_config(config),
            **kwargs,
        )
        return dict(result)

    def get_state_history(
        self,
        config: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:
        return self._workflow.get_state_history(
            _sanitize_ai_tech_workflow_config(config),
            **kwargs,
        )


class _BoundPsychologyLearningWorkflow:
    """Keep one catalog lesson outside every graph input and checkpoint."""

    def __init__(self, *, workflow: Any, contract: Mapping[str, Any]) -> None:
        self._workflow = workflow
        self._contract = contract
        self._checkpoint_namespace = _psychology_learning_checkpoint_namespace(contract)

    def invoke(
        self,
        input: Mapping[str, Any] | None,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        safe_input = _build_psychology_learning_workflow_input(
            contract=self._contract,
            supplied=input or {},
        )
        result = self._workflow.invoke(
            safe_input,
            config=_sanitize_psychology_learning_workflow_config(
                config,
                checkpoint_namespace=self._checkpoint_namespace,
            ),
            **kwargs,
        )
        return dict(result)

    def get_state_history(
        self,
        config: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:
        return self._workflow.get_state_history(
            _sanitize_psychology_learning_workflow_config(
                config,
                checkpoint_namespace=self._checkpoint_namespace,
            ),
            **kwargs,
        )


class _BoundOrdinaryPsychologyWorkflow:
    """Drop caller-supplied graph internals before the initial checkpoint."""

    def __init__(self, *, workflow: Any) -> None:
        self._workflow = workflow

    def invoke(
        self,
        input: Mapping[str, Any] | None,
        config: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result = self._workflow.invoke(
            _build_ordinary_psychology_workflow_input(input or {}),
            config=config,
            **kwargs,
        )
        return dict(result)

    def get_state_history(
        self,
        config: Mapping[str, Any] | None,
        **kwargs: Any,
    ) -> Any:
        return self._workflow.get_state_history(config, **kwargs)


def build_playbook_workflow(
    *,
    playbook_id: str,
    domain: str,
    memory: ExecutionMemoryStore | None = None,
    drafting_agent: FengkuangDraftingAgent | None = None,
    max_attempts: int = 2,
    settings: Settings | None = None,
    artifact_store: FileArtifactStore | None = None,
    expected_artifact_root_identity: os.stat_result | None = None,
    checkpointer: object | None = None,
    skill_context_resolver: SkillContextResolver | None = None,
    content_quality_judge_backend: object | None = None,
    ai_tech_evidence: Mapping[str, Any] | None = None,
    ai_tech_evidence_manifest: Mapping[str, Any] | None = None,
    psychology_learning_contract: Mapping[str, Any] | None = None,
    psychology_learning_manifest: Mapping[str, Any] | None = None,
    psychology_learning_catalog_receipt: Mapping[str, Any] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
    ordinary_psychology_carousel_reservation_sink: (
        OrdinaryPsychologyCarouselReservationSink | None
    ) = None,
):
    """Build a workflow for a specific playbook/domain pair."""
    execution_memory = memory or InMemoryExecutionMemory()
    playbooks = PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    playbook_loader = PlaybookLoader(playbook_root=PLAYBOOK_ROOT)
    skills = SkillRegistry(skill_root=SKILL_ROOT)
    skill_loader = SkillLoader(skills)
    settings = settings or get_settings()
    playbook_def = playbooks.get(playbook_id)
    normalized_ai_tech_evidence: dict[str, Any] | None = None
    normalized_ai_tech_evidence_manifest: dict[str, Any] | None = None
    normalized_psychology_learning_contract: dict[str, Any] | None = None
    normalized_psychology_learning_manifest: dict[str, Any] | None = None
    normalized_psychology_learning_catalog_receipt: dict[str, Any] | None = None
    if playbook_id == AI_TECH_PLAYBOOK_ID:
        if ai_tech_evidence is None:
            raise ValueError("ai_tech_daily_post requires a normalized AI evidence contract")
        if ai_tech_evidence_manifest is None:
            raise ValueError("ai_tech_daily_post requires an opaque AI evidence manifest")
        try:
            normalized_ai_tech_evidence = parse_ai_tech_runtime_contract(ai_tech_evidence)
            normalized_ai_tech_evidence_manifest = AiTechEvidenceManifest.model_validate(
                ai_tech_evidence_manifest
            ).model_dump(mode="json")
        except ValidationError as exc:
            raise ValueError("invalid normalized AI evidence contract or manifest") from exc
    elif ai_tech_evidence is not None or ai_tech_evidence_manifest is not None:
        raise ValueError("AI evidence contracts are only valid for ai_tech_daily_post")
    if playbook_id == MODERN_PSYCHOLOGY_PLAYBOOK_ID:
        if (
            psychology_learning_contract is None
            and psychology_learning_manifest is not None
        ) or (
            psychology_learning_contract is not None
            and psychology_learning_manifest is None
        ) or (
            psychology_learning_contract is None
            and psychology_learning_catalog_receipt is not None
        ) or (
            psychology_learning_preflight_capability is not None
            and psychology_learning_contract is None
        ):
            raise ValueError(
                "psychology learning requires both a normalized catalog contract and opaque manifest"
            )
        if psychology_learning_contract is not None:
            try:
                normalized_psychology_learning_contract = (
                    parse_psychology_learning_runtime_contract(
                        psychology_learning_contract
                    )
                )
                normalized_psychology_learning_manifest = (
                    PsychologyLearningEvidenceManifest.model_validate(
                        psychology_learning_manifest
                    ).model_dump(mode="json")
                )
            except ValidationError as exc:
                raise ValueError(
                    "invalid normalized psychology learning contract or manifest"
                ) from exc
            (
                normalized_psychology_learning_contract,
                normalized_psychology_learning_manifest,
                normalized_psychology_learning_catalog_receipt,
            ) = _resolve_verified_psychology_learning_catalog_contract(
                contract=normalized_psychology_learning_contract,
                manifest=normalized_psychology_learning_manifest,
                catalog_receipt=psychology_learning_catalog_receipt,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
    elif (
        psychology_learning_contract is not None
        or psychology_learning_manifest is not None
        or psychology_learning_catalog_receipt is not None
        or psychology_learning_preflight_capability is not None
    ):
        raise ValueError(
            "psychology learning contracts are only valid for modern_psychology_post"
        )
    if (
        expected_artifact_root_identity is not None
        and normalized_psychology_learning_contract is None
    ):
        raise ValueError(
            "a pinned artifact root is only valid for psychology learning workflows"
        )
    if normalized_ai_tech_evidence is not None and normalized_psychology_learning_contract is not None:
        raise ValueError("a workflow cannot combine AI evidence and psychology learning contracts")
    max_attempts = max_attempts if max_attempts != 2 else playbook_def.max_attempts
    drafting_model = playbook_def.drafting_model or None
    skill_context_resolver = skill_context_resolver or build_skill_context_resolver(
        settings=settings
    )
    drafting_agent = drafting_agent or FengkuangDraftingAgent(
        backend=build_drafting_backend(settings, model=drafting_model)
    )
    if content_quality_judge_backend is None and _playbook_requires_content_quality_judge(
        playbook_id
    ):
        content_quality_judge_backend = build_llm_judge_backend(settings)
    content_quality_judge = (
        build_content_quality_judge_gate(content_quality_judge_backend)
        if content_quality_judge_backend is not None
        else None
    )
    drafting_provider = getattr(drafting_agent, "provider_name", "custom")
    artifact_store = artifact_store or FileArtifactStore()
    ai_tech_draft_gate = (
        _build_ai_tech_draft_gate(normalized_ai_tech_evidence)
        if normalized_ai_tech_evidence is not None
        else None
    )
    psychology_learning_draft_gate = (
        _build_psychology_learning_draft_gate(normalized_psychology_learning_contract)
        if normalized_psychology_learning_contract is not None
        else None
    )
    psychology_carousel_draft_gate = (
        _build_psychology_carousel_draft_gate()
        if playbook_id == MODERN_PSYCHOLOGY_PLAYBOOK_ID
        and normalized_psychology_learning_contract is None
        else None
    )
    workflow = build_execution_graph(
        ingest=build_ingest_node(drafting_provider=drafting_provider),
        planner=build_planner_node(
            domain=domain,
            playbook_id=playbook_id,
            playbooks=playbooks,
            playbook_loader=playbook_loader,
            skills=skills,
            skill_loader=skill_loader,
            skill_context_resolver=skill_context_resolver,
            ai_tech_evidence=normalized_ai_tech_evidence,
            psychology_learning_contract=normalized_psychology_learning_contract,
        ),
        memory=build_memory_node(
            execution_memory=execution_memory,
            evidence_gated=(
                normalized_ai_tech_evidence is not None
                or normalized_psychology_learning_contract is not None
            ),
        ),
        executor=build_executor_node(
            drafting_agent=drafting_agent,
            ai_tech_draft_gate=(
                (lambda draft: ai_tech_draft_gate({}, draft))
                if ai_tech_draft_gate is not None
                else None
            ),
            psychology_learning_draft_gate=(
                (lambda draft: psychology_learning_draft_gate({}, draft))
                if psychology_learning_draft_gate is not None
                else None
            ),
            psychology_carousel_draft_gate=psychology_carousel_draft_gate,
        ),
        reflector=build_reflector_node(
            max_attempts=max_attempts,
            content_quality_judge=content_quality_judge,
            ai_tech_draft_gate=ai_tech_draft_gate,
            psychology_learning_draft_gate=psychology_learning_draft_gate,
            psychology_carousel_draft_gate=psychology_carousel_draft_gate,
        ),
        finalize=build_finalize_node(
            execution_memory=execution_memory,
            artifact_store=artifact_store,
            ai_tech_evidence=normalized_ai_tech_evidence,
            ai_tech_evidence_manifest=normalized_ai_tech_evidence_manifest,
            psychology_learning_contract=normalized_psychology_learning_contract,
            psychology_learning_manifest=normalized_psychology_learning_manifest,
            psychology_learning_catalog_receipt=normalized_psychology_learning_catalog_receipt,
            psychology_learning_preflight_capability=(
                psychology_learning_preflight_capability
            ),
            psychology_carousel_draft_gate=psychology_carousel_draft_gate,
            expected_artifact_root_identity=expected_artifact_root_identity,
            ordinary_psychology_carousel_reservation_sink=(
                ordinary_psychology_carousel_reservation_sink
            ),
        ),
        checkpointer=checkpointer or InMemorySaver(),
    )
    if normalized_ai_tech_evidence is not None:
        return _BoundAiTechWorkflow(
            workflow=workflow,
            contract=normalized_ai_tech_evidence,
        )
    if normalized_psychology_learning_contract is not None:
        return _BoundPsychologyLearningWorkflow(
            workflow=workflow,
            contract=normalized_psychology_learning_contract,
        )
    if playbook_id == MODERN_PSYCHOLOGY_PLAYBOOK_ID:
        return _BoundOrdinaryPsychologyWorkflow(workflow=workflow)
    return workflow


def build_fengkuang_workflow(
    memory: ExecutionMemoryStore | None = None,
    drafting_agent: FengkuangDraftingAgent | None = None,
    max_attempts: int = 2,
    settings: Settings | None = None,
    artifact_store: FileArtifactStore | None = None,
    checkpointer: object | None = None,
    skill_context_resolver: SkillContextResolver | None = None,
    content_quality_judge_backend: object | None = None,
):
    """Build a dry-run fengkuang workflow with one revision loop."""
    return build_playbook_workflow(
        playbook_id="fengkuang_daily_post",
        domain=DOMAIN_FENGKUANG,
        memory=memory,
        drafting_agent=drafting_agent,
        max_attempts=max_attempts,
        settings=settings,
        artifact_store=artifact_store,
        checkpointer=checkpointer,
        skill_context_resolver=skill_context_resolver,
        content_quality_judge_backend=content_quality_judge_backend,
    )


def _playbook_requires_content_quality_judge(playbook_id: str) -> bool:
    contract = load_playbook_eval_contract(PLAYBOOK_ROOT, playbook_id)
    if contract is None:
        return False
    judge = contract.quality_judges.get("executor_content_quality")
    return isinstance(judge, dict) and judge.get("gate_level") == "required"


def _build_ai_tech_draft_gate(
    contract: Mapping[str, Any],
):
    """Bind a normalized contract outside graph state and checkpoint input."""

    def gate(_: ExecutionState, draft: dict[str, object]) -> list[str]:
        return validate_ai_tech_draft_contract(contract, draft)

    return gate


def _build_psychology_learning_draft_gate(
    contract: Mapping[str, Any],
):
    """Bind one approved lesson contract outside graph state and inputs."""

    def gate(_: ExecutionState, draft: dict[str, object]) -> list[str]:
        return validate_psychology_learning_draft_contract(contract, draft)

    return gate


def _build_psychology_carousel_draft_gate() -> PsychologyCarouselDraftGate:
    """Validate optional ordinary psychology slides without exposing bad text."""

    def gate(state: ExecutionState, draft: dict[str, object]) -> list[str]:
        raw_plan = draft.get("image_plan")
        if not isinstance(raw_plan, Mapping) or not _is_psychology_carousel_plan(
            raw_plan
        ):
            return []
        try:
            normalized_plan = normalize_psychology_carousel_plan(raw_plan)
        except (TypeError, ValueError) as exc:
            return [f"invalid psychology carousel plan: {_validation_error_detail(exc)}"]
        draft["image_plan"] = normalized_plan
        fingerprint = psychology_carousel_inner_pages_fingerprint(normalized_plan)
        if fingerprint in _recent_psychology_carousel_fingerprints(state):
            return ["psychology carousel inner pages repeat recent account memory"]
        return []

    return gate


def _validation_error_detail(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        try:
            details = errors()
        except Exception:
            details = None
        if isinstance(details, list) and details:
            parts = []
            for error in details:
                if not isinstance(error, dict):
                    continue
                location = ".".join(str(part) for part in error.get("loc", ()))
                message = str(error.get("msg", "")).strip()
                if location and message:
                    parts.append(f"{location}: {message}")
            if parts:
                return "; ".join(parts)
    return str(exc)


def _is_psychology_carousel_plan(raw_plan: Mapping[str, Any]) -> bool:
    return (
        "slides" in raw_plan
        or "carousel_style" in raw_plan
        or raw_plan.get("style") == "psychology_text_card"
        or raw_plan.get("role") == "text_carousel"
    )


def _recent_psychology_carousel_fingerprints(state: ExecutionState) -> set[str]:
    raw_fingerprints = state.get("recent_psychology_carousel_inner_fingerprints")
    if not isinstance(raw_fingerprints, list):
        return set()
    fingerprints: set[str] = set()
    for raw_fingerprint in raw_fingerprints:
        if not isinstance(raw_fingerprint, str):
            continue
        fingerprint = raw_fingerprint.strip()
        if _INNER_CAROUSEL_FINGERPRINT_PATTERN.fullmatch(fingerprint) is not None:
            fingerprints.add(fingerprint)
    return fingerprints


def _resolve_verified_psychology_learning_catalog_contract(
    *,
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
    catalog_receipt: Mapping[str, Any] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any] | None]:
    """Rebuild the selected lesson so public runtime calls cannot forge it."""
    if any(
        contract.get(field_name) != manifest.get(field_name)
        for field_name in ("series_id", "curriculum_version", "lesson_id", "lesson_number")
    ):
        raise ValueError(
            "psychology learning manifest does not match the selected catalog lesson"
        )
    if psychology_learning_preflight_capability is not None:
        preflight_bundle = require_sealed_psychology_learning_preflight_bundle(
            psychology_learning_preflight_capability
        )
    else:
        preflight_bundle = None
    try:
        if preflight_bundle is None:
            bundle = resolve_psychology_learning_selection(
                series_id=str(contract["series_id"]),
                lesson_id=str(contract["lesson_id"]),
                curriculum_version=str(contract["curriculum_version"]),
            )
        else:
            bundle = preflight_bundle
            if (
                contract.get("series_id") != bundle.series_id
                or contract.get("lesson_id") != bundle.lesson_id
                or contract.get("curriculum_version")
                != bundle.runtime_contract["curriculum_version"]
            ):
                raise ValueError("trusted psychology learning bundle does not match contract")
    except (KeyError, ValueError) as exc:
        raise ValueError("psychology learning catalog selection is invalid") from exc
    expected_contract = bundle.runtime_contract
    expected_manifest = bundle.manifest
    if dict(contract) != expected_contract or dict(manifest) != expected_manifest:
        raise ValueError(
            "psychology learning contract or manifest does not exactly match the approved catalog"
        )
    expected_catalog_receipt = verify_psychology_learning_catalog_receipt(
        bundle=bundle,
        receipt=catalog_receipt,
    )
    return expected_contract, expected_manifest, expected_catalog_receipt


def _build_ai_tech_workflow_input(
    *,
    contract: Mapping[str, Any],
    supplied: Mapping[str, Any],
) -> dict[str, str]:
    """Construct the complete initial AI graph state from an allowlist only."""
    account_id = supplied.get("account_id")
    if not isinstance(account_id, str) or not _SAFE_AI_RUNTIME_IDENTIFIER.fullmatch(
        account_id
    ):
        raise ValueError("AI tech workflow requires a safe account_id")

    platform = supplied.get("platform")
    if platform != "xiaohongshu":
        raise ValueError("AI tech workflow only supports platform xiaohongshu")

    return {
        "scene": _build_ai_tech_runtime_scene_from_contract(contract),
        "platform": "xiaohongshu",
        "account_id": account_id,
    }


def _build_psychology_learning_workflow_input(
    *,
    contract: Mapping[str, Any],
    supplied: Mapping[str, Any],
) -> dict[str, str]:
    """Build a graph input from safe identifiers plus the bound catalog lesson."""
    account_id = supplied.get("account_id")
    if not isinstance(account_id, str) or not _SAFE_AI_RUNTIME_IDENTIFIER.fullmatch(
        account_id
    ):
        raise ValueError("psychology learning workflow requires a safe account_id")

    platform = supplied.get("platform")
    if platform != "xiaohongshu":
        raise ValueError("psychology learning workflow only supports platform xiaohongshu")

    normalized = parse_psychology_learning_runtime_contract(contract)
    return {
        "scene": _build_psychology_learning_runtime_scene_from_contract(normalized),
        "platform": "xiaohongshu",
        "account_id": account_id,
    }


def _build_ordinary_psychology_workflow_input(
    supplied: Mapping[str, Any],
) -> dict[str, Any]:
    """Allow user inputs while excluding draft and control-state injection."""
    safe_input = {
        key: supplied[key]
        for key in ("scene", "platform", "account_id")
        if key in supplied
    }
    topic_selection = supplied.get("topic_selection")
    if isinstance(topic_selection, dict):
        safe_input["topic_selection"] = dict(topic_selection)
    return safe_input


def _build_psychology_learning_runtime_scene_from_contract(
    contract: Mapping[str, Any],
) -> str:
    normalized = parse_psychology_learning_runtime_contract(contract)
    return f"心理学学习专题：{normalized['series_badge']}｜{normalized['lesson_title']}"


def _build_ai_tech_runtime_scene_from_contract(contract: Mapping[str, Any]) -> str:
    payload = contract.get("drafting_payload")
    if not isinstance(payload, Mapping):
        raise ValueError("AI tech workflow requires a valid evidence payload")
    mode = contract.get("mode")
    if mode == "news_brief":
        items = payload.get("news_items")
        if not isinstance(items, (list, tuple)):
            raise ValueError("AI tech news brief payload is invalid")
        labels = [
            item.get("label", "").strip()
            for item in items
            if isinstance(item, Mapping) and isinstance(item.get("label"), str)
        ]
        if not labels:
            raise ValueError("AI tech news brief requires safe item labels")
        return f"AI 科技资讯简报：{' / '.join(labels)}"

    topic = payload.get("topic")
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("AI tech evidence payload requires a safe topic")
    if mode == "hands_on":
        hands_on = payload.get("hands_on")
        if not isinstance(hands_on, Mapping):
            raise ValueError("AI tech hands-on payload is invalid")
        product = hands_on.get("product")
        version = hands_on.get("version")
        task = hands_on.get("task")
        if not all(isinstance(value, str) and value.strip() for value in (product, version, task)):
            raise ValueError("AI tech hands-on payload is incomplete")
        return f"AI 科技实测：{topic.strip()}；{product.strip()} {version.strip()}；任务：{task.strip()}"
    if mode == "fact_translation":
        return f"AI 科技事实转译：{topic.strip()}"
    raise ValueError("AI tech workflow requires a known evidence mode")


def _sanitize_ai_tech_workflow_config(
    config: Mapping[str, Any] | None,
) -> dict[str, dict[str, str]] | None:
    if config is None:
        return None
    configurable = config.get("configurable")
    if not isinstance(configurable, Mapping):
        return {}
    thread_id = configurable.get("thread_id")
    if thread_id is None:
        return {}
    if not isinstance(thread_id, str) or not _SAFE_AI_RUNTIME_IDENTIFIER.fullmatch(thread_id):
        raise ValueError("AI tech workflow requires a safe thread_id")
    return {"configurable": {"thread_id": thread_id}}


def _psychology_learning_checkpoint_namespace(contract: Mapping[str, Any]) -> str:
    """Return a stable private checkpoint namespace for one catalog lesson."""
    normalized = parse_psychology_learning_runtime_contract(contract)
    identity = ":".join(
        (
            normalized["series_id"],
            normalized["curriculum_version"],
            normalized["lesson_id"],
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"ptsm-psychology-learning-{digest}"


def _sanitize_psychology_learning_workflow_config(
    config: Mapping[str, Any] | None,
    *,
    checkpoint_namespace: str,
) -> dict[str, dict[str, str]] | None:
    """Map public thread IDs into a catalog-private LangGraph checkpoint lane."""
    sanitized = _sanitize_ai_tech_workflow_config(config)
    if sanitized is None:
        return None
    configurable = sanitized.get("configurable", {})
    thread_id = configurable.get("thread_id")
    if not isinstance(thread_id, str):
        return sanitized
    digest = hashlib.sha256(
        f"{checkpoint_namespace}:{thread_id}".encode("utf-8")
    ).hexdigest()[:32]
    return {
        "configurable": {
            "thread_id": f"psychology-learning-{digest}",
        }
    }


def build_file_backed_runtime_state(
    base_dir: Path | str = DEFAULT_RUNTIME_STATE_DIR,
) -> tuple[FileExecutionMemory, FileCheckpointSaver]:
    root = Path(base_dir).resolve()
    return (
        FileExecutionMemory(path=root / "execution-memory.json"),
        FileCheckpointSaver(path=root / "checkpoints.pkl"),
    )


def build_finalize_node(
    *,
    execution_memory: ExecutionMemoryStore,
    artifact_store: FileArtifactStore,
    ai_tech_evidence: Mapping[str, Any] | None = None,
    ai_tech_evidence_manifest: Mapping[str, Any] | None = None,
    psychology_learning_contract: Mapping[str, Any] | None = None,
    psychology_learning_manifest: Mapping[str, Any] | None = None,
    psychology_learning_catalog_receipt: Mapping[str, Any] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
    psychology_carousel_draft_gate: PsychologyCarouselDraftGate | None = None,
    expected_artifact_root_identity: os.stat_result | None = None,
    ordinary_psychology_carousel_reservation_sink: (
        OrdinaryPsychologyCarouselReservationSink | None
    ) = None,
):
    normalized_ai_tech_manifest = (
        AiTechEvidenceManifest.model_validate(ai_tech_evidence_manifest).model_dump(mode="json")
        if ai_tech_evidence_manifest is not None
        else None
    )
    normalized_psychology_learning_manifest = (
        PsychologyLearningEvidenceManifest.model_validate(
            psychology_learning_manifest
        ).model_dump(mode="json")
        if psychology_learning_manifest is not None
        else None
    )

    def finalize(state: ExecutionState) -> ExecutionState:
        if state.get("reflection_decision") == "fail" or not state.get("final_content"):
            return {"status": "failed"}

        final_content = state["final_content"]
        if ai_tech_evidence is not None:
            validation_errors = validate_ai_tech_draft_contract(
                ai_tech_evidence,
                final_content,
            )
            if validation_errors:
                # The reflector owns retry feedback; this duplicate gate is the
                # durable-write backstop for future graph/custom node changes.
                return {
                    "status": "ai_tech_draft_invalid",
                    "reflection_decision": "fail",
                    "reflection_feedback": "; ".join(validation_errors),
                }
            if normalized_ai_tech_manifest is None:
                # A valid-looking draft without an opaque audit receipt is not
                # a completed AI evidence run.  This protects direct callers
                # of the finalize node as well as normal workflow assembly.
                return {
                    "status": "ai_tech_evidence_receipt_required",
                    "reflection_decision": "fail",
                    "reflection_feedback": "opaque AI evidence manifest is required",
                }

        if psychology_learning_contract is not None:
            validation_errors = validate_psychology_learning_draft_contract(
                psychology_learning_contract,
                final_content,
            )
            if validation_errors:
                return {
                    "status": "psychology_learning_draft_invalid",
                    "reflection_decision": "fail",
                    "reflection_feedback": "; ".join(validation_errors),
                }
            if normalized_psychology_learning_manifest is None:
                return {
                    "status": "psychology_learning_receipt_required",
                    "reflection_decision": "fail",
                    "reflection_feedback": "opaque psychology learning manifest is required",
                }
            _resolve_verified_psychology_learning_catalog_contract(
                contract=psychology_learning_contract,
                manifest=normalized_psychology_learning_manifest,
                catalog_receipt=psychology_learning_catalog_receipt,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
        elif psychology_carousel_draft_gate is not None:
            validation_errors = psychology_carousel_draft_gate(state, final_content)
            if validation_errors:
                return {
                    "status": "psychology_carousel_draft_invalid",
                    "reflection_decision": "fail",
                    "reflection_feedback": "; ".join(validation_errors),
                }

        content_review = _build_content_review(state)
        activated_skills = list(state.get("activated_skills", []))
        activated_skill_details = list(state.get("activated_skill_details", []))
        runtime_skill_details = list(state.get("runtime_skill_details", []))
        artifact_payload: dict[str, object] = {
            "playbook_id": state["playbook_id"],
            "drafting_provider": state["drafting_provider"],
            "loaded_skills": activated_skills,
            "activated_skills": activated_skills,
            "activated_skill_details": activated_skill_details,
            # AI contract facts remain prompt-only runtime context. The
            # finalizer writes only the opaque evidence manifest below.
            "runtime_skill_contents": (
                []
                if ai_tech_evidence is not None or psychology_learning_contract is not None
                else list(state.get("runtime_skill_contents", []))
            ),
            "runtime_skill_details": runtime_skill_details,
            "step_outputs": _build_step_outputs(state),
            "final_content": state["final_content"],
            "content_review": content_review,
        }
        if ai_tech_evidence is not None:
            assert normalized_ai_tech_manifest is not None
            artifact_payload.update(
                _build_ai_tech_evidence_receipt(
                    contract=ai_tech_evidence,
                    manifest=normalized_ai_tech_manifest,
                )
            )
        if psychology_learning_contract is not None:
            assert normalized_psychology_learning_manifest is not None
            artifact_payload.update(
                _build_psychology_learning_receipt(
                    contract=psychology_learning_contract,
                    manifest=normalized_psychology_learning_manifest,
                    catalog_receipt=psychology_learning_catalog_receipt,
                    psychology_learning_preflight_capability=(
                        psychology_learning_preflight_capability
                    ),
                )
            )

        lesson_memory_item: dict[str, object] | None = None
        fingerprint: str | None = None
        reservation_id: str | None = None
        lesson_namespace = ("accounts", state["account_id"], "lessons")
        if psychology_learning_contract is None:
            lesson_memory_item = {
                "playbook_id": state["playbook_id"],
                "scene": state["scene"],
                "attempt_count": state["attempt_count"],
                "title": final_content.get("title", ""),
                "image_text": final_content.get("image_text", ""),
                "hashtags": list(final_content.get("hashtags", [])),
                "final_body": final_content.get("body", ""),
            }
            fingerprint = _ordinary_psychology_carousel_inner_fingerprint(
                state=state,
                final_content=final_content,
            )
            if fingerprint is not None:
                lesson_memory_item["psychology_carousel_inner_fingerprint"] = fingerprint
                lesson_memory_item[ORDINARY_PSYCHOLOGY_CAROUSEL_MEMORY_MARKER] = True
                if not _supports_psychology_carousel_memory_reservations(
                    execution_memory
                ):
                    return {
                        "status": "psychology_carousel_memory_capability_required",
                        "reflection_decision": "fail",
                        "reflection_feedback": (
                            "execution memory lacks atomic psychology carousel reservations"
                        ),
                    }
                reservation_id = (
                    execution_memory.reserve_psychology_carousel_inner_fingerprint(
                        namespace=lesson_namespace,
                        fingerprint=fingerprint,
                        item=lesson_memory_item,
                    )
                )
                if reservation_id is None:
                    return {
                        "status": "psychology_carousel_draft_invalid",
                        "reflection_decision": "fail",
                        "reflection_feedback": (
                            "psychology carousel inner pages repeat recent account memory"
                        ),
                    }

        try:
            artifact_path = artifact_store.write(
                artifact_payload,
                run_key=f"{state['account_id']}-{state['playbook_id']}-{state['attempt_count']}",
                expected_base_identity=expected_artifact_root_identity,
            )
        except Exception:
            if fingerprint is not None and reservation_id is not None:
                execution_memory.release_psychology_carousel_inner_fingerprint(
                    namespace=lesson_namespace,
                    fingerprint=fingerprint,
                    reservation_id=reservation_id,
                )
            raise

        if lesson_memory_item is not None:
            if fingerprint is not None and reservation_id is not None:
                reservation = OrdinaryPsychologyCarouselMemoryReservation(
                    _execution_memory=execution_memory,
                    _namespace=lesson_namespace,
                    _fingerprint=fingerprint,
                    _reservation_id=reservation_id,
                    _item=lesson_memory_item,
                )
                if ordinary_psychology_carousel_reservation_sink is None:
                    # A direct workflow/finalizer invocation has no local
                    # renderer lifecycle to prove the carousel was created.
                    # Do not let artifact creation alone populate recent-12.
                    reservation.release()
                else:
                    try:
                        ordinary_psychology_carousel_reservation_sink(reservation)
                    except Exception:
                        reservation.release()
                        raise
            else:
                execution_memory.record(
                    namespace=lesson_namespace,
                    item=lesson_memory_item,
                )
        return {
            "status": "completed",
            "artifact_path": str(artifact_path),
            "content_review": content_review,
        }

    return finalize


def _ordinary_psychology_carousel_inner_fingerprint(
    *,
    state: ExecutionState,
    final_content: dict[str, object],
) -> str | None:
    if state.get("playbook_id") != MODERN_PSYCHOLOGY_PLAYBOOK_ID:
        return None
    raw_plan = final_content.get("image_plan")
    if not isinstance(raw_plan, Mapping) or not _is_psychology_carousel_plan(raw_plan):
        return None
    try:
        normalized_plan = normalize_psychology_carousel_plan(raw_plan)
    except (TypeError, ValueError):
        return None
    return psychology_carousel_inner_pages_fingerprint(normalized_plan)


def _supports_psychology_carousel_memory_reservations(
    execution_memory: object,
) -> bool:
    return all(
        callable(getattr(execution_memory, method_name, None))
        for method_name in (
            "reserve_psychology_carousel_inner_fingerprint",
            "renew_psychology_carousel_inner_fingerprint",
            "persist_psychology_carousel_inner_fingerprint_receipt_intent",
            "commit_psychology_carousel_inner_fingerprint_receipt_intent",
            "abort_psychology_carousel_inner_fingerprint_receipt_intent",
            "release_psychology_carousel_inner_fingerprint",
        )
    )


def _build_ai_tech_evidence_receipt(
    *,
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, object]:
    """Build the only AI evidence data that may be written to an artifact."""
    normalized_contract = parse_ai_tech_runtime_contract(contract)
    normalized_manifest = AiTechEvidenceManifest.model_validate(manifest).model_dump(mode="json")
    mode = normalized_contract["mode"]
    return {
        "ai_tech_content_mode": mode,
        "ai_tech_evidence_manifest": normalized_manifest,
        "ai_tech_evidence_gate": {
            "status": "passed",
            "mode": mode,
            "validator": "ai_tech_draft_contract",
            "validator_version": "1",
            "errors": [],
        },
    }


def _build_psychology_learning_receipt(
    *,
    contract: Mapping[str, Any],
    manifest: Mapping[str, Any],
    catalog_receipt: Mapping[str, Any] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> dict[str, object]:
    """Build the only catalog-audit data permitted in a lesson artifact."""
    normalized_contract = parse_psychology_learning_runtime_contract(contract)
    normalized_manifest = PsychologyLearningEvidenceManifest.model_validate(
        manifest
    ).model_dump(mode="json")
    (
        normalized_contract,
        normalized_manifest,
        normalized_catalog_receipt,
    ) = _resolve_verified_psychology_learning_catalog_contract(
        contract=normalized_contract,
        manifest=normalized_manifest,
        catalog_receipt=catalog_receipt,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
    )
    receipt: dict[str, object] = {
        "psychology_learning_mode": PSYCHOLOGY_LEARNING_MODE,
        "psychology_learning_series_id": normalized_contract["series_id"],
        "psychology_learning_curriculum_version": normalized_contract[
            "curriculum_version"
        ],
        "psychology_learning_lesson_id": normalized_contract["lesson_id"],
        "psychology_learning_lesson_number": normalized_contract["lesson_number"],
        "psychology_learning_evidence_manifest": normalized_manifest,
        "psychology_learning_gate": {
            "status": "passed",
            "series_id": normalized_contract["series_id"],
            "lesson_id": normalized_contract["lesson_id"],
            "validator": "psychology_learning_draft_contract",
            "validator_version": normalized_contract[
                "controlled_template_version"
            ],
            "errors": [],
        },
    }
    if normalized_catalog_receipt is not None:
        receipt["psychology_learning_catalog_receipt"] = normalized_catalog_receipt
    return receipt


def _build_step_outputs(state: ExecutionState) -> dict[str, object]:
    return {
        "planner": {
            "selected_playbook": state.get("selected_playbook"),
            "candidate_skills": list(state.get("candidate_skills", [])),
            "activated_skills": list(state.get("activated_skills", [])),
            "activated_skill_details": list(state.get("activated_skill_details", [])),
            "runtime_skill_details": list(state.get("runtime_skill_details", [])),
            "planner_prompt": state.get("planner_prompt"),
            "persona_prompt": state.get("persona_prompt"),
            "reflection_prompt": state.get("reflection_prompt"),
        },
        "executor": {
            "attempt_count": int(state.get("attempt_count", 0)),
            "draft_content": state.get("draft_content"),
        },
        "reflector": {
            "required_revision": state.get("required_revision"),
            "reflection_decision": state.get("reflection_decision"),
            "reflection_feedback": state.get("reflection_feedback"),
            "content_quality_eval": state.get("content_quality_eval"),
        },
    }


def _build_content_review(state: ExecutionState) -> dict[str, object]:
    final_content = state["final_content"]
    title = str(final_content.get("title", "")).strip()
    image_text = str(final_content.get("image_text", "")).strip()
    body = str(final_content.get("body", "")).strip()
    carousel_text = _collect_carousel_review_text(final_content)
    combined = f"{title}\n{image_text}\n{body}\n{carousel_text}"
    interaction_text = f"{body}\n{carousel_text}"
    comment_trigger = any(
        term in interaction_text
        for term in (
            "评论区",
            "接一句",
            "你最",
            "哪类瞬间",
            "哪派",
            "A.",
            "B.",
            "____",
        )
    )
    save_trigger = any(
        term in combined
        for term in (
            "可复制",
            "模板",
            "写在",
            "金句",
            "话术",
            "事实 / 猜测 / 下一步",
            "事实=",
            "猜测=",
            "下一步=",
            "三栏",
            "5分钟",
            "边界句",
            "消息草稿",
            "写下来",
            "备忘录",
            "存下来",
            "收藏",
            "收藏清单",
            "可收藏",
            "截图",
            "可截图",
            "清单",
            "三步",
            "先试",
            "记住",
            "记下来",
            "这一句",
            "句型",
        )
    )
    safety_risks = [
        term
        for term in (
            "精神病",
            "心理医生",
            "医院",
            "治疗",
            "用药",
            "诊断",
            "治好",
            "治好焦虑",
            "治愈抑郁",
        )
        if term in combined
    ]
    quality_eval = state.get("content_quality_eval")
    notes = [
        "人工确认：发布前请检查标题/封面是否像真实小红书首屏，而不是内部模板说明。",
    ]
    if isinstance(quality_eval, dict):
        notes.append(
            "LLM 内容质量门结果："
            f"{quality_eval.get('status', 'unknown')}，"
            f"{quality_eval.get('reason', 'no reason')}"
        )
    else:
        notes.append("本次未配置 LLM 内容质量门，只使用确定性规则和人工 review。")
    if not comment_trigger:
        notes.append("建议补充评论或角色认领提示。")
    if not save_trigger:
        notes.append("建议补充可复制句、模板、三栏工具或可截图清单。")
    if safety_risks:
        notes.append("发布前必须移除安全风险词：" + "、".join(safety_risks))

    runtime_skills = [
        str(item.get("skill_name"))
        for item in state.get("runtime_skill_details", [])
        if isinstance(item, dict) and item.get("skill_name")
    ]
    review: dict[str, object] = {
        "status": "needs_human_review",
        "publish_recommendation": "hold_for_human_confirmation",
        "generation_logic": {
            "playbook_id": state.get("playbook_id", ""),
            "account_id": state.get("account_id", ""),
            "scene": state.get("scene", ""),
            "title_cover_strategy": (
                "标题负责点出点击冲突，封面文案负责给用户一眼能截图/转发的句子"
            ),
            "interaction_strategy": (
                "已包含评论或角色认领提示"
                if comment_trigger
                else "缺少评论或角色认领提示"
            ),
            "save_strategy": (
                "已包含可复制或可保存元素"
                if save_trigger
                else "缺少可复制或可保存元素"
            ),
            "safety_strategy": (
                "未发现明显安全风险词"
                if not safety_risks
                else "发现安全风险词，发布前必须处理"
            ),
            "runtime_context_used": runtime_skills,
        },
        "quality_signals": {
            "hook_specificity": bool(title and image_text),
            "comment_trigger": comment_trigger,
            "save_trigger": save_trigger,
            "safety_risk_terms": safety_risks,
            "content_quality_judge_status": (
                quality_eval.get("status") if isinstance(quality_eval, dict) else "not_run"
            ),
        },
        "review_notes": notes,
    }
    image_form = _build_image_form_review(state)
    if image_form:
        review["image_form"] = image_form
    image_plan = _build_image_plan_review(final_content)
    if image_plan:
        review["image_plan"] = image_plan
    return review


def _build_image_plan_review(final_content: dict[str, object]) -> dict[str, object] | None:
    raw_plan = final_content.get("image_plan")
    if not isinstance(raw_plan, dict):
        return None
    if _is_psychology_carousel_plan(raw_plan):
        return normalize_psychology_carousel_plan(raw_plan)
    allowed_fields = (
        "backend",
        "style",
        "role",
        "text_density",
        "max_text_units",
        "cover_text_strategy",
        "reason",
        "prompt_focus",
    )
    image_plan = {
        field: str(raw_plan[field]).strip()
        for field in allowed_fields
        if raw_plan.get(field) is not None and str(raw_plan[field]).strip()
    }
    return image_plan or None


def _collect_carousel_review_text(final_content: dict[str, object]) -> str:
    raw_plan = final_content.get("image_plan")
    if not isinstance(raw_plan, dict):
        return ""
    raw_slides = raw_plan.get("slides")
    if not isinstance(raw_slides, (list, tuple)):
        return ""
    text_units: list[str] = []
    for raw_slide in raw_slides:
        if not isinstance(raw_slide, dict):
            continue
        headline = raw_slide.get("headline")
        if isinstance(headline, str) and headline.strip():
            text_units.append(headline.strip())
        body_lines = raw_slide.get("body_lines")
        if isinstance(body_lines, (list, tuple)):
            text_units.extend(
                line.strip()
                for line in body_lines
                if isinstance(line, str) and line.strip()
            )
    return "\n".join(text_units)


def _build_image_form_review(state: ExecutionState) -> dict[str, object] | None:
    if state.get("playbook_id") != "human_enrichment_daily_post":
        return None
    pattern_ids = _extract_format_pattern_ids(state)
    primary_ratio = _extract_format_context_value(state, "primary_ratio") or "3:4"
    sequence = _extract_image_sequence(state) or [
        "cover",
        "before state",
        "variable/material flat lay",
        "mini checklist",
        "after state",
        "comment invitation",
    ]
    carousel_brief = _build_carousel_brief(sequence)
    image_form: dict[str, object] = {
        "primary_ratio": primary_ratio,
        "cover_style": "real-life creator cover",
        "recommended_sequence": sequence,
        "carousel_brief": carousel_brief,
        "text_constraints": {
            "cover_max_chars": 14,
            "checklist_max_bullets": 3,
            "forbid_hashtags": True,
            "forbid_watermarks": True,
        },
        "notes": (
            "Use a real-life-looking vertical cover first. Treat generated images "
            "as mood/reference visuals, not factual before-after evidence."
        ),
    }
    if pattern_ids:
        image_form["image_pattern_id"] = pattern_ids[0]
        image_form["carousel_pattern_id"] = pattern_ids[1] if len(pattern_ids) > 1 else pattern_ids[0]
    return image_form


def _extract_format_pattern_ids(state: ExecutionState) -> list[str]:
    value = _extract_format_context_value(state, "pattern_ids")
    return [part.strip() for part in value.split(",") if part.strip()]


def _extract_image_sequence(state: ExecutionState) -> list[str]:
    value = _extract_format_context_value(state, "image_sequences")
    if not value:
        return []
    first_sequence = value.split("|", 1)[0]
    return [part.strip() for part in first_sequence.split("->") if part.strip()]


def _extract_format_context_value(state: ExecutionState, key: str) -> str:
    for content in state.get("runtime_skill_contents", []):
        text = str(content)
        if "# XHS Format Pattern Library Context" not in text:
            continue
        for line in text.splitlines():
            prefix = f"- {key}:"
            if line.startswith(prefix):
                return line[len(prefix):].strip()
    return ""


def _build_carousel_brief(sequence: list[str]) -> list[dict[str, object]]:
    purpose_by_role = {
        "cover": "3:4 cover with one short sentence",
        "before state": "show the ordinary friction or original state",
        "variable/material flat lay": "show the low-cost variable or material",
        "mini checklist": "show no more than three action bullets",
        "after state": "show the changed detail or sensory result",
        "comment invitation": "invite readers to share a concrete example",
    }
    return [
        {
            "slide": index,
            "role": role,
            "purpose": purpose_by_role.get(role, role),
            "text_limit": "one short sentence" if role == "cover" else "keep text sparse",
        }
        for index, role in enumerate(sequence, start=1)
    ]
