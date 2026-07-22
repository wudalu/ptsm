"""Discover hotspots first, then conservatively route them to playbooks."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any, Iterable

from ptsm.domain.hotspot_routing import (
    HotspotRoutingProfile,
    route_hotspot,
)
from ptsm.playbooks.registry import PlaybookRegistry


DEFAULT_HOTSPOT_DISCOVERY_DIR = Path("outputs") / "artifacts" / "hotspot-discovery"
DEFAULT_MAX_HOTSPOTS = 12
DEFAULT_MAX_SUPPLEMENTAL_ROUTED_HOTSPOTS = 6
SUPPORTED_SCAN_QUALITIES = frozenset(
    {"completed", "partial", "insufficient_evidence"}
)
PLAYBOOK_ROOT = Path(__file__).resolve().parents[2] / "playbooks" / "definitions"


def run_hotspot_discovery(
    *,
    output_dir: Path | str = DEFAULT_HOTSPOT_DISCOVERY_DIR,
    playbooks: PlaybookRegistry | None = None,
    max_hotspots: int = DEFAULT_MAX_HOTSPOTS,
) -> dict[str, Any]:
    """Run the public unfiltered scan and write an operator-only route artifact.

    The scan intentionally receives no playbook, domain, account, platform, or
    keyword filter.  Existing playbook coverage is consulted only after Topic
    Radar has produced evidence-backed event clusters.
    """
    if max_hotspots < 1:
        raise ValueError("max_hotspots must be at least 1")

    from topic_radar.cli import run_scan

    scan_result = asyncio.run(run_scan())
    playbooks = playbooks or PlaybookRegistry(PLAYBOOK_ROOT)
    raw_status = _text(_field(scan_result, "scan_quality"))
    status = (
        raw_status
        if raw_status in SUPPORTED_SCAN_QUALITIES
        else "insufficient_evidence"
    )
    scan = _scan_receipt(scan_result, status=status)
    eligible_hotspots = (
        _route_verified_clusters(scan_result, playbooks=playbooks)
        if status != "insufficient_evidence"
        else []
    )
    hotspots = eligible_hotspots[:max_hotspots]
    primary_cluster_ids = {row["cluster_id"] for row in hotspots}
    primary_playbook_ids = {
        playbook_id
        for row in hotspots
        for playbook_id in _candidate_playbook_ids(row)
    }
    supplemental_routed_candidates = _diverse_routed_hotspots(
        (
            row
            for row in eligible_hotspots
            if row["cluster_id"] not in primary_cluster_ids
            and row["route"]["status"] != "unmapped"
        ),
        excluded_playbook_ids=primary_playbook_ids,
    )
    supplemental_routed_limit = min(
        max_hotspots,
        DEFAULT_MAX_SUPPLEMENTAL_ROUTED_HOTSPOTS,
    )
    routed_hotspots = supplemental_routed_candidates[:supplemental_routed_limit]
    route_status_counts = _route_status_counts(eligible_hotspots)
    result: dict[str, Any] = {
        "schema_version": 1,
        "status": status,
        "scope_note": _scope_note(status),
        "scan": scan,
        "hotspots": hotspots,
        "hotspot_limit": max_hotspots,
        "eligible_hotspot_count": len(eligible_hotspots),
        "returned_hotspot_count": len(hotspots),
        "route_status_counts": route_status_counts,
        "routed_hotspots": routed_hotspots,
        "supplemental_routed_hotspot_limit": supplemental_routed_limit,
        "eligible_supplemental_routed_hotspot_count": len(
            supplemental_routed_candidates
        ),
        "returned_supplemental_routed_hotspot_count": len(routed_hotspots),
        "next_action": (
            "restore_evidence_sources_then_rescan"
            if status == "insufficient_evidence"
            else _next_action(route_status_counts)
        ),
    }
    artifact_path = _next_artifact_path(Path(output_dir), scan=scan)
    markdown_path = artifact_path.with_suffix(".md")
    result["artifact_path"] = str(artifact_path)
    result["markdown_path"] = str(markdown_path)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(_format_markdown(result), encoding="utf-8")
    return result


def _route_verified_clusters(
    scan_result: object,
    *,
    playbooks: PlaybookRegistry,
) -> list[dict[str, Any]]:
    profiles = tuple(_routing_profiles(playbooks))
    rows: list[dict[str, Any]] = []
    for cluster in _verified_clusters(scan_result):
        route = route_hotspot(cluster["operator_headline"], profiles=profiles)
        route_payload = _route_payload(
            route,
            evidence_count=cluster["evidence_count"],
            platform_count=len(cluster["platforms"]),
        )
        rows.append({**cluster, "route": route_payload})
    return rows


def _verified_clusters(scan_result: object) -> list[dict[str, Any]]:
    evidence_by_id = {
        evidence_id: row
        for row in _object_list(_field(scan_result, "evidence"))
        if (evidence_id := _text(row.get("evidence_id")))
    }
    verified: list[dict[str, Any]] = []
    for cluster in _object_list(_field(scan_result, "topic_clusters")):
        cluster_id = _text(cluster.get("cluster_id"))
        event_fingerprint = _text(cluster.get("event_fingerprint"))
        operator_headline = _text(cluster.get("representative_title"))
        evidence_ids = _string_list(cluster.get("evidence_ids"))
        if not (cluster_id and event_fingerprint and operator_headline and evidence_ids):
            continue
        evidence_rows = [evidence_by_id.get(evidence_id) for evidence_id in evidence_ids]
        if any(row is None for row in evidence_rows):
            continue
        if any(
            _text(row.get("event_fingerprint")) != event_fingerprint
            for row in evidence_rows
            if row is not None
        ):
            continue
        if operator_headline not in {
            _text(row.get("title"))
            for row in evidence_rows
            if row is not None
        }:
            continue
        platforms = sorted(
            {
                platform
                for row in evidence_rows
                if row is not None
                if (platform := _text(row.get("platform")))
            }
        )
        if not platforms:
            continue
        declared_platforms = sorted(set(_string_list(cluster.get("platforms"))))
        if declared_platforms != platforms:
            continue
        verified.append(
            {
                "cluster_id": cluster_id,
                "event_fingerprint": event_fingerprint,
                "operator_headline": operator_headline,
                "evidence_ids": evidence_ids,
                "evidence_count": len(evidence_ids),
                "platforms": platforms,
                "score": _number(cluster.get("score")),
            }
        )
    return sorted(verified, key=lambda row: (-row["score"], row["cluster_id"]))


def _routing_profiles(playbooks: PlaybookRegistry) -> Iterable[HotspotRoutingProfile]:
    for playbook in playbooks.list_playbooks():
        routing = playbook.hotspot_routing
        include_any = tuple(_string_list(routing.get("include_any")))
        require_all = tuple(
            tuple(_string_list(group))
            for group in _object_sequence(routing.get("require_all"))
            if _string_list(group)
        )
        exclude_any = tuple(_string_list(routing.get("exclude_any")))
        if include_any or require_all:
            yield HotspotRoutingProfile(
                playbook_id=playbook.playbook_id,
                domain=playbook.domain,
                include_any=include_any,
                require_all=require_all,
                exclude_any=exclude_any,
            )


def _route_payload(route: object, *, evidence_count: int, platform_count: int) -> dict[str, Any]:
    candidates = [asdict(candidate) for candidate in getattr(route, "candidates", ())]
    is_new_domain_candidate = (
        getattr(route, "status", "") == "unmapped"
        and evidence_count >= 2
        and platform_count >= 2
    )
    return {
        "status": _text(getattr(route, "status", "")),
        "candidates": candidates,
        "new_domain_candidate": is_new_domain_candidate,
        "next_action": (
            "new_domain_review"
            if is_new_domain_candidate
            else _text(getattr(route, "next_action", ""))
        ),
    }


def _route_status_counts(rows: Iterable[dict[str, Any]]) -> dict[str, int]:
    statuses = ("existing_playbook_fit", "ambiguous", "unmapped")
    return {
        status: sum(row["route"]["status"] == status for row in rows)
        for status in statuses
    }


def _diverse_routed_hotspots(
    rows: Iterable[dict[str, Any]],
    *,
    excluded_playbook_ids: Iterable[str] = (),
) -> list[dict[str, Any]]:
    """Keep supplements concise while retaining every newly available choice."""
    selected: list[dict[str, Any]] = []
    selected_playbook_ids = set(excluded_playbook_ids)
    for row in rows:
        playbook_ids = _candidate_playbook_ids(row)
        if not playbook_ids or playbook_ids <= selected_playbook_ids:
            continue
        selected.append(row)
        selected_playbook_ids.update(playbook_ids)
    return selected


def _candidate_playbook_ids(row: dict[str, Any]) -> set[str]:
    candidates = row["route"]["candidates"]
    return {
        candidate["playbook_id"]
        for candidate in candidates
        if isinstance(candidate, dict)
        and isinstance(candidate.get("playbook_id"), str)
    }


def _next_action(route_status_counts: dict[str, int]) -> str:
    if (
        route_status_counts["existing_playbook_fit"]
        or route_status_counts["ambiguous"]
    ):
        return "ask_operator_to_choose_a_routed_hotspot"
    return "monitor_unmapped_hotspots_or_start_new_domain_review"


def _scan_receipt(scan_result: object, *, status: str) -> dict[str, Any]:
    return {
        "scan_date": _text(_field(scan_result, "scan_date")),
        "scan_quality": status,
        "platforms": _string_list(_field(scan_result, "platforms")),
        "platform_errors": _error_map(_field(scan_result, "platform_errors")),
        "artifact_path": _path_text(_field(scan_result, "artifact_path")),
        "report_path": _path_text(_field(scan_result, "report_path")),
    }


def _next_artifact_path(output_dir: Path, *, scan: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_name = Path(str(scan.get("artifact_path") or "")).stem
    if not source_name:
        scan_date = _text(scan.get("scan_date")) or "undated"
        source_name = f"topic-scan-{scan_date}"
    stem = f"hotspot-discovery-{source_name}"
    candidate = output_dir / f"{stem}.json"
    index = 2
    while candidate.exists() or candidate.with_suffix(".md").exists():
        candidate = output_dir / f"{stem}-{index}.json"
        index += 1
    return candidate


def _format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Hotspot Discovery",
        "",
        f"- 状态：`{result['status']}`",
        f"- 范围说明：{result['scope_note']}",
        f"- Topic Radar artifact：{result['scan']['artifact_path'] or 'unavailable'}",
        f"- Topic Radar report：{result['scan']['report_path'] or 'unavailable'}",
        (
            "- 热点列表：展示前 "
            f"{result['returned_hotspot_count']} / {result['eligible_hotspot_count']} 个"
            "（按 Topic Radar score 降序）"
        ),
        (
            "- 全扫描路由："
            f"已有 playbook {result['route_status_counts']['existing_playbook_fit']}，"
            f"需选择 {result['route_status_counts']['ambiguous']}，"
            f"未映射 {result['route_status_counts']['unmapped']}"
        ),
        "",
    ]
    platform_errors = result["scan"]["platform_errors"]
    if platform_errors:
        lines.extend(["## 平台诊断", ""])
        lines.extend(f"- {platform}: {detail}" for platform, detail in platform_errors.items())
        lines.append("")
    if result["hotspots"]:
        lines.extend(["## 全平台 Top 热点", ""])
        _append_hotspot_rows(lines, result["hotspots"], numbered=True)
        lines.append("")
    if result["routed_hotspots"]:
        lines.extend(
            [
                "## 全扫描补充：可进入现有 playbook",
                "",
                (
                    "以下候选不在全平台 Top-N 内；展示前 "
                    f"{result['returned_supplemental_routed_hotspot_count']} / "
                    f"{result['eligible_supplemental_routed_hotspot_count']} 个，"
                    "不改变全平台排名。"
                ),
                "每条补充候选至少引入一个未展示 playbook；ambiguous 保留完整候选。",
                "",
            ]
        )
        _append_hotspot_rows(lines, result["routed_hotspots"])
        lines.append("")
    lines.extend(
        [
            "## 下一步",
            "",
            _next_action_message(result["next_action"]),
            "不要把此报告中的来源标题、作者、链接或抓取标识直接复制到草稿上下文。",
        ]
    )
    return "\n".join(lines) + "\n"


def _append_hotspot_rows(
    lines: list[str],
    rows: Iterable[dict[str, Any]],
    *,
    numbered: bool = False,
) -> None:
    for position, row in enumerate(rows, start=1):
        route = row["route"]
        candidate_ids = ", ".join(
            candidate["playbook_id"] for candidate in route["candidates"]
        ) or "无"
        headline = (
            f"{position}. {row['operator_headline']}"
            if numbered
            else f"- {row['operator_headline']}"
        )
        lines.extend(
            [
                headline,
                (
                    f"  - evidence: {row['evidence_count']} | "
                    f"platforms: {', '.join(row['platforms'])} | score: {row['score']}"
                ),
                f"  - route: {route['status']} | {candidate_ids}",
                f"  - next: {route['next_action']}",
            ]
        )


def _scope_note(status: str) -> str:
    if status == "partial":
        return "partial scan; do not describe these as all-platform results"
    if status == "insufficient_evidence":
        return "insufficient evidence; no hotspot recommendation is available"
    return "completed scan; results reflect configured public platform sources"


def _next_action_message(next_action: object) -> str:
    if next_action == "restore_evidence_sources_then_rescan":
        return "先恢复证据来源和不可用平台，再重新扫描；当前没有可用热点建议。"
    if next_action == "ask_operator_to_choose_a_routed_hotspot":
        return "选择一个已路由热点和目标 playbook/account 后，再进入现有 guide-post 或 run-playbook 流程。"
    return "当前没有现有 playbook 匹配；监测未映射热点或启动新领域复盘。"


def _field(source: object, key: str) -> object:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _text(value: object) -> str:
    if hasattr(value, "value"):
        value = getattr(value, "value")
    return value.strip() if isinstance(value, str) else ""


def _path_text(value: object) -> str:
    return str(value) if isinstance(value, str | Path) and str(value) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [text for item in value if (text := _text(item))]


def _object_sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, list | tuple) else []


def _object_list(value: object) -> list[dict[str, object]]:
    return [dict(item) for item in _object_sequence(value) if isinstance(item, dict)]


def _error_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        key: detail
        for raw_key, raw_detail in value.items()
        if (key := _text(raw_key)) and (detail := _text(raw_detail))
    }


def _number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0
