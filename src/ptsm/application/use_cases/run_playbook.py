from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys
from typing import Any, Mapping, Sequence

from pydantic import ValidationError

from ptsm.accounts.registry import AccountRegistry
from ptsm.agent_runtime.runtime import (
    build_playbook_workflow,
    build_fengkuang_workflow,
    build_file_backed_runtime_state,
)
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.services.side_effect_ledger import SideEffectLedger
from ptsm.application.use_cases.guide_post import (
    SUPPORTED_PLAYBOOK_ID,
    build_topic_guidance,
    build_psychology_topic_guidance,
    resolve_psychology_lane,
)
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
)
from ptsm.application.use_cases.topic_guidance_packs import TOPIC_GUIDANCE_PACKS
from ptsm.application.use_cases.xhs_login import (
    DEFAULT_XHS_LOGIN_QRCODE_PATH,
    build_xhs_login_instructions,
    materialize_xhs_login_qrcode,
)
from ptsm.application.use_cases.xhs_browser import open_xhs_browser
from ptsm.application.use_cases.xhs_publish_status import check_xhs_publish_status
from ptsm.config.settings import Settings, get_settings
from ptsm.infrastructure.observability.run_store import RunStore
from ptsm.infrastructure.artifacts.file_store import (
    ArtifactFileIdentity,
    FileArtifactStore,
)
from ptsm.infrastructure.memory.store import ExecutionMemoryStore
from ptsm.infrastructure.images.asset_ledger import append_generated_image_assets
from ptsm.infrastructure.images.factory import build_image_backend
from ptsm.infrastructure.images.note_card_backend import NoteCardImageBackend
from ptsm.infrastructure.images.watermark_policy import generated_no_watermark_policy
from ptsm.infrastructure.images.watermark_remover import WatermarkRemover
from ptsm.infrastructure.publishers.contracts import Publisher
from ptsm.infrastructure.publishers.factory import build_publisher
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import PublisherPreflightError
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.domain.topic_guidance import resolve_topic_lane
from ptsm.domain.ai_tech_content import (
    AiTechEvidenceBundle,
    is_ai_tech_drafting_safe_text,
    parse_ai_tech_evidence_bundle,
    validate_ai_tech_draft,
)
from ptsm.domain.psychology_learning import (
    DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT,
    PSYCHOLOGY_LEARNING_MODE,
    PsychologyLearningBundle,
    PsychologyLearningEvidenceManifest,
    _PsychologyLearningPreflightCapability,
    build_psychology_learning_catalog_receipt,
    contains_psychology_learning_raw_provenance,
    require_sealed_psychology_learning_preflight_bundle,
    resolve_psychology_learning_selection,
    seal_psychology_learning_preflight_bundle,
    validate_psychology_learning_draft_contract,
)
from ptsm.skills.runtime_context import (
    PatternAwareTopicResearchContextBuilder,
    RedditDiscussionContextBuilder,
    SkillContextResolver,
    TopicResearchContextBuilder,
    XhsPatternContextBuilder,
    build_skill_context_resolver,
    run_topic_radar_scan,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
DEFAULT_SIDE_EFFECT_LEDGER_PATH = Path(".ptsm") / "agent_runtime" / "side-effects.json"
DEFAULT_GENERATED_IMAGES_DIR = Path("outputs") / "generated_images"
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_ATTEMPTS = 4
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_INTERVAL_SECONDS = 2.0
AI_TECH_PLAYBOOK_ID = "ai_tech_daily_post"
MODERN_PSYCHOLOGY_PLAYBOOK_ID = "modern_psychology_post"
_PSYCHOLOGY_LEARNING_ACCOUNT_ID_PATTERN = re.compile(
    r"^acct-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
_PSYCHOLOGY_LEARNING_RUN_ID_PATTERN = re.compile(
    r"^\d{8}T\d{6}Z-[0-9a-f]{8}$"
)
_PSYCHOLOGY_LEARNING_PUBLISH_STATUSES = frozenset(
    {"dry_run", "published", "login_required", "error", "unknown"}
)
_PSYCHOLOGY_LEARNING_POST_PUBLISH_STATUSES = frozenset(
    {
        "skipped",
        "unknown",
        "published",
        "published_visible",
        "published_search_verified",
        "manual_check_required",
        "login_required",
        "unsupported",
        "error",
        "failed",
    }
)


def _run_topic_radar_scan(*, output_dir: str) -> dict[str, Any]:
    """Run Topic Radar's public full-platform API for explicit fresh research."""
    print(f"\n{'='*60}")
    print(f"Topic Radar: scanning hot topics across platforms...")
    print(f"{'='*60}\n")
    return run_topic_radar_scan(output_dir)


def _interactive_topic_selection(scan_result: dict[str, Any]) -> dict[str, Any] | None:
    """Present topic radar results interactively and return user selection."""
    verticals = scan_result.get("verticals", [])
    angles = scan_result.get("recommended_angles", [])

    if not verticals and not angles:
        print("No evidence-backed topic directions are available.")
        return None

    print(f"\n{'='*60}")
    print("Discovered Content Verticals & Recommended Angles")
    print(f"{'='*60}\n")

    # Show scan summary
    summary = scan_result.get("scan_summary", "")
    if summary:
        print(f"Scan Summary: {summary}\n")

    # Show verticals
    for i, v in enumerate(verticals, 1):
        density_bar = {"high": "🔥🔥🔥", "medium": "🔥🔥", "low": "🔥"}.get(
            v.get("discussion_density", "medium"), "🔥🔥"
        )
        print(f"  [{i}] {v['name']}  {density_bar}  confidence: {v['confidence']:.0%}")
        if v.get("keywords"):
            print(f"      Keywords: {', '.join(v['keywords'])}")
        if v.get("sample_topics"):
            print(f"      Sample topics: {'; '.join(v['sample_topics'][:3])}")
        if v.get("suggested_angles"):
            print(f"      Suggested angles:")
            for angle in v["suggested_angles"]:
                print(f"        - {angle}")
        print()

    # Show recommended angles as a flat list
    if angles:
        offset = len(verticals)
        print(f"{'─'*60}")
        print("Additional recommended angles:\n")
        for j, a in enumerate(angles, 1):
            idx = offset + j
            print(f"  [{idx}] {a.get('angle', '')}")
            print(f"      Vertical: {a.get('vertical', '')}  |  Why: {a.get('why_discussion_likely', '')}")
            print()

    # User selection
    total_options = len(verticals) + len(angles)
    while True:
        try:
            choice = input(f"Select a topic [1-{total_options}] (or 'q' to quit): ").strip()
            if choice.lower() == "q":
                print("Cancelled.")
                sys.exit(0)
            idx = int(choice)
            if 1 <= idx <= total_options:
                break
            print(f"Please enter a number between 1 and {total_options}.")
        except ValueError:
            print(f"Please enter a valid number or 'q'.")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)

    # Build selection result
    if idx <= len(verticals):
        vertical = verticals[idx - 1]
        selected_angle = (
            vertical["suggested_angles"][0] if vertical.get("suggested_angles") else vertical["name"]
        )
        return _with_topic_radar_traceability(
            {
            "vertical": vertical["name"],
            "angle": selected_angle,
            "why_discussion_likely": vertical.get("discussion_density", ""),
            "keywords": vertical.get("keywords", []),
            "discussion_density": vertical.get("discussion_density", ""),
            "comment_themes": vertical.get("comment_themes", []),
            },
            scan_result=scan_result,
            selected=vertical,
        )
    else:
        angle = angles[idx - len(verticals) - 1]
        return _with_topic_radar_traceability(
            {
            "vertical": angle.get("vertical", ""),
            "angle": angle.get("angle", ""),
            "why_discussion_likely": angle.get("why_discussion_likely", ""),
            "keywords": [],
            "discussion_density": "",
            "comment_themes": [],
            },
            scan_result=scan_result,
            selected=angle,
        )


def _build_enriched_scene(selection: dict[str, Any]) -> str:
    """Build an enriched scene string from the user's topic selection."""
    parts = [
        f"选题方向：{selection['vertical']}",
    ]
    if selection.get("angle"):
        parts.append(f"切入角度：{selection['angle']}")
    if selection.get("why_discussion_likely"):
        parts.append(f"讨论诱因：{selection['why_discussion_likely']}")
    return "\n".join(parts)


def _with_topic_radar_traceability(
    selection: dict[str, Any],
    *,
    scan_result: dict[str, Any],
    selected: dict[str, Any],
) -> dict[str, Any]:
    """Keep opaque scan traceability in artifacts, not the enriched scene."""
    metadata = dict(selection)
    metadata["source"] = "topic-radar"
    for field in ("scan_quality", "artifact_path", "report_path"):
        value = scan_result.get(field)
        if isinstance(value, str) and value.strip():
            metadata[field] = value.strip()
    errors = scan_result.get("platform_errors")
    if isinstance(errors, dict):
        metadata["platform_errors"] = {
            str(platform): str(detail)
            for platform, detail in errors.items()
            if isinstance(platform, str) and isinstance(detail, str)
        }
    for field in ("cluster_id", "angle_signature", "event_fingerprint"):
        value = selected.get(field)
        if isinstance(value, str) and value.strip():
            metadata[field] = value.strip()
    evidence_ids = selected.get("evidence_ids")
    if isinstance(evidence_ids, list):
        metadata["evidence_ids"] = [
            value.strip() for value in evidence_ids if isinstance(value, str) and value.strip()
        ]
    return metadata


def _topic_scan_is_insufficient(scan_result: dict[str, Any]) -> bool:
    return str(scan_result.get("scan_quality") or "").strip() == "insufficient_evidence"


def _topic_research_receipt(scan_result: dict[str, Any]) -> dict[str, Any]:
    """Return only operator-safe freshness diagnostics on a blocked run."""
    receipt: dict[str, Any] = {
        "scan_quality": str(scan_result.get("scan_quality") or "insufficient_evidence"),
        "platform_errors": {},
        "artifact_path": "",
        "report_path": "",
    }
    errors = scan_result.get("platform_errors")
    if isinstance(errors, dict):
        receipt["platform_errors"] = {
            str(platform): str(detail)
            for platform, detail in errors.items()
            if isinstance(platform, str) and isinstance(detail, str)
        }
    for field in ("artifact_path", "report_path"):
        value = scan_result.get(field)
        if isinstance(value, str) and value.strip():
            receipt[field] = value.strip()
    return receipt


def _topic_selection_metadata(
    topic_selection: dict[str, Any] | None,
    topic_direction_id: str | None,
    *,
    playbook_id: str,
    scene: str,
) -> dict[str, Any] | None:
    if topic_selection is None and not topic_direction_id:
        return None

    metadata = dict(topic_selection or {})
    if topic_direction_id:
        metadata["topic_direction_id"] = topic_direction_id
        metadata.setdefault("source", "guide-post")
        direction = _resolve_topic_direction_payload(
            playbook_id=playbook_id,
            scene=scene,
            topic_direction_id=topic_direction_id,
        )
        if direction is not None:
            metadata["direction"] = direction
    return metadata


def _resolve_topic_direction_payload(
    *,
    playbook_id: str,
    scene: str,
    topic_direction_id: str,
) -> dict[str, Any] | None:
    if playbook_id == SUPPORTED_PLAYBOOK_ID:
        lane = resolve_psychology_lane(scene=scene)
        guidance = build_psychology_topic_guidance(
            scene=scene,
            lane_name=lane.name,
        )
    else:
        pack = TOPIC_GUIDANCE_PACKS.get(playbook_id)
        if pack is None:
            return None
        lane = resolve_topic_lane(lanes=pack.lanes, scene=scene)
        guidance = build_topic_guidance(
            pack=pack,
            scene=scene,
            lane_name=lane.name,
        )

    directions = guidance.get("directions")
    if not isinstance(directions, list):
        return None
    for direction in directions:
        if isinstance(direction, dict) and direction.get("id") == topic_direction_id:
            return direction
    return None


def _resolve_ai_tech_evidence_preflight(
    *,
    request: PlaybookRequest,
    platform: str,
    playbook_id: str,
) -> tuple[AiTechEvidenceBundle | None, dict[str, Any] | None]:
    """Validate AI evidence before a run, workflow, artifact, or publisher exists."""
    response_context = {
        # An AI evidence failure occurs before the free-form scene has been
        # normalized.  Never echo that operator input back in an application
        # response: it can contain raw headlines, URLs, authors, or feeds.
        "scene": "AI 科技证据模式",
        "platform": platform,
        "account_id": request.account_id,
        "playbook_id": playbook_id,
    }
    if not request.ai_content_mode or request.ai_evidence_bundle is None:
        return None, {
            **response_context,
            "status": "ai_tech_evidence_required",
            "next_step": (
                "Choose --ai-content-mode and provide --ai-evidence-file with "
                "the required evidence bundle before drafting AI tech content."
            ),
        }

    try:
        evidence_bundle = parse_ai_tech_evidence_bundle(request.ai_evidence_bundle)
    except ValidationError:
        return None, {
            **response_context,
            "status": "ai_tech_evidence_invalid",
            "diagnostic": "invalid_evidence_bundle",
        }

    if request.ai_content_mode != evidence_bundle.mode:
        return None, {
            **response_context,
            "status": "ai_tech_evidence_invalid",
            "diagnostic": "content_mode_mismatch",
        }
    return evidence_bundle, None


def _is_matching_ai_tech_topic_direction(
    *,
    topic_direction_id: str,
    content_mode: str,
) -> bool:
    """Accept only a current static AI direction for the selected evidence mode."""
    pack = TOPIC_GUIDANCE_PACKS.get(AI_TECH_PLAYBOOK_ID)
    if pack is None:
        return False
    return any(
        direction.id == topic_direction_id and direction.content_mode == content_mode
        for direction in pack.directions
    )


def _build_ai_tech_runtime_scene(evidence: AiTechEvidenceBundle) -> str:
    """Build the only scene text an evidence-gated AI run may receive.

    ``scene`` is still consumed by the generic executor, artifact flow, and
    image helpers.  For AI tech it therefore cannot be the operator's free
    text (which may contain raw headlines or provenance); derive a compact
    label solely from the already-validated drafting payload instead.
    """
    payload = evidence.drafting_payload
    if evidence.mode == "news_brief":
        labels = [
            str(item.get("label") or "").strip()
            for item in payload["news_items"]
            if isinstance(item, dict)
        ]
        return f"AI 科技资讯简报：{' / '.join(label for label in labels if label)}"

    topic = str(payload.get("topic") or "").strip()
    if evidence.mode == "hands_on":
        hands_on = payload.get("hands_on")
        if isinstance(hands_on, dict):
            product = str(hands_on.get("product") or "").strip()
            version = str(hands_on.get("version") or "").strip()
            task = str(hands_on.get("task") or "").strip()
            return f"AI 科技实测：{topic}；{product} {version}；任务：{task}"
    return f"AI 科技事实转译：{topic}"


def _build_ai_tech_evidence_receipt(evidence: AiTechEvidenceBundle) -> dict[str, object]:
    """Return the opaque receipt that an AI artifact may retain or expose."""
    return {
        "ai_tech_content_mode": evidence.mode,
        "ai_tech_evidence_manifest": evidence.manifest.model_dump(mode="json"),
        "ai_tech_evidence_gate": {
            "status": "passed",
            "mode": evidence.mode,
            "validator": "ai_tech_draft_contract",
            "validator_version": "1",
            "errors": [],
        },
    }


def _is_safe_ai_tech_artifact(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    expected_final_content: dict[str, Any],
) -> bool:
    """Check an AI artifact before adding an opaque receipt or publishing.

    A custom workflow may return a path it did not create.  Never merge into a
    foreign or provenance-bearing JSON document: that would persist raw source
    data even when the final draft itself passed the AI evidence gate.
    """
    path = Path(artifact_path)
    try:
        owned_root = artifact_store.base_dir.resolve()
        path.resolve().relative_to(owned_root)
        artifact = artifact_store.read(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False

    if artifact.get("playbook_id") != AI_TECH_PLAYBOOK_ID:
        return False
    if artifact.get("final_content") != expected_final_content:
        return False
    return not _contains_raw_ai_tech_provenance(artifact)


def _contains_raw_ai_tech_provenance(value: object) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _is_raw_ai_tech_provenance_key(str(key)):
                return True
            if _contains_raw_ai_tech_provenance(nested):
                return True
        return False
    if isinstance(value, list):
        return any(_contains_raw_ai_tech_provenance(item) for item in value)
    if isinstance(value, tuple):
        return any(_contains_raw_ai_tech_provenance(item) for item in value)
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not is_ai_tech_drafting_safe_text(value)
    )


def _is_raw_ai_tech_provenance_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in {
        "author",
        "authorname",
        "feed",
        "feedid",
        "feedidentifier",
        "rawheadline",
        "rawsourcetitle",
        "rawsourceurl",
        "sourceauthor",
        "sourcetitle",
        "sourceurl",
    }


def _is_psychology_learning_request(request: PlaybookRequest) -> bool:
    """Return whether the caller is opting into the closed learning submode."""
    return bool(
        (request.psychology_content_mode or "").strip()
        or request.psychology_series_id is not None
        or request.psychology_lesson_id is not None
        or request.psychology_curriculum_version is not None
    )


def _resolve_psychology_learning_preflight(
    *,
    request: PlaybookRequest,
    platform: str,
    playbook_id: str,
) -> tuple[_PsychologyLearningPreflightCapability | None, dict[str, Any] | None]:
    """Resolve only an explicit catalog selection before side effects exist."""
    response_context = {
        # Never echo a free scene on this path. It may include an operator's
        # unreviewed psychological claim, source URL, or personal detail.
        "scene": "心理学学习专题",
        "platform": platform,
        "account_id": request.account_id,
        "playbook_id": playbook_id,
    }
    mode = (request.psychology_content_mode or "").strip()
    series_id = (request.psychology_series_id or "").strip()
    lesson_id = (request.psychology_lesson_id or "").strip()
    curriculum_version = (request.psychology_curriculum_version or "").strip()
    if (
        mode != PSYCHOLOGY_LEARNING_MODE
        or not series_id
        or not lesson_id
        or not curriculum_version
    ):
        return None, {
            **response_context,
            "status": "psychology_learning_required",
            "next_step": (
                "Choose --psychology-content-mode learning_series and provide "
                "an approved --psychology-series-id and --psychology-lesson-id "
                "and --psychology-curriculum-version "
                "before drafting psychology learning content."
            ),
        }
    try:
        bundle = resolve_psychology_learning_selection(
            series_id=series_id,
            lesson_id=lesson_id,
            curriculum_version=curriculum_version,
        )
    except ValueError:
        return None, {
            **response_context,
            "status": "psychology_learning_invalid",
            "diagnostic": "unknown_or_malformed_catalog_selection",
        }
    if request.local_image_style or request.publish_image_paths:
        return None, {
            **response_context,
            "status": "psychology_learning_image_override_invalid",
            "diagnostic": "learning_series_uses_the_catalog_image_plan_only",
        }
    try:
        return seal_psychology_learning_preflight_bundle(bundle), None
    except ValueError:
        return None, {
            **response_context,
            "status": "psychology_learning_invalid",
            "diagnostic": "catalog_confirmation_could_not_be_verified",
        }


def _build_psychology_learning_runtime_scene(bundle: PsychologyLearningBundle) -> str:
    contract = bundle.runtime_contract
    return (
        f"心理学学习专题：{contract['series_badge']}｜{contract['lesson_title']}"
    )


def _build_psychology_learning_topic_selection(
    bundle: PsychologyLearningBundle,
) -> dict[str, Any]:
    """Build safe topic metadata from the catalog, never the operator scene."""
    return {
        "source": "psychology-learning-series",
        "topic_direction_id": bundle.direction_id,
        "direction": bundle.public_direction,
        "psychology_learning": {
            "series_id": bundle.series_id,
            "curriculum_version": bundle.runtime_contract["curriculum_version"],
            "lesson_id": bundle.lesson_id,
            "lesson_number": bundle.lesson_number,
        },
    }


def _build_psychology_learning_topic_guidance(
    bundle: PsychologyLearningBundle,
) -> dict[str, Any]:
    return {
        "status": "available",
        "message": "请确认已审核专题中的具体课次；自由场景不能替换课程概念或练习。",
        "selection_policy": "catalog_learning_series",
        "matched_direction_id": bundle.direction_id,
        "open_direction_id": "",
        "open_direction_ids": [],
        "direction_type_counts": {"learning_series_lesson": len(bundle.roadmap)},
        "directions": [lesson.public_direction for lesson in bundle.lessons],
    }


def _build_psychology_learning_receipt(
    bundle: PsychologyLearningBundle,
) -> dict[str, object]:
    manifest = PsychologyLearningEvidenceManifest.model_validate(bundle.manifest).model_dump(
        mode="json"
    )
    contract = bundle.runtime_contract
    receipt: dict[str, object] = {
        "psychology_learning_mode": PSYCHOLOGY_LEARNING_MODE,
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": contract["curriculum_version"],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
        "psychology_learning_evidence_manifest": manifest,
        "psychology_learning_gate": {
            "status": "passed",
            "series_id": bundle.series_id,
            "lesson_id": bundle.lesson_id,
            "validator": "psychology_learning_draft_contract",
            "validator_version": str(contract["controlled_template_version"]),
            "errors": [],
        },
    }
    catalog_receipt = build_psychology_learning_catalog_receipt(bundle)
    if catalog_receipt is not None:
        receipt["psychology_learning_catalog_receipt"] = catalog_receipt
    return receipt


def _build_psychology_learning_artifact_update(
    *,
    account: object,
    effective_scene: str,
    platform: str,
    publish_mode: str,
    publish_result: object,
    image_generation: object,
    watermark_removal: object,
    run_id: str,
) -> dict[str, object]:
    """Persist a closed operational receipt for a catalog lesson artifact."""
    artifact_update: dict[str, object] = {
        "scene": effective_scene,
        "platform": "xiaohongshu",
        "publish_mode": _normalize_psychology_learning_publish_mode(publish_mode),
        # Learning rendering does not consume format-library prose; retaining
        # a path to the library would create an unnecessary provenance surface.
        "format_patterns_used": {"status": "not_used"},
    }
    account_receipt = _sanitize_psychology_learning_account(account)
    if account_receipt is not None:
        artifact_update["account"] = account_receipt
    publish_receipt = _sanitize_psychology_learning_publish_result(publish_result)
    if publish_receipt is not None:
        artifact_update["publish_result"] = publish_receipt
    image_receipt = _sanitize_psychology_learning_image_generation(image_generation)
    if image_receipt is not None:
        artifact_update["image_generation"] = image_receipt
    watermark_receipt = _sanitize_psychology_learning_watermark_removal(
        watermark_removal
    )
    if watermark_receipt is not None:
        artifact_update["watermark_removal"] = watermark_receipt
    if _PSYCHOLOGY_LEARNING_RUN_ID_PATTERN.fullmatch(run_id):
        artifact_update["run"] = {"run_id": run_id}
    return artifact_update


def _build_psychology_learning_artifact_envelope(
    *,
    final_content: dict[str, Any],
    learning_receipt: dict[str, object],
) -> dict[str, object]:
    """Drop workflow-internal fields before a closed lesson reaches publishing.

    The generic runtime may carry prompts, tool metadata, and arbitrary custom
    workflow fields.  Learning artifacts deliberately retain only the exact
    approved draft, opaque receipt, and empty skill lists required by the
    shared artifact contract.  Publish metadata is added later through the
    dedicated sanitizers above.
    """
    return {
        "playbook_id": MODERN_PSYCHOLOGY_PLAYBOOK_ID,
        "activated_skills": [],
        "activated_skill_details": [],
        "final_content": final_content,
        "topic_selection": _build_psychology_learning_artifact_topic_marker(
            learning_receipt
        ),
        **learning_receipt,
    }


def _build_psychology_learning_artifact_topic_marker(
    learning_receipt: Mapping[str, object],
) -> dict[str, object]:
    """Keep a minimal catalog marker if a receipt is later tampered away."""
    return {
        "source": "psychology-learning-series",
        "psychology_learning": {
            "series_id": learning_receipt["psychology_learning_series_id"],
            "curriculum_version": learning_receipt[
                "psychology_learning_curriculum_version"
            ],
            "lesson_id": learning_receipt["psychology_learning_lesson_id"],
            "lesson_number": learning_receipt["psychology_learning_lesson_number"],
        },
    }


def _sanitize_psychology_learning_account(account: object) -> dict[str, str] | None:
    account_id = getattr(account, "account_id", None)
    if not isinstance(account_id, str) or not _PSYCHOLOGY_LEARNING_ACCOUNT_ID_PATTERN.fullmatch(
        account_id
    ):
        return None
    if getattr(account, "platform", None) != "xiaohongshu":
        return None
    return {"account_id": account_id, "platform": "xiaohongshu"}


def _sanitize_psychology_learning_publish_result(value: object) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    return {"status": _normalize_psychology_learning_publish_status(value.get("status"))}


def _sanitize_psychology_learning_post_publish_checks(
    value: Mapping[str, Any],
) -> dict[str, object]:
    receipt: dict[str, object] = {
        "requested": bool(value.get("requested")),
        "browser_opened": bool(value.get("browser_opened")),
        "publish_status": _normalize_psychology_learning_post_publish_status(
            value.get("publish_status")
        ),
    }
    status_result = _sanitize_psychology_learning_status_result(value.get("status_result"))
    if status_result is not None:
        receipt["status_result"] = status_result
    return receipt


def _sanitize_psychology_learning_status_result(
    value: object,
) -> dict[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    receipt: dict[str, str] = {
        "status": _normalize_psychology_learning_post_publish_status(
            value.get("status")
        )
    }
    source = value.get("source")
    if source in {"mcp", "mcp_search"}:
        receipt["source"] = str(source)
    return receipt


def _sanitize_psychology_learning_image_generation(
    value: object,
) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    provenance = value.get("provenance")
    image_count = value.get("image_count")
    manifest_sha256 = value.get("manifest_sha256")
    if (
        value.get("status") != "committed"
        or value.get("provider") != "local_note_card"
        or value.get("carousel_style") != "psychology_text_card_v1"
        or not isinstance(image_count, int)
        or isinstance(image_count, bool)
        or not 4 <= image_count <= 7
        or not isinstance(manifest_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", manifest_sha256) is None
        or not isinstance(provenance, Mapping)
        or provenance.get("source") != "ptsm_local_renderer"
    ):
        return None
    return {
        "status": "committed",
        "renderer": "ptsm_local_renderer",
        "carousel_style": "psychology_text_card_v1",
        "image_count": image_count,
        "manifest_sha256": manifest_sha256,
    }


def _sanitize_psychology_learning_watermark_removal(
    value: object,
) -> dict[str, object] | None:
    if not isinstance(value, Mapping):
        return None
    if value.get("status") != "skipped":
        return None
    return {"status": "skipped"}


def _normalize_psychology_learning_publish_mode(value: object) -> str:
    return value if value in {"dry-run", "mcp-real"} else "dry-run"


def _normalize_psychology_learning_publish_status(value: object) -> str:
    return (
        value
        if value in _PSYCHOLOGY_LEARNING_PUBLISH_STATUSES
        else "unknown"
    )


def _normalize_psychology_learning_post_publish_status(value: object) -> str:
    return (
        value
        if value in _PSYCHOLOGY_LEARNING_POST_PUBLISH_STATUSES
        else "unknown"
    )


@dataclass(frozen=True)
class _PsychologyLearningArtifactScope:
    """Filesystem identities trusted before an untrusted learning workflow runs."""

    owned_root_path: Path
    owned_root_identity: os.stat_result
    reserved_catalog_root_path: Path
    reserved_catalog_root_identity: os.stat_result | None
    reserved_progress_identity: os.stat_result | None


def _capture_psychology_learning_artifact_scope(
    *,
    artifact_store: FileArtifactStore,
    require_progress_identity: bool = False,
) -> _PsychologyLearningArtifactScope | None:
    """Freeze storage roots so later validation cannot re-authorize a rebound path."""
    try:
        # ``absolute`` preserves the operator-facing path spelling.  We must
        # revisit that spelling later, rather than resolving a fresh root
        # after workflow code has had an opportunity to rebind it.
        owned_root_path = artifact_store.base_dir.absolute()
        reserved_catalog_root_path = (
            DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT.absolute()
        )
        # A fresh builtin lesson has no catalog persistence yet, so establish
        # its writable root before workflow code can touch it.  The lexical
        # leaf itself must be a real directory rather than a final symlink.
        owned_root_path.mkdir(parents=True, exist_ok=True)
        owned_root_entry = owned_root_path.lstat()
        if not stat.S_ISDIR(owned_root_entry.st_mode):
            return None
        owned_root_identity = owned_root_path.resolve().stat()
        if not stat.S_ISDIR(owned_root_identity.st_mode):
            return None
        try:
            reserved_catalog_root_entry = reserved_catalog_root_path.lstat()
        except FileNotFoundError:
            # ``None`` records that the catalog root was intentionally absent
            # at preflight.  Its later appearance is a scope violation, not a
            # reason to rediscover a mutable path.
            reserved_catalog_root_identity = None
            reserved_progress_identity = None
        else:
            if not stat.S_ISDIR(reserved_catalog_root_entry.st_mode):
                return None
            reserved_catalog_root_identity = reserved_catalog_root_path.resolve().stat()
            if not stat.S_ISDIR(reserved_catalog_root_identity.st_mode):
                return None
            reserved_progress_identity = None
            if require_progress_identity:
                reserved_progress_identity = (
                    PsychologyLearningSeriesStore(
                        catalog_root=reserved_catalog_root_path
                    )._capture_pinned_progress_directory_identity(
                        expected_catalog_root_identity=(
                            reserved_catalog_root_identity
                        )
                    )
                )
        if require_progress_identity and reserved_progress_identity is None:
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return _PsychologyLearningArtifactScope(
        owned_root_path=owned_root_path,
        owned_root_identity=owned_root_identity,
        reserved_catalog_root_path=reserved_catalog_root_path,
        reserved_catalog_root_identity=reserved_catalog_root_identity,
        reserved_progress_identity=reserved_progress_identity,
    )


def _is_psychology_learning_artifact_scope_intact(
    scope: _PsychologyLearningArtifactScope,
) -> bool:
    """Reject a learning run once either trusted storage boundary changes."""
    try:
        current_owned_root_entry = scope.owned_root_path.lstat()
        if not stat.S_ISDIR(current_owned_root_entry.st_mode):
            return False
        current_owned_root = scope.owned_root_path.resolve().stat()
        try:
            current_reserved_catalog_root_entry = (
                scope.reserved_catalog_root_path.lstat()
            )
        except FileNotFoundError:
            current_reserved_catalog_root = None
        else:
            if not stat.S_ISDIR(current_reserved_catalog_root_entry.st_mode):
                return False
            current_reserved_catalog_root = (
                scope.reserved_catalog_root_path.resolve().stat()
            )
    except (OSError, RuntimeError, ValueError):
        return False
    if scope.reserved_catalog_root_identity is None:
        reserved_catalog_root_matches = current_reserved_catalog_root is None
    else:
        reserved_catalog_root_matches = (
            current_reserved_catalog_root is not None
            and os.path.samestat(
                current_reserved_catalog_root,
                scope.reserved_catalog_root_identity,
            )
        )
    return (
        stat.S_ISDIR(current_owned_root.st_mode)
        and os.path.samestat(current_owned_root, scope.owned_root_identity)
        and reserved_catalog_root_matches
    )


def _is_safe_psychology_learning_artifact(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    expected_final_content: dict[str, Any],
    strict_artifact_shape: bool = False,
    scope: _PsychologyLearningArtifactScope | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> bool:
    """Require an owned, provenance-safe artifact before a lesson can publish."""
    entry = _owned_psychology_learning_artifact_entry(
        artifact_store=artifact_store,
        artifact_path=artifact_path,
        scope=scope,
    )
    if entry is None:
        return False
    path, parent_identity = entry
    try:
        entry_stat = path.lstat()
    except OSError:
        return False
    if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
        return False
    try:
        artifact, _ = artifact_store.read_with_identity(
            path,
            expected_parent_identity=parent_identity,
        )
    except (OSError, json.JSONDecodeError):
        return False
    return _is_safe_psychology_learning_artifact_payload(
        artifact=artifact,
        expected_final_content=expected_final_content,
        strict_artifact_shape=strict_artifact_shape,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
    )


def _is_safe_psychology_learning_artifact_payload(
    *,
    artifact: Mapping[str, object],
    expected_final_content: dict[str, Any],
    strict_artifact_shape: bool,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> bool:
    if artifact.get("playbook_id") != MODERN_PSYCHOLOGY_PLAYBOOK_ID:
        return False
    if artifact.get("final_content") != expected_final_content:
        return False
    return not contains_psychology_learning_raw_provenance(
        artifact,
        strict_artifact_shape=strict_artifact_shape,
        preflight_capability=psychology_learning_preflight_capability,
    )


def _read_verified_psychology_learning_artifact(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    expected_final_content: dict[str, Any],
    strict_artifact_shape: bool,
    scope: _PsychologyLearningArtifactScope | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> tuple[Path, dict[str, object], ArtifactFileIdentity] | None:
    """Read one sealed lesson artifact once, pinned to a regular file identity."""
    entry = _owned_psychology_learning_artifact_entry(
        artifact_store=artifact_store,
        artifact_path=artifact_path,
        scope=scope,
    )
    if entry is None:
        return None
    path, parent_identity = entry
    try:
        entry_stat = path.lstat()
    except OSError:
        return None
    if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
        return None
    try:
        artifact, identity = artifact_store.read_with_identity(
            path,
            expected_parent_identity=parent_identity,
        )
    except (OSError, json.JSONDecodeError):
        return None
    if identity.file.st_nlink != 1:
        # A catalog snapshot can be exposed under an owned-looking filename
        # through a hard link.  Learning receipts must never accept it.
        return None
    if not _is_safe_psychology_learning_artifact_payload(
        artifact=artifact,
        expected_final_content=expected_final_content,
        strict_artifact_shape=strict_artifact_shape,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
    ):
        return None
    return path, artifact, identity


def _update_verified_psychology_learning_artifact(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    expected_final_content: dict[str, Any],
    update: Mapping[str, object],
    scope: _PsychologyLearningArtifactScope | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> bool:
    """Apply one post-publish update without merging an unverified artifact.

    The safe read supplies the exact sealed payload and inode identity.  A
    later path swap therefore either fails before replacement or is replaced
    as a directory entry by the store's atomic write; it cannot redirect a
    write into a catalog snapshot.
    """
    verified = _read_verified_psychology_learning_artifact(
        artifact_store=artifact_store,
        artifact_path=artifact_path,
        expected_final_content=expected_final_content,
        strict_artifact_shape=True,
        scope=scope,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
    )
    if verified is None:
        return False
    path, artifact, identity = verified
    updated_artifact = dict(artifact)
    updated_artifact.update(update)
    try:
        artifact_store.replace(
            path,
            updated_artifact,
            expected_identity=identity,
            require_single_link=True,
        )
    except (OSError, json.JSONDecodeError):
        return False
    return True


def _owned_psychology_learning_artifact_path(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    scope: _PsychologyLearningArtifactScope | None = None,
) -> Path | None:
    """Return an owned regular artifact without resolving its terminal leaf."""
    entry = _owned_psychology_learning_artifact_entry(
        artifact_store=artifact_store,
        artifact_path=artifact_path,
        scope=scope,
    )
    if entry is None:
        return None
    path, _ = entry
    try:
        entry_stat = path.lstat()
    except (OSError, RuntimeError, ValueError):
        return None
    if stat.S_ISLNK(entry_stat.st_mode) or not stat.S_ISREG(entry_stat.st_mode):
        # FileArtifactStore must be the first component allowed to open the
        # leaf.  A symlink is never an owned learning artifact, even when its
        # target happens to sit under the ordinary artifact root.
        return None
    return path


def _owned_psychology_learning_artifact_entry(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: str,
    scope: _PsychologyLearningArtifactScope | None = None,
) -> tuple[Path, os.stat_result] | None:
    """Anchor an artifact entry under owned parents while preserving its leaf.

    Resolving ``artifact_path`` itself would turn a final symlink into its
    target before FileArtifactStore has a chance to no-follow it.  Resolve only
    the parent, then append the original lexical filename.
    """
    if scope is not None and not _is_psychology_learning_artifact_scope_intact(scope):
        return None
    raw_path = Path(artifact_path)
    leaf_name = raw_path.name
    if leaf_name in {"", ".", ".."}:
        return None
    try:
        parent = raw_path.parent.resolve()
        parent_identity = parent.stat()
    except (OSError, RuntimeError, ValueError):
        return None
    path = parent / leaf_name
    if scope is None:
        try:
            owned_root_identity = artifact_store.base_dir.resolve().stat()
        except (OSError, RuntimeError):
            return None
    else:
        owned_root_identity = scope.owned_root_identity
    if (
        _has_existing_filesystem_ancestor(
            path=parent,
            ancestor_identity=owned_root_identity,
        )
        is not True
    ):
        # A missing or racing parent cannot be safely authorized from a string
        # prefix. The leaf is intentionally not stat'ed here: rejected entries
        # remain untouched for trusted offline maintenance.
        return None

    if scope is None:
        try:
            reserved_catalog_root = (
                DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT.resolve()
            )
            reserved_catalog_root_identity = reserved_catalog_root.stat()
        except FileNotFoundError:
            # No custom-series store exists yet, so no immutable subtree exists to
            # reserve. Ordinary candidates may still be validated, but rejected
            # leaves are never removed online.
            reserved_catalog_root_identity = None
        except (OSError, RuntimeError):
            return None
    else:
        reserved_catalog_root_identity = scope.reserved_catalog_root_identity
    if reserved_catalog_root_identity is not None:
        if (
            _has_existing_filesystem_ancestor(
                path=parent,
                ancestor_identity=reserved_catalog_root_identity,
            )
            is not False
        ):
            # The default custom-series store shares the artifact parent directory,
            # but it is application-owned persistence rather than a workflow
            # artifact. Identity comparison catches case aliases, symlinks, and
            # normalized parent traversals before artifact validation.
            return None
    # Check the lexical anchors again after resolving the candidate.  A
    # rebind that races this authorization therefore fails closed; a later
    # parent-FD operation is additionally pinned by ``parent_identity``.
    if scope is not None and not _is_psychology_learning_artifact_scope_intact(scope):
        return None
    return path, parent_identity


def _has_existing_filesystem_ancestor(
    *,
    path: Path,
    ancestor: Path | None = None,
    ancestor_identity: os.stat_result | None = None,
) -> bool | None:
    """Compare an existing path's ancestors by filesystem identity.

    ``None`` means a stat failed while walking, so callers must fail closed
    rather than authorize a later file operation using an unresolved path.
    """
    if (ancestor is None) == (ancestor_identity is None):
        raise ValueError("provide exactly one ancestor identity source")
    try:
        ancestor_stat = ancestor_identity if ancestor_identity is not None else ancestor.stat()
        current = path
        while True:
            if os.path.samestat(current.stat(), ancestor_stat):
                return True
            parent = current.parent
            if parent == current:
                return False
            current = parent
    except OSError:
        return None


def _remove_owned_unsafe_psychology_learning_artifact(
    *,
    artifact_store: FileArtifactStore,
    artifact_path: object,
    scope: _PsychologyLearningArtifactScope | None = None,
) -> None:
    """Leave rejected artifacts for trusted offline cleanup.

    Runtime cleanup would have to unlink a mutable leaf by name after an
    untrusted workflow ran.  A same-UID writer can replace that name between
    verification and unlink, so the run fails closed and never reuses or
    publishes the artifact instead of attempting online deletion.
    """
    del artifact_store, artifact_path, scope


def run_playbook(
    request: PlaybookRequest,
    *,
    thread_id: str | None = None,
    settings: Settings | None = None,
    memory: ExecutionMemoryStore | None = None,
    checkpointer: object | None = None,
    accounts: AccountRegistry | None = None,
    playbooks: PlaybookRegistry | None = None,
    publisher: Publisher | None = None,
    run_store: RunStore | None = None,
    side_effect_ledger: SideEffectLedger | None = None,
    command_name: str = "run-playbook",
    eval_enabled: bool = False,
) -> dict[str, Any]:
    """Execute the selected playbook workflow and prepare a publish receipt."""

    settings = settings or get_settings()
    if memory is None or checkpointer is None:
        default_memory, default_checkpointer = build_file_backed_runtime_state()
        memory = memory or default_memory
        checkpointer = checkpointer or default_checkpointer
    accounts = accounts or AccountRegistry()
    playbooks = playbooks or PlaybookRegistry(playbook_root=PLAYBOOK_ROOT)
    run_store = run_store or RunStore()
    side_effect_ledger = side_effect_ledger or SideEffectLedger(
        path=Path.cwd() / DEFAULT_SIDE_EFFECT_LEDGER_PATH
    )
    artifact_store = FileArtifactStore()
    account = accounts.get(request.account_id)
    resolved_platform = request.platform or account.platform
    if resolved_platform != account.platform:
        raise ValueError(
            f"Request platform {resolved_platform!r} does not match account platform {account.platform!r}"
        )
    playbook = playbooks.select_for_account(
        account=account,
        platform=resolved_platform,
        playbook_id=request.playbook_id,
    )
    if (
        _is_psychology_learning_request(request)
        and playbook.playbook_id != MODERN_PSYCHOLOGY_PLAYBOOK_ID
    ):
        return {
            "scene": "心理学学习专题",
            "platform": resolved_platform,
            "account_id": request.account_id,
            "playbook_id": playbook.playbook_id,
            "status": "psychology_learning_playbook_invalid",
            "diagnostic": "learning_series_is_only_supported_by_modern_psychology_post",
        }
    ai_tech_evidence_bundle: AiTechEvidenceBundle | None = None
    psychology_learning_bundle: PsychologyLearningBundle | None = None
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None
    psychology_learning_catalog_receipt: dict[str, Any] | None = None
    psychology_learning_artifact_scope: _PsychologyLearningArtifactScope | None = None
    if playbook.playbook_id == AI_TECH_PLAYBOOK_ID:
        ai_tech_evidence_bundle, preflight_failure = _resolve_ai_tech_evidence_preflight(
            request=request,
            platform=resolved_platform,
            playbook_id=playbook.playbook_id,
        )
        if preflight_failure is not None:
            return preflight_failure
        if (
            request.topic_direction_id
            and not _is_matching_ai_tech_topic_direction(
                topic_direction_id=request.topic_direction_id,
                content_mode=ai_tech_evidence_bundle.mode,
            )
        ):
            return {
                "scene": _build_ai_tech_runtime_scene(ai_tech_evidence_bundle),
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "ai_tech_topic_direction_invalid",
                "diagnostic": "unknown_or_mode_mismatched_topic_direction",
            }
    elif playbook.playbook_id == MODERN_PSYCHOLOGY_PLAYBOOK_ID and _is_psychology_learning_request(
        request
    ):
        (
            psychology_learning_preflight_capability,
            preflight_failure,
        ) = _resolve_psychology_learning_preflight(
            request=request,
            platform=resolved_platform,
            playbook_id=playbook.playbook_id,
        )
        if preflight_failure is not None:
            return preflight_failure
        assert psychology_learning_preflight_capability is not None
        psychology_learning_bundle = require_sealed_psychology_learning_preflight_bundle(
            psychology_learning_preflight_capability
        )
        if request.topic_direction_id != psychology_learning_bundle.direction_id:
            return {
                "scene": _build_psychology_learning_runtime_scene(
                    psychology_learning_bundle
                ),
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "psychology_learning_topic_direction_invalid",
                "diagnostic": "missing_or_mismatched_catalog_topic_direction",
            }
        psychology_learning_catalog_receipt = (
            build_psychology_learning_catalog_receipt(psychology_learning_bundle)
        )
        psychology_learning_artifact_scope = (
            _capture_psychology_learning_artifact_scope(
                artifact_store=artifact_store,
                require_progress_identity=(
                    psychology_learning_bundle.catalog is not None
                ),
            )
        )
        if psychology_learning_artifact_scope is None:
            return {
                "scene": _build_psychology_learning_runtime_scene(
                    psychology_learning_bundle
                ),
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "psychology_learning_artifact_store_invalid",
                "diagnostic": "could_not_freeze_artifact_and_catalog_storage_identities",
            }
    effective_scene = request.scene
    if ai_tech_evidence_bundle is not None:
        effective_scene = _build_ai_tech_runtime_scene(ai_tech_evidence_bundle)
    elif psychology_learning_bundle is not None:
        effective_scene = _build_psychology_learning_runtime_scene(psychology_learning_bundle)
    if ai_tech_evidence_bundle is not None and request.fresh_topic_research:
        # Topic Radar is intentionally a separate discovery operation for AI
        # evidence modes.  Its public output can assist an operator in
        # collecting an opaque trend reference, but it cannot supply the
        # verified facts or reproducible test record required for drafting.
        # Returning here also ensures raw scan output is never printed,
        # checkpointed, or attached to this AI run.
        return {
            "scene": effective_scene,
            "platform": resolved_platform,
            "account_id": request.account_id,
            "playbook_id": playbook.playbook_id,
            "status": "ai_tech_fresh_research_separate",
            "next_step": (
                "Run hotspot discovery separately, collect only eligible opaque "
                "trend support, then provide a complete --ai-evidence-file before drafting."
            ),
        }
    if psychology_learning_bundle is not None and request.fresh_topic_research:
        # A hotspot scan can help an operator decide whether to run discovery,
        # but its public text cannot become a course claim or lesson content.
        return {
            "scene": effective_scene,
            "platform": resolved_platform,
            "account_id": request.account_id,
            "playbook_id": playbook.playbook_id,
            "status": "psychology_learning_fresh_research_separate",
            "next_step": (
                "Run hotspot discovery separately, then select an approved "
                "psychology learning lesson without passing hotspot text into this run."
            ),
        }
    if _requires_openclaw_psychology_guidance(
        caller=request.caller,
        guidance_ack=request.guidance_ack,
        playbook_id=playbook.playbook_id,
    ):
        if psychology_learning_bundle is not None:
            return {
                "scene": effective_scene,
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "topic_guidance_required",
                "caller": request.caller,
                "guidance_ack": False,
                "topic_guidance": _build_psychology_learning_topic_guidance(
                    psychology_learning_bundle
                ),
                "next_step": (
                    "Show the catalog lesson directions to the user, ask them to "
                    "confirm this exact lesson, then call run-playbook again with "
                    "--guidance-ack."
                ),
            }
        lane = resolve_psychology_lane(scene=request.scene)
        return {
            "scene": request.scene,
            "platform": resolved_platform,
            "account_id": request.account_id,
            "playbook_id": playbook.playbook_id,
            "status": "topic_guidance_required",
            "caller": request.caller,
            "guidance_ack": False,
            "topic_guidance": build_psychology_topic_guidance(
                scene=request.scene,
                lane_name=lane.name,
            ),
            "next_step": (
                "Show topic_guidance.directions to the user, ask them to choose "
                "or confirm a direction, then call run-playbook again with "
                "--guidance-ack."
            ),
        }

    # Topic-radar integration: scan hot topics, let user pick, enrich scene
    topic_selection: dict[str, Any] | None = None
    if request.fresh_topic_research:
        scan_result = _run_topic_radar_scan(
            output_dir=str(Path.cwd() / "outputs" / "artifacts"),
        )
        if _topic_scan_is_insufficient(scan_result):
            return {
                "scene": request.scene,
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "insufficient_evidence",
                "topic_research": _topic_research_receipt(scan_result),
                "next_step": (
                    "No evidence-backed fresh direction is available. Resolve the "
                    "reported platform issues or continue with a local topic pack."
                ),
            }
        topic_selection = _interactive_topic_selection(scan_result)
        if topic_selection is None:
            return {
                "scene": request.scene,
                "platform": resolved_platform,
                "account_id": request.account_id,
                "playbook_id": playbook.playbook_id,
                "status": "insufficient_evidence",
                "topic_research": _topic_research_receipt(scan_result),
                "next_step": (
                    "The fresh scan returned no evidence-backed direction. "
                    "Resolve the reported platform issues or continue with a local topic pack."
                ),
            }
        enriched_scene = _build_enriched_scene(topic_selection)
        if ai_tech_evidence_bundle is None and psychology_learning_bundle is None:
            request.scene = enriched_scene
            effective_scene = enriched_scene
        print(f"\n{'='*60}")
        print(f"Scene built from topic selection:")
        print(
            effective_scene
            if ai_tech_evidence_bundle is not None or psychology_learning_bundle is not None
            else enriched_scene
        )
        print(f"{'='*60}\n")

    # Fresh Topic Radar is selection support only for AI evidence modes.  Its
    # free-form vertical/angle metadata must not enter graph state, checkpoints,
    # or the publish artifact; any eligible trend reference is already carried
    # as an opaque ID in the operator's evidence manifest.
    topic_selection_metadata = (
        None
        if ai_tech_evidence_bundle is not None
        else (
            _build_psychology_learning_topic_selection(psychology_learning_bundle)
            if psychology_learning_bundle is not None
            else _topic_selection_metadata(
                topic_selection,
                request.topic_direction_id,
                playbook_id=playbook.playbook_id,
                scene=effective_scene,
            )
        )
    )

    run = run_store.start(
        command=command_name,
        account_id=request.account_id,
        platform=resolved_platform,
        playbook_id=playbook.playbook_id,
    )

    publish_mode = request.publish_mode or account.publish_mode
    publisher = publisher or build_publisher(
        platform=resolved_platform,
        publish_mode=publish_mode,
        settings=settings,
    )
    qrcode_output_path = Path(request.login_qrcode_output_path or DEFAULT_XHS_LOGIN_QRCODE_PATH)
    post_publish_checks: dict[str, Any] = {
        "requested": request.open_browser_if_needed or request.wait_for_publish_status,
        "browser_opened": False,
        "browser_result": None,
        "publish_status": "skipped",
        "status_result": None,
    }

    if publish_mode == "mcp-real":
        preflight_method = getattr(publisher, "preflight", None)
        if callable(preflight_method):
            preflight = materialize_xhs_login_qrcode(
                preflight_method(),
                output_path=qrcode_output_path,
            )
            if preflight.get("status") != "ready":
                login_request = _build_safe_login_rerun_request(
                    request=request,
                    effective_scene=effective_scene,
                    ai_tech_evidence_bundle=ai_tech_evidence_bundle,
                    psychology_learning_bundle=psychology_learning_bundle,
                )
                publish_result = _build_login_required_result(
                    account_id=account.account_id,
                    account_nickname=account.nickname,
                    platform=account.platform,
                    provider=getattr(publisher, "provider_name", publisher.__class__.__name__),
                    preflight=preflight,
                    request=login_request,
                    command_name=command_name,
                    resolved_platform=resolved_platform,
                    playbook_id=playbook.playbook_id,
                )
                if request.open_browser_if_needed:
                    browser_result = open_xhs_browser(
                        target="login",
                        qrcode_output_path=qrcode_output_path,
                    )
                    post_publish_checks["browser_opened"] = (
                        browser_result.get("status") == "opened"
                    )
                    post_publish_checks["browser_result"] = browser_result
                post_publish_checks["publish_status"] = "login_required"
                return {
                    "scene": effective_scene,
                    "platform": resolved_platform,
                    "account_id": request.account_id,
                    "playbook_id": playbook.playbook_id,
                    "status": "login_required",
                    "account": account.to_dict(),
                    "publish_mode": publish_mode,
                    "publish_result": publish_result,
                    "post_publish_checks": post_publish_checks,
                    "run": run_store.finish(
                        run.run_id,
                        status="login_required",
                        payload={"publish_mode": publish_mode},
                    ),
                }

    workflow = _build_workflow_for_playbook(
        domain=playbook.domain,
        playbook_id=playbook.playbook_id,
        memory=memory,
        checkpointer=checkpointer,
        settings=settings,
        format_pattern_path=request.format_pattern_path,
        ai_tech_evidence=(
            ai_tech_evidence_bundle.runtime_contract
            if ai_tech_evidence_bundle is not None
            else None
        ),
        ai_tech_evidence_manifest=(
            ai_tech_evidence_bundle.manifest.model_dump(mode="json")
            if ai_tech_evidence_bundle is not None
            else None
        ),
        psychology_learning_contract=(
            psychology_learning_bundle.runtime_contract
            if psychology_learning_bundle is not None
            else None
        ),
        psychology_learning_manifest=(
            psychology_learning_bundle.manifest
            if psychology_learning_bundle is not None
            else None
        ),
        psychology_learning_catalog_receipt=psychology_learning_catalog_receipt,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
        artifact_store=artifact_store,
        expected_artifact_root_identity=(
            psychology_learning_artifact_scope.owned_root_identity
            if psychology_learning_artifact_scope is not None
            else None
        ),
    )
    effective_thread_id = thread_id or run.run_id
    config = {"configurable": {"thread_id": effective_thread_id}}
    workflow_payload: dict[str, Any] = {
        **request.model_dump(
            mode="python",
            exclude={
                "ai_content_mode",
                "ai_evidence_bundle",
                "ai_evidence_file_path",
                "psychology_content_mode",
                "psychology_series_id",
                "psychology_lesson_id",
                "psychology_curriculum_version",
            },
        ),
        "platform": resolved_platform,
        "scene": effective_scene,
    }
    if topic_selection_metadata is not None:
        workflow_payload["topic_selection"] = topic_selection_metadata
        if topic_selection_metadata.get("source") == "topic-radar":
            # The explicit scan above already selected a safe angle. Runtime
            # builders must remain local-only for this workflow invocation so
            # they cannot run another scan or add a competing live context.
            workflow_payload["fresh_topic_research"] = False
    result = workflow.invoke(workflow_payload, config=config)
    result = {"playbook_id": playbook.playbook_id, **result}
    # Evidence is a workflow-construction capability, never a graph/input
    # state field.  The artifact receipt retains only the opaque manifest.
    if ai_tech_evidence_bundle is not None and result.get("status") == "completed":
        draft = result.get("final_content")
        draft_mapping = draft if isinstance(draft, dict) else {}
        validation_errors = validate_ai_tech_draft(ai_tech_evidence_bundle, draft_mapping)
        if validation_errors:
            result["status"] = "ai_tech_draft_invalid"
            result["ai_tech_draft_validation"] = {"errors": validation_errors}
        else:
            artifact_path = result.get("artifact_path")
            if not isinstance(artifact_path, str) or not Path(artifact_path).is_file():
                result["status"] = "ai_tech_artifact_required"
                result["ai_tech_artifact_validation"] = {
                    "error": "completed AI workflow must write an artifact before publish"
                }
            elif not _is_safe_ai_tech_artifact(
                artifact_store=artifact_store,
                artifact_path=artifact_path,
                expected_final_content=draft_mapping,
            ):
                result["status"] = "ai_tech_artifact_invalid"
                result["ai_tech_artifact_validation"] = {
                    "error": "AI artifact failed ownership or provenance validation"
                }
            else:
                evidence_receipt = _build_ai_tech_evidence_receipt(ai_tech_evidence_bundle)
                try:
                    # Standard workflows write this receipt during finalization.
                    # Replacing the same safe values here also closes the
                    # custom-workflow path without trusting a caller-supplied
                    # receipt or copying the full evidence bundle.
                    artifact_store.merge(artifact_path, evidence_receipt)
                except (OSError, json.JSONDecodeError):
                    result["status"] = "ai_tech_artifact_invalid"
                    result["ai_tech_artifact_validation"] = {
                        "error": "could not persist AI evidence receipt before publish"
                    }
                else:
                    result.update(evidence_receipt)
    if psychology_learning_bundle is not None and result.get("status") == "completed":
        draft = result.get("final_content")
        draft_mapping = draft if isinstance(draft, dict) else {}
        validation_errors = validate_psychology_learning_draft_contract(
            psychology_learning_bundle.runtime_contract,
            draft_mapping,
        )
        if validation_errors:
            result["status"] = "psychology_learning_draft_invalid"
            result["psychology_learning_draft_validation"] = {
                "errors": validation_errors
            }
            _remove_owned_unsafe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=result.get("artifact_path"),
                scope=psychology_learning_artifact_scope,
            )
        else:
            artifact_path = result.get("artifact_path")
            if not isinstance(artifact_path, str) or not Path(artifact_path).is_file():
                result["status"] = "psychology_learning_artifact_required"
                result["psychology_learning_artifact_validation"] = {
                    "error": "completed learning workflow must write an artifact before publish"
                }
            elif not _is_safe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=artifact_path,
                expected_final_content=draft_mapping,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            ):
                result["status"] = "psychology_learning_artifact_invalid"
                result["psychology_learning_artifact_validation"] = {
                    "error": "learning artifact failed ownership or provenance validation"
                }
                _remove_owned_unsafe_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=artifact_path,
                    scope=psychology_learning_artifact_scope,
                )
            else:
                sealed_artifact = _read_verified_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=artifact_path,
                    expected_final_content=draft_mapping,
                    strict_artifact_shape=False,
                    scope=psychology_learning_artifact_scope,
                    psychology_learning_preflight_capability=(
                        psychology_learning_preflight_capability
                    ),
                )
                if sealed_artifact is None:
                    result["status"] = "psychology_learning_artifact_invalid"
                    result["psychology_learning_artifact_validation"] = {
                        "error": "learning artifact failed ownership or provenance validation"
                    }
                    _remove_owned_unsafe_psychology_learning_artifact(
                        artifact_store=artifact_store,
                        artifact_path=artifact_path,
                        scope=psychology_learning_artifact_scope,
                    )
                else:
                    sealed_artifact_path, _, sealed_artifact_identity = sealed_artifact
                    learning_receipt = _build_psychology_learning_receipt(
                        psychology_learning_bundle
                    )
                    try:
                        artifact_store.replace(
                            sealed_artifact_path,
                            _build_psychology_learning_artifact_envelope(
                                final_content=draft_mapping,
                                learning_receipt=learning_receipt,
                            ),
                            expected_identity=sealed_artifact_identity,
                            require_single_link=True,
                        )
                    except (OSError, json.JSONDecodeError):
                        result["status"] = "psychology_learning_artifact_invalid"
                        result["psychology_learning_artifact_validation"] = {
                            "error": "could not persist learning receipt before publish"
                        }
                        _remove_owned_unsafe_psychology_learning_artifact(
                            artifact_store=artifact_store,
                            artifact_path=artifact_path,
                            scope=psychology_learning_artifact_scope,
                        )
                    else:
                        result.update(learning_receipt)
    format_patterns_used = (
        {"status": "not_used"}
        if psychology_learning_bundle is not None
        else _extract_format_patterns_used(
            result,
            pattern_path=request.format_pattern_path or settings.xhs_pattern_library_path,
        )
    )
    result["format_patterns_used"] = format_patterns_used
    if topic_selection_metadata is not None:
        result["topic_selection"] = topic_selection_metadata
    run_store.append_event(
        run.run_id,
        event="workflow_completed",
        step="workflow",
        status=str(result["status"]),
        payload={"artifact_path": result.get("artifact_path")},
    )

    publish_result = None
    image_generation: dict[str, Any] | None = None
    watermark_removal: dict[str, Any] | None = None
    if result["status"] == "completed":
        resolved_image_paths = list(request.publish_image_paths)
        artifact_path = Path(result["artifact_path"])
        if not resolved_image_paths and _should_generate_images(
            publish_mode=publish_mode,
            auto_generate_images=request.auto_generate_images,
        ):
            image_backend = build_image_backend(settings)
            runtime_skill_contents = (
                []
                if ai_tech_evidence_bundle is not None or psychology_learning_bundle is not None
                else list(result.get("runtime_skill_contents") or [])
            )
            runtime_context_summary = _summarize_runtime_skill_contents(
                runtime_skill_contents
            )
            image_decision = _resolve_image_generation_decision(
                request=request,
                final_content=result["final_content"],
                image_backend_available=image_backend is not None,
            )
            if image_decision["route"] == "local":
                image_generation = NoteCardImageBackend().generate(
                    prompt=_build_note_card_image_payload(
                        scene=effective_scene,
                        runtime_context_summary=runtime_context_summary,
                        final_content=result["final_content"],
                        local_image_style=str(image_decision.get("requested_style") or ""),
                        image_plan=image_decision,
                    ),
                    output_dir=Path.cwd() / DEFAULT_GENERATED_IMAGES_DIR,
                    output_stem=f"{artifact_path.stem}-cover",
                )
                image_decision["selected_backend"] = str(
                    image_generation.get("provider") or "local_note_card"
                )
                image_generation["image_plan"] = _image_generation_decision_metadata(
                    image_decision
                )
                image_generation["runtime_context_summary"] = runtime_context_summary
                resolved_image_paths = list(
                    image_generation.get("generated_image_paths")
                    or image_generation.get("image_paths")
                    or []
                )
            else:
                if image_backend is None:
                    raise RuntimeError("image backend decision selected provider without backend")
                image_generation = image_backend.generate(
                    prompt=_build_image_generation_prompt(
                        scene=effective_scene,
                        persona_prompt=str(result.get("persona_prompt") or ""),
                        runtime_skill_contents=runtime_skill_contents,
                        content_review=result.get("content_review"),
                        final_content=result["final_content"],
                        image_plan=image_decision,
                    ),
                    output_dir=Path.cwd() / DEFAULT_GENERATED_IMAGES_DIR,
                    output_stem=f"{artifact_path.stem}-cover",
                )
                image_decision["selected_backend"] = str(
                    image_generation.get("provider") or image_decision["selected_backend"]
                )
                image_generation["image_plan"] = _image_generation_decision_metadata(
                    image_decision
                )
                image_generation["runtime_context_summary"] = runtime_context_summary
                resolved_image_paths = list(
                    image_generation.get("generated_image_paths")
                    or image_generation.get("image_paths")
                    or []
                )

        if image_generation is not None:
            _ensure_generated_image_watermark_policy(image_generation)
            if psychology_learning_bundle is None:
                asset_ledger = append_generated_image_assets(
                    base_dir=Path.cwd(),
                    artifact_path=str(result["artifact_path"]),
                    playbook_id=playbook.playbook_id,
                    account_id=account.account_id,
                    image_generation=image_generation,
                )
                if asset_ledger is not None:
                    image_generation["asset_ledger"] = asset_ledger

        watermark_removal = None
        if _should_skip_watermark_removal_for_local_renderer(
            image_generation=image_generation,
            image_paths=resolved_image_paths,
        ):
            watermark_removal = _local_renderer_watermark_removal_skipped_result()
        elif _should_remove_watermark(
            publish_mode=publish_mode,
            watermark_removal_enabled=settings.watermark_removal_enabled,
            image_paths=resolved_image_paths,
        ):
            remover = WatermarkRemover(
                corner_search_ratio=settings.watermark_removal_corner_search_ratio,
                inpaint_radius=settings.watermark_removal_inpaint_radius,
            )
            cleaned_paths: list[str] = []
            watermark_results: list[dict[str, object]] = []
            for img_path_str in resolved_image_paths:
                img_path = Path(img_path_str)
                wm_result = remover.remove(
                    image_path=img_path,
                    output_dir=Path.cwd() / DEFAULT_GENERATED_IMAGES_DIR,
                    output_stem=f"{img_path.stem}-nowm",
                )
                watermark_results.append(wm_result)
                cleaned = wm_result.get("output_path")
                if isinstance(cleaned, str):
                    cleaned_paths.append(cleaned)
            watermark_removal = {
                "status": "completed",
                "policy": _watermark_removal_policy(
                    publish_mode=publish_mode,
                    watermark_removal_enabled=settings.watermark_removal_enabled,
                ),
                "results": watermark_results,
            }
            if cleaned_paths:
                resolved_image_paths = cleaned_paths

        publish_idempotency_key = _build_publish_idempotency_key(
            account_id=account.account_id,
            playbook_id=playbook.playbook_id,
            publish_mode=publish_mode,
            artifact_path=str(result["artifact_path"]),
            image_paths=resolved_image_paths,
            visibility=request.publish_visibility or settings.xhs_default_visibility,
        )
        cached_publish_result = side_effect_ledger.read(
            thread_id=effective_thread_id,
            step="publish",
            idempotency_key=publish_idempotency_key,
        )
        if cached_publish_result is not None:
            publish_result = cached_publish_result
        else:
            try:
                publish_result = publisher.publish(
                    account=account,
                    content=result["final_content"],
                    artifact_path=result["artifact_path"],
                    image_paths=resolved_image_paths,
                    visibility=request.publish_visibility or settings.xhs_default_visibility,
                )
            except PublisherPreflightError as exc:
                preflight = materialize_xhs_login_qrcode(
                    exc.preflight,
                    output_path=qrcode_output_path,
                )
                login_request = _build_safe_login_rerun_request(
                    request=request,
                    effective_scene=effective_scene,
                    ai_tech_evidence_bundle=ai_tech_evidence_bundle,
                    psychology_learning_bundle=psychology_learning_bundle,
                )
                publish_result = {
                    **_build_login_required_result(
                        account_id=account.account_id,
                        account_nickname=account.nickname,
                        platform=account.platform,
                        provider=getattr(publisher, "provider_name", publisher.__class__.__name__),
                        preflight=preflight,
                        request=login_request,
                        command_name=command_name,
                        resolved_platform=resolved_platform,
                        playbook_id=playbook.playbook_id,
                    ),
                    "artifact_path": result["artifact_path"],
                    "error": str(exc),
                }
            except Exception as exc:
                publish_result = {
                    "status": "error",
                    "platform": account.platform,
                    "provider": getattr(publisher, "provider_name", publisher.__class__.__name__),
                    "account_id": account.account_id,
                    "account_nickname": account.nickname,
                    "artifact_path": result["artifact_path"],
                    "error": str(exc),
                }
            ledger_publish_result = (
                _sanitize_psychology_learning_publish_result(publish_result)
                if psychology_learning_bundle is not None
                else publish_result
            )
            if _should_record_publish_result(ledger_publish_result):
                side_effect_ledger.record(
                    thread_id=effective_thread_id,
                    step="publish",
                    idempotency_key=publish_idempotency_key,
                    result=ledger_publish_result,
                )
        if psychology_learning_bundle is not None:
            artifact_update = _build_psychology_learning_artifact_update(
                account=account,
                effective_scene=effective_scene,
                platform=resolved_platform,
                publish_mode=publish_mode,
                publish_result=publish_result,
                image_generation=image_generation,
                watermark_removal=watermark_removal,
                run_id=run.run_id,
            )
        else:
            artifact_update = {
                "scene": effective_scene,
                "platform": request.platform,
                "account": account.to_dict(),
                "publish_mode": publish_mode,
                "publish_result": publish_result,
                "image_generation": image_generation,
                "watermark_removal": watermark_removal,
                "format_patterns_used": format_patterns_used,
                "run": run.to_dict(),
            }
            if topic_selection_metadata is not None:
                artifact_update["topic_selection"] = topic_selection_metadata
        if psychology_learning_bundle is not None:
            final_content = result.get("final_content")
            if not isinstance(final_content, dict) or not _update_verified_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(result["artifact_path"]),
                expected_final_content=final_content,
                update=artifact_update,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            ):
                result["status"] = "psychology_learning_artifact_invalid"
                result["psychology_learning_artifact_validation"] = {
                    "error": "learning artifact failed final provenance validation"
                }
                _remove_owned_unsafe_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=result.get("artifact_path"),
                    scope=psychology_learning_artifact_scope,
                )
        else:
            artifact_store.merge(result["artifact_path"], artifact_update)

    if result["status"] == "completed" and result.get("artifact_path"):
        artifact_path = Path(result["artifact_path"])
        if request.wait_for_publish_status:
            status_result = check_xhs_publish_status(
                artifact_path=artifact_path,
                settings=settings,
                publisher=None,
                search_retry_attempts=WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_ATTEMPTS,
                search_retry_interval_seconds=WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_INTERVAL_SECONDS,
                publish_result=(
                    (
                        publish_result
                        if isinstance(publish_result, Mapping)
                        else {}
                    )
                    if psychology_learning_bundle is not None
                    else None
                ),
                fallback_title=(
                    str(result["final_content"].get("title") or "")
                    if psychology_learning_bundle is not None
                    and isinstance(result.get("final_content"), Mapping)
                    else None
                ),
                fallback_body=(
                    str(result["final_content"].get("body") or "")
                    if psychology_learning_bundle is not None
                    and isinstance(result.get("final_content"), Mapping)
                    else None
                ),
                fallback_visibility=(
                    request.publish_visibility or settings.xhs_default_visibility
                    if psychology_learning_bundle is not None
                    else None
                ),
            )
            post_publish_checks["status_result"] = status_result
            post_publish_checks["publish_status"] = str(
                status_result.get("status", "unknown")
            )

        should_open_browser = False
        if request.open_browser_if_needed:
            should_open_browser = not request.wait_for_publish_status
            if request.wait_for_publish_status:
                should_open_browser = post_publish_checks["publish_status"] in {
                    "manual_check_required",
                    "login_required",
                }

        if should_open_browser:
            if psychology_learning_bundle is not None:
                # Learning artifacts are a sealed, mutable filesystem boundary.
                # Browser assistance must not reopen them merely to discover a
                # provider URL; the controlled creator surface is sufficient.
                browser_result = open_xhs_browser(
                    target="creator",
                    qrcode_output_path=qrcode_output_path,
                )
            else:
                browser_result = open_xhs_browser(
                    target="artifact",
                    artifact_path=artifact_path,
                    qrcode_output_path=qrcode_output_path,
                )
            post_publish_checks["browser_opened"] = browser_result.get("status") == "opened"
            post_publish_checks["browser_result"] = browser_result

        post_publish_update = {
            "post_publish_checks": (
                _sanitize_psychology_learning_post_publish_checks(post_publish_checks)
                if psychology_learning_bundle is not None
                else post_publish_checks
            ),
        }
        if psychology_learning_bundle is not None:
            final_content = result.get("final_content")
            if not isinstance(final_content, dict) or not _update_verified_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(artifact_path),
                expected_final_content=final_content,
                update=post_publish_update,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            ):
                result["status"] = "psychology_learning_artifact_invalid"
                result["psychology_learning_artifact_validation"] = {
                    "error": "learning artifact failed final provenance validation"
                }
                _remove_owned_unsafe_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=result.get("artifact_path"),
                    scope=psychology_learning_artifact_scope,
                )
        else:
            artifact_store.merge(artifact_path, post_publish_update)

    if (
        psychology_learning_bundle is not None
        and result["status"] == "completed"
        and result.get("artifact_path")
        and not _is_safe_psychology_learning_artifact(
            artifact_store=artifact_store,
            artifact_path=str(result["artifact_path"]),
            expected_final_content=result["final_content"],
            strict_artifact_shape=True,
            scope=psychology_learning_artifact_scope,
            psychology_learning_preflight_capability=(
                psychology_learning_preflight_capability
            ),
        )
    ):
        result["status"] = "psychology_learning_artifact_invalid"
        result["psychology_learning_artifact_validation"] = {
            "error": "learning artifact failed final provenance validation"
        }
        _remove_owned_unsafe_psychology_learning_artifact(
            artifact_store=artifact_store,
            artifact_path=result.get("artifact_path"),
            scope=psychology_learning_artifact_scope,
        )

    eval_result = None
    if (
        eval_enabled
        and psychology_learning_bundle is not None
        and psychology_learning_bundle.catalog is not None
        and result["status"] == "completed"
    ):
        final_content = result.get("final_content")
        verified_eval_artifact = (
            _read_verified_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(result.get("artifact_path") or ""),
                expected_final_content=final_content,
                strict_artifact_shape=True,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
            if isinstance(final_content, dict)
            else None
        )
        if verified_eval_artifact is None:
            result["status"] = "psychology_learning_artifact_invalid"
            result["psychology_learning_artifact_validation"] = {
                "error": "learning artifact failed final provenance validation"
            }
            _remove_owned_unsafe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=result.get("artifact_path"),
                scope=psychology_learning_artifact_scope,
            )
        else:
            _, eval_artifact_payload, _ = verified_eval_artifact
            eval_result = _run_eval_on_artifact(
                artifact_path=result.get("artifact_path"),
                run_id=run.run_id,
                artifact_payload=eval_artifact_payload,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
            if not _is_safe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(result.get("artifact_path") or ""),
                expected_final_content=final_content,
                strict_artifact_shape=True,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            ):
                result["status"] = "psychology_learning_artifact_invalid"
                result["psychology_learning_artifact_validation"] = {
                    "error": "learning artifact failed final provenance validation"
                }
                _remove_owned_unsafe_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=result.get("artifact_path"),
                    scope=psychology_learning_artifact_scope,
                )
            elif (
                not isinstance(eval_result, Mapping)
                or eval_result.get("status") != "passed"
            ):
                result["status"] = "psychology_learning_eval_failed"
                result["psychology_learning_eval_validation"] = {
                    "error": "learning artifact did not pass offline evaluation"
                }

    if (
        psychology_learning_bundle is not None
        and psychology_learning_bundle.catalog is not None
        and result["status"] == "completed"
        and result.get("artifact_path")
    ):
        final_content = result.get("final_content")
        if not isinstance(final_content, dict) or not _is_safe_psychology_learning_artifact(
            artifact_store=artifact_store,
            artifact_path=str(result.get("artifact_path") or ""),
            expected_final_content=final_content,
            strict_artifact_shape=True,
            scope=psychology_learning_artifact_scope,
            psychology_learning_preflight_capability=(
                psychology_learning_preflight_capability
            ),
        ):
            result["status"] = "psychology_learning_artifact_invalid"
            result["psychology_learning_artifact_validation"] = {
                "error": "learning artifact failed final provenance validation"
            }
            _remove_owned_unsafe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=result.get("artifact_path"),
                scope=psychology_learning_artifact_scope,
            )
        else:
            try:
                if (
                    psychology_learning_artifact_scope is None
                    or psychology_learning_artifact_scope.reserved_catalog_root_identity
                    is None
                    or psychology_learning_artifact_scope.reserved_progress_identity
                    is None
                ):
                    raise OSError("psychology learning storage scope is unavailable")
                PsychologyLearningSeriesStore(
                    catalog_root=(
                        psychology_learning_artifact_scope.reserved_catalog_root_path
                    )
                ).mark_production_lesson_completed(
                    series_id=psychology_learning_bundle.series_id,
                    curriculum_version=str(
                        psychology_learning_bundle.runtime_contract["curriculum_version"]
                    ),
                    lesson_id=psychology_learning_bundle.lesson_id,
                    catalog=psychology_learning_bundle.catalog,
                    expected_catalog_root_identity=(
                        psychology_learning_artifact_scope.reserved_catalog_root_identity
                    ),
                    expected_progress_identity=(
                        psychology_learning_artifact_scope.reserved_progress_identity
                    ),
                    expected_artifact_root_path=(
                        psychology_learning_artifact_scope.owned_root_path
                    ),
                    expected_artifact_root_identity=(
                        psychology_learning_artifact_scope.owned_root_identity
                    ),
                )
            except (OSError, ValueError):
                # The content artifact is safe, but reporting it as a completed
                # production step would make the sequence recommendation lie.  A
                # retry can re-mark idempotently after storage recovers.
                result["status"] = "psychology_learning_progress_persist_failed"
                result["psychology_learning_progress"] = {
                    "status": "not_recorded",
                    "reason": "production_progress_persist_failed",
                }

    if (
        eval_enabled
        and psychology_learning_bundle is not None
        and psychology_learning_bundle.catalog is None
        and result["status"] == "completed"
    ):
        # Builtin lessons do not gate production progress on evaluation, but
        # their eval still consumes an artifact path.  Run it before the final
        # run summary and pin both sides to the same frozen storage boundary.
        final_content = result.get("final_content")
        verified_eval_artifact = (
            _read_verified_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(result.get("artifact_path") or ""),
                expected_final_content=final_content,
                strict_artifact_shape=True,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
            if isinstance(final_content, dict)
            else None
        )
        if verified_eval_artifact is None:
            result["status"] = "psychology_learning_artifact_invalid"
            result["psychology_learning_artifact_validation"] = {
                "error": "learning artifact failed final provenance validation"
            }
            _remove_owned_unsafe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=result.get("artifact_path"),
                scope=psychology_learning_artifact_scope,
            )
        else:
            _, eval_artifact_payload, _ = verified_eval_artifact
            eval_result = _run_eval_on_artifact(
                artifact_path=result.get("artifact_path"),
                run_id=run.run_id,
                artifact_payload=eval_artifact_payload,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            )
            if not _is_safe_psychology_learning_artifact(
                artifact_store=artifact_store,
                artifact_path=str(result.get("artifact_path") or ""),
                expected_final_content=final_content,
                strict_artifact_shape=True,
                scope=psychology_learning_artifact_scope,
                psychology_learning_preflight_capability=(
                    psychology_learning_preflight_capability
                ),
            ):
                result["status"] = "psychology_learning_artifact_invalid"
                result["psychology_learning_artifact_validation"] = {
                    "error": "learning artifact failed final provenance validation"
                }
                _remove_owned_unsafe_psychology_learning_artifact(
                    artifact_store=artifact_store,
                    artifact_path=result.get("artifact_path"),
                    scope=psychology_learning_artifact_scope,
                )

    learning_publish_receipt = (
        _sanitize_psychology_learning_publish_result(publish_result)
        if psychology_learning_bundle is not None
        else None
    )
    learning_image_receipt = (
        _sanitize_psychology_learning_image_generation(image_generation)
        if psychology_learning_bundle is not None
        else None
    )
    learning_watermark_receipt = (
        _sanitize_psychology_learning_watermark_removal(watermark_removal)
        if psychology_learning_bundle is not None
        else None
    )
    learning_post_publish_receipt = (
        _sanitize_psychology_learning_post_publish_checks(post_publish_checks)
        if psychology_learning_bundle is not None
        else None
    )
    run_summary_payload: dict[str, object] = {
        "artifact_path": result.get("artifact_path"),
        "publish_mode": publish_mode,
        "publish_status": (
            learning_publish_receipt.get("status")
            if learning_publish_receipt is not None
            else None if publish_result is None else publish_result.get("status")
        ),
        "activated_skills": (
            []
            if psychology_learning_bundle is not None
            else list(result.get("activated_skills") or [])
        ),
        "activated_skill_details": (
            []
            if psychology_learning_bundle is not None
            else list(result.get("activated_skill_details") or [])
        ),
        "runtime_skill_details": (
            []
            if psychology_learning_bundle is not None
            else list(result.get("runtime_skill_details") or [])
        ),
        "format_patterns_used": format_patterns_used,
        "topic_selection": topic_selection_metadata,
    }
    run_summary = run_store.finish(
        run.run_id,
        status=str(result["status"]),
        payload=run_summary_payload,
    )

    # Learning-series evaluation has already run inside its frozen storage
    # boundary. Ordinary playbooks retain the established post-run order.
    if eval_enabled and eval_result is None and psychology_learning_bundle is None:
        eval_result = _run_eval_on_artifact(
            artifact_path=result.get("artifact_path"),
            run_id=run.run_id,
        )

    response: dict[str, Any] = {
        **result,
        "account": (
            _sanitize_psychology_learning_account(account)
            if psychology_learning_bundle is not None
            else account.to_dict()
        ),
        "publish_mode": publish_mode,
        "publish_result": (
            learning_publish_receipt
            if psychology_learning_bundle is not None
            else publish_result
        ),
        "image_generation": (
            learning_image_receipt
            if psychology_learning_bundle is not None
            else image_generation
        ),
        "watermark_removal": (
            learning_watermark_receipt
            if psychology_learning_bundle is not None
            else watermark_removal
        ),
        "post_publish_checks": (
            learning_post_publish_receipt
            if psychology_learning_bundle is not None
            else post_publish_checks
        ),
        "run": run_summary,
        "eval": eval_result,
    }
    if topic_selection_metadata is not None:
        response["topic_selection"] = topic_selection_metadata
    return response


def run_fengkuang_playbook(
    request: FengkuangRequest,
    *,
    thread_id: str | None = None,
    settings: Settings | None = None,
    memory: ExecutionMemoryStore | None = None,
    checkpointer: object | None = None,
    accounts: AccountRegistry | None = None,
    publisher: Publisher | None = None,
    run_store: RunStore | None = None,
    side_effect_ledger: SideEffectLedger | None = None,
    eval_enabled: bool = False,
) -> dict[str, Any]:
    return run_playbook(
        request,
        thread_id=thread_id,
        settings=settings,
        memory=memory,
        checkpointer=checkpointer,
        accounts=accounts,
        publisher=publisher,
        run_store=run_store,
        side_effect_ledger=side_effect_ledger,
        command_name="run-fengkuang",
        eval_enabled=eval_enabled,
    )


def _requires_openclaw_psychology_guidance(
    *,
    caller: str | None,
    guidance_ack: bool,
    playbook_id: str,
) -> bool:
    return (
        (caller or "").strip().lower() == "openclaw"
        and playbook_id == "modern_psychology_post"
        and not guidance_ack
    )


def _build_safe_login_rerun_request(
    *,
    request: PlaybookRequest,
    effective_scene: str,
    ai_tech_evidence_bundle: AiTechEvidenceBundle | None,
    psychology_learning_bundle: PsychologyLearningBundle | None,
) -> PlaybookRequest:
    """Keep a catalog/evidence run's recovery command free of operator input."""
    if ai_tech_evidence_bundle is None and psychology_learning_bundle is None:
        return request
    updates: dict[str, Any] = {"scene": effective_scene}
    if psychology_learning_bundle is not None:
        updates["psychology_curriculum_version"] = (
            psychology_learning_bundle.runtime_contract["curriculum_version"]
        )
    return request.model_copy(update=updates)


def _build_login_required_result(
    *,
    account_id: str,
    account_nickname: str,
    platform: str,
    provider: str,
    preflight: dict[str, Any],
    request: PlaybookRequest,
    command_name: str,
    resolved_platform: str,
    playbook_id: str,
) -> dict[str, Any]:
    qrcode_output_path = None
    qrcode = preflight.get("qrcode")
    if isinstance(qrcode, dict):
        qrcode_output_path = qrcode.get("output_path")
    rerun_command = _build_rerun_command(
        command_name=command_name,
        request=request,
        resolved_platform=resolved_platform,
        resolved_playbook_id=playbook_id,
        requires_ai_evidence=playbook_id == AI_TECH_PLAYBOOK_ID,
        requires_psychology_learning=(
            playbook_id == MODERN_PSYCHOLOGY_PLAYBOOK_ID
            and _is_psychology_learning_request(request)
        ),
    )
    recovery_instruction = None
    if rerun_command is None:
        recovery_instruction = (
            "After login, retry the original API request with the same "
            "ai_content_mode and ai_evidence_bundle. No evidence-file path was "
            "supplied, so PTSM intentionally omits a CLI rerun command."
        )
    return {
        "status": "login_required",
        "platform": platform,
        "provider": provider,
        "account_id": account_id,
        "account_nickname": account_nickname,
        "preflight": preflight,
        "login_instructions": build_xhs_login_instructions(
            qrcode_output_path=str(qrcode_output_path) if qrcode_output_path else None,
            rerun_command=rerun_command,
            recovery_instruction=recovery_instruction,
        ),
    }


def _build_workflow_for_playbook(
    *,
    domain: str,
    playbook_id: str,
    memory: ExecutionMemoryStore,
    checkpointer: object,
    settings: Settings,
    format_pattern_path: str | None = None,
    artifact_store: FileArtifactStore | None = None,
    expected_artifact_root_identity: os.stat_result | None = None,
    ai_tech_evidence: dict[str, Any] | None = None,
    ai_tech_evidence_manifest: dict[str, Any] | None = None,
    psychology_learning_contract: dict[str, Any] | None = None,
    psychology_learning_manifest: dict[str, Any] | None = None,
    psychology_learning_catalog_receipt: dict[str, Any] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
):
    skill_context_resolver = _build_runtime_skill_context_resolver(
        settings,
        format_pattern_path=format_pattern_path,
    )
    if playbook_id == "fengkuang_daily_post":
        return build_fengkuang_workflow(
            memory=memory,
            checkpointer=checkpointer,
            settings=settings,
            skill_context_resolver=skill_context_resolver,
        )
    return build_playbook_workflow(
        playbook_id=playbook_id,
        domain=domain,
        memory=memory,
        checkpointer=checkpointer,
        settings=settings,
        artifact_store=artifact_store,
        expected_artifact_root_identity=expected_artifact_root_identity,
        skill_context_resolver=skill_context_resolver,
        ai_tech_evidence=ai_tech_evidence,
        ai_tech_evidence_manifest=ai_tech_evidence_manifest,
        psychology_learning_contract=psychology_learning_contract,
        psychology_learning_manifest=psychology_learning_manifest,
        psychology_learning_catalog_receipt=psychology_learning_catalog_receipt,
        psychology_learning_preflight_capability=(
            psychology_learning_preflight_capability
        ),
    )


def _build_runtime_skill_context_resolver(
    settings: Settings,
    *,
    format_pattern_path: str | None = None,
) -> SkillContextResolver | None:
    provider = settings.default_model_provider.lower().strip()
    pattern_path = format_pattern_path or settings.xhs_pattern_library_path
    if provider == "deterministic":
        return _build_local_pattern_skill_context_resolver(
            pattern_path=pattern_path,
            settings=settings,
        )
    if provider == "deepseek" and not settings.deepseek_api_key:
        return _build_local_pattern_skill_context_resolver(
            pattern_path=pattern_path,
            settings=settings,
        )
    if format_pattern_path:
        return build_skill_context_resolver(settings=settings, pattern_path=pattern_path)
    return _build_reddit_skill_context_resolver(settings=settings)


def _build_reddit_skill_context_resolver(*, settings: Settings) -> SkillContextResolver:
    return SkillContextResolver(
        builders={
            "reddit_discussion_scan": RedditDiscussionContextBuilder.from_settings(settings),
        }
    )


def _build_local_pattern_skill_context_resolver(
    *,
    pattern_path: str,
    settings: Settings,
) -> SkillContextResolver:
    pattern_builder = XhsPatternContextBuilder(pattern_path=pattern_path)
    return SkillContextResolver(
        builders={
            "xhs_trend_scan": pattern_builder,
            "topic_research": PatternAwareTopicResearchContextBuilder(
                topic_builder=TopicResearchContextBuilder(allow_fresh_scan=False),
                pattern_builder=pattern_builder,
            ),
            "reddit_discussion_scan": RedditDiscussionContextBuilder.from_settings(settings),
        }
    )


def _build_rerun_command(
    *,
    command_name: str,
    request: PlaybookRequest,
    resolved_platform: str,
    resolved_playbook_id: str,
    requires_ai_evidence: bool,
    requires_psychology_learning: bool,
) -> str | None:
    if requires_ai_evidence and not request.ai_evidence_file_path:
        return None
    requires_catalog_bound_scene = requires_ai_evidence or requires_psychology_learning
    if not requires_catalog_bound_scene and (
        command_name == "run-fengkuang" or request.playbook_id in {None, "fengkuang_daily_post"}
    ):
        return (
            f"ptsm run-fengkuang --scene '{request.scene}' --platform {resolved_platform} "
            f"--account-id {request.account_id} --publish-mode mcp-real"
        )
    parts = [
        "ptsm run-playbook",
        f"--account-id {request.account_id}",
        f"--publish-mode mcp-real",
    ]
    if not requires_catalog_bound_scene:
        parts.append(f"--scene '{request.scene}'")
    if request.playbook_id or requires_catalog_bound_scene:
        parts.append(f"--playbook-id {request.playbook_id or resolved_playbook_id}")
    if request.platform:
        parts.append(f"--platform {resolved_platform}")
    if requires_ai_evidence and request.ai_content_mode:
        parts.append(f"--ai-content-mode {shlex.quote(request.ai_content_mode)}")
    if requires_ai_evidence and request.ai_evidence_file_path:
        parts.append(
            f"--ai-evidence-file={shlex.quote(request.ai_evidence_file_path)}"
        )
    if requires_psychology_learning:
        if request.psychology_content_mode:
            parts.append(
                "--psychology-content-mode "
                f"{shlex.quote(request.psychology_content_mode)}"
            )
        if request.psychology_series_id:
            parts.append(
                "--psychology-series-id "
                f"{shlex.quote(request.psychology_series_id)}"
            )
        if request.psychology_lesson_id:
            parts.append(
                "--psychology-lesson-id "
                f"{shlex.quote(request.psychology_lesson_id)}"
            )
        if request.psychology_curriculum_version:
            parts.append(
                "--psychology-curriculum-version "
                f"{shlex.quote(request.psychology_curriculum_version)}"
            )
        if request.topic_direction_id:
            parts.append(
                "--topic-direction-id "
                f"{shlex.quote(request.topic_direction_id)}"
            )
    return " ".join(parts)


def _build_publish_idempotency_key(
    *,
    account_id: str,
    playbook_id: str,
    publish_mode: str,
    artifact_path: str,
    image_paths: list[str],
    visibility: str | None,
) -> str:
    return "|".join(
        [
            account_id,
            playbook_id,
            publish_mode,
            artifact_path,
            ",".join(image_paths),
            visibility or "",
        ]
    )


def _should_generate_images(
    *,
    publish_mode: str,
    auto_generate_images: bool | None,
) -> bool:
    if auto_generate_images is True:
        return True
    if auto_generate_images is False:
        return False
    return publish_mode == "mcp-real"


def _should_remove_watermark(
    *,
    publish_mode: str,
    watermark_removal_enabled: bool,
    image_paths: Sequence[str],
) -> bool:
    if not image_paths:
        return False
    if publish_mode == "mcp-real":
        return True
    return watermark_removal_enabled


def _watermark_removal_policy(
    *,
    publish_mode: str,
    watermark_removal_enabled: bool,
) -> str:
    if publish_mode == "mcp-real":
        return "required_for_real_publish"
    if watermark_removal_enabled:
        return "enabled_by_settings"
    return "disabled"


def _should_skip_watermark_removal_for_local_renderer(
    *,
    image_generation: dict[str, Any] | None,
    image_paths: Sequence[str],
) -> bool:
    if not image_paths or not isinstance(image_generation, dict):
        return False
    provenance = image_generation.get("provenance")
    if not isinstance(provenance, dict):
        return False
    return (
        provenance.get("source") == "ptsm_local_renderer"
        and provenance.get("watermark_removal") == "skip"
    )


def _local_renderer_watermark_removal_skipped_result() -> dict[str, object]:
    return {
        "status": "skipped",
        "policy": "skipped_for_local_renderer",
        "reason": "local_renderer_trusted_no_watermark",
    }


def _ensure_generated_image_watermark_policy(image_generation: dict[str, Any]) -> None:
    if image_generation.get("watermark_policy"):
        return
    provider = str(image_generation.get("provider") or "unknown")
    image_generation["watermark_policy"] = generated_no_watermark_policy(
        provider,
        {"runtime_policy": "generated_images_request_no_provider_watermark"},
    )


def _build_image_generation_prompt(
    *,
    scene: str,
    persona_prompt: str | None = None,
    runtime_skill_contents: list[str] | None = None,
    content_review: dict[str, Any] | None = None,
    final_content: dict[str, Any],
    image_plan: dict[str, Any] | None = None,
) -> str:
    scene_text = _truncate_text(str(final_content.get("scene", scene)).strip() or scene, 80)
    title = _truncate_text(str(final_content.get("title", "")).strip(), 80)
    image_text = _truncate_text(str(final_content.get("image_text", "")).strip(), 120)
    body = _truncate_text(
        " ".join(str(final_content.get("body", "")).split()),
        220,
    )
    persona = _truncate_text(" ".join((persona_prompt or "").split()), 140)
    runtime_context = _truncate_text(
        _summarize_runtime_skill_contents(runtime_skill_contents or []),
        120,
    )
    image_form = _truncate_text(_summarize_image_form(content_review), 120)
    image_plan_summary = _truncate_text(_summarize_image_plan(image_plan), 140)
    provider_policy = _provider_image_prompt_policy(image_plan)
    prompt = (
        "为小红书帖子生成一张 3:4 竖版封面图，适合中文社交媒体发布。"
        f"主题场景：{scene_text}。"
        f"标题氛围：{title}。"
        f"封面文案参考：{image_text}。"
        f"正文情绪摘要：{body}。"
        f"账号人设参考：{persona or '像真实创作者在发帖'}。"
        f"实时话题切口：{runtime_context or '贴近日常讨论热感即可'}。"
        f"图片形式参考：{image_form or '单张真实感封面'}。"
        f"图片策略：{image_plan_summary or '未指定，按真实感封面处理'}。"
        f"{provider_policy}"
        "要求：中文互联网感，构图干净，有留白，像真人账号会发的封面"
        "，避免机械对称、塑料质感和营销海报感，保留真实随手拍氛围，"
        "AI 生成图只作为氛围参考，不要伪装成真实前后对比或真实观察证据，"
        "真人随手拍，不要复杂小字，不要在图片上添加任何标签文字如#发疯文学等话题标签，不要额外水印。"
    )
    return _truncate_text(prompt, 800)


def _provider_image_prompt_policy(image_plan: dict[str, Any] | None) -> str:
    metadata = _image_generation_decision_metadata(image_plan or {})
    role = metadata.get("role", "").lower()
    parts = [
        "真实感约束：手机随手拍，自然光或室内环境光，不完美构图，边缘轻微裁切；",
        "不要塑料皮肤，不要伪造真实界面截图，不要做营销海报，不要密集排版。",
    ]
    if role == "evidence_or_scene":
        parts.append("画面重点是真实物件、空间或过程，不用大字海报。")
    elif role == "cover_hook":
        parts.append("如需文字，最多一行短字，像创作者后期轻贴的封面字。")
    elif role in {"save_tool", "comment_prompt"}:
        parts.append("不要让外部模型伪造聊天或备忘录截图，只生成真实桌面/纸张氛围。")
    return "".join(parts)


def _build_note_card_image_payload(
    *,
    scene: str,
    runtime_context_summary: str,
    final_content: dict[str, Any],
    local_image_style: str | None = None,
    image_plan: dict[str, Any] | None = None,
) -> str:
    renderer_options = _local_renderer_options_from_final_content(final_content)
    renderer_image_plan = _local_renderer_image_plan_payload(
        final_content,
        image_plan or {},
    )
    return json.dumps(
        {
            "style": local_image_style or "xhs_note_card_v1",
            "scene": _truncate_text(str(final_content.get("scene", scene)).strip() or scene, 80),
            "title": _truncate_text(str(final_content.get("title", "")).strip(), 80),
            "image_text": _truncate_text(str(final_content.get("image_text", "")).strip(), 120),
            "body": _select_local_image_body(final_content, image_plan or {}),
            "hashtags": list(final_content.get("hashtags", []) or []),
            "runtime_context_summary": runtime_context_summary,
            "image_plan": renderer_image_plan,
            **renderer_options,
        },
        ensure_ascii=False,
    )


_LOW_DENSITY_IMAGE_ROLES = {
    "cover_hook",
    "save_tool",
    "comment_prompt",
    "evidence_or_scene",
    "shareable_line",
}


def _select_local_image_body(
    final_content: dict[str, Any],
    image_plan: dict[str, Any],
) -> str:
    body = str(final_content.get("body", "") or "")
    if _uses_wechat_chat_image(final_content, image_plan):
        chat_body = _select_wechat_chat_body(final_content)
        if chat_body:
            return chat_body

    if not _uses_low_density_image_copy(image_plan):
        return _truncate_text(" ".join(body.split()), 360)

    max_units = _image_plan_max_text_units(image_plan, default=2)
    short_lines = _extract_short_image_lines(body, max_units=max_units)
    if short_lines:
        return "\n".join(short_lines[:max_units])
    return ""


_LOCAL_RENDERER_IMAGE_PLAN_FIELDS = (
    "theme",
    "status_time",
    "chat_title",
    "conversation_title",
    "show_avatars",
    "chat_times",
    "unread_count",
)


def _local_renderer_options_from_final_content(
    final_content: dict[str, Any],
) -> dict[str, Any]:
    raw_plan = final_content.get("image_plan")
    image_plan = raw_plan if isinstance(raw_plan, dict) else {}
    options: dict[str, Any] = {}
    for field in _LOCAL_RENDERER_IMAGE_PLAN_FIELDS:
        if field in final_content and final_content[field] is not None:
            options[field] = final_content[field]
        elif field in image_plan and image_plan[field] is not None:
            options[field] = image_plan[field]
    return options


def _local_renderer_image_plan_payload(
    final_content: dict[str, Any],
    image_plan: dict[str, Any],
) -> dict[str, Any]:
    raw_plan = final_content.get("image_plan")
    final_image_plan = raw_plan if isinstance(raw_plan, dict) else {}
    return {
        **final_image_plan,
        **_image_generation_decision_metadata(image_plan),
    }


def _uses_wechat_chat_image(
    final_content: dict[str, Any],
    image_plan: dict[str, Any],
) -> bool:
    raw_plan = final_content.get("image_plan")
    final_image_plan = raw_plan if isinstance(raw_plan, dict) else {}
    candidates = (
        image_plan.get("requested_style"),
        image_plan.get("style"),
        final_image_plan.get("style"),
    )
    return any(
        _normalized_image_plan_value(candidate) in {"wechat_chat", "wechat_chat_v1"}
        for candidate in candidates
    )


def _select_wechat_chat_body(final_content: dict[str, Any]) -> str:
    raw_plan = final_content.get("image_plan")
    image_plan = raw_plan if isinstance(raw_plan, dict) else {}
    for raw_messages in (
        final_content.get("chat_messages"),
        final_content.get("messages"),
        image_plan.get("chat_messages"),
        image_plan.get("messages"),
    ):
        structured_lines = _structured_chat_message_lines(raw_messages)
        if structured_lines:
            return "\n".join(structured_lines[:8])

    body = str(final_content.get("body", "") or "")
    explicit_lines = [
        line.strip()
        for line in body.splitlines()
        if _looks_like_chat_message_line(line)
    ]
    if explicit_lines:
        return "\n".join(explicit_lines[:8])
    return ""


def _structured_chat_message_lines(raw_messages: object) -> list[str]:
    if not isinstance(raw_messages, list):
        return []

    lines: list[str] = []
    for raw_message in raw_messages:
        speaker = ""
        text = ""
        if isinstance(raw_message, dict):
            speaker = _first_string_value(
                raw_message, ("speaker", "sender", "role", "name", "author")
            )
            text = _first_string_value(
                raw_message, ("text", "message", "content", "body")
            )
        elif isinstance(raw_message, Sequence) and not isinstance(raw_message, str):
            values = list(raw_message)
            if len(values) >= 2:
                speaker = str(values[0] or "").strip()
                text = str(values[1] or "").strip()
        elif isinstance(raw_message, str):
            text = raw_message.strip()

        if not text:
            continue
        if speaker:
            lines.append(f"{_normalize_chat_speaker_label(speaker)}：{text}")
        else:
            lines.append(text)
    return lines


def _first_string_value(payload: dict[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_chat_speaker_label(speaker: str) -> str:
    value = speaker.strip()
    lowered = value.lower()
    if lowered in {"me", "self", "user", "mine"}:
        return "我"
    if lowered in {"other", "assistant", "friend", "peer"}:
        return "对方"
    return value


def _looks_like_chat_message_line(line: str) -> bool:
    return re.match(r"^\s*[^:：\n]{1,12}\s*[:：]\s*\S+", line) is not None


def _uses_low_density_image_copy(image_plan: dict[str, Any]) -> bool:
    metadata = _image_generation_decision_metadata(image_plan)
    text_density = metadata.get("text_density", "").lower()
    role = metadata.get("role", "").lower()
    return text_density == "low" or role in _LOW_DENSITY_IMAGE_ROLES


def _image_plan_max_text_units(
    image_plan: dict[str, Any],
    *,
    default: int,
) -> int:
    raw_value = str(image_plan.get("max_text_units") or "").strip()
    try:
        value = int(raw_value)
    except ValueError:
        value = default
    return max(1, min(value, 4))


def _extract_short_image_lines(body: str, *, max_units: int) -> list[str]:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        inline_tool_lines = _extract_inline_tool_lines(line, max_units=max_units)
        if inline_tool_lines:
            lines.extend(inline_tool_lines)
            if len(lines) >= max_units:
                return lines[:max_units]
            continue
        list_match = re.match(r"^(?:[-*•]|\d+[.)、．])\s*(.+)$", line)
        if list_match is not None:
            candidate = list_match.group(1).strip()
        elif len(line) <= 24:
            candidate = line
        else:
            continue
        if candidate:
            lines.append(_truncate_text(candidate, 32))
        if len(lines) >= max_units:
            return lines

    if lines:
        return lines

    compact = " ".join(body.split())
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[。！？!?]\s*", compact)
        if sentence.strip()
    ]
    return [_truncate_text(sentence, 32) for sentence in sentences[:max_units] if len(sentence) <= 36]


def _extract_inline_tool_lines(line: str, *, max_units: int) -> list[str]:
    marker_match = re.search(r"(?:三栏|清单|步骤|工具)[:：]", line)
    if marker_match is None:
        return []
    tail = line[marker_match.end() :].strip()
    parts = [part.strip(" 。") for part in re.split(r"[;；]\s*", tail) if part.strip()]
    lines: list[str] = []
    for part in parts:
        if not part:
            continue
        if not any(separator in part for separator in ("=", "＝", ":", "：")) and len(part) > 24:
            continue
        lines.append(_truncate_text(part, 32))
        if len(lines) >= max_units:
            break
    return lines


def _resolve_image_generation_decision(
    *,
    request: PlaybookRequest,
    final_content: dict[str, Any],
    image_backend_available: bool,
) -> dict[str, Any]:
    raw_plan = final_content.get("image_plan")
    image_plan = raw_plan if isinstance(raw_plan, dict) else {}
    requested_backend = _normalized_image_plan_value(image_plan.get("backend"))
    requested_style = _normalized_image_plan_value(image_plan.get("style"))
    reason = str(image_plan.get("reason") or "").strip()
    prompt_focus = str(image_plan.get("prompt_focus") or "").strip()
    role_fields = _image_plan_role_fields(image_plan)

    if request.local_image_style:
        return {
            "route": "local",
            "source": "manual_override",
            "requested_backend": "local_note_card",
            "selected_backend": "local_note_card",
            "requested_style": request.local_image_style,
            "reason": "manual --local-image-style override",
            **role_fields,
        }

    if requested_backend in {
        "local_social_screenshot",
        "local_note_card",
        "local",
        "local_renderer",
    }:
        return {
            "route": "local",
            "source": "llm_image_plan",
            "requested_backend": requested_backend,
            "selected_backend": "local_note_card",
            "requested_style": requested_style or "note_card",
            "reason": reason,
            "prompt_focus": prompt_focus,
            **role_fields,
        }

    if requested_backend in {"provider_image", "provider", "external", "external_provider"}:
        if image_backend_available:
            return {
                "route": "provider",
                "source": "llm_image_plan",
                "requested_backend": requested_backend,
                "selected_backend": "provider_image",
                "requested_style": requested_style,
                "reason": reason,
                "prompt_focus": prompt_focus,
                **role_fields,
            }
        return {
            "route": "local",
            "source": "llm_image_plan",
            "requested_backend": requested_backend,
            "selected_backend": "local_note_card",
            "requested_style": "note_card",
            "reason": reason,
            "prompt_focus": prompt_focus,
            "fallback_reason": "provider_image_requested_but_unavailable",
            **role_fields,
        }

    if image_backend_available:
        return {
            "route": "provider",
            "source": "default",
            "requested_backend": "provider_image",
            "selected_backend": "provider_image",
            "requested_style": requested_style,
            "reason": reason,
            "prompt_focus": prompt_focus,
            **role_fields,
        }

    return {
        "route": "local",
        "source": "default",
        "requested_backend": "local_note_card",
        "selected_backend": "local_note_card",
        "requested_style": requested_style or "note_card",
        "reason": reason,
        "prompt_focus": prompt_focus,
        **role_fields,
    }


def _image_generation_decision_metadata(decision: dict[str, Any]) -> dict[str, str]:
    fields = (
        "source",
        "requested_backend",
        "selected_backend",
        "requested_style",
        "reason",
        "prompt_focus",
        "fallback_reason",
        "role",
        "text_density",
        "max_text_units",
        "cover_text_strategy",
    )
    return {
        field: str(decision[field]).strip()
        for field in fields
        if decision.get(field) is not None and str(decision[field]).strip()
    }


def _image_plan_role_fields(image_plan: dict[str, Any]) -> dict[str, str]:
    fields = ("role", "text_density", "max_text_units", "cover_text_strategy")
    return {
        field: str(image_plan[field]).strip()
        for field in fields
        if image_plan.get(field) is not None and str(image_plan[field]).strip()
    }


def _normalized_image_plan_value(value: object) -> str:
    return str(value or "").strip().lower()


def _summarize_image_plan(image_plan: dict[str, Any] | None) -> str:
    if not isinstance(image_plan, dict):
        return ""
    metadata = _image_generation_decision_metadata(image_plan)
    parts: list[str] = []
    if metadata.get("requested_backend"):
        parts.append(f"backend={metadata['requested_backend']}")
    if metadata.get("requested_style"):
        parts.append(f"style={metadata['requested_style']}")
    if metadata.get("reason"):
        parts.append(metadata["reason"])
    if metadata.get("prompt_focus"):
        parts.append(metadata["prompt_focus"])
    if metadata.get("role"):
        parts.append(f"role={metadata['role']}")
    if metadata.get("text_density"):
        parts.append(f"text_density={metadata['text_density']}")
    if metadata.get("max_text_units"):
        parts.append(f"max_text_units={metadata['max_text_units']}")
    if metadata.get("cover_text_strategy"):
        parts.append(metadata["cover_text_strategy"])
    return "；".join(parts)


def _summarize_runtime_skill_contents(contents: list[str]) -> str:
    signals: list[str] = []
    for content in contents:
        primary_hook = _extract_runtime_signal(content, label="主切口")
        tension = _extract_runtime_signal(content, label="场景张力")
        if primary_hook:
            signals.append(f"主切口 {primary_hook}")
        if tension:
            signals.append(f"场景张力 {tension}")
        if signals:
            break
    return "，".join(signals)


def _summarize_image_form(content_review: dict[str, Any] | None) -> str:
    if not isinstance(content_review, dict):
        return ""
    image_form = content_review.get("image_form")
    if not isinstance(image_form, dict):
        return ""
    sequence = image_form.get("recommended_sequence")
    if not isinstance(sequence, list):
        return ""
    translated = {
        "cover": "封面",
        "before state": "原本状态",
        "variable/material flat lay": "变量或材料平铺",
        "mini checklist": "清单",
        "after state": "改变后细节",
        "comment invitation": "评论区提问",
    }
    return "，".join(translated.get(str(item), str(item)) for item in sequence[:5])


def _extract_runtime_signal(content: str, *, label: str) -> str:
    match = re.search(rf"{re.escape(label)}[:：]\s*`?([^`\n]+)`?", content)
    if match is None:
        return ""
    return match.group(1).strip()


def _truncate_text(value: str, limit: int) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    if limit <= 1:
        return normalized[:limit]
    return normalized[: limit - 1].rstrip() + "…"


def _extract_format_patterns_used(
    result: dict[str, Any],
    *,
    pattern_path: str,
) -> dict[str, Any]:
    for content in result.get("runtime_skill_contents") or []:
        text = str(content)
        if "# XHS Format Pattern Library Context" not in text:
            continue
        return {
            "status": _extract_context_value(text, "status") or "available",
            "freshness": _extract_context_value(text, "freshness"),
            "lane": _extract_context_value(text, "lane"),
            "source_artifact_path": _extract_context_value(text, "source"),
            "pattern_ids": _split_context_list(_extract_context_value(text, "pattern_ids")),
            "hook_archetypes": _split_context_list(
                _extract_context_value(text, "hook_archetypes")
            ),
            "body_structures": _split_context_list(
                _extract_context_value(text, "body_structures"),
                separator="|",
            ),
            "image_sequences": _split_context_list(
                _extract_context_value(text, "image_sequences"),
                separator="|",
            ),
            "primary_ratio": _extract_context_value(text, "primary_ratio"),
        }
    return {
        "status": "unavailable",
        "source_artifact_path": pattern_path,
        "pattern_ids": [],
    }


def _extract_context_value(content: str, key: str) -> str:
    match = re.search(rf"^-\s*{re.escape(key)}:\s*(.+)$", content, flags=re.MULTILINE)
    return match.group(1).strip() if match else ""


def _split_context_list(value: str, *, separator: str = ",") -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(separator) if part.strip()]


def _should_record_publish_result(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return result.get("status") not in {"error", "login_required", None}


def _run_eval_on_artifact(
    *,
    artifact_path: str | None,
    run_id: str,
    artifact_payload: dict[str, object] | None = None,
    psychology_learning_preflight_capability: _PsychologyLearningPreflightCapability | None = None,
) -> dict[str, Any] | None:
    if artifact_path is None:
        return None
    try:
        from ptsm.application.use_cases.eval_artifact import run_eval_artifact

        return run_eval_artifact(
            artifact_path=artifact_path,
            run_id=run_id,
            artifact_payload=artifact_payload,
            psychology_learning_preflight_capability=(
                psychology_learning_preflight_capability
            ),
        )
    except Exception:
        return {"status": "error", "reason": "eval step raised exception"}
