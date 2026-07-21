from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
import re
from pathlib import Path
from typing import Any, Protocol, Sequence

from ptsm.config.settings import Settings
from ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher import (
    LangChainMcpToolRunner,
    McpToolRunner,
)
from ptsm.infrastructure.reddit.client import (
    RedditAccessConfig,
    RedditClient,
    RedditDiscussion,
    RedditPublicJsonClient,
    RedditPublicJsonConfig,
)
from ptsm.playbooks.registry import PlaybookDefinition
from ptsm.skills.loader import LoadedSkill
from topic_radar.analysis.evidence import (
    SOURCE_PROVENANCE_FIELD_NAMES,
    contains_raw_source_provenance,
    normalized_source_keys,
    source_provenance_keys,
)

_WEEKDAY_TOKENS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
_WORK_CUES = ("老板", "领导", "工位", "下班", "上班", "需求", "开会", "会议", "群里", "打工")
_OVERTIME_CUES = ("下班", "需求", "加班", "临时", "今晚", "初稿", "工位", "微信", "群里")
_POETRY_CUES = (
    "古诗词",
    "诗词",
    "诗词金句",
    "经典诗句",
    "金句",
    "李白",
    "李清照",
    "王维",
    "杜甫",
    "长风破浪",
    "苏轼",
    "定风波",
    "赤壁赋",
    "水调歌头",
)
_REDDIT_AI_TERMS = (
    "ai",
    "openai",
    "chatgpt",
    "claude",
    "llm",
    "agent",
    "agents",
    "model",
    "automation",
    "workflow",
    "gpt",
)
_REDDIT_PSYCHOLOGY_TERMS = (
    "psychology",
    "therapist",
    "therapy",
    "burnout",
    "anxiety",
    "overwhelmed",
    "notification",
    "attention",
    "mental",
    "relationship",
    "lonely",
    "stress",
    "work",
)


class RuntimeContextBuilder(Protocol):
    """Build dynamic skill context for a planner pass."""

    def build(
        self,
        *,
        scene: str,
        domain: str,
        playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        """Return dynamic context text or `None` when unavailable."""


class RedditDiscussionProvider(Protocol):
    """Read-only provider used by the Reddit runtime context builder."""

    def fetch_posts(
        self,
        *,
        subreddits: list[str],
        sorts: list[str],
        time_filter: str,
        limit_per_listing: int,
    ) -> list[RedditDiscussion]:
        """Return normalized Reddit posts."""


@dataclass(frozen=True)
class TrendHit:
    keyword: str
    title: str
    author: str
    likes: int
    comments: int
    shares: int
    collects: int

    @property
    def score(self) -> int:
        return self.likes + (self.comments * 4) + (self.shares * 6) + (self.collects * 2)


@dataclass(frozen=True)
class ContentMechanic:
    label: str
    description: str
    signal_title: str


@dataclass(frozen=True)
class FormatPatternContext:
    lane: str
    pattern_ids: list[str]
    hook_archetypes: list[str]
    body_structures: list[str]
    image_sequences: list[list[str]]
    freshness: str
    source_artifact_path: str
    status: str
    primary_ratio: str = ""


class SkillContextResolver:
    """Resolve dynamic context blocks for activated skills."""

    def __init__(self, *, builders: dict[str, RuntimeContextBuilder] | None = None) -> None:
        self._builders = builders or {}

    def resolve(
        self,
        *,
        state: dict[str, Any],
        playbook: PlaybookDefinition,
        loaded_skills: Sequence[LoadedSkill],
    ) -> dict[str, str]:
        contexts: dict[str, str] = {}
        keyword_hints = list(playbook.trend_keywords) if playbook.trend_keywords else None
        for loaded_skill in loaded_skills:
            if (
                loaded_skill.skill.skill_name == "topic_research"
                and _has_topic_radar_selection(state)
            ):
                # run-playbook already performed the explicit fresh scan and
                # converted the chosen angle into the scene. Re-running the
                # topic builder here would either launch a second scan or add
                # a competing live direction to the same draft.
                continue
            builder = self._builders.get(loaded_skill.skill.skill_name)
            if builder is None:
                continue
            context = builder.build(
                scene=state["scene"],
                domain=playbook.domain,
                playbook_id=playbook.playbook_id,
                keyword_hints=keyword_hints,
                fresh_topic_research=bool(state.get("fresh_topic_research", False)),
            )
            if context:
                contexts[loaded_skill.skill.skill_name] = context
                if hasattr(builder, "last_selection") and builder.last_selection:  # type: ignore[union-attr]
                    state["selected_topic_angle"] = builder.last_selection  # type: ignore[union-attr]
        return contexts


def _has_topic_radar_selection(state: dict[str, Any]) -> bool:
    selection = state.get("topic_selection")
    return isinstance(selection, dict) and selection.get("source") == "topic-radar"


class RedditDiscussionContextBuilder:
    """Build runtime context from current English Reddit discussions."""

    def __init__(
        self,
        *,
        client: RedditDiscussionProvider | None,
        credentials_configured: bool = True,
        access_mode: str = "oauth",
        subreddits: list[str] | None = None,
        sorts: list[str] | None = None,
        time_filter: str = "day",
        limit_per_listing: int = 12,
    ) -> None:
        self.client = client
        self.credentials_configured = credentials_configured
        self.access_mode = access_mode
        self.subreddits = subreddits or [
            "OpenAI",
            "ChatGPT",
            "ClaudeAI",
            "psychology",
            "AskPsychology",
        ]
        self.sorts = sorts or ["hot", "top"]
        self.time_filter = time_filter
        self.limit_per_listing = limit_per_listing

    @classmethod
    def from_settings(cls, settings: Settings) -> "RedditDiscussionContextBuilder":
        usable_user_agent = _is_usable_reddit_user_agent(settings.reddit_user_agent)
        configured = bool(
            settings.reddit_client_id
            and settings.reddit_client_secret
            and usable_user_agent
        )
        public_json_configured = (
            settings.reddit_public_json_fallback
            and usable_user_agent
        )
        client: RedditClient | RedditPublicJsonClient | None = None
        access_mode = "missing"
        if configured:
            client = RedditClient(
                config=RedditAccessConfig(
                    client_id=str(settings.reddit_client_id),
                    client_secret=str(settings.reddit_client_secret),
                    user_agent=settings.reddit_user_agent,
                )
            )
            access_mode = "oauth"
        elif public_json_configured:
            client = RedditPublicJsonClient(
                config=RedditPublicJsonConfig(
                    user_agent=settings.reddit_user_agent,
                )
            )
            access_mode = "public_json"
        return cls(
            client=client,
            credentials_configured=configured or public_json_configured,
            access_mode=access_mode,
            subreddits=_split_csv(settings.reddit_subreddits),
            sorts=_split_csv(settings.reddit_sorts),
            time_filter=settings.reddit_time_filter,
            limit_per_listing=settings.reddit_limit_per_listing,
        )

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        if not self.credentials_configured or self.client is None:
            return _render_reddit_missing_credentials_context()
        try:
            posts = self.client.fetch_posts(
                subreddits=self.subreddits,
                sorts=self.sorts,
                time_filter=self.time_filter,
                limit_per_listing=self.limit_per_listing,
            )
        except Exception as exc:
            return _render_reddit_unavailable_context(str(exc))

        selected = _select_reddit_discussions(posts, scene=scene)
        if not selected:
            return _render_reddit_unavailable_context(
                "no AI or psychology discussion candidates returned"
            )
        return _render_reddit_discussion_context(
            posts=selected,
            subreddits=self.subreddits,
            sorts=self.sorts,
            time_filter=self.time_filter,
            access_mode=self.access_mode,
        )


class XhsTrendScanContextBuilder:
    """Live XiaoHongShu trend scan for the `xhs_trend_scan` builtin skill."""

    def __init__(
        self,
        *,
        server_url: str,
        tool_runner: McpToolRunner | None = None,
        timeout_seconds: float = 4.0,
    ) -> None:
        self.server_url = server_url
        self.tool_runner = tool_runner or LangChainMcpToolRunner(server_url=server_url)
        self.timeout_seconds = timeout_seconds

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        try:
            return asyncio.run(
                asyncio.wait_for(
                    self._build_async(
                        scene=scene,
                        domain=domain,
                        playbook_id=playbook_id,
                        keyword_hints=keyword_hints,
                    ),
                    timeout=self.timeout_seconds,
                )
            )
        except RuntimeError as exc:
            if "asyncio.run()" in str(exc):
                raise
            return None
        except Exception:
            return None

    async def _build_async(
        self,
        *,
        scene: str,
        domain: str,
        playbook_id: str,
        keyword_hints: list[str] | None = None,
    ) -> str | None:
        tool_names = await self.tool_runner.list_tool_names()
        if "check_login_status" not in tool_names or "search_feeds" not in tool_names:
            return None

        login_payload = await self.tool_runner.invoke_tool("check_login_status", {})
        login_text = _extract_text(login_payload).strip()
        if "已登录" not in login_text or "未登录" in login_text:
            return None

        keywords = _derive_keywords(scene=scene, domain=domain, playbook_id=playbook_id, hints=keyword_hints)
        if not keywords:
            return None

        hits: list[TrendHit] = []
        for keyword in keywords:
            payload = await self.tool_runner.invoke_tool("search_feeds", {"keyword": keyword})
            hits.extend(_parse_trend_hits(payload=payload, keyword=keyword))

        if not hits:
            return None

        return _render_trend_context(scene=scene, keywords=keywords, hits=hits)


class XhsPatternContextBuilder:
    """Load approved/candidate XHS format patterns from a local snapshot."""

    def __init__(
        self,
        *,
        pattern_path: Path | str = "outputs/artifacts/xhs-pattern-library/current.json",
        stale_after_days: int = 14,
    ) -> None:
        self.pattern_path = Path(pattern_path)
        self.stale_after_days = stale_after_days

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        context = self.load_context(playbook_id=playbook_id, domain=domain)
        if context is None or not context.pattern_ids:
            return None
        return _render_format_pattern_context(context)

    def load_context(self, *, playbook_id: str, domain: str) -> FormatPatternContext | None:
        if not self.pattern_path.exists():
            return None
        try:
            data = json.loads(self.pattern_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        lane = _lane_for_playbook(playbook_id=playbook_id, domain=domain)
        if str(data.get("lane") or "") != lane:
            return None
        patterns = [
            item for item in data.get("patterns", [])
            if isinstance(item, dict) and item.get("status") in {"approved", "candidate"}
        ][:4]
        if not patterns:
            return None
        created_at = str(data.get("created_at") or "")
        freshness = _freshness_status(created_at, stale_after_days=self.stale_after_days)
        return FormatPatternContext(
            lane=lane,
            pattern_ids=[str(item.get("pattern_id")) for item in patterns if item.get("pattern_id")],
            hook_archetypes=[str(item.get("title_hook")) for item in patterns if item.get("title_hook")],
            body_structures=[
                str(item.get("body_structure")) for item in patterns if item.get("body_structure")
            ],
            image_sequences=[
                [str(part) for part in item.get("image_sequence", [])]
                for item in patterns
                if isinstance(item.get("image_sequence"), list)
            ],
            freshness=freshness,
            source_artifact_path=str(data.get("source_snapshot") or self.pattern_path),
            status=str(data.get("status") or "available"),
            primary_ratio=_dominant_pattern_ratio(patterns),
        )


class PatternAwareXhsTrendContextBuilder:
    """Use the local pattern library for normal runs and live MCP only on fresh research."""

    def __init__(
        self,
        *,
        pattern_builder: XhsPatternContextBuilder,
        live_builder: XhsTrendScanContextBuilder,
    ) -> None:
        self.pattern_builder = pattern_builder
        self.live_builder = live_builder

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        pattern_context = self.pattern_builder.build(
            scene=scene,
            domain=domain,
            playbook_id=playbook_id,
            keyword_hints=keyword_hints,
            fresh_topic_research=fresh_topic_research,
        )
        if pattern_context:
            return pattern_context
        if not fresh_topic_research:
            return None
        return self.live_builder.build(
            scene=scene,
            domain=domain,
            playbook_id=playbook_id,
            keyword_hints=keyword_hints,
            fresh_topic_research=fresh_topic_research,
        )


class PatternAwareTopicResearchContextBuilder:
    """Append local XHS format patterns to topic research context when available."""

    def __init__(
        self,
        *,
        topic_builder: TopicResearchContextBuilder,
        pattern_builder: XhsPatternContextBuilder,
    ) -> None:
        self.topic_builder = topic_builder
        self.pattern_builder = pattern_builder

    @property
    def last_selection(self) -> dict[str, Any] | None:
        return self.topic_builder.last_selection

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        topic_context = self.topic_builder.build(
            scene=scene,
            domain=domain,
            playbook_id=playbook_id,
            keyword_hints=keyword_hints,
            fresh_topic_research=fresh_topic_research,
        )
        pattern_context = self.pattern_builder.build(
            scene=scene,
            domain=domain,
            playbook_id=playbook_id,
            keyword_hints=keyword_hints,
            fresh_topic_research=fresh_topic_research,
        )
        if topic_context and pattern_context:
            return f"{topic_context}\n\n{pattern_context}"
        return topic_context or pattern_context


class TopicResearchContextBuilder:
    """Read topic-radar artifact and inject topic suggestions for the `topic_research` skill."""

    def __init__(
        self,
        *,
        artifact_dir: str = "outputs/artifacts",
        allow_fresh_scan: bool = True,
    ) -> None:
        self._artifact_dir = Path(artifact_dir)
        self._allow_fresh_scan = allow_fresh_scan
        self._last_selection: dict[str, Any] | None = None

    @property
    def last_selection(self) -> dict[str, Any] | None:
        return self._last_selection

    def build(
        self, *, scene: str, domain: str, playbook_id: str,
        keyword_hints: list[str] | None = None,
        fresh_topic_research: bool = False,
    ) -> str | None:
        try:
            self._last_selection = None
            # A Topic Radar artifact is evidence from a particular scan, not
            # a reusable ambient prompt source. Ordinary runs stay on local
            # patterns, and local-only resolvers cannot prove an on-disk
            # artifact belongs to this fresh request.
            if not fresh_topic_research or not self._allow_fresh_scan:
                return None

            scan_result = _run_topic_radar_scan(str(self._artifact_dir))
            artifact_path = _scan_artifact_path(scan_result)
            # A fresh request has to name the artifact written by that exact
            # scan. Falling back to today's conventional filename could turn a
            # previous scan into fake fresh evidence, so missing/unreadable
            # receipts fail closed.
            if artifact_path is None or not artifact_path.is_file():
                return None
            data = json.loads(artifact_path.read_text(encoding="utf-8"))

            _merge_scan_diagnostics(
                data,
                scan_result=scan_result,
                artifact_path=artifact_path,
            )
            if _is_insufficient_evidence(data):
                return None

            if self._is_domain_hint(scene):
                # Domain mode: select angle from topic-radar, construct scene
                return self._build_with_angle_selection(
                    scene,
                    data,
                    require_evidence=True,
                )
            else:
                # Scene mode: user provided specific scene, use topic-radar as supplement
                return _render_topic_research_context(
                    data,
                    evidence_backed_only=True,
                )
        except Exception:
            return None

    def _is_domain_hint(self, scene: str) -> bool:
        """A short, non-specific scene is treated as a domain filter."""
        return len(scene) < 20 and not any(
            cue in scene for cue in ("今天", "昨天", "刚才", "路上", "工位", "回家", "开会", "地铁", "我")
        )

    def _build_with_angle_selection(
        self,
        scene: str,
        data: dict[str, Any],
        *,
        require_evidence: bool = False,
    ) -> str | None:
        """Render one safe selected angle without copying source provenance."""
        evidence_catalog = _topic_evidence_catalog(data)
        angles = _safe_recommended_angles(
            data.get("recommended_angles"),
            require_evidence=require_evidence,
            evidence_catalog=evidence_catalog,
        )
        verticals = data.get("discovered_verticals", [])

        if not angles and not verticals:
            return None

        selected = _pick_best_angle(
            scene,
            angles,
            verticals if not require_evidence else [],
            evidence_catalog=evidence_catalog,
        )
        if selected is None:
            return None

        raw_scene = _angle_to_scene(selected)
        lines = [
            "# Topic Research — Selected Angle",
            "",
            f"## 选定选题方向：{selected.get('vertical', '')}",
            f"**选题角度**: {selected.get('angle', '')}",
            f"**讨论诱因**: {selected.get('why_discussion_likely', '')}",
            f"**构造场景**: {raw_scene}",
            "",
            "你将以这个场景为出发点撰写内容。场景是选题角度的具体化，保持角度核心不变。",
            "约束：以选定角度为核心，将场景展开为具体故事。不要复写报告原文。",
        ]
        # Preserve only opaque traceability in state/artifacts. Never render
        # it (or any raw source field) into a drafting context.
        self._last_selection = _selection_traceability(
            selected,
            data,
            constructed_scene=raw_scene,
        )
        return "\n".join(lines)


def run_topic_radar_scan(output_dir: str | Path) -> dict[str, Any]:
    """Use Topic Radar's public full-platform scan API for fresh research.

    ``platforms`` is deliberately omitted. Topic Radar's configuration owns
    the supported eight-platform default; PTSM only supplies an artifact
    destination for the explicit fresh-research path.
    """
    from topic_radar.cli import run_scan

    result = asyncio.run(run_scan(output_dir=str(output_dir)))
    return _topic_radar_scan_receipt(result)


def _run_topic_radar_scan(output_dir: str) -> dict[str, Any]:
    """Compatibility wrapper for the runtime builder and its unit tests."""
    return run_topic_radar_scan(output_dir)


_TOPIC_TRACEABILITY_FIELDS = (
    "cluster_id",
    "angle_signature",
    "event_fingerprint",
    "evidence_ids",
)


@dataclass(frozen=True)
class TopicEvidenceCatalog:
    """The opaque evidence relationship catalog carried by a Topic Radar artifact."""

    evidence_event_fingerprints: dict[str, str]
    evidence_title_keys: frozenset[str]
    raw_provenance_keys: frozenset[str]
    cluster_evidence_ids: dict[str, frozenset[str]]
    cluster_event_fingerprints: dict[str, str]


def _topic_radar_scan_receipt(result: object) -> dict[str, Any]:
    """Normalize the public result without copying raw source rows into PTSM."""
    return {
        "scan_summary": _topic_text(_topic_field(result, "scan_summary")),
        "scan_date": _topic_text(_topic_field(result, "scan_date")),
        "platforms": _topic_string_list(_topic_field(result, "platforms")),
        # PTSM fresh drafting only accepts a Topic Radar angle when the
        # public result attached evidence IDs.  Verticals are diagnostic
        # material (and can contain raw sample headlines), so they stay in
        # the topic-radar artifact rather than becoming selectable here.
        "verticals": [],
        "recommended_angles": _safe_recommended_angles(
            _topic_field(result, "recommended_angles"),
            require_evidence=True,
            evidence_catalog=_topic_evidence_catalog(result),
        ),
        "noise_topics": _topic_string_list(_topic_field(result, "noise_topics")),
        "scan_quality": _topic_text(_topic_field(result, "scan_quality")),
        "platform_errors": _topic_error_map(_topic_field(result, "platform_errors")),
        "artifact_path": _topic_path(_topic_field(result, "artifact_path")),
        "report_path": _topic_path(_topic_field(result, "report_path")),
    }


def _topic_field(value: object, key: str) -> object:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _topic_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list | tuple) else []


def _topic_text(value: object) -> str:
    if hasattr(value, "value"):
        value = getattr(value, "value")
    return value.strip() if isinstance(value, str) else ""


def _topic_number(value: object, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _topic_string_list(value: object) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _topic_error_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(platform): detail.strip()
        for platform, detail in value.items()
        if isinstance(platform, str) and isinstance(detail, str) and detail.strip()
    }


def _topic_path(value: object) -> str:
    return str(value) if isinstance(value, str | Path) and str(value) else ""


def _topic_trace_value(field: str, value: object) -> str | list[str]:
    if field == "evidence_ids":
        return _topic_string_list(value)
    return _topic_text(value)


def _topic_evidence_catalog(source: object) -> TopicEvidenceCatalog:
    evidence_event_fingerprints: dict[str, str] = {}
    evidence_rows = _topic_list(_topic_field(source, "evidence"))
    raw_trending_rows = _topic_list(_topic_field(source, "raw_trending"))
    for row in evidence_rows:
        evidence_id = _topic_text(_topic_field(row, "evidence_id"))
        if evidence_id:
            evidence_event_fingerprints[evidence_id] = _topic_text(
                _topic_field(row, "event_fingerprint")
            )
    source_rows = [*evidence_rows, *raw_trending_rows]
    evidence_title_keys = normalized_source_keys(
        _topic_field(row, field)
        for row in source_rows
        for field in ("title", "canonical_title", "source_title")
    )
    raw_provenance_keys = source_provenance_keys(
        {
            field: _topic_field(row, field)
            for field in SOURCE_PROVENANCE_FIELD_NAMES
        }
        for row in source_rows
    )

    cluster_evidence_ids: dict[str, frozenset[str]] = {}
    cluster_event_fingerprints: dict[str, str] = {}
    for row in _topic_list(_topic_field(source, "topic_clusters")):
        cluster_id = _topic_text(_topic_field(row, "cluster_id"))
        if not cluster_id:
            continue
        cluster_evidence_ids[cluster_id] = frozenset(
            _topic_string_list(_topic_field(row, "evidence_ids"))
        )
        cluster_event_fingerprints[cluster_id] = _topic_text(
            _topic_field(row, "event_fingerprint")
        )

    return TopicEvidenceCatalog(
        evidence_event_fingerprints=evidence_event_fingerprints,
        evidence_title_keys=evidence_title_keys,
        raw_provenance_keys=raw_provenance_keys,
        cluster_evidence_ids=cluster_evidence_ids,
        cluster_event_fingerprints=cluster_event_fingerprints,
    )


def _angle_has_catalogued_evidence(
    candidate: object,
    *,
    evidence_ids: list[str],
    catalog: TopicEvidenceCatalog | None,
) -> bool:
    """Require an angle's opaque evidence IDs to belong to its real cluster."""
    if catalog is None or not evidence_ids:
        return False

    cluster_id = _topic_text(_topic_field(candidate, "cluster_id"))
    cluster_evidence_ids = catalog.cluster_evidence_ids.get(cluster_id)
    if not cluster_id or not cluster_evidence_ids:
        return False

    selected_ids = frozenset(evidence_ids)
    if not selected_ids.issubset(cluster_evidence_ids):
        return False
    if not selected_ids.issubset(catalog.evidence_event_fingerprints):
        return False

    cluster_event = catalog.cluster_event_fingerprints.get(cluster_id, "")
    candidate_event = _topic_text(_topic_field(candidate, "event_fingerprint"))
    if candidate_event and candidate_event != cluster_event:
        return False
    if cluster_event and any(
        catalog.evidence_event_fingerprints[evidence_id] not in {"", cluster_event}
        for evidence_id in selected_ids
    ):
        return False
    return True


def _safe_recommended_angles(
    value: object,
    *,
    require_evidence: bool,
    evidence_catalog: "TopicEvidenceCatalog | None" = None,
) -> list[dict[str, Any]]:
    """Whitelist drafting-safe angle fields and opaque traceability only."""
    angles: list[dict[str, Any]] = []
    for candidate in _topic_list(value):
        vertical = _topic_text(_topic_field(candidate, "vertical"))
        angle = _topic_text(_topic_field(candidate, "angle"))
        if not vertical or not angle:
            continue
        evidence_ids = _topic_string_list(_topic_field(candidate, "evidence_ids"))
        if require_evidence and not _angle_has_catalogued_evidence(
            candidate,
            evidence_ids=evidence_ids,
            catalog=evidence_catalog,
        ):
            continue
        why = _topic_text(
            _topic_field(candidate, "why_discussion_likely")
            or _topic_field(candidate, "why")
        )
        if _drafting_fields_leak_raw_source(
            (vertical, angle, why),
            evidence_catalog=evidence_catalog,
        ):
            continue
        payload: dict[str, Any] = {
            "vertical": vertical,
            "angle": angle,
            "why_discussion_likely": why,
        }
        confidence = _topic_field(candidate, "confidence")
        if confidence is not None:
            payload["confidence"] = _topic_number(confidence, default=0.0)
        for field in _TOPIC_TRACEABILITY_FIELDS:
            trace = evidence_ids if field == "evidence_ids" else _topic_trace_value(
                field,
                _topic_field(candidate, field),
            )
            if trace not in ("", []):
                payload[field] = trace
        angles.append(payload)
    return angles


def _drafting_fields_leak_raw_source(
    fields: Sequence[str],
    *,
    evidence_catalog: TopicEvidenceCatalog | None,
) -> bool:
    """Reject any raw source text before it can reach drafting."""
    if evidence_catalog is None:
        return False
    return contains_raw_source_provenance(
        fields,
        source_title_keys=evidence_catalog.evidence_title_keys,
        provenance_keys=evidence_catalog.raw_provenance_keys,
    )


def _scan_artifact_path(
    scan_result: dict[str, Any] | None,
) -> Path | None:
    if isinstance(scan_result, dict):
        raw_path = scan_result.get("artifact_path")
        if isinstance(raw_path, str) and raw_path.strip():
            return Path(raw_path)
    return None


def _merge_scan_diagnostics(
    data: dict[str, Any],
    *,
    scan_result: dict[str, Any] | None,
    artifact_path: Path,
) -> None:
    if not isinstance(scan_result, dict):
        return
    for field in ("scan_quality", "platform_errors", "report_path"):
        if field not in data or data.get(field) in (None, "", {}):
            data[field] = scan_result.get(field)
    data["artifact_path"] = str(artifact_path)


def _is_insufficient_evidence(data: dict[str, Any]) -> bool:
    return _topic_text(data.get("scan_quality")) == "insufficient_evidence"


def _selection_traceability(
    selected: dict[str, Any],
    data: dict[str, Any],
    *,
    constructed_scene: str,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "source": "topic-radar",
        "vertical": _topic_text(selected.get("vertical")),
        "angle": _topic_text(selected.get("angle")),
        "why": _topic_text(selected.get("why_discussion_likely")),
        "constructed_scene": constructed_scene,
        "scan_quality": _topic_text(data.get("scan_quality")),
        "platform_errors": _topic_error_map(data.get("platform_errors")),
        "artifact_path": _topic_path(data.get("artifact_path")),
        "report_path": _topic_path(data.get("report_path")),
    }
    for field in _TOPIC_TRACEABILITY_FIELDS:
        trace = _topic_trace_value(field, selected.get(field))
        if trace not in ("", []):
            metadata[field] = trace
    return metadata


def _pick_best_angle(
    scene: str,
    angles: list[dict],
    verticals: list[dict],
    *,
    evidence_catalog: TopicEvidenceCatalog | None = None,
) -> dict | None:
    """Pick the best matching angle from topic-radar recommendations based on scene keywords."""
    if not angles:
        for vertical in verticals:
            suggested_angles = _topic_string_list(vertical.get("suggested_angles"))
            candidate = {
                "vertical": _topic_text(vertical.get("name")),
                "angle": suggested_angles[0] if suggested_angles else "",
                "why_discussion_likely": _topic_text(
                    vertical.get("discussion_density")
                ),
            }
            if not candidate["vertical"] or not candidate["angle"]:
                continue
            if _drafting_fields_leak_raw_source(
                (
                    candidate["vertical"],
                    candidate["angle"],
                    candidate["why_discussion_likely"],
                ),
                evidence_catalog=evidence_catalog,
            ):
                continue
            return candidate
        return None

    # Score each angle by keyword overlap with scene
    scene_terms = set(scene)
    best_score = 0
    best_angle = angles[0]
    for a in angles:
        vertical = a.get("vertical", "")
        angle = a.get("angle", "")
        text = f"{vertical} {angle}"
        score = sum(1 for c in scene_terms if c in text)
        if score > best_score:
            best_score = score
            best_angle = a

    return best_angle


def _angle_to_scene(selected: dict) -> str:
    """Convert a topic-radar angle into a concrete scene for the executor."""
    angle = selected.get("angle", "")
    # Strip common angle templates and extract core imagery
    scene = angle.replace("？", "，").replace("!", "，").rstrip("，。")
    return f"以'{scene}'为选题切入点，构建一个具体的个人化场景"


def _render_topic_research_context(
    data: dict[str, Any],
    *,
    evidence_backed_only: bool = False,
) -> str | None:
    if evidence_backed_only:
        angles = _safe_recommended_angles(
            data.get("recommended_angles"),
            require_evidence=True,
            evidence_catalog=_topic_evidence_catalog(data),
        )
        if not angles:
            return None
        lines = ["# Topic Research Live Context", "", "## 推荐选题角度"]
        for index, angle in enumerate(angles[:3], start=1):
            lines.append(f"{index}. [{angle['vertical']}] {angle['angle']}")
            if angle["why_discussion_likely"]:
                lines.append(f"   - 讨论诱因：{angle['why_discussion_likely']}")
        lines.extend(
            [
                "",
                "约束：只选一个角度切入，将其转化为具体场景和情绪表达，不要复写报告原文。",
            ]
        )
        return "\n".join(lines)

    evidence_catalog = _topic_evidence_catalog(data)
    angles = _safe_recommended_angles(
        data.get("recommended_angles"),
        require_evidence=False,
        evidence_catalog=evidence_catalog,
    )
    if not angles:
        angles = _safe_vertical_angles(
            data.get("discovered_verticals"),
            evidence_catalog=evidence_catalog,
        )
    if not angles:
        return None

    lines = ["# Topic Research Live Context", "", "## 推荐选题角度"]
    for index, angle in enumerate(angles[:3], start=1):
        lines.append(f"{index}. [{angle['vertical']}] {angle['angle']}")
        if angle["why_discussion_likely"]:
            lines.append(f"   - 讨论诱因：{angle['why_discussion_likely']}")
    lines.extend(
        [
            "",
            "约束：只选一个角度切入，将其转化为具体场景和情绪表达，不要复写报告原文。",
        ]
    )
    return "\n".join(lines)


def _safe_vertical_angles(
    value: object,
    *,
    evidence_catalog: TopicEvidenceCatalog | None = None,
) -> list[dict[str, str]]:
    """Fallback only to generated vertical labels, never to sample headlines."""
    angles: list[dict[str, str]] = []
    for vertical in _topic_list(value):
        name = _topic_text(_topic_field(vertical, "name"))
        suggested = _topic_string_list(_topic_field(vertical, "suggested_angles"))
        if not name or not suggested:
            continue
        why = _topic_text(_topic_field(vertical, "discussion_density"))
        if _drafting_fields_leak_raw_source(
            (name, suggested[0], why),
            evidence_catalog=evidence_catalog,
        ):
            continue
        angles.append(
            {
                "vertical": name,
                "angle": suggested[0],
                "why_discussion_likely": why,
            }
        )
    return angles


def build_skill_context_resolver(
    *,
    settings: Settings,
    xhs_tool_runner: McpToolRunner | None = None,
    pattern_path: Path | str | None = None,
) -> SkillContextResolver:
    pattern_builder = XhsPatternContextBuilder(
        pattern_path=pattern_path or settings.xhs_pattern_library_path
    )
    topic_builder = TopicResearchContextBuilder()
    return SkillContextResolver(
        builders={
            "xhs_trend_scan": PatternAwareXhsTrendContextBuilder(
                pattern_builder=pattern_builder,
                live_builder=XhsTrendScanContextBuilder(
                    server_url=settings.xhs_mcp_server_url,
                    tool_runner=xhs_tool_runner,
                ),
            ),
            "topic_research": PatternAwareTopicResearchContextBuilder(
                topic_builder=topic_builder,
                pattern_builder=pattern_builder,
            ),
            "reddit_discussion_scan": RedditDiscussionContextBuilder.from_settings(settings),
        }
    )


def _split_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _is_usable_reddit_user_agent(value: str) -> bool:
    normalized = value.strip().lower()
    return bool(normalized) and "replace-me" not in normalized


def _select_reddit_discussions(
    posts: Sequence[RedditDiscussion],
    *,
    scene: str,
    limit: int = 4,
) -> list[RedditDiscussion]:
    scored: list[tuple[int, RedditDiscussion]] = []
    for post in posts:
        fit_labels = _reddit_fit_labels(post)
        if not fit_labels:
            continue
        score = (len(fit_labels) * 10_000) + post.engagement_score
        if _scene_mentions_ai(scene) and "AI/tool anxiety" in fit_labels:
            score += 5_000
        if _scene_mentions_psychology(scene) and "psychology/life pressure" in fit_labels:
            score += 5_000
        scored.append((score, post))
    return [post for _, post in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]]


def _reddit_fit_labels(post: RedditDiscussion) -> list[str]:
    haystack = f"{post.subreddit} {post.title} {post.selftext}".lower()
    labels: list[str] = []
    if any(term in haystack for term in _REDDIT_AI_TERMS):
        labels.append("AI/tool anxiety")
    if any(term in haystack for term in _REDDIT_PSYCHOLOGY_TERMS):
        labels.append("psychology/life pressure")
    if any(term in haystack for term in ("work", "job", "productivity", "workflow", "office")):
        labels.append("workplace relevance")
    return labels


def _scene_mentions_ai(scene: str) -> bool:
    lower = scene.lower()
    return "ai" in lower or "openai" in lower or "人工智能" in scene or "模型" in scene


def _scene_mentions_psychology(scene: str) -> bool:
    lower = scene.lower()
    return "心理" in scene or "psychology" in lower or "burnout" in lower or "焦虑" in scene


def _render_reddit_missing_credentials_context() -> str:
    return "\n".join(
        [
            "# Reddit Discussion Scan Live Context",
            "- status: missing_credentials",
            "- required_env: REDDIT_USER_AGENT plus REDDIT_PUBLIC_JSON_FALLBACK=true, or REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET for OAuth.",
            "- policy: follow Reddit's Responsible Builder Policy and get explicit Reddit approval before accessing Reddit data through the API.",
            "- note: read-only Reddit scan is disabled until a non-placeholder user agent is configured for public JSON fallback or approved app-only OAuth credentials are configured.",
            "- operator_action: set REDDIT_USER_AGENT for low-volume public JSON fallback, or create a Reddit app with a transparent read-only purpose and set OAuth env vars.",
            "- 约束：未拿到实时素材时，不要声称这条内容来自最新热点；成稿不要暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。",
        ]
    )


def _render_reddit_unavailable_context(reason: str) -> str:
    return "\n".join(
        [
            "# Reddit Discussion Scan Live Context",
            "- status: unavailable",
            f"- reason: {_truncate_runtime_text(reason, 160)}",
            "- 约束：不要声称这条内容来自最新热点；可以退回常青角度，且成稿不要暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。",
        ]
    )


def _render_reddit_discussion_context(
    *,
    posts: Sequence[RedditDiscussion],
    subreddits: Sequence[str],
    sorts: Sequence[str],
    time_filter: str,
    access_mode: str = "oauth",
) -> str:
    lines = [
        "# Reddit Discussion Scan Live Context",
        "- status: available",
        f"- access_mode: {access_mode}",
        f"- fetched_at: {date.today().isoformat()}",
        f"- subreddits: {', '.join(subreddits)}",
        f"- sorts: {', '.join(sorts)}",
        f"- time_filter: {time_filter}",
        "",
        "## Selected English discussions",
    ]
    for index, post in enumerate(posts, start=1):
        fit = ", ".join(_reddit_fit_labels(post))
        lines.append(f"{index}. r/{post.subreddit} `{post.title}`")
        lines.append(
            f"   - engagement: {post.score} upvotes / {post.num_comments} comments"
            f" / ratio {post.upvote_ratio:.2f}"
        )
        lines.append(f"   - Chinese-reader fit: {fit}")
        lines.append(f"   - source_url: {post.source_url}")
        excerpt = _truncate_runtime_text(post.selftext, 180)
        if excerpt:
            lines.append(f"   - excerpt_en: {excerpt}")
    lines.extend(
        [
            "",
            "## 改写约束",
            "- 只借讨论现象和观点结构，不复写原文长段。",
            "- 用中文解释为什么这个现象适合国内读者；来源追踪只留在 artifact/runtime context。",
            "- 读者可见标题、封面、正文和标签不要出现 Reddit、subreddit、英文讨论、翻译过程或来源 URL。",
            "- 不展示 Reddit 用户名，不把网友经历写成作者亲历。",
            "- 心理相关内容不诊断、不治疗承诺；AI 相关内容不做投资建议。",
        ]
    )
    return "\n".join(lines)


def _truncate_runtime_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1].rstrip()}..."


def _derive_keywords(*, scene: str, domain: str, playbook_id: str, hints: list[str] | None = None) -> list[str]:
    keywords: list[str] = []
    if hints:
        keywords.extend(hints)
    day_token = next((token for token in _WEEKDAY_TOKENS if token in scene), None)
    is_work_scene = any(cue in scene for cue in _WORK_CUES) or domain == "发疯文学"
    is_poetry_scene = any(cue in scene for cue in _POETRY_CUES) or domain == "古诗词金句"

    if day_token:
        if day_token == "周四":
            keywords.append("怎么才周四")
        else:
            keywords.append(day_token)
        if is_work_scene and day_token not in {"周六", "周日"} and "怎么才周四" not in keywords:
            keywords.append(f"打工人 {day_token}")

    if playbook_id == "fengkuang_daily_post" or domain == "发疯文学":
        keywords.append("发疯文学 打工人")
        if any(cue in scene for cue in _OVERTIME_CUES):
            keywords.append("隐形加班")
            keywords.append("下班前 新需求")

    if is_poetry_scene:
        for cue in _POETRY_CUES:
            if cue in scene:
                keywords.append(cue)

    return _dedupe_preserve_order(keywords)[:4]


def _dedupe_preserve_order(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped


def _lane_for_playbook(*, playbook_id: str, domain: str) -> str:
    mapping = {
        "human_enrichment_daily_post": "human_enrichment",
    }
    if playbook_id in mapping:
        return mapping[playbook_id]
    normalized = re.sub(r"[^a-z0-9]+", "_", playbook_id.lower()).strip("_")
    return normalized or re.sub(r"\s+", "_", domain.strip().lower())


def _freshness_status(created_at: str, *, stale_after_days: int) -> str:
    if not created_at:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError:
        return "unknown"
    now = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return "stale" if (now - parsed).days > stale_after_days else "fresh"


def _dominant_pattern_ratio(patterns: list[dict]) -> str:
    counts: dict[str, int] = {}
    for pattern in patterns:
        ratio = str(pattern.get("cover_ratio") or "").strip()
        if ratio:
            counts[ratio] = counts.get(ratio, 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)


def _render_format_pattern_context(context: FormatPatternContext) -> str:
    image_sequences = [
        " -> ".join(sequence) for sequence in context.image_sequences[:2] if sequence
    ]
    lines = [
        "# XHS Format Pattern Library Context",
        f"- status: {context.status}",
        f"- freshness: {context.freshness}",
        f"- lane: {context.lane}",
        f"- source: {context.source_artifact_path}",
        f"- pattern_ids: {', '.join(context.pattern_ids)}",
        f"- hook_archetypes: {', '.join(context.hook_archetypes)}",
        f"- body_structures: {' | '.join(context.body_structures[:3])}",
    ]
    if image_sequences:
        lines.append(f"- image_sequences: {' | '.join(image_sequences)}")
    if context.primary_ratio:
        lines.append(f"- primary_ratio: {context.primary_ratio}")
    lines.append("- 约束：借鉴结构、节奏和互动机制，不要复写样本标题。")
    return "\n".join(lines)


def _parse_trend_hits(*, payload: object, keyword: str) -> list[TrendHit]:
    data = _extract_json_payload(payload)
    if not isinstance(data, dict):
        return []

    feeds = data.get("feeds")
    if not isinstance(feeds, list):
        return []

    hits: list[TrendHit] = []
    for item in feeds:
        if not isinstance(item, dict):
            continue
        card = item.get("noteCard")
        if not isinstance(card, dict):
            continue
        title = str(card.get("displayTitle", "")).strip()
        if not title:
            continue
        user = card.get("user")
        interact = card.get("interactInfo")
        if not isinstance(user, dict) or not isinstance(interact, dict):
            continue
        hits.append(
            TrendHit(
                keyword=keyword,
                title=title,
                author=str(user.get("nickname", "")).strip(),
                likes=_to_int(interact.get("likedCount")),
                comments=_to_int(interact.get("commentCount")),
                shares=_to_int(interact.get("sharedCount")),
                collects=_to_int(interact.get("collectedCount")),
            )
        )
    return hits


def _to_int(value: object) -> int:
    try:
        return int(str(value).replace(",", "").strip() or "0")
    except (TypeError, ValueError):
        return 0


def _render_trend_context(*, scene: str, keywords: Sequence[str], hits: Sequence[TrendHit]) -> str:
    top_hits = _top_unique_hits(hits=hits, limit=4)
    mechanics = _infer_content_mechanics(hits)
    persona_titles = [
        hit.title for hit in top_hits if hit.keyword == "发疯文学 打工人" or "打工人" in hit.title
    ]
    primary_hook = _pick_primary_hook(keywords=keywords, hits=hits)
    tension = _infer_tension(scene)
    expression_template = " / ".join(persona_titles[:2]) or "打工人发疯文学"

    lines = [
        "# XHS Trend Scan Live Context",
        "",
        f"已执行实时站内热点扫描（{date.today().isoformat()}）：",
        f"- 查询词：{', '.join(f'`{keyword}`' for keyword in keywords)}",
        "",
        "高互动表达样本：",
    ]
    for hit in top_hits:
        lines.append(
            f"- `{hit.title}` by `{hit.author or '匿名'}`"
            f"（{hit.likes}赞/{hit.comments}评/{hit.shares}分享/{hit.collects}藏）"
        )

    if mechanics:
        lines.extend(["", "可借鉴内容机制："])
        for mechanic in mechanics:
            lines.append(
                f"- {mechanic.label}: {mechanic.description}"
                f"（样本信号：`{mechanic.signal_title}`）"
            )

    lines.extend(
        [
            "",
            "建议写法：",
            f"- 主切口：`{primary_hook}`",
            f"- 表达模版：`{expression_template}`",
            f"- 场景张力：`{tension}`",
            "- 约束：只借情绪结构和讨论点，不复写原题，不堆砌热词。",
        ]
    )
    return "\n".join(lines)


def _infer_content_mechanics(hits: Sequence[TrendHit]) -> list[ContentMechanic]:
    candidates: dict[str, tuple[str, TrendHit]] = {}
    descriptions = {
        "comment_chain": "用一句可接龙的话触发评论补充",
        "save_tool": "给一个可收藏清单/三栏/话术模板",
        "copyable_line": "生成一句用户想截图或转发的封面句",
        "identity_conflict": "点名具体身份或冲突，强化转发给同类人的理由",
    }
    for hit in sorted(hits, key=lambda item: item.score, reverse=True):
        for label in _mechanic_labels(hit):
            candidates.setdefault(label, (descriptions[label], hit))

    preferred_order = ["comment_chain", "save_tool", "copyable_line", "identity_conflict"]
    return [
        ContentMechanic(
            label=label,
            description=candidates[label][0],
            signal_title=candidates[label][1].title,
        )
        for label in preferred_order
        if label in candidates
    ]


def _mechanic_labels(hit: TrendHit) -> list[str]:
    title = hit.title
    labels: list[str] = []
    if (
        hit.comments >= 500
        or any(cue in title for cue in ("评论", "评论区", "接一句", "交出", "补充", "哈哈", "笑"))
    ):
        labels.append("comment_chain")
    if (
        hit.collects >= 1000
        or hit.collects >= max(hit.likes // 2, 1)
        or any(cue in title for cue in ("Tips", "法则", "判断", "反复观看", "方法", "清单", "必看", "教程"))
    ):
        labels.append("save_tool")
    if any(cue in title for cue in ("文案", "个签", "话术", "请假条", "模板", "金句", "一句")):
        labels.append("copyable_line")
    if any(cue in title for cue in ("打工人", "工资", "优秀员工", "躺平", "优等生", "领导", "职场")):
        labels.append("identity_conflict")
    return labels


def _top_unique_hits(*, hits: Sequence[TrendHit], limit: int) -> list[TrendHit]:
    ranked = sorted(hits, key=lambda item: item.score, reverse=True)
    titles_seen: set[str] = set()
    unique_hits: list[TrendHit] = []
    for hit in ranked:
        normalized = re.sub(r"\s+", "", hit.title)
        if normalized in titles_seen:
            continue
        titles_seen.add(normalized)
        unique_hits.append(hit)
        if len(unique_hits) >= limit:
            break
    return unique_hits


def _pick_primary_hook(*, keywords: Sequence[str], hits: Sequence[TrendHit]) -> str:
    if "怎么才周四" in keywords:
        return "怎么才周四"
    if "发疯文学 打工人" in keywords:
        return "打工人发疯文学"
    best_hit = max(hits, key=lambda item: item.score, default=None)
    if best_hit is not None:
        return best_hit.keyword
    return keywords[0]


def _infer_tension(scene: str) -> str:
    if "需求" in scene and any(cue in scene for cue in ("下班", "工位", "群里", "老板", "领导")):
        return "下班前被新需求拽回工位"
    if any(cue in scene for cue in ("老板", "领导")):
        return "情绪快要下班时又被上级一句话拽回现实"
    if any(cue in scene for cue in ("开会", "会议")):
        return "本来已经快要解放，结果又被会议续上半条命"
    return "把一个临近释放却突然被拽回现实的瞬间写具体"


def _extract_text(payload: object) -> str:
    content = _normalize_mcp_payload(payload)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                texts.append(str(item["text"]))
            else:
                texts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(texts)
    return json.dumps(content, ensure_ascii=False)


def _normalize_mcp_payload(payload: object) -> object:
    """Unwrap LangChain message objects to their raw content."""
    if hasattr(payload, "content") and not isinstance(payload, (str, list, dict)):
        return getattr(payload, "content")
    return payload


def _extract_json_payload(payload: object) -> object:
    content = _normalize_mcp_payload(payload)
    if isinstance(content, dict):
        return content
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and "text" in first:
            try:
                return json.loads(str(first["text"]))
            except json.JSONDecodeError:
                return {"text": str(first["text"])}
    try:
        return json.loads(_extract_text(content))
    except json.JSONDecodeError:
        return {"text": _extract_text(content)}
