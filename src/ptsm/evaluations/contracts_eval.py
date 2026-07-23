from __future__ import annotations

from typing import Any, Mapping

from pydantic import ValidationError

from ptsm.domain.ai_tech_content import (
    AiTechEvidenceManifest,
    is_ai_tech_drafting_safe_text,
)
from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
    PsychologyLearningEvidenceManifest,
    contains_psychology_learning_raw_provenance,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
    verify_psychology_learning_catalog_receipt,
)
from ptsm.evaluations.contracts import EvalResult, EvaluatorSpec, EvalTarget
from ptsm.evaluations.rules import _result  # noqa: F401
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract


_AI_TECH_PLAYBOOK_ID = "ai_tech_daily_post"
_AI_TECH_CONTENT_MODES = frozenset(
    ("news_brief", "hands_on", "fact_translation")
)
_AI_TECH_GATE_FIELDS = frozenset(
    ("status", "mode", "validator", "validator_version", "errors")
)
_PSYCHOLOGY_LEARNING_PLAYBOOK_ID = "modern_psychology_post"
_PSYCHOLOGY_LEARNING_GATE_FIELDS = frozenset(
    ("status", "series_id", "lesson_id", "validator", "validator_version", "errors")
)
_AI_TECH_NON_HANDS_ON_EXPERIENCE_MARKERS = (
    "我",
    "本人",
    "亲自",
    "我实测",
    "我试了",
    "我测了",
    "我用了",
    "亲测",
    "实测",
    "跑了一遍",
    "试了",
    "试过",
    "测了",
    "跑了",
    "跑过",
    "上手",
    "用过",
    "体验",
    "观察到",
    "昨晚",
    "刚刚",
    "结果很",
    "效果很",
    "很稳",
)


def contract_artifact_root_fields(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:artifact.root_fields",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="artifact.root_fields",
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )
    required = [
        "playbook_id", "final_content", "activated_skill_details",
        "scene", "publish_mode",
    ]
    missing = [f for f in required if f not in ref]
    if missing:
        return EvalResult(
            eval_result_id=f"{target.target_id}:artifact.root_fields",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="artifact.root_fields",
            evaluator_version="1",
            status="failed",
            reason=f"missing required root fields: {missing}",
            score=0.0,
        )
    return EvalResult(
        eval_result_id=f"{target.target_id}:artifact.root_fields",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id="artifact.root_fields",
        evaluator_version="1",
        status="passed",
        reason="all required root fields present",
        score=1.0,
    )


def contract_skill_details_match(target: EvalTarget) -> EvalResult:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )
    activated = ref.get("activated_skills")
    details = ref.get("activated_skill_details", [])
    if not isinstance(activated, list) or not isinstance(details, list):
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="skipped",
            reason="activated_skills or activated_skill_details not lists",
        )
    detail_names = {
        d.get("skill_name")
        for d in details
        if isinstance(d, dict) and d.get("skill_name")
    }
    missing = [s for s in activated if s not in detail_names]
    if missing:
        return EvalResult(
            eval_result_id=f"{target.target_id}:skill_activation.details_match",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id="skill_activation.details_match",
            evaluator_version="1",
            status="failed",
            reason=f"activated skills missing details: {missing}",
            score=0.0,
        )
    return EvalResult(
        eval_result_id=f"{target.target_id}:skill_activation.details_match",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id="skill_activation.details_match",
        evaluator_version="1",
        status="passed",
        reason=f"all {len(activated)} skills have details",
        score=1.0,
    )


def contract_ai_tech_evidence_receipt(target: EvalTarget) -> EvalResult:
    """Audit the opaque evidence receipt on a completed AI-tech artifact.

    This is deliberately an offline regression/audit check rather than a
    publishing gate.  It validates only the receipt that finalize writes: a
    selected mode, an opaque manifest, and proof that the runtime draft gate
    passed.  Failure output is intentionally static and never copies artifact
    values, because a malformed historical artifact may itself contain raw
    source URLs, titles, authors, or feed identifiers.
    """
    evaluator_id = "ai_tech.evidence_receipt"
    if target.playbook_id != _AI_TECH_PLAYBOOK_ID:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="not an AI tech artifact",
        )

    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )

    failures: list[dict[str, str]] = []
    mode = ref.get("ai_tech_content_mode")
    if not isinstance(mode, str) or mode not in _AI_TECH_CONTENT_MODES:
        failures.append(_receipt_failure("ai_tech_content_mode", "unsupported content mode"))
        normalized_mode: str | None = None
    else:
        normalized_mode = mode

    manifest = _parse_ai_tech_manifest(ref, failures)
    if manifest is not None and normalized_mode is not None:
        _validate_manifest_for_mode(
            mode=normalized_mode,
            manifest=manifest,
            failures=failures,
        )

    _validate_receipt_gate(
        gate=ref.get("ai_tech_evidence_gate"),
        mode=normalized_mode,
        failures=failures,
    )
    _validate_visible_ai_tech_content(
        ref=ref,
        mode=normalized_mode,
        failures=failures,
    )

    if failures:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="failed",
            reason="; ".join(
                f"{item['path']}: {item['observation']}" for item in failures
            ),
            score=0.0,
            evidence=failures,
        )

    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status="passed",
        reason="AI tech evidence receipt is complete and provenance-safe",
        score=1.0,
    )


def contract_psychology_learning_receipt(target: EvalTarget) -> EvalResult:
    """Rebuild and audit a closed psychology-learning catalog receipt offline."""
    evaluator_id = "psychology.learning_receipt"
    if target.playbook_id != _PSYCHOLOGY_LEARNING_PLAYBOOK_ID:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="not a modern psychology artifact",
        )
    ref = target.output_ref
    if not isinstance(ref, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )

    receipt_keys = (
        "psychology_learning_mode",
        "psychology_learning_series_id",
        "psychology_learning_curriculum_version",
        "psychology_learning_lesson_id",
        "psychology_learning_lesson_number",
        "psychology_learning_catalog_receipt",
        "psychology_learning_evidence_manifest",
        "psychology_learning_gate",
    )
    has_receipt = any(key in ref for key in receipt_keys)
    catalog_marked = _is_catalog_marked_psychology_learning_artifact(ref)
    if not has_receipt and not catalog_marked:
        # Ordinary modern psychology posts remain valid and intentionally do
        # not acquire a learning-series audit contract retroactively.
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="not a psychology learning artifact",
        )
    if not has_receipt:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="failed",
            reason="catalog-marked psychology learning artifact is missing its required receipt",
            score=0.0,
            evidence=[
                _receipt_failure(
                    "psychology_learning_receipt",
                    "catalog-marked learning artifact is missing its required receipt",
                )
            ],
        )

    failures: list[dict[str, str]] = []
    if contains_psychology_learning_raw_provenance(ref):
        failures.append(
            _receipt_failure(
                "artifact_provenance",
                "raw provenance exists outside the opaque learning manifest",
            )
        )
    if ref.get("psychology_learning_mode") != PSYCHOLOGY_LEARNING_MODE:
        failures.append(
            _receipt_failure(
                "psychology_learning_mode",
                "unsupported learning mode",
            )
        )

    bundle = _resolve_psychology_learning_receipt_bundle(ref, failures)
    manifest = _parse_psychology_learning_manifest(ref, failures)
    if bundle is not None:
        _validate_psychology_learning_receipt_identity(
            ref=ref,
            bundle=bundle,
            manifest=manifest,
            failures=failures,
        )
        _validate_psychology_learning_gate(
            gate=ref.get("psychology_learning_gate"),
            bundle=bundle,
            failures=failures,
        )
        final_content = ref.get("final_content")
        if not isinstance(final_content, Mapping):
            failures.append(
                _receipt_failure("final_content", "learning artifact is missing final content")
            )
        else:
            validation_errors = validate_psychology_learning_draft_contract(
                bundle.runtime_contract,
                final_content,
            )
            if validation_errors:
                failures.append(
                    _receipt_failure(
                        "final_content",
                        "visible content does not match the approved lesson contract",
                    )
                )

    if failures:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="failed",
            reason="; ".join(
                f"{item['path']}: {item['observation']}" for item in failures
            ),
            score=0.0,
            evidence=failures,
        )
    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status="passed",
        reason="psychology learning receipt matches the approved catalog lesson",
        score=1.0,
    )


def _is_catalog_marked_psychology_learning_artifact(ref: Mapping[str, Any]) -> bool:
    topic_selection = ref.get("topic_selection")
    if not isinstance(topic_selection, Mapping):
        return False
    if topic_selection.get("source") != "psychology-learning-series":
        return False
    selection = topic_selection.get("psychology_learning")
    return isinstance(selection, Mapping)


def _resolve_psychology_learning_receipt_bundle(
    ref: Mapping[str, Any],
    failures: list[dict[str, str]],
):
    series_id = ref.get("psychology_learning_series_id")
    lesson_id = ref.get("psychology_learning_lesson_id")
    curriculum_version = ref.get("psychology_learning_curriculum_version")
    if not all(isinstance(value, str) and value.strip() for value in (series_id, lesson_id)):
        failures.append(
            _receipt_failure(
                "psychology_learning_selection",
                "learning receipt is missing a catalog series or lesson identifier",
            )
        )
        return None
    try:
        bundle = resolve_psychology_learning_selection(
            series_id=series_id,
            lesson_id=lesson_id,
            curriculum_version=(
                curriculum_version if isinstance(curriculum_version, str) else None
            ),
        )
    except ValueError:
        failures.append(
            _receipt_failure(
                "psychology_learning_selection",
                "learning receipt does not resolve to an approved catalog lesson",
            )
        )
        return None
    try:
        verify_psychology_learning_catalog_receipt(
            bundle=bundle,
            receipt=(
                ref.get("psychology_learning_catalog_receipt")
                if isinstance(ref.get("psychology_learning_catalog_receipt"), Mapping)
                else None
            ),
        )
    except ValueError:
        failures.append(
            _receipt_failure(
                "psychology_learning_catalog_receipt",
                "custom catalog receipt does not match the approved immutable catalog",
            )
        )
        return None
    return bundle


def _parse_psychology_learning_manifest(
    ref: Mapping[str, Any],
    failures: list[dict[str, str]],
) -> PsychologyLearningEvidenceManifest | None:
    raw_manifest = ref.get("psychology_learning_evidence_manifest")
    if not isinstance(raw_manifest, Mapping):
        failures.append(
            _receipt_failure(
                "psychology_learning_evidence_manifest",
                "learning receipt manifest is missing or invalid",
            )
        )
        return None
    try:
        return PsychologyLearningEvidenceManifest.model_validate(raw_manifest)
    except (TypeError, ValidationError):
        failures.append(
            _receipt_failure(
                "psychology_learning_evidence_manifest",
                "learning receipt manifest is missing or invalid",
            )
        )
        return None


def _validate_psychology_learning_receipt_identity(
    *,
    ref: Mapping[str, Any],
    bundle: Any,
    manifest: PsychologyLearningEvidenceManifest | None,
    failures: list[dict[str, str]],
) -> None:
    contract = bundle.runtime_contract
    expected_fields = {
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": contract["curriculum_version"],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
    }
    for field_name, expected in expected_fields.items():
        if ref.get(field_name) != expected:
            failures.append(
                _receipt_failure(
                    field_name,
                    "learning receipt identity does not match the approved catalog lesson",
                )
            )
    if manifest is None:
        return
    expected_manifest = bundle.manifest
    if manifest.model_dump(mode="json") != expected_manifest:
        failures.append(
            _receipt_failure(
                "psychology_learning_evidence_manifest",
                "learning manifest does not match the approved catalog lesson",
            )
        )


def _validate_psychology_learning_gate(
    *,
    gate: object,
    bundle: Any,
    failures: list[dict[str, str]],
) -> None:
    if not isinstance(gate, Mapping):
        failures.append(
            _receipt_failure(
                "psychology_learning_gate",
                "learning receipt gate is missing or invalid",
            )
        )
        return
    if {str(key) for key in gate} != _PSYCHOLOGY_LEARNING_GATE_FIELDS:
        failures.append(
            _receipt_failure(
                "psychology_learning_gate",
                "learning receipt gate has an invalid receipt shape",
            )
        )
    if gate.get("status") != "passed":
        failures.append(
            _receipt_failure(
                "psychology_learning_gate.status",
                "learning receipt gate did not pass",
            )
        )
    if gate.get("series_id") != bundle.series_id or gate.get("lesson_id") != bundle.lesson_id:
        failures.append(
            _receipt_failure(
                "psychology_learning_gate",
                "learning receipt gate does not match the approved lesson",
            )
        )
    if gate.get("validator") != "psychology_learning_draft_contract":
        failures.append(
            _receipt_failure(
                "psychology_learning_gate.validator",
                "learning receipt gate did not use the required validator",
            )
        )
    if gate.get("validator_version") != "1":
        failures.append(
            _receipt_failure(
                "psychology_learning_gate.validator_version",
                "learning receipt gate did not use the required validator version",
            )
        )
    errors = gate.get("errors")
    if not isinstance(errors, list) or errors:
        failures.append(
            _receipt_failure(
                "psychology_learning_gate.errors",
                "learning receipt gate must record an empty error list",
            )
        )


def _parse_ai_tech_manifest(
    ref: Mapping[str, Any],
    failures: list[dict[str, str]],
) -> AiTechEvidenceManifest | None:
    raw_manifest = ref.get("ai_tech_evidence_manifest")
    if not isinstance(raw_manifest, Mapping):
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_manifest",
                "AI tech evidence manifest is missing or invalid",
            )
        )
        return None
    try:
        return AiTechEvidenceManifest.model_validate(raw_manifest)
    except (TypeError, ValidationError):
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_manifest",
                "AI tech evidence manifest is missing or invalid",
            )
        )
        return None


def _validate_manifest_for_mode(
    *,
    mode: str,
    manifest: AiTechEvidenceManifest,
    failures: list[dict[str, str]],
) -> None:
    source_refs = manifest.source_refs
    test_evidence_refs = manifest.test_evidence_refs
    event_fingerprints = manifest.event_fingerprints

    if mode == "news_brief":
        if not source_refs:
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest.source_refs",
                    "news brief manifest requires opaque source references",
                )
            )
        if not 3 <= len(event_fingerprints) <= 5:
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest.event_fingerprints",
                    "news brief manifest requires 3 to 5 event fingerprints",
                )
            )
        elif len(set(event_fingerprints)) != len(event_fingerprints):
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest.event_fingerprints",
                    "news brief manifest requires distinct event fingerprints",
                )
            )
        if test_evidence_refs:
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest.test_evidence_refs",
                    "news brief manifest cannot contain hands-on test evidence",
                )
            )
        return

    if mode == "hands_on":
        if not test_evidence_refs:
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest.test_evidence_refs",
                    "hands-on manifest requires opaque test evidence references",
                )
            )
        if source_refs or event_fingerprints:
            failures.append(
                _receipt_failure(
                    "ai_tech_evidence_manifest",
                    "hands-on manifest contains evidence for a different content mode",
                )
            )
        return

    if not source_refs:
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_manifest.source_refs",
                "fact translation manifest requires opaque source references",
            )
        )
    if test_evidence_refs or event_fingerprints:
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_manifest",
                "fact translation manifest contains evidence for a different content mode",
            )
        )


def _validate_receipt_gate(
    *,
    gate: object,
    mode: str | None,
    failures: list[dict[str, str]],
) -> None:
    if not isinstance(gate, Mapping):
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate",
                "AI tech evidence gate is missing or invalid",
            )
        )
        return

    gate_keys = {str(key) for key in gate}
    if gate_keys != _AI_TECH_GATE_FIELDS:
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate",
                "AI tech evidence gate has an invalid receipt shape",
            )
        )
    if gate.get("status") != "passed":
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate.status",
                "AI tech evidence gate did not pass",
            )
        )
    if mode is not None and gate.get("mode") != mode:
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate.mode",
                "gate mode does not match receipt mode",
            )
        )
    if gate.get("validator") != "ai_tech_draft_contract":
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate.validator",
                "AI tech evidence gate did not use the required validator",
            )
        )
    if gate.get("validator_version") != "1":
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate.validator_version",
                "AI tech evidence gate did not use the required validator version",
            )
        )
    errors = gate.get("errors")
    if not isinstance(errors, list) or errors:
        failures.append(
            _receipt_failure(
                "ai_tech_evidence_gate.errors",
                "AI tech evidence gate must record an empty error list",
            )
        )


def _validate_visible_ai_tech_content(
    *,
    ref: Mapping[str, Any],
    mode: str | None,
    failures: list[dict[str, str]],
) -> None:
    final_content = ref.get("final_content")
    if not isinstance(final_content, Mapping):
        return

    visible_texts = _visible_content_texts(final_content)
    if any(not is_ai_tech_drafting_safe_text(text) for text in visible_texts):
        failures.append(
            _receipt_failure(
                "final_content",
                "AI tech visible content contains a raw source locator",
            )
        )
    if mode not in {"news_brief", "fact_translation"}:
        return
    visible_text = "\n".join(visible_texts)
    if any(marker in visible_text for marker in _AI_TECH_NON_HANDS_ON_EXPERIENCE_MARKERS):
        failures.append(
            _receipt_failure(
                "final_content",
                "non-hands-on content contains experiential language",
            )
        )


def _visible_content_texts(final_content: Mapping[str, Any]) -> tuple[str, ...]:
    texts = [
        value.strip()
        for key in ("title", "image_text", "body")
        if isinstance((value := final_content.get(key)), str) and value.strip()
    ]
    hashtags = final_content.get("hashtags")
    if isinstance(hashtags, list):
        texts.extend(tag.strip() for tag in hashtags if isinstance(tag, str) and tag.strip())
    return tuple(texts)


def _receipt_failure(path: str, observation: str) -> dict[str, str]:
    return {
        "path": path,
        "value_preview": "[redacted]",
        "observation": observation,
    }


def contract_playbook_node_contract(
    target: EvalTarget,
    playbook_contract: PlaybookEvalContract,
) -> EvalResult:
    evaluator_id = "playbook.node_contract"
    node_contract = playbook_contract.node_contracts.get(target.phase)
    if not isinstance(node_contract, dict):
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason=f"no playbook node contract for phase {target.phase}",
        )

    payload = _node_payload(target)
    if payload is None:
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="skipped",
            reason="no output ref",
        )

    failures: list[dict[str, object]] = []
    required_fields = node_contract.get("required_fields", [])
    if isinstance(required_fields, list):
        for field in required_fields:
            field_name = str(field)
            value = payload.get(field_name)
            if field_name not in payload or value is None or value == "":
                failures.append(
                    {
                        "path": _field_path(target, field_name),
                        "value_preview": str(value),
                        "observation": "missing required field",
                    }
                )

    constraints = node_contract.get("constraints", {})
    if isinstance(constraints, dict):
        failures.extend(_constraint_failures(target=target, payload=payload, constraints=constraints))

    if failures:
        reasons = [f"{item['path']}: {item['observation']}" for item in failures]
        return EvalResult(
            eval_result_id=f"{target.target_id}:{evaluator_id}",
            eval_run_id="",
            target_id=target.target_id,
            evaluator_id=evaluator_id,
            evaluator_version="1",
            status="failed",
            reason="; ".join(reasons),
            score=0.0,
            evidence=failures,
        )

    return EvalResult(
        eval_result_id=f"{target.target_id}:{evaluator_id}",
        eval_run_id="",
        target_id=target.target_id,
        evaluator_id=evaluator_id,
        evaluator_version="1",
        status="passed",
        reason=f"playbook node contract satisfied for phase {target.phase}",
        score=1.0,
    )


def _node_payload(target: EvalTarget) -> dict | None:
    ref = target.output_ref
    if not isinstance(ref, dict):
        return None
    if target.phase == "executor" and isinstance(ref.get("final_content"), dict):
        return ref["final_content"]
    return ref


def _field_path(target: EvalTarget, field_name: str) -> str:
    if target.phase == "executor":
        return f"final_content.{field_name}"
    return field_name


def _constraint_failures(
    *,
    target: EvalTarget,
    payload: dict,
    constraints: dict,
) -> list[dict[str, object]]:
    failures: list[dict[str, object]] = []
    title = payload.get("title")
    title_max_chars = constraints.get("title_max_chars")
    if isinstance(title, str) and isinstance(title_max_chars, int):
        if len(title) > title_max_chars:
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": f"title_max_chars exceeded: {len(title)} > {title_max_chars}",
                }
            )
    if isinstance(title, str):
        forbidden_titles = _string_list(constraints.get("title_must_not_equal_any"))
        if title in forbidden_titles:
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": f"title_must_not_equal_any violated: {title}",
                }
            )
        required_title_terms = _string_list(constraints.get("title_must_include_any"))
        if required_title_terms and not any(term in title for term in required_title_terms):
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": (
                        "title_must_include_any violated: "
                        f"missing one of {required_title_terms}"
                    ),
                }
            )
        tension_terms = _string_list(constraints.get("title_must_include_tension_any"))
        if tension_terms and not any(term in title for term in tension_terms):
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": (
                        "title_must_include_tension_any violated: "
                        f"missing one of {tension_terms}"
                    ),
                }
            )
        forbidden_title_terms = _string_list(
            constraints.get("title_must_not_include_any")
        )
        present_forbidden_title_terms = [
            term for term in forbidden_title_terms if term in title
        ]
        if present_forbidden_title_terms:
            failures.append(
                {
                    "path": _field_path(target, "title"),
                    "value_preview": title,
                    "observation": (
                        "title_must_not_include_any violated: "
                        f"found {present_forbidden_title_terms}"
                    ),
                }
            )

    image_text = payload.get("image_text")
    if isinstance(image_text, str):
        forbidden_image_texts = _string_list(
            constraints.get("image_text_must_not_equal_any")
        )
        if image_text in forbidden_image_texts:
            failures.append(
                {
                    "path": _field_path(target, "image_text"),
                    "value_preview": image_text,
                    "observation": (
                        "image_text_must_not_equal_any violated: "
                        f"{image_text}"
                    ),
                }
            )

    hashtags = payload.get("hashtags")
    if isinstance(hashtags, list):
        min_count = constraints.get("hashtags_min_count")
        max_count = constraints.get("hashtags_max_count")
        if isinstance(min_count, int) and len(hashtags) < min_count:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": f"hashtags_min_count violated: {len(hashtags)} < {min_count}",
                }
            )
        if isinstance(max_count, int) and len(hashtags) > max_count:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": f"hashtags_max_count violated: {len(hashtags)} > {max_count}",
                }
            )
        required_any = _string_list(constraints.get("hashtags_must_include_any"))
        if required_any and not any(tag in hashtags for tag in required_any):
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": (
                        "hashtags_must_include_any violated: "
                        f"missing one of {required_any}"
                    ),
                }
            )
        forbidden_any = _string_list(constraints.get("hashtags_must_not_include_any"))
        present_forbidden = [tag for tag in forbidden_any if tag in hashtags]
        if present_forbidden:
            failures.append(
                {
                    "path": _field_path(target, "hashtags"),
                    "value_preview": str(hashtags),
                    "observation": (
                        "hashtags_must_not_include_any violated: "
                        f"found {present_forbidden}"
                    ),
                }
            )

    body = payload.get("body")
    if isinstance(body, str):
        body_min_chars = constraints.get("body_min_chars")
        if isinstance(body_min_chars, int) and len(body) < body_min_chars:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_min_chars violated: "
                        f"{len(body)} < {body_min_chars}"
                    ),
                }
            )

        body_max_chars = _body_max_chars_for_payload(body=body, constraints=constraints)
        if isinstance(body_max_chars, int) and len(body) > body_max_chars:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_max_chars violated: "
                        f"{len(body)} > {body_max_chars}"
                    ),
                }
            )

        include_any = _string_list(constraints.get("body_must_include_any"))
        if include_any and not any(term in body for term in include_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_any violated: "
                        f"missing one of {include_any}"
                    ),
                }
            )

        include_all = _string_list(constraints.get("body_must_include_all"))
        missing_all = [term for term in include_all if term not in body]
        if missing_all:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_all violated: "
                        f"missing {missing_all}"
                    ),
                }
            )

        comment_prompt_any = _string_list(
            constraints.get("body_must_include_comment_prompt_any")
        )
        if comment_prompt_any and not any(term in body for term in comment_prompt_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_comment_prompt_any violated: "
                        f"missing one of {comment_prompt_any}"
                    ),
                }
            )

        save_trigger_any = _string_list(
            constraints.get("body_must_include_save_trigger_any")
        )
        if save_trigger_any and not any(term in body for term in save_trigger_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_include_save_trigger_any violated: "
                        f"missing one of {save_trigger_any}"
                    ),
                }
            )

        if constraints.get("body_must_include_scene_signal") is True:
            scene_signal_any = _string_list(constraints.get("body_scene_signal_any"))
            if scene_signal_any and not any(term in body for term in scene_signal_any):
                failures.append(
                    {
                        "path": _field_path(target, "body"),
                        "value_preview": body[:120],
                        "observation": (
                            "body_must_include_scene_signal violated: "
                            f"missing one of {scene_signal_any}"
                        ),
                    }
                )

        human_anchor_any = _string_list(constraints.get("body_human_anchor_any"))
        if human_anchor_any and not any(term in body for term in human_anchor_any):
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_human_anchor_any violated: "
                        f"missing one of {human_anchor_any}"
                    ),
                }
            )

        forbidden = _string_list(constraints.get("body_must_not_include_any"))
        present = [term for term in forbidden if term in body]
        if present:
            failures.append(
                {
                    "path": _field_path(target, "body"),
                    "value_preview": body[:120],
                    "observation": (
                        "body_must_not_include_any violated: "
                        f"found {present}"
                    ),
                }
            )
    combined_forbidden = _string_list(constraints.get("combined_must_not_include_any"))
    if combined_forbidden:
        combined_text = "\n".join(
            value
            for value in (title, image_text, body)
            if isinstance(value, str)
        )
        present = [term for term in combined_forbidden if term in combined_text]
        if present:
            failures.append(
                {
                    "path": (
                        "final_content.title/image_text/body"
                        if target.phase == "executor"
                        else "title/image_text/body"
                    ),
                    "value_preview": combined_text[:120],
                    "observation": (
                        "combined_must_not_include_any violated: "
                        f"found {present}"
                    ),
                }
            )
    return failures


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _body_max_chars_for_payload(*, body: str, constraints: dict) -> int | None:
    """Allow a bounded long asset only when every declared proof marker is present."""
    normal_max = constraints.get("body_max_chars")
    extended_max = constraints.get("body_extended_asset_max_chars")
    required_markers = _string_list(constraints.get("body_extended_asset_must_include_all"))
    if (
        isinstance(extended_max, int)
        and required_markers
        and all(marker in body for marker in required_markers)
    ):
        return extended_max
    return normal_max if isinstance(normal_max, int) else None


ALL_CONTRACT_EVALUATORS: list[EvaluatorSpec] = [
    EvaluatorSpec(
        "artifact.root_fields", "1", "contract", "shared observability",
        {"phases": ["final"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "skill_activation.details_match", "1", "contract", "shared skill/runtime",
        {"phases": ["planner"], "playbook_ids": [], "platforms": []},
        1.0, "required",
    ),
    EvaluatorSpec(
        "ai_tech.evidence_receipt", "1", "contract", "ai tech evidence boundary",
        {
            "phases": ["final"],
            "playbook_ids": [_AI_TECH_PLAYBOOK_ID],
            "platforms": [],
        },
        1.0, "required",
    ),
    EvaluatorSpec(
        "psychology.learning_receipt", "1", "contract", "psychology learning catalog boundary",
        {
            "phases": ["final"],
            "playbook_ids": [_PSYCHOLOGY_LEARNING_PLAYBOOK_ID],
            "platforms": [],
        },
        1.0, "required",
    ),
]
