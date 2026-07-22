from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = PROJECT_ROOT / "docs"


def test_topic_radar_docs_define_evidence_quality_and_novelty_contract() -> None:
    topic_radar = (DOCS_ROOT / "topic-radar.md").read_text(encoding="utf-8")
    runbook = (DOCS_ROOT / "operations" / "topic-radar-runbook.md").read_text(
        encoding="utf-8"
    )
    observability = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")

    for marker in [
        "xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai",
        "schema_version: 2",
        "completed",
        "partial",
        "insufficient_evidence",
        "topic_clusters",
        "event_fingerprint",
        "topic-radar-history.jsonl",
    ]:
        assert marker in topic_radar

    assert "exit code `1`" in runbook
    assert "exit code `2`" in runbook
    assert "diagnostic artifact" in runbook
    assert "分 server 加载和缓存" in topic_radar
    assert "工具发现也有 bounded timeout" in topic_radar
    assert "单次快照只说明共现" in topic_radar
    assert "不得包含未展开的 `{placeholder}`" in topic_radar
    assert "每平台 12 条热搜、48 条 evidence、24 个事件簇" in topic_radar
    assert "round-robin 保留各平台可见证据" in topic_radar
    assert "首个真实 ID 会消费该 bridge" in topic_radar
    assert "后来的缺 ID 观察保持 unresolved" in topic_radar
    assert "--platforms \"小红书，微博\"" in topic_radar
    assert "open_feed_listing" in topic_radar
    assert "not an exhaustive whole-site ranking" in topic_radar
    assert 'search_feeds("打工人", "治愈")' not in runbook
    assert '默认关键词（"打工人", "治愈"）' not in runbook
    assert "回退到默认关键词" not in runbook
    assert "separator-only fallback" not in observability


def test_runtime_and_skill_docs_preserve_fresh_research_provenance_boundary() -> None:
    runtime = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    skills = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    topic_radar = (DOCS_ROOT / "topic-radar.md").read_text(encoding="utf-8")

    assert "topic_radar.cli.run_scan()" in runtime
    assert "never receives raw source titles, authors, URLs, feed IDs, or tokens" in runtime
    assert "canonical evidence title" in runtime
    assert "author/URL/feed/token" in runtime
    assert "does not start a second live scan" in runtime
    assert "也不会回读当天或其他运行遗留" in runtime
    assert "builder 只接受本次 fresh `run_scan()` receipt" in runtime
    assert "明示且存在的常规 artifact 文件" in runtime
    assert "终端展示用的 `scan_summary`" in runtime
    assert "xhs_compact_native_v1" in skills
    assert "2–4 short beats" in skills
    assert "不回读当天/其他运行留下的 Topic Radar artifact" in skills
    assert "hotspot-discovery" in runtime
    assert "operator_headline" in runtime
    assert "does not enter drafting" in runtime
    assert "ptsm-topic-radar-discovery" in skills
    assert "--max-hotspots" in topic_radar
    assert "默认展示前 12 个" in topic_radar
    assert "routed_hotspots" in topic_radar
    assert "不改变全平台排名" in topic_radar
    assert "至少引入一个未展示的 playbook" in topic_radar


def test_domain_opportunity_docs_require_real_xhs_search_evidence() -> None:
    topic_radar = (DOCS_ROOT / "topic-radar.md").read_text(encoding="utf-8")
    operations = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")

    assert "no successful unique samples" in topic_radar
    assert "login_required" in topic_radar
    assert "not a whole-site or cross-platform trend ranking" in topic_radar
    assert "标题单独不能折叠不同笔记" in topic_radar
    assert "中文 `，` 都能分隔关键词" in topic_radar
    assert "只传分隔符或空白时会被拒绝" in topic_radar
    assert "insufficient_evidence" in operations


def test_domain_opportunity_wrapper_handles_empty_and_partial_evidence() -> None:
    skill = (
        PROJECT_ROOT
        / "integrations"
        / "openclaw"
        / "ptsm-xhs-domain-opportunity"
        / "SKILL.md"
    ).read_text(encoding="utf-8")

    assert "insufficient_evidence" in skill
    assert "no successful unique samples" in skill
    assert "no fits, rankings, or new-domain candidates" in skill
    assert "partial" in skill
    assert "diagnostics" in skill
    assert "login_required" in skill
    assert "ptsm xhs-login-qrcode" in skill
    assert "Do not call `run-playbook`" in skill


def test_discovery_first_routing_docs_cover_all_operator_surfaces() -> None:
    architecture = (DOCS_ROOT / "architecture.md").read_text(encoding="utf-8")
    playbooks = (DOCS_ROOT / "playbooks.md").read_text(encoding="utf-8")
    operations = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    harness = (DOCS_ROOT / "harness-engineering.md").read_text(encoding="utf-8")
    runbook = (DOCS_ROOT / "operations" / "topic-radar-runbook.md").read_text(
        encoding="utf-8"
    )
    local_runbook = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    topic_index = (DOCS_ROOT / "xhs-topics" / "index.md").read_text(encoding="utf-8")
    landscape = (DOCS_ROOT / "xhs-topics" / "skills-landscape.md").read_text(
        encoding="utf-8"
    )
    harness_integration = (
        DOCS_ROOT / "xhs-topics" / "harness-integration.md"
    ).read_text(encoding="utf-8")

    for text in (architecture, playbooks, operations, harness, runbook, local_runbook):
        assert "hotspot-discovery" in text

    assert "hotspot_routing" in architecture
    assert "unmapped" in playbooks
    assert "ptsm-topic-radar-discovery" in operations
    assert "new_domain_candidate" in harness
    assert "open feed listing" in runbook
    assert "xhs-domain-opportunity" in local_runbook
    assert "discovery-first" in topic_index
    assert "ptsm-topic-radar-discovery" in landscape
    assert "operator_headline" in harness_integration
    assert "已选 playbook 的发帖前" in landscape
    assert "先运行 `hotspot-discovery`" in harness_integration
