from __future__ import annotations

import asyncio
import json
from pathlib import Path
import re
import sys
from typing import Any, Sequence

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
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
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
from ptsm.skills.runtime_context import (
    PatternAwareTopicResearchContextBuilder,
    RedditDiscussionContextBuilder,
    SkillContextResolver,
    TopicResearchContextBuilder,
    XhsPatternContextBuilder,
    build_skill_context_resolver,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
DEFAULT_SIDE_EFFECT_LEDGER_PATH = Path(".ptsm") / "agent_runtime" / "side-effects.json"
DEFAULT_GENERATED_IMAGES_DIR = Path("outputs") / "generated_images"
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_ATTEMPTS = 4
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_INTERVAL_SECONDS = 2.0


def _run_topic_radar_scan(platform: str) -> dict[str, Any]:
    """Run topic-radar scan across all platforms and return structured results for user selection."""
    from topic_radar.cli import run_scan

    print(f"\n{'='*60}")
    print(f"Topic Radar: scanning hot topics across platforms...")
    print(f"{'='*60}\n")

    try:
        result = asyncio.run(run_scan())
    except RuntimeError as e:
        print(f"Topic radar scan failed: {e}")
        sys.exit(2)

    verticals = [
        {
            "name": v.name,
            "keywords": v.keywords,
            "confidence": v.confidence,
            "discussion_density": v.discussion_density,
            "sample_topics": v.sample_topics,
            "suggested_angles": v.suggested_angles,
            "comment_themes": v.comment_themes,
        }
        for v in result.discovered_verticals
    ]

    angles = result.recommended_angles

    return {
        "scan_summary": result.scan_summary,
        "scan_date": result.scan_date,
        "platforms": result.platforms,
        "verticals": verticals,
        "recommended_angles": angles,
        "noise_topics": result.noise_topics,
    }


def _interactive_topic_selection(scan_result: dict[str, Any]) -> dict[str, Any]:
    """Present topic radar results interactively and return user selection."""
    verticals = scan_result.get("verticals", [])
    angles = scan_result.get("recommended_angles", [])

    if not verticals:
        print("No verticals discovered. Cannot proceed with topic selection.")
        sys.exit(1)

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
        return {
            "vertical": vertical["name"],
            "angle": selected_angle,
            "keywords": vertical.get("keywords", []),
            "discussion_density": vertical.get("discussion_density", ""),
            "comment_themes": vertical.get("comment_themes", []),
            "scan_summary": summary,
        }
    else:
        angle = angles[idx - len(verticals) - 1]
        return {
            "vertical": angle.get("vertical", ""),
            "angle": angle.get("angle", ""),
            "keywords": [],
            "discussion_density": "",
            "comment_themes": [],
            "scan_summary": summary,
        }


def _build_enriched_scene(selection: dict[str, Any]) -> str:
    """Build an enriched scene string from the user's topic selection."""
    parts = [
        f"选题方向：{selection['vertical']}",
    ]
    if selection.get("angle"):
        parts.append(f"切入角度：{selection['angle']}")
    if selection.get("keywords"):
        parts.append(f"关键标签：{'、'.join(selection['keywords'])}")
    if selection.get("comment_themes"):
        parts.append(f"预期讨论方向：{'、'.join(selection['comment_themes'])}")
    if selection.get("scan_summary"):
        parts.append(f"热点背景：{selection['scan_summary']}")
    return "\n".join(parts)


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
    if _requires_openclaw_psychology_guidance(
        caller=request.caller,
        guidance_ack=request.guidance_ack,
        playbook_id=playbook.playbook_id,
    ):
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
        scan_result = _run_topic_radar_scan(platform=resolved_platform)
        topic_selection = _interactive_topic_selection(scan_result)
        enriched_scene = _build_enriched_scene(topic_selection)
        request.scene = enriched_scene
        print(f"\n{'='*60}")
        print(f"Scene built from topic selection:")
        print(f"{enriched_scene}")
        print(f"{'='*60}\n")

    topic_selection_metadata = _topic_selection_metadata(
        topic_selection,
        request.topic_direction_id,
        playbook_id=playbook.playbook_id,
        scene=request.scene,
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
                publish_result = _build_login_required_result(
                    account_id=account.account_id,
                    account_nickname=account.nickname,
                    platform=account.platform,
                    provider=getattr(publisher, "provider_name", publisher.__class__.__name__),
                    preflight=preflight,
                    request=request,
                    command_name=command_name,
                    resolved_platform=resolved_platform,
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
                    "scene": request.scene,
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
    )
    effective_thread_id = thread_id or run.run_id
    config = {"configurable": {"thread_id": effective_thread_id}}
    workflow_payload: dict[str, Any] = {
        **request.model_dump(mode="python"),
        "platform": resolved_platform,
    }
    if topic_selection_metadata is not None:
        workflow_payload["topic_selection"] = topic_selection_metadata
    result = workflow.invoke(workflow_payload, config=config)
    result = {"playbook_id": playbook.playbook_id, **result}
    format_patterns_used = _extract_format_patterns_used(
        result,
        pattern_path=request.format_pattern_path or settings.xhs_pattern_library_path,
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
            runtime_skill_contents = list(result.get("runtime_skill_contents") or [])
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
                        scene=request.scene,
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
                        scene=request.scene,
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
                publish_result = {
                    **_build_login_required_result(
                        account_id=account.account_id,
                        account_nickname=account.nickname,
                        platform=account.platform,
                        provider=getattr(publisher, "provider_name", publisher.__class__.__name__),
                        preflight=preflight,
                        request=request,
                        command_name=command_name,
                        resolved_platform=resolved_platform,
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
            if _should_record_publish_result(publish_result):
                side_effect_ledger.record(
                    thread_id=effective_thread_id,
                    step="publish",
                    idempotency_key=publish_idempotency_key,
                    result=publish_result,
                )
        artifact_update = {
            "scene": request.scene,
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
            browser_result = open_xhs_browser(
                target="artifact",
                artifact_path=artifact_path,
                qrcode_output_path=qrcode_output_path,
            )
            post_publish_checks["browser_opened"] = browser_result.get("status") == "opened"
            post_publish_checks["browser_result"] = browser_result

        artifact_store.merge(
            artifact_path,
            {
                "post_publish_checks": post_publish_checks,
            },
        )

    run_summary = run_store.finish(
        run.run_id,
        status=str(result["status"]),
        payload={
            "artifact_path": result.get("artifact_path"),
            "publish_mode": publish_mode,
            "publish_status": None if publish_result is None else publish_result.get("status"),
            "activated_skills": list(result.get("activated_skills") or []),
            "activated_skill_details": list(result.get("activated_skill_details") or []),
            "runtime_skill_details": list(result.get("runtime_skill_details") or []),
            "format_patterns_used": format_patterns_used,
            "topic_selection": topic_selection_metadata,
        },
    )

    eval_result = None
    if eval_enabled:
        eval_result = _run_eval_on_artifact(
            artifact_path=result.get("artifact_path"),
            run_id=run.run_id,
        )

    response: dict[str, Any] = {
        **result,
        "account": account.to_dict(),
        "publish_mode": publish_mode,
        "publish_result": publish_result,
        "image_generation": image_generation,
        "watermark_removal": watermark_removal,
        "post_publish_checks": post_publish_checks,
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
) -> dict[str, Any]:
    qrcode_output_path = None
    qrcode = preflight.get("qrcode")
    if isinstance(qrcode, dict):
        qrcode_output_path = qrcode.get("output_path")
    rerun_command = _build_rerun_command(
        command_name=command_name,
        request=request,
        resolved_platform=resolved_platform,
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
        skill_context_resolver=skill_context_resolver,
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
) -> str:
    if command_name == "run-fengkuang" or request.playbook_id in {None, "fengkuang_daily_post"}:
        return (
            f"ptsm run-fengkuang --scene '{request.scene}' --platform {resolved_platform} "
            f"--account-id {request.account_id} --publish-mode mcp-real"
        )
    parts = [
        "ptsm run-playbook",
        f"--account-id {request.account_id}",
        f"--scene '{request.scene}'",
        f"--publish-mode mcp-real",
    ]
    if request.playbook_id:
        parts.append(f"--playbook-id {request.playbook_id}")
    if request.platform:
        parts.append(f"--platform {resolved_platform}")
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
) -> dict[str, Any] | None:
    if artifact_path is None:
        return None
    try:
        from ptsm.application.use_cases.eval_artifact import run_eval_artifact

        return run_eval_artifact(
            artifact_path=artifact_path,
            run_id=run_id,
        )
    except Exception:
        return {"status": "error", "reason": "eval step raised exception"}
