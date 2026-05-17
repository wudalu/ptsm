from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

from ptsm.config.settings import Settings, get_settings
from ptsm.domain.xhs_patterns import normalize_xhs_sample, XhsSample
from topic_radar.mcp_client import McpClient, _clean_error
from topic_radar.platforms.xiaohongshu import FeedItem, XiaohongshuPlatform


DEFAULT_PATTERN_LIBRARY_DIR = Path("outputs") / "artifacts" / "xhs-pattern-library"


def run_collect_xhs_patterns(
    *,
    lane: str,
    keywords: Sequence[str] | str,
    sample_limit_per_keyword: int = 8,
    output_dir: Path | str = DEFAULT_PATTERN_LIBRARY_DIR,
    dry_run: bool = False,
    delay_seconds: float = 1.0,
    settings: Settings | None = None,
    xhs_platform: Any | None = None,
    collected_at: str | None = None,
) -> dict[str, Any]:
    keyword_list = _normalize_keywords(keywords)
    collected_at = collected_at or datetime.now(timezone.utc).isoformat()
    output_path = _artifact_path(Path(output_dir), collected_at)
    if dry_run and xhs_platform is None:
        result = _build_result(
            status="dry_run",
            lane=lane,
            keywords=keyword_list,
            sample_limit_per_keyword=sample_limit_per_keyword,
            collected_at=collected_at,
            samples=[],
            keyword_errors={},
            artifact_path=output_path,
        )
        _write_artifact(result, output_path)
        return result

    settings = settings or get_settings()
    platform = xhs_platform or XiaohongshuPlatform(
        McpClient(xhs_server_url=settings.xhs_mcp_server_url)
    )
    result = asyncio.run(
        _collect_async(
            platform=platform,
            lane=lane,
            keywords=keyword_list,
            sample_limit_per_keyword=sample_limit_per_keyword,
            output_path=output_path,
            collected_at=collected_at,
            delay_seconds=delay_seconds,
        )
    )
    return result


async def _collect_async(
    *,
    platform: Any,
    lane: str,
    keywords: list[str],
    sample_limit_per_keyword: int,
    output_path: Path,
    collected_at: str,
    delay_seconds: float,
) -> dict[str, Any]:
    samples: list[XhsSample] = []
    keyword_errors: dict[str, str] = {}
    if not keywords:
        result = _build_result(
            status="empty",
            lane=lane,
            keywords=[],
            sample_limit_per_keyword=sample_limit_per_keyword,
            collected_at=collected_at,
            samples=[],
            keyword_errors={},
            artifact_path=output_path,
        )
        _write_artifact(result, output_path)
        return result

    check_login = getattr(platform, "check_login", None)
    if callable(check_login):
        try:
            is_logged_in, _qr = await check_login()
        except Exception as exc:
            is_logged_in = False
            keyword_errors["_login"] = _clean_error(exc)
        if not is_logged_in:
            result = _build_result(
                status="login_required",
                lane=lane,
                keywords=keywords,
                sample_limit_per_keyword=sample_limit_per_keyword,
                collected_at=collected_at,
                samples=[],
                keyword_errors=keyword_errors or {"_login": "login required"},
                artifact_path=output_path,
            )
            _write_artifact(result, output_path)
            return result

    for index, keyword in enumerate(keywords):
        try:
            feeds = await platform.search_feeds(keyword, limit=sample_limit_per_keyword)
            for feed in feeds:
                samples.append(
                    normalize_xhs_sample(
                        _feed_to_row(feed=feed, keyword=keyword),
                        lane=lane,
                        collected_at=collected_at,
                    )
                )
        except Exception as exc:
            keyword_errors[keyword] = _clean_error(exc)
        result = _build_result(
            status=_status_for(samples=samples, keyword_errors=keyword_errors),
            lane=lane,
            keywords=keywords,
            sample_limit_per_keyword=sample_limit_per_keyword,
            collected_at=collected_at,
            samples=samples,
            keyword_errors=keyword_errors,
            artifact_path=output_path,
        )
        _write_artifact(result, output_path)
        if delay_seconds > 0 and index < len(keywords) - 1:
            await asyncio.sleep(delay_seconds)
    return result


def _feed_to_row(*, feed: FeedItem, keyword: str) -> dict[str, Any]:
    return {
        "sample_id": feed.feed_id,
        "feed_id": feed.feed_id,
        "xsec_token": feed.xsec_token,
        "keyword": keyword,
        "title": feed.title,
        "author": feed.author,
        "likes": feed.likes,
        "comments": feed.comments,
        "shares": feed.shares,
        "collects": feed.collects,
        "cover_width": feed.cover_width,
        "cover_height": feed.cover_height,
        "has_cover_url": feed.has_cover_url,
    }


def _build_result(
    *,
    status: str,
    lane: str,
    keywords: list[str],
    sample_limit_per_keyword: int,
    collected_at: str,
    samples: list[XhsSample],
    keyword_errors: dict[str, str],
    artifact_path: Path,
) -> dict[str, Any]:
    successful_keywords = _successful_keywords(samples)
    failed_keywords = list(keyword_errors)
    payload = {
        "status": status,
        "lane": lane,
        "collected_at": collected_at,
        "artifact_path": str(artifact_path),
        "collection_metadata": {
            "keyword_count": len(keywords),
            "keywords": keywords,
            "successful_keywords": successful_keywords,
            "failed_keywords": failed_keywords,
            "sample_limit_per_keyword": sample_limit_per_keyword,
            "live_source": "xiaohongshu-mcp",
            "collected_at": collected_at,
            "lane": lane,
        },
        "samples": [sample.to_dict() for sample in samples],
        "keyword_errors": dict(keyword_errors),
    }
    return payload


def _write_artifact(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def _status_for(*, samples: list[XhsSample], keyword_errors: dict[str, str]) -> str:
    if keyword_errors and samples:
        return "partial"
    if keyword_errors:
        return "error"
    if samples:
        return "completed"
    return "empty"


def _successful_keywords(samples: list[XhsSample]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for sample in samples:
        if sample.keyword in seen:
            continue
        seen.add(sample.keyword)
        ordered.append(sample.keyword)
    return ordered


def _normalize_keywords(keywords: Sequence[str] | str) -> list[str]:
    if isinstance(keywords, str):
        raw = keywords.split(",")
    else:
        raw = keywords
    return [str(keyword).strip() for keyword in raw if str(keyword).strip()]


def _artifact_path(output_dir: Path, collected_at: str) -> Path:
    day = collected_at[:10] if collected_at else "undated"
    return output_dir / f"samples-{day}.json"
