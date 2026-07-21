from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
import json
from pathlib import Path

from topic_radar.analysis.note_teardown import TeardownResult
from topic_radar.analysis.cross_platform import CrossPlatformSignal, DiscoveredVertical
from topic_radar.analysis.evidence import (
    EvidenceRecord,
    ScanQuality,
    canonicalize_trending_items,
    determine_scan_quality,
)
from topic_radar.platforms.weibo import TrendingItem


@dataclass
class TopicScanResult:
    scan_date: str
    platforms: list[str]
    discovered_verticals: list[DiscoveredVertical] = field(default_factory=list)
    cross_platform_signals: list[CrossPlatformSignal] = field(default_factory=list)
    high_engagement_patterns: list[dict] = field(default_factory=list)
    recommended_angles: list[dict] = field(default_factory=list)
    raw_trending: list[dict] = field(default_factory=list)
    platform_errors: dict[str, str] = field(default_factory=dict)
    analysis_method: str = "rules"
    scan_summary: str = ""
    noise_topics: list[str] = field(default_factory=list)
    schema_version: int = 2
    scan_quality: str = ScanQuality.COMPLETED.value
    evidence: list[dict] = field(default_factory=list)
    topic_clusters: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if isinstance(self.scan_quality, ScanQuality):
            self.scan_quality = self.scan_quality.value

    def to_json(self) -> str:
        return json.dumps(self, ensure_ascii=False, indent=2, default=_serialize)

    @property
    def artifact_path(self) -> Path | None:
        """Path selected by the last write, excluded from serialized schema."""
        return getattr(self, "_artifact_path", None)

    @property
    def report_path(self) -> Path | None:
        """Path selected by the last Markdown render, excluded from schema."""
        return getattr(self, "_report_path", None)

    def write(self, output_dir: str = "outputs/artifacts") -> Path:
        dir_path = Path(output_dir)
        dir_path.mkdir(parents=True, exist_ok=True)
        filepath = _next_scan_artifact_path(dir_path, self.scan_date)
        filepath.write_text(self.to_json(), encoding="utf-8")
        self._artifact_path = filepath
        return filepath


def _next_scan_artifact_path(dir_path: Path, scan_date: str) -> Path:
    """Return a new daily artifact path without replacing an earlier scan."""
    primary = dir_path / f"topic-scan-{scan_date}.json"
    primary_report = dir_path / f"topic-brief-{scan_date}.md"
    if not primary.exists() and not primary_report.exists():
        return primary
    index = 2
    while True:
        candidate = dir_path / f"topic-scan-{scan_date}-{index}.json"
        report_candidate = dir_path / f"topic-brief-{scan_date}-{index}.md"
        if not candidate.exists() and not report_candidate.exists():
            return candidate
        index += 1


def build_scan_result(
    *,
    trending_items: dict[str, list[TrendingItem]],
    verticals: list[DiscoveredVertical],
    cross_signals: list[CrossPlatformSignal],
    teardowns: list[TeardownResult] | None = None,
    errors: dict[str, str] | None = None,
    scan_quality: ScanQuality | str | None = None,
    evidence: list[EvidenceRecord] | list[dict] | None = None,
    topic_clusters: list[dict] | None = None,
    requested_platforms: list[str] | None = None,
) -> TopicScanResult:
    teardowns = teardowns or []

    patterns = _summarize_teardown_patterns(teardowns)
    angles = _build_recommended_angles(verticals, cross_signals, patterns)
    raw = _flatten_trending(trending_items)
    if evidence is None:
        _canonical, canonical_evidence = canonicalize_trending_items(trending_items)
        artifact_evidence = [asdict(record) for record in canonical_evidence]
    else:
        artifact_evidence = [
            asdict(record) if isinstance(record, EvidenceRecord) else dict(record)
            for record in evidence
        ]
    quality = scan_quality or determine_scan_quality(
        trending_items,
        errors,
        requested_platforms,
    )

    return TopicScanResult(
        scan_date=date.today().isoformat(),
        platforms=sorted(trending_items),
        scan_quality=quality,
        evidence=artifact_evidence,
        topic_clusters=topic_clusters or [],
        discovered_verticals=verticals,
        cross_platform_signals=cross_signals,
        high_engagement_patterns=patterns,
        recommended_angles=angles,
        raw_trending=raw,
        platform_errors=errors or {},
    )


def _summarize_teardown_patterns(teardowns: list[TeardownResult]) -> list[dict]:
    if not teardowns:
        return []

    hook_counter: dict[str, int] = {}
    trigger_counter: dict[str, int] = {}
    for t in teardowns:
        hook_counter[t.hook_type] = hook_counter.get(t.hook_type, 0) + 1
        for trigger in t.engagement_triggers:
            trigger_counter[trigger] = trigger_counter.get(trigger, 0) + 1

    top_hooks = sorted(hook_counter, key=hook_counter.get, reverse=True)[:3]
    top_triggers = sorted(trigger_counter, key=trigger_counter.get, reverse=True)[:3]

    return [
        {
            "top_hook_types": top_hooks,
            "top_engagement_triggers": top_triggers,
            "teardown_count": len(teardowns),
            "avg_hook_confidence": round(
                sum(t.hook_confidence for t in teardowns) / len(teardowns), 3
            ),
        }
    ]


def _build_recommended_angles(
    verticals: list[DiscoveredVertical],
    cross_signals: list[CrossPlatformSignal],
    patterns: list[dict],
) -> list[dict]:
    angles: list[dict] = []

    for v in verticals:
        if v.is_noise:
            continue
        for angle in v.suggested_angles:
            angles.append({
                "vertical": v.name,
                "angle": angle,
                "why_discussion_likely": _pick_why(v.name),
                "confidence": v.confidence,
                # This is consumed by the scan pipeline before persistence to
                # bind a generic rule angle to canonical event evidence.
                "sample_topics": list(v.sample_topics),
            })

    angles.sort(key=lambda a: a["confidence"], reverse=True)
    return angles[:10]


def _pick_why(vertical: str) -> str:
    mapping = {
        "修复系手作": "低门槛可复制 + 天然晒图欲望 + 评论区经验交换",
        "情绪疗愈": "情绪共鸣切入 + 身份标签唤起 + 你来我往式讨论",
        "AI效率": "反常识开头 + 实用性驱动 + 收藏/转发激励",
        "轻养生": "日常可坚持 + 效果可见 + 经验交流自发产生",
        "宠物陪伴": "萌宠天然互动 + 养宠心得交换 + 评论区晒宠",
        "文博非遗": "文化审美认同 + 季节/节气关联 + 打卡式分享",
        "打工人日常": "身份共鸣 + 情绪宣泄 + 评论区互助取暖",
    }
    return mapping.get(vertical, "通用讨论诱因：低门槛参与 + 情绪共鸣 + 经验交换")


def _flatten_trending(
    trending_items: dict[str, list[TrendingItem]],
    *,
    raw_trending_limit_per_platform: int = 100,
) -> list[dict]:
    flat: list[dict] = []
    for platform, items in trending_items.items():
        for item in items[:raw_trending_limit_per_platform]:
            row = {
                "platform": item.platform,
                "rank": item.rank,
                "title": item.title,
                "hot_score": item.hot_score,
                "label": item.label,
                "url": item.url,
            }
            row.update({
                key: value
                for key, value in item.metadata.items()
                if not key.startswith("_evidence_")
            })
            flat.append(row)
    return flat


def _serialize(obj: object) -> object:
    if isinstance(obj, date):
        return obj.isoformat()
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)  # type: ignore[arg-type]
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
