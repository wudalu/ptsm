"""Canonical source evidence used by the topic-radar scan pipeline.

This module intentionally depends only on topic-radar's platform model.  It
normalizes collection output before any LLM or rule-based analysis so that a
source discovered by more than one query is represented once, with its query
provenance retained.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta
from difflib import SequenceMatcher
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence
import unicodedata

from topic_radar.platforms.weibo import TrendingItem


SUPPORTED_PLATFORMS = frozenset(
    {
        "xiaohongshu",
        "weibo",
        "douyin",
        "zhihu",
        "bilibili",
        "toutiao",
        "douban",
        "sspai",
    }
)

_PLATFORM_ALIASES = {
    "xhs": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "小红书": "xiaohongshu",
    "weibo": "weibo",
    "微博": "weibo",
    "douyin": "douyin",
    "抖音": "douyin",
    "zhihu": "zhihu",
    "知乎": "zhihu",
    "bilibili": "bilibili",
    "b站": "bilibili",
    "哔哩哔哩": "bilibili",
    "toutiao": "toutiao",
    "头条": "toutiao",
    "今日头条": "toutiao",
    "douban": "douban",
    "豆瓣": "douban",
    "sspai": "sspai",
    "少数派": "sspai",
}


class ScanQuality(str, Enum):
    """Truthful completeness state for a scan artifact."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class EvidenceRecord:
    """One canonical source observation retained in a scan artifact."""

    evidence_id: str
    source_identity: str
    platform: str
    title: str
    canonical_title: str
    event_fingerprint: str
    hot_score: int
    normalized_heat: float
    matched_queries: list[str]
    source_observation_count: int = 1


@dataclass(frozen=True)
class TopicCluster:
    """One conservative event-level grouping of canonical source evidence.

    The identifiers deliberately contain only deterministic hashes; source ids
    remain in ``evidence_ids`` rather than leaking into an event key.
    """

    cluster_id: str
    event_fingerprint: str
    representative_title: str
    evidence_ids: list[str]
    platforms: list[str]
    score: float


_GENERIC_EVENT_NGRAMS = frozenset(
    {
        "一个",
        "今天",
        "公众",
        "关注",
        "官方",
        "回应",
        "大家",
        "宣布",
        "我们",
        "提醒",
        "报道",
        "发布",
        "热搜",
        "热议",
        "热点",
        "热门",
        "网友",
        "新闻",
        "最新",
        "近日",
        "消息",
        "相关",
        "网络",
        "视频",
        "话题",
        "这个",
        "事件",
        "出现",
    }
)

# These are compact, mutually exclusive headline slots.  Aliases in the same
# slot are equivalent (for example 绘图/绘画/作图), while different slots in a
# group describe incompatible event subjects (for example visual generation
# vs 写作). They protect conservative clustering when fuzzy wording alone is
# too similar.
_CONFLICTING_EVENT_TERM_SLOT_GROUPS = (
    (
        frozenset(("暴雨",)),
        frozenset(("暴雪",)),
        frozenset(("台风",)),
        frozenset(("高温",)),
        frozenset(("寒潮",)),
        frozenset(("大雾",)),
        frozenset(("沙尘",)),
        frozenset(("地震",)),
        frozenset(("洪水",)),
    ),
    (
        frozenset(("绘图", "绘画", "作图", "画图", "生图", "图像", "图片")),
        frozenset(("写作", "写文", "文案")),
        frozenset(("编程", "代码")),
        frozenset(("视频",)),
        frozenset(("音乐",)),
        frozenset(("翻译",)),
        frozenset(("搜索",)),
    ),
)

_TOPIC_HISTORY_FILENAME = "topic-radar-history.jsonl"
_SOURCE_TITLE_EMBEDDED_MIN_LENGTH = 4
SOURCE_PROVENANCE_FIELD_NAMES = (
    "author",
    "author_name",
    "nickname",
    "source_author",
    "url",
    "source_url",
    "feed_id",
    "feedId",
    "source_feed_id",
    "id",
    "xsec_token",
    "xsecToken",
    "token",
    "source_token",
)


def canonicalize_platform(value: str) -> str:
    """Return a stable platform identifier while accepting common aliases."""
    normalized = unicodedata.normalize("NFKC", value or "").strip().casefold()
    normalized = re.sub(r"[\s_-]+", "", normalized)
    return _PLATFORM_ALIASES.get(normalized, normalized)


def canonicalize_platforms(platforms: Iterable[str] | str) -> list[str]:
    """Canonicalize and de-duplicate a requested platform list in input order."""
    values = re.split(r"[,，]", platforms) if isinstance(platforms, str) else platforms
    result: list[str] = []
    for value in values:
        platform = canonicalize_platform(value)
        if platform and platform not in result:
            result.append(platform)
    return result


def normalize_text(value: object) -> str:
    """Normalize a title or author for deterministic source identity matching."""
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\W_]+", "", normalized, flags=re.UNICODE)


def normalized_source_keys(values: Iterable[object]) -> frozenset[str]:
    """Return non-empty canonical forms for raw source fields."""
    return frozenset(
        normalized
        for value in values
        if (normalized := normalize_text(value))
    )


def source_provenance_keys(
    rows: Iterable[Mapping[str, object]],
) -> frozenset[str]:
    """Extract author/URL/feed/token values that must never reach drafting."""
    return normalized_source_keys(
        row.get(field)
        for row in rows
        for field in SOURCE_PROVENANCE_FIELD_NAMES
    )


def contains_raw_source_provenance(
    fields: Iterable[object],
    *,
    source_title_keys: Iterable[str],
    provenance_keys: Iterable[str] = (),
) -> bool:
    """Whether drafting-facing text copies or embeds a raw source value.

    Every non-empty source title is rejected as an exact drafting field. More
    specific titles are also rejected when embedded in a larger field; a very
    short generic title such as ``AI`` is not source-identifying when it
    appears inside a new angle. Raw provenance (author, URL, feed ID, token)
    remains strict for every non-empty value, including short author names.
    """
    titles = normalized_source_keys(source_title_keys)
    provenance = normalized_source_keys(provenance_keys)
    for field in fields:
        candidate = normalize_text(field)
        if not candidate:
            continue
        if _source_key_matches(
            candidate,
            titles,
            embedded_min_length=_SOURCE_TITLE_EMBEDDED_MIN_LENGTH,
        ):
            return True
        if _source_key_matches(candidate, provenance, embedded_min_length=1):
            return True
    return False


def _source_key_matches(
    candidate: str,
    keys: Iterable[str],
    *,
    embedded_min_length: int,
) -> bool:
    return any(
        candidate == key or (len(key) >= embedded_min_length and key in candidate)
        for key in keys
        if key
    )


def source_identity(item: TrendingItem, *, platform: str | None = None) -> str:
    """Build an idempotent per-source identity for a valid trending item."""
    canonical_platform = canonicalize_platform(platform or item.platform)
    canonical_title = normalize_text(item.title)
    if canonical_platform == "xiaohongshu":
        feed_id = item.metadata.get("feed_id")
        if isinstance(feed_id, str) and feed_id.strip():
            return f"xiaohongshu:feed:{feed_id.strip()}"
        author = normalize_text(item.metadata.get("author"))
        if author:
            return f"xiaohongshu:title:{canonical_title}:{author}"
        url = item.url.strip()
        if url:
            return f"xiaohongshu:url:{url}"
        observation_key = item.metadata.get("_evidence_observation_key")
        if isinstance(observation_key, str) and observation_key:
            digest = sha256(
                f"{canonical_title}|{observation_key}".encode("utf-8")
            ).hexdigest()[:16]
            return f"xiaohongshu:unresolved:{digest}"
        return f"xiaohongshu:unresolved:{canonical_title}:unidentified"
    return f"{canonical_platform}:title:{canonical_title}"


def event_fingerprint(title: str) -> str:
    """Return a deterministic exact-title event fingerprint for this first stage."""
    canonical_title = normalize_text(title)
    digest = sha256(canonical_title.encode("utf-8")).hexdigest()[:16]
    return f"event:{digest}"


def canonicalize_trending_items(
    trending_items: dict[str, list[TrendingItem]],
) -> tuple[dict[str, list[TrendingItem]], list[EvidenceRecord]]:
    """Collapse duplicate source observations and build artifact-ready evidence.

    A collection may return the same XHS feed for several query terms. Feed ID
    is authoritative when present; title+author can safely bridge one preceding
    ID-less observation to its first resolved feed ID, without collapsing later
    distinct IDs with the same visible title. Once that visible identity has
    multiple real IDs, later ID-less observations remain unresolved rather than
    attaching to an arbitrary feed. Other platforms are de-duplicated
    by canonical title within their own platform.
    """
    canonical: dict[str, list[TrendingItem]] = {}
    observation_counts: dict[tuple[str, str], int] = {}
    observation_index = 0
    xhs_alias_to_identity: dict[str, str] = {}
    xhs_idless_aliases: set[str] = set()
    xhs_known_identities_by_alias: dict[str, set[str]] = {}

    for requested_platform, items in trending_items.items():
        platform = canonicalize_platform(requested_platform)
        if not platform:
            continue

        existing = canonical.setdefault(platform, [])
        by_identity = {source_identity(item, platform=platform): item for item in existing}
        for item in items:
            observation_index += 1
            if not normalize_text(item.title):
                continue
            normalized_item = _normalized_item(
                item,
                platform,
                fallback_observation_key=f"{platform}:{observation_index}",
            )
            identity = source_identity(normalized_item, platform=platform)
            key = (platform, identity)

            if platform == "xiaohongshu":
                title_author_alias = _xhs_title_author_alias(normalized_item)
                is_known_feed = identity.startswith("xiaohongshu:feed:")
                known_identities = (
                    xhs_known_identities_by_alias.setdefault(title_author_alias, set())
                    if title_author_alias is not None
                    else set()
                )
                if is_known_feed:
                    known_identities.add(identity)

                if (
                    is_known_feed
                    and title_author_alias is not None
                    and title_author_alias in xhs_idless_aliases
                    and len(known_identities) == 1
                ):
                    # An ID-less result appeared first. Upgrade that canonical
                    # record to the real feed ID and consume the bridge so a
                    # later distinct ID with the same title/author stays real.
                    bridged_identity = xhs_alias_to_identity[title_author_alias]
                    bridged_item = by_identity.get(bridged_identity)
                    if bridged_item is not None:
                        _merge_observation(bridged_item, normalized_item)
                        by_identity.pop(bridged_identity)
                        by_identity[identity] = bridged_item
                        xhs_alias_to_identity[title_author_alias] = identity
                        xhs_idless_aliases.discard(title_author_alias)
                        observation_counts.pop((platform, bridged_identity), None)
                        observation_counts[key] = _source_observation_count(bridged_item)
                        continue

                if (
                    not is_known_feed
                    and title_author_alias is not None
                    and len(known_identities) == 1
                    and (bridged_identity := xhs_alias_to_identity.get(title_author_alias))
                    is not None
                ):
                    # A complete feed observed earlier is authoritative; an
                    # ID-less result with the same full title+author only adds
                    # query provenance to that canonical source.
                    bridged_item = by_identity.get(bridged_identity)
                    if bridged_item is not None:
                        _merge_observation(bridged_item, normalized_item)
                        observation_counts[(platform, bridged_identity)] = (
                            _source_observation_count(bridged_item)
                        )
                        continue

            if identity in by_identity:
                _merge_observation(by_identity[identity], normalized_item)
                observation_counts[key] = _source_observation_count(by_identity[identity])
                continue

            by_identity[identity] = normalized_item
            existing.append(normalized_item)
            observation_counts[key] = _source_observation_count(normalized_item)
            if platform == "xiaohongshu":
                title_author_alias = _xhs_title_author_alias(normalized_item)
                if title_author_alias is not None:
                    xhs_alias_to_identity.setdefault(title_author_alias, identity)
                    known_identities = xhs_known_identities_by_alias.setdefault(
                        title_author_alias,
                        set(),
                    )
                    if identity.startswith("xiaohongshu:feed:"):
                        known_identities.add(identity)
                    elif not known_identities:
                        xhs_idless_aliases.add(title_author_alias)

        if not existing:
            canonical.pop(platform, None)

    evidence = _build_evidence(canonical, observation_counts)
    return canonical, evidence


def determine_scan_quality(
    trending_items: dict[str, list[TrendingItem]],
    errors: dict[str, str] | None = None,
    requested_platforms: Iterable[str] | None = None,
) -> ScanQuality:
    """Classify evidence truthfully without treating empty lists as successes."""
    valid_platforms = {
        canonicalize_platform(platform)
        for platform, items in trending_items.items()
        if any(normalize_text(item.title) for item in items)
    }
    if not valid_platforms:
        return ScanQuality.INSUFFICIENT_EVIDENCE

    requested = set(canonicalize_platforms(requested_platforms or valid_platforms))
    errored = {canonicalize_platform(platform) for platform in (errors or {})}
    if errored or (requested and not requested.issubset(valid_platforms)):
        return ScanQuality.PARTIAL
    return ScanQuality.COMPLETED


def cluster_evidence(
    evidence: Sequence[EvidenceRecord],
    *,
    similarity_threshold: float = 0.58,
) -> tuple[list[EvidenceRecord], list[TopicCluster]]:
    """Group exact titles and conservative near-paraphrases into events.

    Chinese hot-search titles often differ only by a short insertion such as
    ``突降``/``多地``.  We intentionally require both sequence similarity and
    at least two non-generic character bigrams, so a common framing such as
    ``网友热议`` cannot collapse otherwise unrelated stories.
    """
    if not evidence:
        return [], []

    threshold = min(max(float(similarity_threshold), 0.0), 1.0)
    grouped: list[list[EvidenceRecord]] = []
    for record in sorted(
        evidence,
        key=lambda item: (normalize_text(item.title), item.platform, item.evidence_id),
    ):
        best_index: int | None = None
        best_similarity = 0.0
        for index, group in enumerate(grouped):
            similarities = [
                _event_title_similarity(record.title, member.title, threshold=threshold)
                for member in group
            ]
            # Complete-link admission prevents an A~B~C bridge from joining
            # A and C when those two headlines are incompatible events.
            if all(similarity > 0.0 for similarity in similarities):
                similarity = min(similarities)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_index = index
        if best_index is None or best_similarity <= 0.0:
            grouped.append([record])
        else:
            grouped[best_index].append(record)

    clusters: list[TopicCluster] = []
    evidence_fingerprints: dict[str, str] = {}
    for group in grouped:
        representative = min(
            group,
            key=lambda item: (normalize_text(item.title), item.title, item.evidence_id),
        )
        fingerprint = event_fingerprint(representative.title)
        cluster_id = _opaque_id("cluster", fingerprint)
        evidence_ids = sorted(item.evidence_id for item in group)
        platforms = sorted({item.platform for item in group})
        score = _cluster_score(group, platforms)
        clusters.append(
            TopicCluster(
                cluster_id=cluster_id,
                event_fingerprint=fingerprint,
                representative_title=representative.title,
                evidence_ids=evidence_ids,
                platforms=platforms,
                score=score,
            )
        )
        evidence_fingerprints.update({item.evidence_id: fingerprint for item in group})

    clusters.sort(key=lambda item: (-item.score, item.event_fingerprint, item.cluster_id))
    clustered = [
        replace(record, event_fingerprint=evidence_fingerprints[record.evidence_id])
        for record in evidence
    ]
    return clustered, clusters


def find_clusters_for_titles(
    titles: Iterable[str],
    evidence: Sequence[EvidenceRecord],
    clusters: Sequence[TopicCluster],
) -> list[TopicCluster]:
    """Resolve exact sample titles to their event clusters without guessing."""
    by_title: dict[str, set[str]] = {}
    for record in evidence:
        title = normalize_text(record.title)
        if title:
            by_title.setdefault(title, set()).add(record.evidence_id)
    by_evidence_id = {
        evidence_id: cluster
        for cluster in clusters
        for evidence_id in cluster.evidence_ids
    }
    cluster_ids: set[str] = set()
    for title in titles:
        if not isinstance(title, str):
            continue
        for evidence_id in by_title.get(normalize_text(title), set()):
            cluster = by_evidence_id.get(evidence_id)
            if cluster is not None:
                cluster_ids.add(cluster.cluster_id)
    return [cluster for cluster in clusters if cluster.cluster_id in cluster_ids]


def select_recommended_angles(
    candidates: Sequence[Mapping[str, Any]],
    clusters: Sequence[TopicCluster],
    *,
    max_recommendations: int = 6,
    history_records: Sequence[Mapping[str, Any]] | None = None,
    scan_date: str | None = None,
    history_days: int = 14,
) -> list[dict[str, Any]]:
    """Validate, novelty-filter, and diversify content-angle candidates.

    Event support is a hard constraint: candidates without a known cluster and
    at least one source observation never become a recommendation.  The final
    selector uses a small MMR penalty, plus a hard one-angle-per-event rule.
    """
    if max_recommendations <= 0:
        return []

    clusters_by_id = {cluster.cluster_id: cluster for cluster in clusters}
    recent_history = _recent_history_records(
        history_records or [],
        scan_date=scan_date,
        history_days=history_days,
    )
    prepared: list[dict[str, Any]] = []
    for candidate in candidates:
        cluster_id = candidate.get("cluster_id")
        if not isinstance(cluster_id, str):
            continue
        cluster = clusters_by_id.get(cluster_id)
        if cluster is None:
            continue
        angle = candidate.get("angle")
        if not isinstance(angle, str) or not normalize_text(angle):
            continue
        vertical = candidate.get("vertical") if isinstance(candidate.get("vertical"), str) else ""
        why = candidate.get("why_discussion_likely")
        if not isinstance(why, str):
            why = candidate.get("why") if isinstance(candidate.get("why"), str) else ""
        if any(contains_unexpanded_template(value) for value in (vertical, angle, why)):
            continue
        provided_evidence_ids = candidate.get("evidence_ids")
        evidence_ids = _candidate_evidence_ids(provided_evidence_ids, cluster)
        if not evidence_ids:
            continue
        signature = angle_signature(vertical, angle)
        if _history_suppresses(cluster, signature, recent_history):
            continue
        confidence = _coerce_float(candidate.get("confidence"), default=0.5)
        base_score = max(confidence, 0.0) + cluster.score
        enriched = dict(candidate)
        enriched.update(
            {
                "cluster_id": cluster.cluster_id,
                "event_fingerprint": cluster.event_fingerprint,
                "event_title_alias": _history_title_alias(cluster.representative_title),
                "evidence_ids": evidence_ids,
                "angle_signature": signature,
                "novelty_state": "new",
                "_base_score": round(base_score, 4),
            }
        )
        prepared.append(enriched)

    selected: list[dict[str, Any]] = []
    used_clusters: set[str] = set()
    while prepared and len(selected) < max_recommendations:
        viable = [item for item in prepared if item["cluster_id"] not in used_clusters]
        if not viable:
            break
        chosen = max(
            viable,
            key=lambda item: (
                _mmr_score(item, selected),
                item["_base_score"],
                item["angle_signature"],
            ),
        )
        chosen["ranking_score"] = round(float(_mmr_score(chosen, selected)), 4)
        chosen.pop("_base_score", None)
        selected.append(chosen)
        used_clusters.add(chosen["cluster_id"])
        prepared.remove(chosen)
    return selected


def contains_unexpanded_template(value: str) -> bool:
    """Keep template syntax out of drafting-facing recommendation fields."""
    return bool(re.search(r"\{[^{}]*\}", value))


def angle_signature(vertical: str, angle: str) -> str:
    """Return a stable opaque signature for an angle wording within a vertical."""
    return _opaque_id("angle", f"{normalize_text(vertical)}|{normalize_text(angle)}")


def append_topic_history(
    output_dir: str | Path,
    scan_date: str,
    selected_angles: Sequence[Mapping[str, Any]],
) -> Path:
    """Append selected event/angle pairs without modifying earlier history."""
    path = Path(output_dir) / _TOPIC_HISTORY_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for angle in selected_angles:
        event = angle.get("event_fingerprint")
        signature = angle.get("angle_signature")
        if not isinstance(event, str) or not isinstance(signature, str):
            continue
        lines.append(
            json.dumps(
                {
                    "scan_date": scan_date,
                    "event_fingerprint": event,
                    "event_title_alias": angle.get("event_title_alias", ""),
                    "angle_signature": signature,
                    "cluster_id": angle.get("cluster_id", ""),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    if lines:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    return path


def read_recent_topic_history(
    output_dir: str | Path,
    scan_date: str,
    *,
    history_days: int = 14,
) -> list[dict[str, Any]]:
    """Read valid history rows inside the requested rolling cooldown window."""
    path = Path(output_dir) / _TOPIC_HISTORY_FILENAME
    if not path.exists() or history_days <= 0:
        return []
    reference = _parse_date(scan_date)
    if reference is None:
        return []
    cutoff = reference - timedelta(days=history_days)
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        stored_date = _parse_date(row.get("scan_date"))
        if stored_date is None or not cutoff <= stored_date <= reference:
            continue
        if not isinstance(row.get("event_fingerprint"), str) or not isinstance(
            row.get("angle_signature"), str
        ):
            continue
        rows.append(row)
    return rows


def _event_title_similarity(first: str, second: str, *, threshold: float) -> float:
    canonical_first = normalize_text(first)
    canonical_second = normalize_text(second)
    if not canonical_first or not canonical_second:
        return 0.0
    if canonical_first == canonical_second:
        return 1.0
    if _has_conflicting_title_slots(canonical_first, canonical_second):
        return 0.0
    meaningful_first = _meaningful_bigrams(canonical_first)
    meaningful_second = _meaningful_bigrams(canonical_second)
    shared = meaningful_first & meaningful_second
    if len(shared) < 2:
        return 0.0
    union = meaningful_first | meaningful_second
    overlap = len(shared) / len(union) if union else 0.0
    sequence = SequenceMatcher(None, canonical_first, canonical_second).ratio()
    if sequence < threshold or overlap < 0.20:
        return 0.0
    return round((sequence * 0.65) + (overlap * 0.35), 4)


def _has_conflicting_title_slots(first: str, second: str) -> bool:
    """Reject same-frame headlines that swap the central claim/object.

    A short public-figure frame such as ``张三回应…传闻`` can score highly
    despite describing mutually exclusive subjects.  An aligned long prefix
    plus two competing unmatched spans is a conservative contradiction cue;
    ordinary paraphrases such as inserted qualifiers do not meet it.
    """
    if _has_incompatible_event_terms(first, second):
        return True

    matcher = SequenceMatcher(None, first, second)
    blocks = [block for block in matcher.get_matching_blocks() if block.size]
    if not blocks:
        return False
    prefix = blocks[0].size if blocks[0].a == 0 and blocks[0].b == 0 else 0
    if prefix < 4:
        return False
    unmatched_first, unmatched_second = _unmatched_title_text(first, second, blocks)
    if not unmatched_first or not unmatched_second:
        return False
    return len(unmatched_first) <= 6 and len(unmatched_second) <= 6


def _has_incompatible_event_terms(first: str, second: str) -> bool:
    """Detect explicit competing event subjects before fuzzy title matching."""
    for slots in _CONFLICTING_EVENT_TERM_SLOT_GROUPS:
        first_slots = {
            index
            for index, aliases in enumerate(slots)
            if any(alias in first for alias in aliases)
        }
        second_slots = {
            index
            for index, aliases in enumerate(slots)
            if any(alias in second for alias in aliases)
        }
        if first_slots and second_slots and first_slots.isdisjoint(second_slots):
            return True
    return False


def _unmatched_title_text(
    first: str,
    second: str,
    blocks: Sequence[Any],
) -> tuple[str, str]:
    first_cursor = 0
    second_cursor = 0
    first_parts: list[str] = []
    second_parts: list[str] = []
    for block in blocks:
        first_parts.append(first[first_cursor:block.a])
        second_parts.append(second[second_cursor:block.b])
        first_cursor = block.a + block.size
        second_cursor = block.b + block.size
    first_parts.append(first[first_cursor:])
    second_parts.append(second[second_cursor:])
    return "".join(first_parts), "".join(second_parts)


def _meaningful_bigrams(title: str) -> set[str]:
    return {
        title[index : index + 2]
        for index in range(max(len(title) - 1, 0))
        if title[index : index + 2] not in _GENERIC_EVENT_NGRAMS
    }


def _cluster_score(group: Sequence[EvidenceRecord], platforms: Sequence[str]) -> float:
    heat = sum(max(record.normalized_heat, 0.0) for record in group)
    platform_bonus = max(len(platforms) - 1, 0) * 0.35
    evidence_bonus = max(len(group) - 1, 0) * 0.08
    return round(heat + platform_bonus + evidence_bonus, 4)


def _opaque_id(prefix: str, value: str) -> str:
    digest = sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def _candidate_evidence_ids(value: object, cluster: TopicCluster) -> list[str]:
    if value is None:
        return list(cluster.evidence_ids)
    if not isinstance(value, (list, tuple, set)):
        return []
    ids = sorted({item for item in value if isinstance(item, str)})
    if not ids or not set(ids).issubset(cluster.evidence_ids):
        return []
    return ids


def _recent_history_records(
    records: Sequence[Mapping[str, Any]],
    *,
    scan_date: str | None,
    history_days: int,
) -> list[Mapping[str, Any]]:
    if history_days <= 0:
        return []
    reference = _parse_date(scan_date) if scan_date else None
    cutoff = reference - timedelta(days=history_days) if reference else None
    recent: list[Mapping[str, Any]] = []
    for record in records:
        event = record.get("event_fingerprint")
        signature = record.get("angle_signature")
        if not isinstance(event, str) or not isinstance(signature, str):
            continue
        stored_date = _parse_date(record.get("scan_date"))
        if reference and (stored_date is None or cutoff is None or not cutoff <= stored_date <= reference):
            continue
        recent.append(record)
    return recent


def _history_suppresses(
    cluster: TopicCluster,
    angle_signature_value: str,
    records: Sequence[Mapping[str, Any]],
) -> bool:
    for record in records:
        if record.get("angle_signature") != angle_signature_value:
            continue
        if record.get("event_fingerprint") == cluster.event_fingerprint:
            return True
        alias = record.get("event_title_alias")
        if isinstance(alias, str) and _event_title_similarity(
            cluster.representative_title,
            alias,
            threshold=0.58,
        ) > 0.0:
            return True
    return False


def _history_title_alias(title: str) -> str:
    """Persist only the public, normalized event wording required for cooldown."""
    return normalize_text(title)


def _parse_date(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _coerce_float(value: object, *, default: float) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return default


def _mmr_score(candidate: Mapping[str, Any], selected: Sequence[Mapping[str, Any]]) -> float:
    angle = candidate.get("angle") if isinstance(candidate.get("angle"), str) else ""
    penalty = max(
        (_angle_text_similarity(angle, item.get("angle", "")) for item in selected),
        default=0.0,
    )
    return float(candidate["_base_score"]) - (0.15 * penalty)


def _angle_text_similarity(first: str, second: object) -> float:
    if not isinstance(second, str):
        return 0.0
    first_tokens = _meaningful_bigrams(normalize_text(first))
    second_tokens = _meaningful_bigrams(normalize_text(second))
    if not first_tokens or not second_tokens:
        return 0.0
    return len(first_tokens & second_tokens) / len(first_tokens | second_tokens)


def _normalized_item(
    item: TrendingItem,
    platform: str,
    *,
    fallback_observation_key: str,
) -> TrendingItem:
    metadata = dict(item.metadata)
    metadata["matched_queries"] = _merge_query_terms(_query_terms(item))
    metadata["source_observation_count"] = _source_observation_count(item)
    if _needs_conservative_xhs_identity(item, platform):
        metadata.setdefault("_evidence_observation_key", fallback_observation_key)
    return replace(item, platform=platform, metadata=metadata)


def _xhs_title_author_alias(item: TrendingItem) -> str | None:
    """Return the safe visible-identity bridge for a complete XHS title/author."""
    title = normalize_text(item.title)
    author = normalize_text(item.metadata.get("author"))
    if not title or not author:
        return None
    return f"xiaohongshu:title:{title}:{author}"


def _merge_observation(existing: TrendingItem, observed: TrendingItem) -> None:
    """Merge query provenance and keep the strongest deterministic fields."""
    existing.rank = min(existing.rank, observed.rank)
    existing.hot_score = max(existing.hot_score, observed.hot_score)
    if not existing.label:
        existing.label = observed.label
    if not existing.url:
        existing.url = observed.url
    for key, value in observed.metadata.items():
        if key == "matched_queries":
            continue
        if key not in existing.metadata or existing.metadata[key] in (None, "", 0, False):
            existing.metadata[key] = value
    existing.metadata["matched_queries"] = _merge_query_terms(
        _query_terms(existing), _query_terms(observed)
    )
    existing.metadata["source_observation_count"] = (
        _source_observation_count(existing) + _source_observation_count(observed)
    )


def _build_evidence(
    canonical: dict[str, list[TrendingItem]],
    observation_counts: dict[tuple[str, str], int],
) -> list[EvidenceRecord]:
    evidence: list[EvidenceRecord] = []
    for platform in sorted(canonical):
        items = canonical[platform]
        max_heat = max((max(item.hot_score, 0) for item in items), default=0)
        for item in items:
            identity = source_identity(item, platform=platform)
            normalized_heat = round(max(item.hot_score, 0) / max_heat, 4) if max_heat else 0.0
            evidence.append(
                EvidenceRecord(
                    evidence_id=f"evidence:{sha256(identity.encode('utf-8')).hexdigest()[:16]}",
                    source_identity=identity,
                    platform=platform,
                    title=item.title,
                    canonical_title=normalize_text(item.title),
                    event_fingerprint=event_fingerprint(item.title),
                    hot_score=item.hot_score,
                    normalized_heat=normalized_heat,
                    matched_queries=_merge_query_terms(_query_terms(item)),
                    source_observation_count=max(
                        observation_counts.get((platform, identity), 1),
                        _source_observation_count(item),
                    ),
                )
            )
    return evidence


def _query_terms(item: TrendingItem) -> list[str]:
    values: list[object] = []
    for key in ("matched_queries", "keywords", "keyword"):
        value = item.metadata.get(key)
        if isinstance(value, (list, tuple, set)):
            values.extend(value)
        else:
            values.append(value)
    return [value for value in values if isinstance(value, str) and value.strip()]


def _merge_query_terms(*groups: Iterable[str]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for value in group:
            term = value.strip()
            normalized = normalize_text(term)
            if normalized and normalized not in seen:
                terms.append(term)
                seen.add(normalized)
    return terms


def _needs_conservative_xhs_identity(item: TrendingItem, platform: str) -> bool:
    if platform != "xiaohongshu":
        return False
    feed_id = item.metadata.get("feed_id")
    if isinstance(feed_id, str) and feed_id.strip():
        return False
    if normalize_text(item.metadata.get("author")):
        return False
    return not item.url.strip()


def _source_observation_count(item: TrendingItem) -> int:
    value = item.metadata.get("source_observation_count")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return 1
