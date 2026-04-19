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


class FakeFallbackPublisher(FakeStatusPublisher):
    def __init__(self, *, fallback_result: dict[str, object] | None):
        self.fallback_result = fallback_result

    def find_published_note(
        self,
        *,
        title: str,
        body: str,
    ) -> dict[str, object] | None:
        return self.fallback_result


class SequencedFallbackPublisher(FakeStatusPublisher):
    def __init__(self, *results: dict[str, object] | None):
        self.results = list(results)
        self.calls = 0

    def find_published_note(
        self,
        *,
        title: str,
        body: str,
    ) -> dict[str, object] | None:
        self.calls += 1
        if self.results:
            return self.results.pop(0)
        return None


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


def test_check_xhs_publish_status_uses_search_fallback_for_public_posts(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                    "platform_payload": {
                        "title": "周日晚上，我的灵魂已经提前在工位坐牢",
                        "content": "至少今晚还能再瘫两小时，也算最后的狂欢。",
                        "visibility": "公开可见",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = check_xhs_publish_status(
        artifact_path=artifact_path,
        publisher=FakeFallbackPublisher(
            fallback_result={
                "post_id": "note-123",
                "post_url": "https://www.xiaohongshu.com/explore/note-123",
                "source": "mcp_search",
            }
        ),
    )

    assert result["status"] == "published_search_verified"
    assert result["post_id"] == "note-123"
    assert result["source"] == "mcp_search"


def test_check_xhs_publish_status_retries_public_search_fallback(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                    "platform_payload": {
                        "title": "周六晚上十点半，我的周末结束了",
                        "content": "至少今晚还能再瘫两小时，也算最后的狂欢。",
                        "visibility": "公开可见",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    publisher = SequencedFallbackPublisher(
        None,
        {
            "post_id": "note-456",
            "post_url": "https://www.xiaohongshu.com/explore/note-456",
            "source": "mcp_search",
        },
    )
    sleeps: list[float] = []

    result = check_xhs_publish_status(
        artifact_path=artifact_path,
        publisher=publisher,
        search_retry_attempts=2,
        search_retry_interval_seconds=1.5,
        sleep=lambda seconds: sleeps.append(seconds),
    )

    assert result["status"] == "published_search_verified"
    assert result["post_id"] == "note-456"
    assert publisher.calls == 2
    assert sleeps == [1.5]


def test_check_xhs_publish_status_reports_private_visibility_blocker(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "publish_result": {
                    "status": "published",
                    "platform_payload": {
                        "title": "周日晚上，我的灵魂已经提前在工位坐牢",
                        "content": "至少今晚还能再瘫两小时，也算最后的狂欢。",
                        "visibility": "仅自己可见",
                    },
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = check_xhs_publish_status(
        artifact_path=artifact_path,
        publisher=FakeFallbackPublisher(fallback_result=None),
    )

    assert result["status"] == "manual_check_required"
    assert result["reason_code"] == "private_missing_identifiers"
    assert "仅自己可见" in result["reason"]
