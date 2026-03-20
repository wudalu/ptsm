from __future__ import annotations

from typing import Any, Protocol, Sequence

from ptsm.accounts.registry import AccountProfile


class Publisher(Protocol):
    """Sync publisher contract used by application use cases."""

    def publish(
        self,
        *,
        account: AccountProfile,
        content: dict[str, Any],
        artifact_path: str,
        image_paths: Sequence[str],
        visibility: str | None,
    ) -> dict[str, Any]:
        """Publish content or return a structured publish receipt."""

