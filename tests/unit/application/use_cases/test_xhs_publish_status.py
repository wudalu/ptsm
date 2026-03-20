from __future__ import annotations

import json
from pathlib import Path

from ptsm.application.use_cases.xhs_publish_status import check_xhs_publish_status


class FakeStatusPublisher:
    def check_publish_status(
        self,
        *,
        post_id: str | None = None,
        post_url: str | None = None,
    ) -> dict[str, object]:
        return {
            "status": "published_visible",
            "post_id": post_id,
            "post_url": post_url,
            "source": "mcp",
        }


def test_check_xhs_publish_status_uses_publisher_when_artifact_has_identifiers(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                    "post_id": "note-123",
                    "post_url": "https://www.xiaohongshu.com/explore/note-123",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = check_xhs_publish_status(
        artifact_path=artifact_path,
        publisher=FakeStatusPublisher(),
    )

    assert result["status"] == "published_visible"
    assert result["post_id"] == "note-123"
    assert result["source"] == "mcp"


def test_check_xhs_publish_status_requests_manual_check_without_identifiers(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = check_xhs_publish_status(artifact_path=artifact_path)

    assert result["status"] == "manual_check_required"
    assert "artifact" in result["reason"]
