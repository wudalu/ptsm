from __future__ import annotations

from pydantic import BaseModel, Field


class PlaybookRequest(BaseModel):
    """Generic input contract for a playbook run."""

    scene: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    platform: str | None = None
    playbook_id: str | None = None
    publish_mode: str | None = None
    publish_image_paths: list[str] = Field(default_factory=list)
    publish_visibility: str | None = None
    login_qrcode_output_path: str | None = None
    open_browser_if_needed: bool = False
    wait_for_publish_status: bool = False


class FengkuangRequest(PlaybookRequest):
    """Compatibility input contract for the fengkuang workflow."""

    platform: str = Field(default="xiaohongshu", min_length=1)
