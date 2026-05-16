"""Topic Radar CLI — multi-platform discussion-worthy topic research."""
from __future__ import annotations

import argparse
import asyncio
import math
import sys

from topic_radar.config import get_config
from topic_radar.mcp_client import McpClient
from topic_radar.platforms.xiaohongshu import XiaohongshuPlatform, PlatformUnavailable
from topic_radar.platforms.weibo import (
    WeiboPlatform, DouyinPlatform, ZhihuPlatform, BilibiliPlatform,
    ToutiaoPlatform, DoubanPlatform, SspaiPlatform, TrendingItem,
)
from topic_radar.analysis.note_teardown import teardown
from topic_radar.analysis.cross_platform import (
    discover_cross_platform,
    discover_verticals,
)
from topic_radar.analysis.llm_analyzer import LLMAnalyzer
from topic_radar.output.artifacts import (
    TopicScanResult,
    _flatten_trending,
    build_scan_result,
)
from topic_radar.output.report import generate_report
from datetime import date


def _convert_llm_output(
    llm_output, trending_items: dict[str, list[TrendingItem]], scan_date: str
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

    cross_signals = [
        CrossPlatformSignal(
            topic=s.topic,
            platforms=s.platforms,
            first_seen_platform=s.platforms[0] if s.platforms else "",
            velocity=s.velocity,
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
        cross_platform_signals=cross_signals,
        high_engagement_patterns=patterns,
        recommended_angles=angles,
        raw_trending=_flatten_trending(trending_items),
        analysis_method="llm",
        scan_summary=llm_output.scan_summary,
        noise_topics=llm_output.noise_topics,
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
) -> TopicScanResult:
    """Programmatic entry point: scan and return TopicScanResult.

    This is the reusable core used by both the CLI and PTSM integration.
    """
    config = get_config()
    platforms_str = platforms or config.default_platforms
    platform_list = [p.strip() for p in platforms_str.split(",") if p.strip()]
    output_dir = output_dir or config.output_dir
    errors: dict[str, str] = {}
    all_trending: dict[str, list[TrendingItem]] = {}

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

    if not all_trending:
        raise RuntimeError(
            f"No data collected from any platform. Errors: {errors}"
        )

    # Analyze: LLM first, rules fallback
    scan_date = date.today().isoformat()
    analyzer = LLMAnalyzer(
        model=config.llm_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
    )
    llm_output, method = analyzer.analyze(all_trending, scan_date)

    if llm_output is not None:
        result = _convert_llm_output(llm_output, all_trending, scan_date)
    else:
        flat_items = [item for items in all_trending.values() for item in items]
        verticals = discover_verticals(flat_items)
        cross_signals = discover_cross_platform(all_trending)
        result = build_scan_result(
            trending_items=all_trending,
            verticals=verticals,
            cross_signals=cross_signals,
            errors=errors,
        )

    # Write artifacts
    result.write(output_dir)
    generate_report(result, output_dir)

    return result


async def _scan_xiaohongshu(
    client: McpClient,
    config,
    keywords: str | None,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    try:
        xhs = XiaohongshuPlatform(client)
        is_logged_in, qr_data = await xhs.check_login()
        if not is_logged_in:
            errors["xiaohongshu"] = "login required; run ptsm xhs-login-qrcode"
        else:
            keywords_list = (keywords or "").split(",") if keywords else None
            kws = (
                [kw.strip() for kw in keywords_list if kw.strip()]
                if keywords_list
                else ["打工人", "治愈"]
            )
            xhs_items: list[TrendingItem] = []
            per_keyword_limit = max(1, math.ceil(config.scan_sample_limit / len(kws)))
            for kw in kws:
                feeds = await xhs.search_feeds(kw, limit=per_keyword_limit)
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
                            },
                        )
                    )
            all_trending["xiaohongshu"] = xhs_items
    except PlatformUnavailable as e:
        errors["xiaohongshu"] = str(e)


async def _scan_weibo(
    client: McpClient,
    config,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    try:
        weibo = WeiboPlatform(client)
        items = await weibo.get_trending(limit=config.scan_sample_limit)
        all_trending["weibo"] = items
    except PlatformUnavailable as e:
        errors["weibo"] = str(e)


async def _scan_douyin(
    client: McpClient,
    config,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    try:
        douyin = DouyinPlatform(client)
        items = await douyin.get_trending(limit=config.scan_sample_limit)
        all_trending["douyin"] = items
    except PlatformUnavailable as e:
        errors["douyin"] = str(e)


async def _scan_trends_hub_platform(
    client: McpClient,
    config,
    platform_cls,
    platform_name: str,
    display_name: str,
    all_trending: dict[str, list[TrendingItem]],
    errors: dict[str, str],
) -> None:
    try:
        p = platform_cls(client)
        items = await p.get_trending(limit=config.scan_sample_limit)
        all_trending[display_name] = items
    except PlatformUnavailable as e:
        errors[display_name] = str(e)


def main() -> None:
    parser = argparse.ArgumentParser(prog="topic-radar")
    sub = parser.add_subparsers(dest="command")

    scan = sub.add_parser("scan", help="Multi-platform topic scan")
    scan.add_argument("--platforms", default=None, help="Comma-separated: xiaohongshu,weibo,douyin")
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
    platforms_str = args.platforms or config.default_platforms
    platform_list = [p.strip() for p in platforms_str.split(",") if p.strip()]

    client = McpClient(
        xhs_server_url=config.xhs_mcp_server_url,
        enable_trends_hub=any(
            p in {"weibo", "douyin", "zhihu", "bilibili", "toutiao", "douban", "sspai"}
            for p in platform_list
        ),
    )

    if args.mcp_check:
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
        print(f"\nAnalysis: rules (LLM unavailable, {len(result.discovered_verticals)} verticals)")

    print(f"\nArtifacts written:")
    print(f"  JSON: outputs/artifacts/topic-scan-{result.scan_date}.json")
    print(f"  Report: outputs/artifacts/topic-brief-{result.scan_date}.md")

    if result.platform_errors:
        print(f"\nPartial scan — {len(result.platform_errors)} platform(s) unavailable")
        sys.exit(1)
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
