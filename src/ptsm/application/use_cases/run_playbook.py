from __future__ import annotations

from pathlib import Path
from typing import Any

from ptsm.accounts.registry import AccountRegistry
from ptsm.agent_runtime.runtime import (
    build_playbook_workflow,
    build_fengkuang_workflow,
    build_file_backed_runtime_state,
)
from ptsm.application.models import FengkuangRequest, PlaybookRequest
from ptsm.application.services.side_effect_ledger import SideEffectLedger
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
from ptsm.infrastructure.images.factory import build_image_backend
from ptsm.infrastructure.images.watermark_remover import WatermarkRemover
from ptsm.infrastructure.publishers.contracts import Publisher
from ptsm.infrastructure.publishers.factory import build_publisher
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import PublisherPreflightError
from ptsm.playbooks.registry import PlaybookRegistry

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"
DEFAULT_SIDE_EFFECT_LEDGER_PATH = Path(".ptsm") / "agent_runtime" / "side-effects.json"
DEFAULT_GENERATED_IMAGES_DIR = Path("outputs") / "generated_images"
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_ATTEMPTS = 4
WAIT_FOR_PUBLISH_STATUS_SEARCH_RETRY_INTERVAL_SECONDS = 2.0


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
    )
    effective_thread_id = thread_id or run.run_id
    config = {"configurable": {"thread_id": effective_thread_id}}
    result = workflow.invoke(
        {
            **request.model_dump(mode="python"),
            "platform": resolved_platform,
        },
        config=config,
    )
    result = {"playbook_id": playbook.playbook_id, **result}
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
            if image_backend is None:
                image_generation = {
                    "status": "skipped",
                    "reason": "backend_not_configured",
                }
            else:
                image_generation = image_backend.generate(
                    prompt=_build_image_generation_prompt(
                        scene=request.scene,
                        persona_prompt=str(result.get("persona_prompt") or ""),
                        final_content=result["final_content"],
                    ),
                    output_dir=Path.cwd() / DEFAULT_GENERATED_IMAGES_DIR,
                    output_stem=f"{artifact_path.stem}-cover",
                )
                resolved_image_paths = list(
                    image_generation.get("generated_image_paths")
                    or image_generation.get("image_paths")
                    or []
                )

        watermark_removal = None
        if settings.watermark_removal_enabled and resolved_image_paths:
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
        artifact_store.merge(
            result["artifact_path"],
            {
                "scene": request.scene,
                "platform": request.platform,
                "account": account.to_dict(),
                "publish_mode": publish_mode,
                "publish_result": publish_result,
                "image_generation": image_generation,
                "watermark_removal": watermark_removal,
                "run": run.to_dict(),
            },
        )

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
        },
    )
    return {
        **result,
        "account": account.to_dict(),
        "publish_mode": publish_mode,
        "publish_result": publish_result,
        "image_generation": image_generation,
        "watermark_removal": watermark_removal,
        "post_publish_checks": post_publish_checks,
        "run": run_summary,
    }


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
):
    if playbook_id == "fengkuang_daily_post":
        return build_fengkuang_workflow(
            memory=memory,
            checkpointer=checkpointer,
            settings=settings,
        )
    return build_playbook_workflow(
        playbook_id=playbook_id,
        domain=domain,
        memory=memory,
        checkpointer=checkpointer,
        settings=settings,
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


def _build_image_generation_prompt(
    *,
    scene: str,
    persona_prompt: str | None = None,
    final_content: dict[str, Any],
) -> str:
    scene_text = _truncate_text(str(final_content.get("scene", scene)).strip() or scene, 80)
    title = _truncate_text(str(final_content.get("title", "")).strip(), 80)
    image_text = _truncate_text(str(final_content.get("image_text", "")).strip(), 120)
    body = _truncate_text(
        " ".join(str(final_content.get("body", "")).split()),
        260,
    )
    hashtags = _truncate_text(
        " ".join(str(tag).strip() for tag in final_content.get("hashtags", [])[:3]),
        80,
    )
    persona = _truncate_text(" ".join((persona_prompt or "").split()), 180)
    prompt = (
        "为小红书帖子生成一张 3:4 竖版封面图，适合中文社交媒体发布。"
        f"主题场景：{scene_text}。"
        f"标题氛围：{title}。"
        f"封面文案参考：{image_text}。"
        f"正文情绪摘要：{body}。"
        f"标签氛围：{hashtags}。"
        f"账号人设参考：{persona or '像真实创作者在发帖'}。"
        "要求：中文互联网感，构图干净，有留白，像真人账号会发的封面，避免机械对称、塑料质感和营销海报感，保留真实随手拍氛围，真人随手拍，不要复杂小字，不要额外水印。"
    )
    return _truncate_text(prompt, 800)


def _truncate_text(value: str, limit: int) -> str:
    normalized = value.strip()
    if len(normalized) <= limit:
        return normalized
    if limit <= 1:
        return normalized[:limit]
    return normalized[: limit - 1].rstrip() + "…"


def _should_record_publish_result(result: dict[str, Any] | None) -> bool:
    if not isinstance(result, dict):
        return False
    return result.get("status") not in {"error", "login_required", None}
