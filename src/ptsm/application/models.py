from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PlaybookRequest(BaseModel):
    """Generic input contract for a playbook run."""

    scene: str = Field(default="")
    account_id: str = Field(min_length=1)
    platform: str | None = None
    playbook_id: str | None = None
    caller: str | None = None
    guidance_ack: bool = False
    topic_direction_id: str | None = None
    publish_mode: str | None = None
    publish_image_paths: list[str] = Field(default_factory=list)
    auto_generate_images: bool | None = None
    publish_visibility: str | None = None
    login_qrcode_output_path: str | None = None
    open_browser_if_needed: bool = False
    wait_for_publish_status: bool = False
    fresh_topic_research: bool = False
    format_pattern_path: str | None = None
    local_image_style: str | None = None
    ai_content_mode: str | None = None
    ai_evidence_bundle: dict[str, Any] | None = None
    ai_evidence_file_path: str | None = None


class FengkuangRequest(PlaybookRequest):
    """Compatibility input contract for the fengkuang workflow."""

    platform: str = Field(default="xiaohongshu", min_length=1)
