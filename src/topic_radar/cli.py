"""Topic Radar CLI — multi-platform discussion-worthy topic research."""
from __future__ import annotations

import argparse
import asyncio
import sys

from topic_radar.config import get_config
from topic_radar.mcp_client import McpClient
from topic_radar.platforms.xiaohongshu import XiaohongshuPlatform, PlatformUnavailable
from topic_radar.platforms.weibo import WeiboPlatform, DouyinPlatform, TrendingItem
from topic_radar.analysis.note_teardown import teardown
from topic_radar.analysis.cross_platform import (
    discover_cross_platform,
    discover_verticals,
)
from topic_radar.output.artifacts import build_scan_result
from topic_radar.output.report import generate_report


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
    platforms = [p.strip() for p in platforms_str.split(",") if p.strip()]
    output_dir = args.output_dir or config.output_dir
    errors: dict[str, str] = {}
    all_trending: dict[str, list[TrendingItem]] = {}

    client = McpClient(
        xhs_server_url=config.xhs_mcp_server_url,
        enable_trends_hub=any(p in {"weibo", "douyin"} for p in platforms),
    )

    if args.mcp_check:
        health = await client.health()
        for name, h in health.items():
            status = "✓" if h.reachable else "✗"
            print(f"{status} {name}: {h.tool_count} tools" + (f" ({h.error})" if h.error else ""))
        return

    # Scan each platform
    if "xiaohongshu" in platforms:
        try:
            xhs = XiaohongshuPlatform(client)

            is_logged_in, qr_data = await xhs.check_login()
            if not is_logged_in:
                print("xiaohongshu: not logged in")
                print("  To log in, run: python -m ptsm.bootstrap xhs-login-qrcode")
                if qr_data:
                    print(f"  QR code data available — scan with XHS app to log in")
                all_trending["xiaohongshu"] = []
            else:
                keywords = (args.keywords or "").split(",") if args.keywords else None
                kws = [kw.strip() for kw in keywords if kw.strip()] if keywords else ["打工人", "治愈"]
                xhs_items: list[TrendingItem] = []
                for kw in kws[:3]:
                    feeds = await xhs.search_feeds(kw, limit=config.scan_sample_limit // len(kws))
                    for feed in feeds:
                        xhs_items.append(TrendingItem(
                            rank=0, title=feed.title,
                            hot_score=feed.engagement_score,
                            platform="xiaohongshu",
                        ))
                all_trending["xiaohongshu"] = xhs_items
                print(f"xiaohongshu: {len(xhs_items)} feeds")
        except PlatformUnavailable as e:
            errors["xiaohongshu"] = str(e)
            print(f"xiaohongshu: unavailable — {e.reason}")

    if "weibo" in platforms:
        try:
            weibo = WeiboPlatform(client)
            items = await weibo.get_trending(limit=config.scan_sample_limit)
            all_trending["weibo"] = items
            print(f"weibo: {len(items)} trending items")
        except PlatformUnavailable as e:
            errors["weibo"] = str(e)
            print(f"weibo: unavailable ({e.reason})")

    if "douyin" in platforms:
        try:
            douyin = DouyinPlatform(client)
            items = await douyin.get_trending(limit=config.scan_sample_limit)
            all_trending["douyin"] = items
            print(f"douyin: {len(items)} trending items")
        except PlatformUnavailable as e:
            errors["douyin"] = str(e)
            print(f"douyin: unavailable ({e.reason})")

    if not all_trending:
        print("No data collected from any platform.")
        if errors:
            for p, e in errors.items():
                print(f"  {p}: {e}")
        sys.exit(2)

    # Analyze
    flat_items = [item for items in all_trending.values() for item in items]
    verticals = discover_verticals(flat_items)
    cross_signals = discover_cross_platform(all_trending)

    result = build_scan_result(
        trending_items=all_trending,
        verticals=verticals,
        cross_signals=cross_signals,
        errors=errors,
    )

    # Output
    json_path = result.write(output_dir)
    md_path = generate_report(result, output_dir)

    print(f"\nArtifacts written:")
    print(f"  JSON: {json_path}")
    print(f"  Report: {md_path}")

    if errors:
        print(f"\nPartial scan — {len(errors)} platform(s) unavailable")
        sys.exit(1)
    sys.exit(0)


async def _teardown(args: argparse.Namespace) -> None:
    config = get_config()
    client = McpClient(xhs_server_url=config.xhs_mcp_server_url, enable_trends_hub=False)
    xhs = XiaohongshuPlatform(client)

    detail = await xhs.get_feed_detail(args.feed_id, args.xsec_token)
    if detail is None:
        print(f"Failed to fetch detail for feed {args.feed_id}")
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
