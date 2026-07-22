from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.use_cases.hotspot_discovery import (
    _diverse_routed_hotspots,
    run_hotspot_discovery,
)
from ptsm.playbooks.registry import PlaybookRegistry
from topic_radar.output.artifacts import TopicScanResult


def _playbooks() -> PlaybookRegistry:
    return PlaybookRegistry(Path("src/ptsm/playbooks/definitions"))


def _scan_result(*, quality: str = "completed") -> TopicScanResult:
    result = TopicScanResult(
        scan_date="2026-07-22",
        platforms=["weibo", "zhihu"],
        scan_quality=quality,
        platform_errors={"xiaohongshu": "login required"} if quality == "partial" else {},
        evidence=[
            {
                "evidence_id": "ev-ai",
                "event_fingerprint": "fp-ai",
                "platform": "weibo",
                "title": "OpenAI 发布面向开发者的新一代 AI Agent",
                "author": "raw-author",
                "url": "https://example.invalid/raw-url",
                "feed_id": "raw-feed-id",
                "xsec_token": "raw-secret-token",
            },
            {
                "evidence_id": "ev-news",
                "event_fingerprint": "fp-news",
                "platform": "zhihu",
                "title": "斯塔默卸任后穿运动鞋直奔酒吧喝酒",
            },
        ],
        topic_clusters=[
            {
                "cluster_id": "cluster-news",
                "event_fingerprint": "fp-news",
                "representative_title": "斯塔默卸任后穿运动鞋直奔酒吧喝酒",
                "evidence_ids": ["ev-news"],
                "platforms": ["zhihu"],
                "score": 6.0,
            },
            {
                "cluster_id": "cluster-ai",
                "event_fingerprint": "fp-ai",
                "representative_title": "OpenAI 发布面向开发者的新一代 AI Agent",
                "evidence_ids": ["ev-ai"],
                "platforms": ["weibo"],
                "score": 9.0,
            },
            {
                "cluster_id": "cluster-malformed",
                "event_fingerprint": "fp-ai",
                "representative_title": "不应进入路由的坏簇",
                "evidence_ids": ["ev-news"],
                "platforms": ["zhihu"],
                "score": 99.0,
            },
            {
                "cluster_id": "cluster-platform-mismatch",
                "event_fingerprint": "fp-news",
                "representative_title": "平台关系不一致的坏簇",
                "evidence_ids": ["ev-news"],
                "platforms": ["weibo"],
                "score": 98.0,
            },
        ],
        raw_trending=[
            {
                "title": "OpenAI 发布面向开发者的新一代 AI Agent",
                "author": "raw-author",
                "url": "https://example.invalid/raw-url",
                "feed_id": "raw-feed-id",
                "xsec_token": "raw-secret-token",
            }
        ],
    )
    result._artifact_path = Path("outputs/artifacts/topic-scan-2026-07-22.json")
    result._report_path = Path("outputs/artifacts/topic-brief-2026-07-22.md")
    return result


def test_hotspot_discovery_scans_before_routing_without_filters_and_writes_safe_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    async def fake_run_scan(*args: object, **kwargs: object) -> TopicScanResult:
        assert args == ()
        calls.append(dict(kwargs))
        return _scan_result()

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    assert calls == [{}]
    assert result["status"] == "completed"
    assert [row["cluster_id"] for row in result["hotspots"]] == [
        "cluster-ai",
        "cluster-news",
    ]
    ai_route = result["hotspots"][0]["route"]
    assert ai_route["status"] == "existing_playbook_fit"
    assert ai_route["candidates"][0]["playbook_id"] == "ai_tech_daily_post"
    assert "OpenAI 发布面向开发者" not in ai_route["candidates"][0]["generation_seed"]
    assert result["hotspots"][1]["route"]["status"] == "unmapped"

    artifact = Path(result["artifact_path"])
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    assert artifact.is_file()
    assert Path(result["markdown_path"]).is_file()
    assert payload["scan"]["artifact_path"] == "outputs/artifacts/topic-scan-2026-07-22.json"
    assert "raw-author" not in json.dumps(payload, ensure_ascii=False)
    assert "raw-url" not in json.dumps(payload, ensure_ascii=False)
    assert "raw-feed-id" not in json.dumps(payload, ensure_ascii=False)
    assert "raw-secret-token" not in json.dumps(payload, ensure_ascii=False)


def test_hotspot_discovery_returns_ranked_top_n_with_transparent_cutoff(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan() -> TopicScanResult:
        return _scan_result()

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
        max_hotspots=1,
    )

    assert [row["cluster_id"] for row in result["hotspots"]] == ["cluster-ai"]
    assert result["hotspot_limit"] == 1
    assert result["eligible_hotspot_count"] == 2
    assert result["returned_hotspot_count"] == 1
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "展示前 1 / 2 个" in markdown


def test_hotspot_discovery_keeps_broad_ranking_and_exposes_distinct_route_ready_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = _scan_result()
    for cluster in scan.topic_clusters:
        if cluster["cluster_id"] == "cluster-news":
            cluster["score"] = 10.0

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
        max_hotspots=1,
    )

    assert [row["cluster_id"] for row in result["hotspots"]] == ["cluster-news"]
    assert [row["cluster_id"] for row in result["routed_hotspots"]] == [
        "cluster-ai"
    ]
    assert result["route_status_counts"] == {
        "existing_playbook_fit": 1,
        "ambiguous": 0,
        "unmapped": 1,
    }
    assert result["eligible_supplemental_routed_hotspot_count"] == 1
    assert result["returned_supplemental_routed_hotspot_count"] == 1
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "全扫描补充：可进入现有 playbook" in markdown
    assert "至少引入一个未展示 playbook" in markdown


def test_hotspot_discovery_markdown_keeps_top_n_in_score_order_across_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = _scan_result()
    for cluster in scan.topic_clusters:
        if cluster["cluster_id"] == "cluster-news":
            cluster["score"] = 10.0

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
        max_hotspots=2,
    )

    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "## 全平台 Top 热点" in markdown
    assert markdown.index("斯塔默卸任后穿运动鞋") < markdown.index(
        "OpenAI 发布面向开发者"
    )


def test_hotspot_discovery_supplement_avoids_repeating_the_same_playbook(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = _scan_result()
    scan.evidence.append(
        {
            "evidence_id": "ev-ai-second",
            "event_fingerprint": "fp-ai-second",
            "platform": "zhihu",
            "title": "ChatGPT 新功能面向开发者开放",
        }
    )
    scan.topic_clusters.append(
        {
            "cluster_id": "cluster-ai-second",
            "event_fingerprint": "fp-ai-second",
            "representative_title": "ChatGPT 新功能面向开发者开放",
            "evidence_ids": ["ev-ai-second"],
            "platforms": ["zhihu"],
            "score": 8.0,
        }
    )
    for cluster in scan.topic_clusters:
        if cluster["cluster_id"] == "cluster-news":
            cluster["score"] = 10.0

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
        max_hotspots=1,
    )

    assert [row["cluster_id"] for row in result["routed_hotspots"]] == [
        "cluster-ai"
    ]
    assert result["eligible_supplemental_routed_hotspot_count"] == 1


def test_hotspot_discovery_supplement_does_not_repeat_a_playbook_already_in_top_n(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = _scan_result()
    scan.evidence.append(
        {
            "evidence_id": "ev-ai-second",
            "event_fingerprint": "fp-ai-second",
            "platform": "zhihu",
            "title": "ChatGPT 新功能面向开发者开放",
        }
    )
    scan.topic_clusters.append(
        {
            "cluster_id": "cluster-ai-second",
            "event_fingerprint": "fp-ai-second",
            "representative_title": "ChatGPT 新功能面向开发者开放",
            "evidence_ids": ["ev-ai-second"],
            "platforms": ["zhihu"],
            "score": 8.0,
        }
    )

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
        max_hotspots=1,
    )

    assert [row["cluster_id"] for row in result["hotspots"]] == ["cluster-ai"]
    assert result["routed_hotspots"] == []
    assert result["eligible_supplemental_routed_hotspot_count"] == 0


def test_hotspot_discovery_rejects_a_cluster_title_not_backed_by_its_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = _scan_result()
    scan.topic_clusters.append(
        {
            "cluster_id": "cluster-title-mismatch",
            "event_fingerprint": "fp-ai",
            "representative_title": "美加墨世界杯的三个意难平",
            "evidence_ids": ["ev-ai"],
            "platforms": ["weibo"],
            "score": 99.0,
        }
    )

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(
        output_dir=tmp_path,
        playbooks=_playbooks(),
    )

    assert "cluster-title-mismatch" not in {
        row["cluster_id"] for row in result["hotspots"]
    }
    assert all(
        row["route"]["status"] != "existing_playbook_fit"
        or row["cluster_id"] != "cluster-title-mismatch"
        for row in result["routed_hotspots"]
    )


@pytest.mark.parametrize("non_finite_score", ["nan", "inf", "-inf"])
def test_hotspot_discovery_normalizes_non_finite_cluster_scores_before_writing_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    non_finite_score: str,
) -> None:
    scan = _scan_result()
    for cluster in scan.topic_clusters:
        if cluster["cluster_id"] == "cluster-ai":
            cluster["score"] = non_finite_score

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    ai_row = next(row for row in result["hotspots"] if row["cluster_id"] == "cluster-ai")
    assert ai_row["score"] == 0.0
    assert json.loads(Path(result["artifact_path"]).read_text(encoding="utf-8"))


def test_hotspot_discovery_fails_closed_for_unknown_scan_quality(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan() -> TopicScanResult:
        return _scan_result(quality="failed")

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    assert result["status"] == "insufficient_evidence"
    assert result["scan"]["scan_quality"] == "insufficient_evidence"
    assert result["hotspots"] == []
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "选择一个已路由热点" not in markdown
    assert "恢复证据来源" in markdown


def test_supplemental_routing_keeps_an_ambiguous_row_that_introduces_a_new_playbook() -> None:
    row = {
        "route": {
            "candidates": [
                {"playbook_id": "already-shown"},
                {"playbook_id": "new-choice"},
            ]
        }
    }

    assert _diverse_routed_hotspots(
        [row],
        excluded_playbook_ids={"already-shown"},
    ) == [row]


def test_hotspot_discovery_preserves_partial_scope_and_platform_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan() -> TopicScanResult:
        return _scan_result(quality="partial")

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    assert result["status"] == "partial"
    assert result["scan"]["platform_errors"] == {"xiaohongshu": "login required"}
    assert result["scope_note"] == "partial scan; do not describe these as all-platform results"
    assert result["hotspots"]


def test_hotspot_discovery_fails_closed_for_insufficient_evidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    async def fake_run_scan() -> TopicScanResult:
        return _scan_result(quality="insufficient_evidence")

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    assert result["status"] == "insufficient_evidence"
    assert result["hotspots"] == []
    assert result["next_action"] == "restore_evidence_sources_then_rescan"
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "选择一个已路由热点" not in markdown
    assert "恢复证据来源" in markdown


def test_hotspot_discovery_marks_evidence_rich_unmapped_cluster_for_new_domain_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    scan = TopicScanResult(
        scan_date="2026-07-22",
        platforms=["weibo", "zhihu"],
        evidence=[
            {
                "evidence_id": "ev-1",
                "event_fingerprint": "fp-unknown",
                "platform": "weibo",
                "title": "陌生的新兴话题",
            },
            {
                "evidence_id": "ev-2",
                "event_fingerprint": "fp-unknown",
                "platform": "zhihu",
                "title": "陌生的新兴话题持续讨论",
            },
        ],
        topic_clusters=[
            {
                "cluster_id": "cluster-unknown",
                "event_fingerprint": "fp-unknown",
                "representative_title": "陌生的新兴话题",
                "evidence_ids": ["ev-1", "ev-2"],
                "platforms": ["weibo", "zhihu"],
                "score": 9.0,
            }
        ],
    )

    async def fake_run_scan() -> TopicScanResult:
        return scan

    monkeypatch.setattr("topic_radar.cli.run_scan", fake_run_scan)

    result = run_hotspot_discovery(output_dir=tmp_path, playbooks=_playbooks())

    route = result["hotspots"][0]["route"]
    assert route["status"] == "unmapped"
    assert route["new_domain_candidate"] is True
    assert route["next_action"] == "new_domain_review"
    assert result["next_action"] == "monitor_unmapped_hotspots_or_start_new_domain_review"
    markdown = Path(result["markdown_path"]).read_text(encoding="utf-8")
    assert "选择一个已路由热点" not in markdown
    assert "监测未映射热点" in markdown
