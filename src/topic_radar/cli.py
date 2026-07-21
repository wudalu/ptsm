"""Topic Radar CLI — multi-platform discussion-worthy topic research."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
import inspect
import math
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

from topic_radar.config import get_config
from topic_radar.mcp_client import McpClient
from topic_radar.platforms.xiaohongshu import XiaohongshuPlatform, PlatformUnavailable
from topic_radar.platforms.weibo import (
    WeiboPlatform, DouyinPlatform, ZhihuPlatform, BilibiliPlatform,
    ToutiaoPlatform, DoubanPlatform, SspaiPlatform, TrendingItem,
)
from topic_radar.analysis.note_teardown import teardown
from topic_radar.analysis.cross_platform import (
    discover_cross_platform_from_clusters,
    discover_verticals,
)
from topic_radar.analysis.evidence import (
    SUPPORTED_PLATFORMS,
    EvidenceRecord,
    ScanQuality,
    TopicCluster,
    append_topic_history,
    canonicalize_platforms,
    canonicalize_trending_items,
    cluster_evidence,
    determine_scan_quality,
    find_clusters_for_titles,
    read_recent_topic_history,
    select_recommended_angles,
)
from topic_radar.analysis.llm_analyzer import LLMAnalyzer, validate_llm_output_evidence
from topic_radar.output.artifacts import (
    TopicScanResult,
    _flatten_trending,
    build_scan_result,
)
from topic_radar.output.report import generate_report
from datetime import date


@dataclass(frozen=True)
class ScanOptions:
    """Optional quality controls for the public scan API.

    Defaults retain existing call sites while allowing operators and PTSM's
    explicit fresh-research path to cap results or tune a bounded novelty
    window without importing internal implementation details.
    """

    max_recommendations: int = 6
    history_days: int = 14
    event_similarity_threshold: float = 0.58


def _convert_llm_output(
    llm_output,
    trending_items: dict[str, list[TrendingItem]],
    scan_date: str,
    *,
    errors: dict[str, str] | None = None,
    scan_quality: ScanQuality | str = ScanQuality.COMPLETED,
    evidence: list[EvidenceRecord] | None = None,
    topic_clusters: list[dict] | None = None,
    cross_signals: list[Any] | None = None,
) -> TopicScanResult:
    """Convert LLM analysis output to TopicScanResult format."""
    from topic_radar.analysis.cross_platform import CrossPlatformSignal, DiscoveredVertical

    verticals = [
        DiscoveredVertical(
            name=v.name,
            keywords=v.keywords,
            confidence=v.confidence,
            heat_signals=_compute_heat(trending_items, v),
            discussion_density=v.discussion_density,
            sample_topics=v.sample_topics,
            suggested_angles=v.suggested_angles,
            comment_themes=v.comment_themes,
        )
        for v in llm_output.discovered_verticals
    ]

    llm_cross_signals = [
        CrossPlatformSignal(
            topic=s.topic,
            platforms=s.platforms,
            # The LLM receives a single scan, not an ordered observation
            # history. Never reinterpret its platform list as first-seen data.
            first_seen_platform="",
            # An LLM has no time-series observations beyond this scan, so its
            # requested velocity label must not become an artifact claim.
            velocity="unknown",
        )
        for s in llm_output.cross_platform_signals
    ]

    patterns = [{
        "top_hook_types": ["(LLM分析)"],
        "top_engagement_triggers": [a.why for a in llm_output.recommended_angles[:3]],
        "teardown_count": 0,
        "avg_hook_confidence": 0,
    }]

    angles = [
        {
            "vertical": a.vertical,
            "angle": a.angle,
            "why_discussion_likely": a.why,
            "cluster_id": a.cluster_id,
            "evidence_ids": list(a.evidence_ids),
            "confidence": next(
                (v.confidence for v in llm_output.discovered_verticals if v.name == a.vertical), 0.5
            ),
        }
        for a in llm_output.recommended_angles
    ]

    return TopicScanResult(
        scan_date=scan_date,
        platforms=sorted(trending_items),
        discovered_verticals=verticals,
        cross_platform_signals=cross_signals if cross_signals is not None else llm_cross_signals,
        high_engagement_patterns=patterns,
        recommended_angles=angles,
        raw_trending=_flatten_trending(trending_items),
        platform_errors=errors or {},
        analysis_method="llm",
        scan_summary=llm_output.scan_summary,
        noise_topics=llm_output.noise_topics,
        scan_quality=scan_quality,
        evidence=[asdict(record) for record in evidence or []],
        topic_clusters=topic_clusters or [],
    )


def _compute_heat(
    trending: dict[str, list[TrendingItem]], vertical
) -> dict[str, float]:
    """Estimate per-platform heat for a vertical from its sample topics."""
    heat: dict[str, float] = {}
    sample_set = set(vertical.sample_topics)
    for platform, items in trending.items():
        matched = [i for i in items if i.title in sample_set]
        if matched:
            heat[platform] = round(sum(i.hot_score for i in matched) / len(matched), 1)
    return heat


async def run_scan(
    platforms: str | None = None,
    keywords: str | None = None,
    output_dir: str | None = None,
    *,
    options: ScanOptions | None = None,
) -> TopicScanResult:
    """Programmatic entry point: scan and return TopicScanResult.

    This is the reusable core used by both the CLI and PTSM integration.
    """
    config = get_config()
    scan_options = _normalize_scan_options(options)
    platforms_str = config.default_platforms if platforms is None else platforms
    requested_platforms = canonicalize_platforms(platforms_str)
    platform_list = [p for p in requested_platforms if p in SUPPORTED_PLATFORMS]
    output_dir = output_dir or config.output_dir
    errors: dict[str, str] = {}
    for platform in requested_platforms:
        if platform not in SUPPORTED_PLATFORMS:
            errors[platform] = "unsupported platform"
    all_trending: dict[str, list[TrendingItem]] = {}

    if not requested_platforms:
        errors["platform_request"] = "no platforms requested"
        return _write_insufficient_evidence_result(
            scan_date=date.today().isoformat(),
            output_dir=output_dir,
            errors=errors,
        )

    client = McpClient(
        xhs_server_url=config.xhs_mcp_server_url,
        enable_trends_hub=any(
            p in {"weibo", "douyin", "zhihu", "bilibili", "toutiao", "douban", "sspai"}
            for p in platform_list
        ),
    )

    # Scan each platform
    if "xiaohongshu" in platform_list:
        await _scan_xiaohongshu(client, config, keywords, all_trending, errors)

    if "weibo" in platform_list:
        await _scan_weibo(client, config, all_trending, errors)

    if "douyin" in platform_list:
        await _scan_douyin(client, config, all_trending, errors)

    for platform_name, platform_cls, display_name in [
        ("zhihu", ZhihuPlatform, "zhihu"),
        ("bilibili", BilibiliPlatform, "bilibili"),
        ("toutiao", ToutiaoPlatform, "toutiao"),
        ("douban", DoubanPlatform, "douban"),
        ("sspai", SspaiPlatform, "sspai"),
    ]:
        if platform_name not in platform_list:
            continue
        await _scan_trends_hub_platform(
            client, config, platform_cls, platform_name, display_name, all_trending, errors
        )

    all_trending, evidence = canonicalize_trending_items(all_trending)
    evidence, clusters = cluster_evidence(
        evidence,
        similarity_threshold=scan_options.event_similarity_threshold,
    )
    cluster_rows = [asdict(cluster) for cluster in clusters]
    for platform in platform_list:
        if platform not in all_trending and platform not in errors:
            errors[platform] = "no valid evidence collected"

    scan_date = date.today().isoformat()
    scan_quality = determine_scan_quality(all_trending, errors, requested_platforms)
    if scan_quality is ScanQuality.INSUFFICIENT_EVIDENCE:
        return _write_insufficient_evidence_result(
            scan_date=scan_date,
            output_dir=output_dir,
            errors=errors,
            platforms=sorted(all_trending),
            evidence=evidence,
        )

    # Analyze: LLM first, rules fallback
    analyzer = LLMAnalyzer(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )
    llm_output, method = _analyze_with_evidence(
        analyzer,
        all_trending,
        scan_date,
        evidence=evidence,
        topic_clusters=clusters,
    )
    llm_error = _safe_llm_error(getattr(analyzer, "last_error", ""))
    if llm_error:
        errors["llm_analysis"] = llm_error
        scan_quality = determine_scan_quality(all_trending, errors, requested_platforms)

    validated_llm_output = (
        validate_llm_output_evidence(
            llm_output,
            evidence,
            clusters,
            raw_provenance=_flatten_trending(all_trending),
        )
        if llm_output is not None
        else None
    )
    # A source-backed vertical alone is useful diagnostic metadata, but it
    # cannot fill the public recommendation list.  Fall back to deterministic
    # rules whenever no evidence-backed angle survives validation.
    if method == "llm" and (
        validated_llm_output is None or not validated_llm_output.recommended_angles
    ):
        llm_output = None
        errors["llm_analysis"] = "LLM output had no verifiable recommendations; rules fallback used"
        scan_quality = determine_scan_quality(all_trending, errors, requested_platforms)
    else:
        llm_output = validated_llm_output

    cross_signals = discover_cross_platform_from_clusters(clusters)
    if llm_output is not None:
        result = _convert_llm_output(
            llm_output,
            all_trending,
            scan_date,
            errors=errors,
            scan_quality=scan_quality,
            evidence=evidence,
            topic_clusters=cluster_rows,
            cross_signals=cross_signals,
        )
    else:
        flat_items = [item for items in all_trending.values() for item in items]
        verticals = discover_verticals(flat_items)
        result = build_scan_result(
            trending_items=all_trending,
            verticals=verticals,
            cross_signals=cross_signals,
            errors=errors,
            scan_quality=scan_quality,
            evidence=evidence,
            topic_clusters=cluster_rows,
            requested_platforms=requested_platforms,
        )

    history = read_recent_topic_history(
        output_dir,
        scan_date,
        history_days=scan_options.history_days,
    )
    result.recommended_angles = select_recommended_angles(
        _attach_angle_cluster_support(result.recommended_angles, evidence, clusters),
        clusters,
        max_recommendations=scan_options.max_recommendations,
        history_records=history,
        scan_date=scan_date,
        history_days=scan_options.history_days,
    )

    # Write artifacts
    result.write(output_dir)
    generate_report(result, output_dir)
    append_topic_history(output_dir, scan_date, result.recommended_angles)

    return result


def _write_insufficient_evidence_result(
    *,
    scan_date: str,
    output_dir: str,
    errors: dict[str, str],
    platforms: list[str] | None = None,
    evidence: list[EvidenceRecord] | None = None,
) -> TopicScanResult:
    """Persist a diagnostic artifact without attempting analysis."""
    result = TopicScanResult(
        scan_date=scan_date,
        platforms=platforms or [],
        platform_errors=errors,
        scan_quality=ScanQuality.INSUFFICIENT_EVIDENCE,
        evidence=[asdict(record) for record in evidence or []],
        topic_clusters=[],
    )
    result.write(output_dir)
    generate_report(result, output_dir)
    return result


def _safe_llm_error(detail: object) -> str:
    """Keep artifact diagnostics useful without serializing provider error text."""
    if not isinstance(detail, str) or not detail:
        return ""
    match = re.fullmatch(
        r"LLM analysis failed \(([A-Za-z_][A-Za-z0-9_]*)\); rules fallback used",
        detail,
    )
    safe_exception_types = {
        "APIConnectionError",
        "APIError",
        "AuthenticationError",
        "BadRequestError",
        "ConnectionError",
        "Exception",
        "JSONDecodeError",
        "KeyError",
        "OSError",
        "RateLimitError",
        "RuntimeError",
        "TimeoutError",
        "TypeError",
        "ValidationError",
        "ValueError",
    }
    if match and match.group(1) in safe_exception_types:
        return detail
    return "LLM analysis failed; rules fallback used"


def _normalize_scan_options(options: ScanOptions | None) -> ScanOptions:
    """Keep optional scan controls bounded and deterministic at the API edge."""
    source = options or ScanOptions()
    return ScanOptions(
        max_recommendations=max(0, int(source.max_recommendations)),
        history_days=max(0, int(source.history_days)),
        event_similarity_threshold=min(
            max(float(source.event_similarity_threshold), 0.0),
            1.0,
        ),
    )


def _analyze_with_evidence(
    analyzer: LLMAnalyzer,
    trending_items: dict[str, list[TrendingItem]],
    scan_date: str,
    *,
    evidence: Sequence[EvidenceRecord],
    topic_clusters: Sequence[TopicCluster],
):
    """Call evidence-aware analyzers while keeping older adapters callable."""
    parameters = inspect.signature(analyzer.analyze).parameters.values()
    supports_keywords = any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters
    ) or {"evidence", "topic_clusters"}.issubset(
        inspect.signature(analyzer.analyze).parameters
    )
    if supports_keywords:
        return analyzer.analyze(
            trending_items,
            scan_date,
            evidence=evidence,
            topic_clusters=topic_clusters,
        )
    return analyzer.analyze(trending_items, scan_date)


def _attach_angle_cluster_support(
    candidates: Sequence[Mapping[str, Any]],
    evidence: Sequence[EvidenceRecord],
    clusters: Sequence[TopicCluster],
) -> list[dict[str, Any]]:
    """Map rules candidates to their strongest sampled event without guessing.

    Rule-based verticals retain their sample titles.  When several evidence
    clusters belong to one vertical, the highest scored cluster is chosen for a
    given generic angle; MMR then prevents that event from taking another slot.
    """
    resolved: list[dict[str, Any]] = []
    known_clusters = {cluster.cluster_id for cluster in clusters}
    for candidate in candidates:
        item = dict(candidate)
        if item.get("cluster_id") not in known_clusters:
            titles = item.get("sample_topics")
            matches = find_clusters_for_titles(
                titles if isinstance(titles, list) else [],
                evidence,
                clusters,
            )
            if matches:
                cluster = matches[0]
                item["cluster_id"] = cluster.cluster_id
                item["evidence_ids"] = list(cluster.evidence_ids)
        item.pop("sample_topics", None)
        resolved.append(item)
    return resolved


async def _scan_xiaohongshu(
    client: McpClient,
    config,
    keywords: str | None,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    xhs = XiaohongshuPlatform(client)
    try:
        is_logged_in, qr_data = await xhs.check_login()
    except Exception as exc:
        errors["xiaohongshu"] = _collection_error(exc)
        return

    if not is_logged_in:
        errors["xiaohongshu"] = "login required; run ptsm xhs-login-qrcode"
        return

    keywords_list = re.split(r"[,，]", keywords or "") if keywords else []
    kws = [kw.strip() for kw in keywords_list if kw.strip()] or ["打工人", "治愈"]
    xhs_items: list[TrendingItem] = []
    keyword_failures: list[str] = []
    successful_searches = 0
    per_keyword_limit = max(1, math.ceil(config.scan_sample_limit / len(kws)))
    for kw in kws:
        try:
            feeds = await xhs.search_feeds(kw, limit=per_keyword_limit)
        except Exception as exc:
            keyword_failures.append(f"{kw} ({type(exc).__name__})")
            continue

        successful_searches += 1
        for feed in feeds:
            url = (
                f"https://www.xiaohongshu.com/explore/{feed.feed_id}"
                if feed.feed_id
                else ""
            )
            xhs_items.append(
                TrendingItem(
                    rank=len(xhs_items) + 1,
                    title=feed.title,
                    hot_score=feed.engagement_score,
                    url=url,
                    platform="xiaohongshu",
                    metadata={
                        "feed_id": feed.feed_id,
                        "xsec_token": feed.xsec_token,
                        "author": feed.author,
                        "likes": feed.likes,
                        "comments": feed.comments,
                        "collects": feed.collects,
                        "shares": feed.shares,
                        "keyword": kw,
                        "cover_width": feed.cover_width,
                        "cover_height": feed.cover_height,
                        "has_cover_url": feed.has_cover_url,
                    },
                )
            )

    if xhs_items:
        _store_collected_items(
            "xiaohongshu",
            xhs_items,
            all_trending,
            errors,
            empty_error="no search results returned for requested keywords",
        )
        if keyword_failures:
            errors["xiaohongshu"] = (
                "partial keyword search failure: " + ", ".join(keyword_failures)
            )
        return

    if keyword_failures:
        if successful_searches:
            errors["xiaohongshu"] = (
                "no search results; keyword search failures: "
                + ", ".join(keyword_failures)
            )
        else:
            errors["xiaohongshu"] = "all keyword searches failed: " + ", ".join(keyword_failures)
        return

    errors["xiaohongshu"] = "no search results returned for requested keywords"


async def _scan_weibo(
    client: McpClient,
    config,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    weibo = WeiboPlatform(client)
    try:
        items = await weibo.get_trending(limit=config.scan_sample_limit)
    except Exception as exc:
        errors["weibo"] = _collection_error(exc)
        return
    _store_collected_items("weibo", items, all_trending, errors)


async def _scan_douyin(
    client: McpClient,
    config,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    douyin = DouyinPlatform(client)
    try:
        items = await douyin.get_trending(limit=config.scan_sample_limit)
    except Exception as exc:
        errors["douyin"] = _collection_error(exc)
        return
    _store_collected_items("douyin", items, all_trending, errors)


async def _scan_trends_hub_platform(
    client: McpClient,
    config,
    platform_cls,
    platform_name: str,
    display_name: str,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    p = platform_cls(client)
    try:
        items = await p.get_trending(limit=config.scan_sample_limit)
    except Exception as exc:
        errors[display_name] = _collection_error(exc)
        return
    _store_collected_items(display_name, items, all_trending, errors)


def _collection_error(exc: Exception) -> str:
    """Convert an external collection failure into a compact platform diagnostic."""
    if isinstance(exc, PlatformUnavailable):
        return str(exc)
    return f"collection failed ({type(exc).__name__})"


def _store_collected_items(
    platform: str,
    items: list[TrendingItem],
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
    *,
    empty_error: str = "no trending results returned",
) -> None:
    """Store only valid canonical evidence; an empty result is an explicit error."""
    canonical, _evidence = canonicalize_trending_items({platform: items})
    canonical_items = canonical.get(platform, [])
    if canonical_items:
        all_trending[platform] = canonical_items
    else:
        errors[platform] = empty_error


def main() -> None:
    parser = argparse.ArgumentParser(prog="topic-radar")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Multi-platform topic scan")
    scan.add_argument(
        "--platforms",
        default=None,
        help=(
            "Comma-separated: xiaohongshu (or xhs), weibo, douyin, zhihu, "
            "bilibili, toutiao, douban, sspai"
        ),
    )
    scan.add_argument("--keywords", default=None, help="Optional comma-separated search keywords")
    scan.add_argument("--output-dir", default=None, help="Output directory for artifacts")
    scan.add_argument("--mcp-check", action="store_true", help="Only check MCP health")

    teardown_p = sub.add_parser("teardown", help="Deconstruct a single post")
    teardown_p.add_argument("feed_id", help="XHS feed ID")
    teardown_p.add_argument("--xsec-token", default="", help="XHS xsec_token")
    teardown_p.add_argument(
        "--timeout-seconds",
        type=float,
        default=20.0,
        help="Maximum seconds to wait for one XHS detail request",
    )

    args = parser.parse_args()

    if args.command == "scan":
        asyncio.run(_scan(args))
    elif args.command == "teardown":
        asyncio.run(_teardown(args))
    else:
        parser.print_help()


async def _scan(args: argparse.Namespace) -> None:
    config = get_config()
    platforms_str = config.default_platforms if args.platforms is None else args.platforms
    platform_list = canonicalize_platforms(platforms_str)

    if args.mcp_check:
        client = McpClient(
            xhs_server_url=config.xhs_mcp_server_url,
            enable_trends_hub=any(
                p in {"weibo", "douyin", "zhihu", "bilibili", "toutiao", "douban", "sspai"}
                for p in platform_list
            ),
        )
        health = await client.health()
        for name, h in health.items():
            status = "✓" if h.reachable else "✗"
            print(f"{status} {name}: {h.tool_count} tools" + (f" ({h.error})" if h.error else ""))
        return

    try:
        result = await run_scan(
            platforms=args.platforms,
            keywords=args.keywords,
            output_dir=args.output_dir,
        )
    except RuntimeError as e:
        print(str(e))
        sys.exit(2)

    method = result.analysis_method
    if method == "llm":
        print(f"\nAnalysis: LLM ({len(result.discovered_verticals)} verticals, {len(result.recommended_angles)} angles)")
    else:
        print(f"\nAnalysis: rules fallback ({len(result.discovered_verticals)} verticals)")

    artifact_dir = Path(args.output_dir or getattr(config, "output_dir", "outputs/artifacts"))
    json_path = result.artifact_path or artifact_dir / f"topic-scan-{result.scan_date}.json"
    report_path = result.report_path or artifact_dir / f"topic-brief-{result.scan_date}.md"
    print(f"\nArtifacts written:")
    print(f"  JSON: {json_path}")
    print(f"  Report: {report_path}")

    if result.scan_quality == ScanQuality.INSUFFICIENT_EVIDENCE.value:
        print("\nScan status: insufficient evidence — diagnostic artifact written")
        sys.exit(2)

    if result.platform_errors:
        print(f"\nScan status: partial — {len(result.platform_errors)} issue(s) recorded")
        sys.exit(1)
    print("\nScan status: completed")
    sys.exit(0)


async def _teardown(args: argparse.Namespace) -> None:
    config = get_config()
    client = McpClient(xhs_server_url=config.xhs_mcp_server_url, enable_trends_hub=False)
    xhs = XiaohongshuPlatform(client)

    try:
        detail = await xhs.get_feed_detail(
            args.feed_id,
            args.xsec_token,
            timeout=float(getattr(args, "timeout_seconds", 20.0)),
        )
    except PlatformUnavailable as exc:
        print(f"Failed to fetch detail for feed {args.feed_id}: {exc.reason}")
        sys.exit(1)
    if detail is None:
        print(
            f"Failed to fetch detail for feed {args.feed_id}: "
            "note inaccessible or timed out"
        )
        sys.exit(1)

    result = teardown(detail)
    print(f"Title: {result.title}")
    print(f"Hook: {result.hook_type} (confidence: {result.hook_confidence})")
    print(f"Body structure: {result.body_structure}")
    print(f"Engagement triggers: {', '.join(result.engagement_triggers) if result.engagement_triggers else 'none'}")
    print(f"Trigger confidence: {result.trigger_confidence}")
    if result.comment_signals:
        cs = result.comment_signals
        print(f"Comments: {cs.comment_count} (real discussion: {cs.is_real_discussion})")
        print(f"Question density: {cs.question_density}")
        print(f"Sentiment ratio: {cs.sentiment_ratio}")
        print(f"Top terms: {cs.top_terms[:5]}")
