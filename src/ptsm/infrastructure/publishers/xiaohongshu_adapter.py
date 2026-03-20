from __future__ import annotations

from typing import Any
from typing import Sequence

from ptsm.accounts.registry import AccountProfile


class XiaohongshuAdapter:
    """Build a dry-run publish receipt for XiaoHongShu."""

    platform_name = "xiaohongshu"

    provider_name = "dry_run"

    def publish(
        self,
        *,
        account: AccountProfile,
        content: dict[str, Any],
        artifact_path: str,
        image_paths: Sequence[str],
        visibility: str | None,
    ) -> dict[str, Any]:
        if account.platform != self.platform_name:
            raise ValueError(
                f"Account {account.account_id} does not belong to platform {self.platform_name}"
            )

        hashtags = self._normalize_hashtags(content.get("hashtags", []))
        body = str(content["body"]).strip()
        platform_content = body
        if hashtags:
            platform_content = f"{body}\n\n{' '.join(hashtags)}"

        return {
            "status": "dry_run",
            "platform": self.platform_name,
            "account_id": account.account_id,
            "account_nickname": account.nickname,
            "artifact_path": artifact_path,
            "platform_payload": {
                "title": str(content["title"]).strip(),
                "cover_text": str(content.get("image_text", "")).strip(),
                "content": platform_content,
                "hashtags": hashtags,
                "images": list(image_paths),
                "visibility": visibility,
            },
        }

    def publish_dry_run(
        self,
        *,
        account: AccountProfile,
        content: dict[str, Any],
        artifact_path: str,
    ) -> dict[str, Any]:
        """Compatibility shim for older call sites."""
        return self.publish(
            account=account,
            content=content,
            artifact_path=artifact_path,
            image_paths=[],
            visibility=None,
        )

    def _normalize_hashtags(self, raw_hashtags: Any) -> list[str]:
        hashtags: list[str] = []
        for hashtag in raw_hashtags:
            text = str(hashtag).strip()
            if not text:
                continue
            hashtags.append(text if text.startswith("#") else f"#{text}")
        return hashtags
