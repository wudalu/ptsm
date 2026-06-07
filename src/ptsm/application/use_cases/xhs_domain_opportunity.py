from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

from ptsm.config.settings import Settings, get_settings
from topic_radar.mcp_client import McpClient, _clean_error
from topic_radar.platforms.xiaohongshu import FeedItem, XiaohongshuPlatform


DEFAULT_DOMAIN_OPPORTUNITY_DIR = (
    Path("outputs") / "artifacts" / "xhs-domain-opportunity"
)
SCORE_FORMULA = "likes + comments * 4 + collects * 2 + shares * 6"


@dataclass(frozen=True)
class DomainMapping:
    domain: str
    keywords: tuple[str, ...]
    current_playbook_fit: tuple[str, ...]
    recommendation: str
    opportunity_tier: str
    new_domain_candidate: bool = False


DOMAIN_MAPPINGS: tuple[DomainMapping, ...] = (
    DomainMapping(
        domain="轻养生 / 睡眠恢复 / 办公室恢复",
        keywords=("睡眠", "轻养生", "恢复", "办公室健康", "熬夜", "睡前"),
        current_playbook_fit=(
            "modern_psychology_post",
            "human_enrichment_daily_post",
        ),
        recommendation="new_domain_candidate",
        opportunity_tier="act_now",
        new_domain_candidate=True,
    ),
    DomainMapping(
        domain="人类丰容 / 修复系手作",
        keywords=("人类丰容", "丰容", "手作", "修复", "低成本改造", "钩织", "拼豆"),
        current_playbook_fit=("human_enrichment_daily_post",),
        recommendation="sublane_first",
        opportunity_tier="invest_as_sublane",
    ),
    DomainMapping(
        domain="古诗词金句 / 文博非遗 / 地方文化体验",
        keywords=("古诗词", "诗词金句", "经典诗句", "苏轼", "东坡", "文博", "非遗", "地方文化", "博物馆"),
        current_playbook_fit=(
            "classic_poetry_quote_post",
            "human_enrichment_daily_post",
        ),
        recommendation="sublane_first",
        opportunity_tier="invest_as_sublane",
    ),
    DomainMapping(
        domain="AI 工作流 / 普通人用 AI",
        keywords=("AI", "ai", "普通人用AI", "工具", "大模型", "工作流"),
        current_playbook_fit=("ai_tech_daily_post",),
        recommendation="improve_workflow_specificity",
        opportunity_tier="invest_as_sublane",
    ),
    DomainMapping(
        domain="每日英语 / 跟读例句",
        keywords=("每日英语", "英语", "单词", "跟读", "例句"),
        current_playbook_fit=("daily_english_post",),
        recommendation="keep_improving",
        opportunity_tier="keep_and_optimize",
    ),
    DomainMapping(
        domain="世界杯 / 看球专项",
        keywords=("世界杯", "看球", "球迷", "美加墨"),
        current_playbook_fit=("world_cup_daily_post",),
        recommendation="short_term_calendar",
        opportunity_tier="act_now_event",
    ),
    DomainMapping(
        domain="宠物户外 / 宠物友好路线",
        keywords=("宠物", "猫", "狗", "宠物户外", "宠物友好"),
        current_playbook_fit=(),
        recommendation="later_with_real_assets",
        opportunity_tier="track_later",
    ),
    DomainMapping(
        domain="武侠人物深度评述",
        keywords=("武侠", "金庸", "古龙", "江湖"),
        current_playbook_fit=("wuxia_character_post",),
        recommendation="keep_niche",
        opportunity_tier="keep_niche",
    ),
)


def run_xhs_domain_opportunity(
    *,
    keywords: Sequence[str] | str,
    lane: str = "xhs_domain_opportunity",
    sample_limit_per_keyword: int = 5,
    output_dir: Path | str = DEFAULT_DOMAIN_OPPORTUNITY_DIR,
    xhs_platform: Any | None = None,
    delay_seconds: float = 0.8,
    collected_at: str | None = None,
    settings: Settings | None = None,
    skip_login_check: bool = False,
    tool_timeout_seconds: float | None = None,
) -> dict[str, Any]:
    keyword_list = _normalize_keywords(keywords)
    collected_at = collected_at or datetime.now(timezone.utc).isoformat()
    output_path = _artifact_path(Path(output_dir), collected_at)

    settings = settings or get_settings()
    platform = xhs_platform or XiaohongshuPlatform(
        McpClient(xhs_server_url=settings.xhs_mcp_server_url)
    )

    result = asyncio.run(
        _scan_async(
            platform=platform,
            keywords=keyword_list,
            lane=lane,
            sample_limit_per_keyword=sample_limit_per_keyword,
            output_path=output_path,
            collected_at=collected_at,
            delay_seconds=delay_seconds,
            skip_login_check=skip_login_check,
            tool_timeout_seconds=tool_timeout_seconds,
        )
    )
    return result


async def _scan_async(
    *,
    platform: Any,
    keywords: list[str],
    lane: str,
    sample_limit_per_keyword: int,
    output_path: Path,
    collected_at: str,
    delay_seconds: float,
    skip_login_check: bool,
    tool_timeout_seconds: float | None,
) -> dict[str, Any]:
    keyword_rows: list[dict[str, Any]] = []
    keyword_errors: dict[str, str] = {}

    check_login = getattr(platform, "check_login", None)
    if callable(check_login) and not skip_login_check:
        try:
            is_logged_in, _qr = await check_login()
        except Exception as exc:
            is_logged_in = False
            keyword_errors["_login"] = _clean_error(exc)
        if not is_logged_in:
            result = _build_result(
                status="login_required",
                lane=lane,
                collected_at=collected_at,
                keywords=[],
                recommendations=[],
                keyword_errors=keyword_errors or {"_login": "login required"},
                artifact_path=output_path,
            sample_limit_per_keyword=sample_limit_per_keyword,
            skip_login_check=skip_login_check,
            tool_timeout_seconds=tool_timeout_seconds,
        )
            _write_artifacts(result, output_path)
            return result

    for index, keyword in enumerate(keywords):
        try:
            feeds = await _search_feeds(
                platform=platform,
                keyword=keyword,
                limit=sample_limit_per_keyword,
                timeout_seconds=tool_timeout_seconds,
            )
            keyword_rows.append(_keyword_summary(keyword=keyword, feeds=feeds))
        except Exception as exc:
            keyword_errors[keyword] = _clean_error(exc)
            keyword_rows.append(_keyword_summary(keyword=keyword, feeds=[]))
        if delay_seconds > 0 and index < len(keywords) - 1:
            await asyncio.sleep(delay_seconds)

    keyword_rows.sort(key=lambda row: row["top_score"], reverse=True)
    result = _build_result(
        status=_status_for(keyword_rows=keyword_rows, keyword_errors=keyword_errors),
        lane=lane,
        collected_at=collected_at,
        keywords=keyword_rows,
        recommendations=_recommendations(keyword_rows),
        keyword_errors=keyword_errors,
        artifact_path=output_path,
        sample_limit_per_keyword=sample_limit_per_keyword,
        skip_login_check=skip_login_check,
        tool_timeout_seconds=tool_timeout_seconds,
    )
    _write_artifacts(result, output_path)
    return result


def _keyword_summary(*, keyword: str, feeds: Sequence[FeedItem]) -> dict[str, Any]:
    mapping = _mapping_for(keyword)
    samples = [_sample_summary(feed) for feed in feeds]
    samples.sort(key=lambda row: row["engagement_score"], reverse=True)
    top_score = samples[0]["engagement_score"] if samples else 0
    return {
        "keyword": keyword,
        "domain": mapping.domain,
        "sample_count": len(samples),
        "top_score": top_score,
        "top_samples": samples[:3],
        "current_playbook_fit": list(mapping.current_playbook_fit),
        "recommendation": mapping.recommendation,
        "opportunity_tier": mapping.opportunity_tier,
        "new_domain_candidate": mapping.new_domain_candidate,
    }


def _sample_summary(feed: FeedItem) -> dict[str, Any]:
    return {
        "title": feed.title,
        "author": feed.author,
        "likes": feed.likes,
        "comments": feed.comments,
        "collects": feed.collects,
        "shares": feed.shares,
        "engagement_score": feed.engagement_score,
        "feed_id": feed.feed_id,
        "xsec_token": feed.xsec_token,
    }


def _recommendations(keyword_rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    for row in keyword_rows:
        domain = str(row["domain"])
        current = by_domain.get(domain)
        if current is None:
            by_domain[domain] = {
                "domain": domain,
                "recommendation": row["recommendation"],
                "opportunity_tier": row["opportunity_tier"],
                "new_domain_candidate": row["new_domain_candidate"],
                "current_playbook_fit": row["current_playbook_fit"],
                "keywords": [row["keyword"]],
                "top_score": row["top_score"],
                "strongest_title": _strongest_title(row),
            }
            continue
        current["keywords"].append(row["keyword"])
        if row["top_score"] > current["top_score"]:
            current["top_score"] = row["top_score"]
            current["strongest_title"] = _strongest_title(row)

    return sorted(
        by_domain.values(),
        key=lambda row: (_tier_rank(str(row["opportunity_tier"])), -int(row["top_score"])),
    )


def _strongest_title(row: dict[str, Any]) -> str | None:
    samples = row.get("top_samples")
    if not isinstance(samples, list) or not samples:
        return None
    first = samples[0]
    if not isinstance(first, dict):
        return None
    title = first.get("title")
    return str(title) if title else None


async def _search_feeds(
    *,
    platform: Any,
    keyword: str,
    limit: int,
    timeout_seconds: float | None,
) -> Sequence[FeedItem]:
    if timeout_seconds is None:
        return await platform.search_feeds(keyword, limit=limit)
    try:
        return await platform.search_feeds(keyword, limit=limit, timeout=timeout_seconds)
    except TypeError as exc:
        if "timeout" not in str(exc):
            raise
        return await platform.search_feeds(keyword, limit=limit)


def _build_result(
    *,
    status: str,
    lane: str,
    collected_at: str,
    keywords: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    keyword_errors: dict[str, str],
    artifact_path: Path,
    sample_limit_per_keyword: int,
    skip_login_check: bool,
    tool_timeout_seconds: float | None,
) -> dict[str, Any]:
    markdown_path = _markdown_path_for(artifact_path)
    return {
        "status": status,
        "lane": lane,
        "collected_at": collected_at,
        "artifact_path": str(artifact_path),
        "markdown_path": str(markdown_path),
        "keywords": keywords,
        "recommendations": recommendations,
        "keyword_errors": dict(keyword_errors),
        "methodology": {
            "sample_level": "search_feeds",
            "score_formula": SCORE_FORMULA,
            "sample_limit_per_keyword": sample_limit_per_keyword,
            "mapping": "deterministic_keyword_family_to_playbook_fit",
        },
        "source": {
            "platform": "xiaohongshu",
            "live_source": "xiaohongshu-mcp.search_feeds",
            "login_check_skipped": skip_login_check,
            "tool_timeout_seconds": tool_timeout_seconds,
        },
    }


def _mapping_for(keyword: str) -> DomainMapping:
    normalized = keyword.lower()
    for mapping in DOMAIN_MAPPINGS:
        if any(item.lower() in normalized for item in mapping.keywords):
            return mapping
    return DomainMapping(
        domain="未归类候选主题",
        keywords=(),
        current_playbook_fit=(),
        recommendation="track_manually",
        opportunity_tier="track_later",
    )


def _tier_rank(tier: str) -> int:
    order = {
        "act_now": 0,
        "act_now_event": 1,
        "invest_as_sublane": 2,
        "keep_and_optimize": 3,
        "track_later": 4,
        "keep_niche": 5,
    }
    return order.get(tier, 99)


def _status_for(
    *,
    keyword_rows: Sequence[dict[str, Any]],
    keyword_errors: dict[str, str],
) -> str:
    has_samples = any(row["sample_count"] for row in keyword_rows)
    if keyword_errors and has_samples:
        return "partial"
    if keyword_errors:
        return "error"
    if has_samples:
        return "completed"
    return "empty"


def _write_artifacts(result: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(str(result["markdown_path"])).write_text(
        _format_markdown(result),
        encoding="utf-8",
    )


def _format_markdown(result: dict[str, Any]) -> str:
    lines = [
        f"# XHS Domain Opportunity Brief - {str(result['collected_at'])[:10]}",
        "",
        "## Top Domains",
    ]
    for index, recommendation in enumerate(result["recommendations"], start=1):
        title = recommendation.get("strongest_title") or "(no title sample)"
        lines.append(
            f"{index}. {recommendation['domain']} - score {recommendation['top_score']}: {title}"
        )

    lines.extend(["", "## Existing Playbook Fit"])
    for row in result["keywords"]:
        fit = row["current_playbook_fit"] or ["(none)"]
        lines.append(f"- {row['keyword']}: {', '.join(fit)}")

    lines.extend(["", "## New Domain Candidates"])
    candidates = [
        row for row in result["keywords"] if row.get("new_domain_candidate")
    ]
    if candidates:
        for row in candidates:
            lines.append(
                f"- {row['domain']}: {row['recommendation']} ({row['opportunity_tier']})"
            )
    else:
        lines.append("- None in this scan.")

    lines.extend(
        [
            "",
            "## Workflow Notes",
            f"- Sample level: {result['methodology']['sample_level']}",
            f"- Score formula: {result['methodology']['score_formula']}",
            "- This brief is search-level evidence. Use note teardown or pattern analysis before treating it as full content-quality proof.",
            "- Ordinary guide-post and run-playbook flows should continue using local topic packs and pattern snapshots by default.",
        ]
    )
    if result["keyword_errors"]:
        lines.append(f"- Keyword errors: {', '.join(result['keyword_errors'])}")
    return "\n".join(lines) + "\n"


def _normalize_keywords(keywords: Sequence[str] | str) -> list[str]:
    if isinstance(keywords, str):
        raw = keywords.split(",")
    else:
        raw = keywords
    return [str(keyword).strip() for keyword in raw if str(keyword).strip()]


def _artifact_path(output_dir: Path, collected_at: str) -> Path:
    day = collected_at[:10] if collected_at else "undated"
    return output_dir / f"domain-opportunity-{day}.json"


def _markdown_path_for(artifact_path: Path) -> Path:
    return artifact_path.with_suffix(".md")
