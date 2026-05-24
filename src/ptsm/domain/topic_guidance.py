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


@dataclass(frozen=True)
class TopicPack:
    playbook_id: str
    default_account_id: str
    default_image_style: str
    lanes: tuple[TopicLane, ...]
    directions: tuple[TopicDirection, ...]
    guidance_message: str


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
    text = f"{lane_name} {scene}"
    scored: list[tuple[int, int, int, TopicDirection]] = []
    for index, direction in enumerate(directions):
        score = direction.base_priority
        if any(affinity in lane_name for affinity in direction.lane_affinity):
            score += 4
        score += min(_keyword_hits(text, direction.scene_keywords), 4) * 10
        rotation = _stable_topic_rotation(
            scene=scene,
            lane_name=lane_name,
            direction_id=direction.id,
        )
        scored.append((-score, rotation, index, direction))

    scored.sort()
    return [
        public_topic_direction(direction)
        for _, _, _, direction in scored[: max(limit, 0)]
    ]


def public_topic_direction(direction: TopicDirection) -> dict[str, Any]:
    data = {field: getattr(direction, field) for field in TOPIC_DIRECTION_PUBLIC_FIELDS}
    data["best_scenes"] = list(direction.best_scenes)
    return data


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in normalized_text)


def _stable_topic_rotation(*, scene: str, lane_name: str, direction_id: str) -> int:
    digest = hashlib.sha256(f"{scene}|{lane_name}|{direction_id}".encode()).hexdigest()
    return int(digest[:8], 16)
