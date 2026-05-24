from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Iterable


TOPIC_DIRECTION_PUBLIC_FIELDS = (
    "id",
    "name",
    "trend_signal",
    "viral_hook",
    "why_it_may_work",
    "best_scenes",
    "content_angle",
    "saveable_tool",
    "comment_prompt",
    "avoid",
)


@dataclass(frozen=True)
class TopicLane:
    name: str
    default_scene: str
    default_content_angle: str
    default_saveable_tool: str
    default_comment_prompt: str
    keywords: tuple[str, ...] = ()
    default_image_style: str = "note_card"
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TopicDirection:
    id: str
    name: str
    trend_signal: str
    viral_hook: str
    why_it_may_work: str
    best_scenes: tuple[str, ...]
    content_angle: str
    saveable_tool: str
    comment_prompt: str
    avoid: str
    lane_affinity: tuple[str, ...] = ()
    scene_keywords: tuple[str, ...] = ()
    base_priority: int = 0
    diversity_key: str = ""


@dataclass(frozen=True)
class TopicPack:
    playbook_id: str
    default_account_id: str
    default_image_style: str
    lanes: tuple[TopicLane, ...]
    directions: tuple[TopicDirection, ...]
    guidance_message: str


@dataclass(frozen=True)
class _ScoredTopicDirection:
    score: int
    rotation: int
    index: int
    direction: TopicDirection
    scene_matches: tuple[str, ...]
    lane_matches: tuple[str, ...]


def resolve_topic_lane(
    *,
    lanes: tuple[TopicLane, ...],
    lane: str | None = None,
    scene: str | None = None,
) -> TopicLane:
    if not lanes:
        raise ValueError("Topic guidance requires at least one lane")

    if lane:
        stripped = lane.strip()
        if stripped.isdigit():
            idx = int(stripped)
            if 1 <= idx <= len(lanes):
                return lanes[idx - 1]
        for candidate in lanes:
            if stripped == candidate.name or stripped in candidate.name:
                return candidate
        available = ", ".join(item.name for item in lanes)
        raise ValueError(f"Unknown topic lane {lane!r}. Available lanes: {available}")

    scene_text = scene or ""
    ranked = [
        (_keyword_hits(scene_text, candidate.keywords), index, candidate)
        for index, candidate in enumerate(lanes)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if ranked and ranked[0][0] > 0:
        return ranked[0][2]
    return lanes[0]


def select_topic_directions(
    *,
    directions: Iterable[TopicDirection],
    scene: str,
    lane_name: str,
    limit: int = 4,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    scene_text = scene or ""
    lane_text = lane_name or ""
    scored: list[_ScoredTopicDirection] = []
    for index, direction in enumerate(directions):
        scene_matches = _matched_keywords(scene_text, direction.scene_keywords)
        lane_matches = tuple(
            affinity for affinity in direction.lane_affinity if affinity in lane_text
        )
        score = direction.base_priority
        score += min(len(scene_matches), 4) * 10
        score += min(len(lane_matches), 2) * 4
        rotation = _stable_topic_rotation(
            scene=scene,
            lane_name=lane_name,
            direction_id=direction.id,
        )
        scored.append(
            _ScoredTopicDirection(
                score=score,
                rotation=rotation,
                index=index,
                direction=direction,
                scene_matches=scene_matches,
                lane_matches=lane_matches,
            )
        )

    scored.sort(key=lambda item: (-item.score, item.rotation, item.index))
    selected = _select_diverse_topic_directions(
        scored=scored,
        limit=limit,
    )
    return [
        public_topic_direction(
            item.direction,
            scene_fit=_build_scene_fit(item),
        )
        for item in selected
    ]


def public_topic_direction(
    direction: TopicDirection,
    *,
    scene_fit: str = "",
) -> dict[str, Any]:
    data = {field: getattr(direction, field) for field in TOPIC_DIRECTION_PUBLIC_FIELDS}
    data["best_scenes"] = list(direction.best_scenes)
    data["scene_fit"] = scene_fit or "补充视角：给当前场景一个不同表达角度。"
    return data


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in normalized_text)


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    normalized_text = text.lower()
    return tuple(
        keyword
        for keyword in keywords
        if keyword and keyword.lower() in normalized_text
    )


def _select_diverse_topic_directions(
    *,
    scored: list[_ScoredTopicDirection],
    limit: int,
) -> list[_ScoredTopicDirection]:
    selected: list[_ScoredTopicDirection] = []
    selected_indexes: set[int] = set()
    used_diversity_keys: set[str] = set()

    for item in scored:
        if len(selected) >= limit:
            break
        diversity_key = _topic_diversity_key(item.direction)
        if diversity_key in used_diversity_keys:
            continue
        selected.append(item)
        selected_indexes.add(item.index)
        used_diversity_keys.add(diversity_key)

    if len(selected) >= limit:
        return selected

    for item in scored:
        if len(selected) >= limit:
            break
        if item.index in selected_indexes:
            continue
        selected.append(item)
        selected_indexes.add(item.index)

    return selected


def _topic_diversity_key(direction: TopicDirection) -> str:
    return direction.diversity_key or direction.id


def _build_scene_fit(item: _ScoredTopicDirection) -> str:
    if item.scene_matches:
        terms = "、".join(item.scene_matches[:3])
        return f"匹配当前场景信号：{terms}"
    if item.lane_matches:
        lanes = "、".join(item.lane_matches[:2])
        return f"贴合当前选题 lane：{lanes}"
    return "补充视角：给当前场景一个不同表达角度。"


def _stable_topic_rotation(*, scene: str, lane_name: str, direction_id: str) -> int:
    digest = hashlib.sha256(f"{scene}|{lane_name}|{direction_id}".encode()).hexdigest()
    return int(digest[:8], 16)
