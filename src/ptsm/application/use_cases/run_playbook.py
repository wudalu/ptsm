from __future__ import annotations

from pathlib import Path
from typing import Any

from ptsm.accounts.registry import AccountRegistry
from ptsm.agent_runtime.runtime import (
    build_fengkuang_workflow,
    build_file_backed_runtime_state,
)
from ptsm.application.models import FengkuangRequest, PlaybookRequest
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
from ptsm.infrastructure.publishers.contracts import Publisher
from ptsm.infrastructure.publishers.factory import build_publisher
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import PublisherPreflightError
from ptsm.playbooks.registry import PlaybookRegistry

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"


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
    if result["status"] == "completed":
        try:
            publish_result = publisher.publish(
                account=account,
                content=result["final_content"],
                artifact_path=result["artifact_path"],
                image_paths=request.publish_image_paths,
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
        artifact_store.merge(
            result["artifact_path"],
            {
                "scene": request.scene,
                "platform": request.platform,
                "account": account.to_dict(),
                "publish_mode": publish_mode,
                "publish_result": publish_result,
                "run": run.to_dict(),
            },
        )

    if result["status"] == "completed" and result.get("artifact_path"):
        artifact_path = Path(result["artifact_path"])
        if request.wait_for_publish_status:
            status_result = check_xhs_publish_status(
                artifact_path=artifact_path,
                settings=settings,
                publisher=publisher,
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
    raise ValueError(f"Unsupported playbook runtime: {playbook_id}")


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
    return (
        f"ptsm run-playbook --account-id {request.account_id} "
        f"--scene '{request.scene}' --publish-mode mcp-real"
    )
