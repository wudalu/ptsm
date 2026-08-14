from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from typing import Any, Iterable


TOPIC_DIRECTION_PUBLIC_FIELDS = (
    "id",
    "name",
    "direction_type",
    "content_mode",
    "trend_signal",
    "viral_hook",
    "why_it_may_work",
    "best_scenes",
    "content_angle",
    "saveable_tool",
    "comment_prompt",
    "avoid",
    "format_recommendation",
)


@dataclass(frozen=True)
class FormatRecommendation:
    format_archetype: str = "note_card"
    cover_role: str = "save_tool"
    body_shape: str = "scene hook / 3-step save tool / comment handoff"
    visual_evidence_need: str = "low"
    avoid_format: tuple[str, ...] = ("dense_text_poster",)


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
    format_recommendation: FormatRecommendation = field(
        default_factory=FormatRecommendation
    )
    lane_affinity: tuple[str, ...] = ()
    scene_keywords: tuple[str, ...] = ()
    base_priority: int = 0
    diversity_key: str = ""
    direction_type: str = "curated"
    content_mode: str | None = None


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
    include_open_slot: bool = False,
    dynamic_breadth: bool = False,
    open_candidate_count: int = 3,
    allowed_open_scene_mechanisms: Iterable[str] | None = None,
    content_mode: str | None = None,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []

    # Evidence-gated modes are curated-only by design.  An open scene carries
    # no operator-approved fact or test record, so it must never become an
    # accidental fourth AI-tech content mode.
    if content_mode is not None:
        include_open_slot = False
        dynamic_breadth = False

    scene_text = scene or ""
    lane_text = lane_name or ""
    scored: list[_ScoredTopicDirection] = []
    for index, direction in enumerate(directions):
        if content_mode is not None and direction.content_mode != content_mode:
            continue
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
    if include_open_slot and dynamic_breadth:
        open_candidates = build_open_scene_topic_directions(
            scene=scene,
            lane_name=lane_name,
            count=max(open_candidate_count, limit - 1),
            allowed_mechanisms=allowed_open_scene_mechanisms,
        )
        open_scored: list[_ScoredTopicDirection] = []
        for offset, (open_direction, open_facets) in enumerate(open_candidates):
            lane_matches = tuple(
                affinity
                for affinity in open_direction.lane_affinity
                if affinity in lane_text
            )
            open_score = open_direction.base_priority
            open_score += min(len(open_facets), 4) * 8
            open_score += min(len(lane_matches), 2) * 4
            if offset == 0:
                open_score += 2
            open_scored.append(
                _ScoredTopicDirection(
                    score=open_score,
                    rotation=_stable_topic_rotation(
                        scene=scene,
                        lane_name=lane_name,
                        direction_id=open_direction.id,
                    ),
                    index=len(scored) + offset,
                    direction=open_direction,
                    scene_matches=open_facets,
                    lane_matches=lane_matches,
                )
            )
        selected = _select_dynamic_breadth_topic_directions(
            scored=[*scored, *open_scored],
            limit=limit,
        )
        return [
            public_topic_direction(
                item.direction,
                scene_fit=_build_scene_fit(item),
            )
            for item in selected
        ]

    curated_limit = max(limit - 1, 0) if include_open_slot else limit
    selected = _select_diverse_topic_directions(
        scored=scored,
        limit=curated_limit,
    )
    result = [
        public_topic_direction(
            item.direction,
            scene_fit=_build_scene_fit(item),
        )
        for item in selected
    ]
    if include_open_slot:
        open_candidates = build_open_scene_topic_directions(
            scene=scene,
            lane_name=lane_name,
            count=1,
            allowed_mechanisms=allowed_open_scene_mechanisms,
        )
        if open_candidates:
            open_direction, open_facets = open_candidates[0]
            result.append(
                public_topic_direction(
                    open_direction,
                    scene_fit=_build_open_scene_fit(open_facets),
                )
            )
    return result[:limit]


def build_open_scene_topic_directions(
    *,
    scene: str,
    lane_name: str,
    count: int = 3,
    allowed_mechanisms: Iterable[str] | None = None,
) -> tuple[tuple[TopicDirection, tuple[str, ...]], ...]:
    if count <= 0:
        return ()

    facets = _extract_scene_facets(scene=scene, lane_name=lane_name)
    mechanisms = _rank_open_scene_mechanisms(
        scene=scene,
        lane_name=lane_name,
        allowed_mechanisms=allowed_mechanisms,
    )
    return tuple(
        _build_open_scene_topic_direction_for_mechanism(
            scene=scene,
            lane_name=lane_name,
            facets=facets,
            mechanism=mechanism,
        )
        for mechanism in mechanisms[:count]
    )


def build_open_scene_topic_direction(
    *,
    scene: str,
    lane_name: str,
) -> tuple[TopicDirection, tuple[str, ...]]:
    return build_open_scene_topic_directions(
        scene=scene,
        lane_name=lane_name,
        count=1,
    )[0]


def _build_open_scene_topic_direction_for_mechanism(
    *,
    scene: str,
    lane_name: str,
    facets: tuple[str, ...],
    mechanism: str,
) -> tuple[TopicDirection, tuple[str, ...]]:
    label = _open_scene_label(facets=facets, lane_name=lane_name)
    digest = hashlib.sha256(f"{scene}|{lane_name}|{mechanism}".encode()).hexdigest()[
        :8
    ]

    if mechanism == "copyable_line":
        name = f"开放探索：{label}的一句话切口"
        trend_signal = "可复制句式 / 评论区改写"
        viral_hook = "把当前场景变成一句可改写的话"
        content_angle = f"不套固定候选，直接把“{label}”拆成一条可发送、可收藏、可评论的表达。"
        saveable_tool = "场景信号 / 最难说的话 / 可替换版本"
        comment_prompt = "把你最难说的那一句留在评论区，我帮你改成不硬撑的版本。"
        avoid = "不要泄露真实聊天隐私，不要把边界表达写成攻击或消失。"
    elif mechanism == "micro_task":
        name = f"开放探索：{label}的今日小任务"
        trend_signal = "低成本变量 / 现场参与"
        viral_hook = "让读者今天就能交作业"
        content_angle = f"把“{label}”做成一个今天能完成的小任务，而不是只讲抽象观点。"
        saveable_tool = "原本惯性 / 一个变量 / 今天能试的一步"
        comment_prompt = "你会把这个小任务换成自己生活里的哪一步？"
        avoid = "不要写成购物清单、旅游攻略或需要额外成本的挑战。"
    elif mechanism == "watch_checklist":
        name = f"开放探索：{label}的普通人看点清单"
        trend_signal = "看球搭子 / 普通球迷入口"
        viral_hook = "赛前赛后都能保存的清单"
        content_angle = f"把“{label}”拆成人话看点、情绪入口和评论区讨论点。"
        saveable_tool = "比赛语境 / 2 个看点 / 看球前一句话"
        comment_prompt = "你最想让朋友用人话解释哪个看点？"
        avoid = "不要写赌球、盘口、预测比分、内部消息或官方消息伪装。"
    elif mechanism == "tool_handoff":
        name = f"开放探索：{label}的交接清单"
        trend_signal = "AI 工具生活化 / 工作流边界"
        viral_hook = "普通人能照抄的检查表"
        content_angle = f"把“{label}”写成普通人使用工具前后的交接动作，降低科技感门槛。"
        saveable_tool = "我要交给工具什么 / 我要检查什么 / 哪一步必须自己确认"
        comment_prompt = "你最想把哪一步交给工具，但又不太放心？"
        avoid = "不要夸大工具能力，不给投资、法律、医疗等高风险建议。"
    elif mechanism == "comment_pattern":
        name = f"开放探索：{label}的评论区两派观察"
        trend_signal = "评论区模式 / 中文读者共鸣"
        viral_hook = "把争论翻成可参与的问题"
        content_angle = f"不复述原始讨论，直接把“{label}”整理成中文读者能接话的现象。"
        saveable_tool = "两派观点 / 普通人困惑 / 可讨论问题"
        comment_prompt = "你更接近哪一派？或者你卡在第三种感受里？"
        avoid = "不要展示外部链接、原帖、来源路径或把争论写成确定结论。"
    else:
        name = f"开放探索：{label}的三格保存卡"
        trend_signal = "场景重组 / 可保存小工具"
        viral_hook = "把具体瞬间整理成三格卡片"
        content_angle = f"围绕“{label}”现场组合一个保存型选题，补足固定候选没有覆盖的细节。"
        saveable_tool = "我遇到什么 / 我真正需要什么 / 我先试哪一步"
        comment_prompt = "你会把哪一个细节换成自己的版本？"
        avoid = "不要把开放探索写成确定结论，也不要越过当前领域的安全边界。"

    return (
        TopicDirection(
            id=f"open_scene_{mechanism}_{digest}",
            name=name,
            trend_signal=trend_signal,
            viral_hook=viral_hook,
            why_it_may_work="它不是从固定候选池里挑选，而是把用户这次给出的具体场景现场重组成一个可测试切口。",
            best_scenes=(
                scene.strip() or "用户给出的具体发帖场景",
                f"{lane_name} 下固定候选还没有完全覆盖的细节场景",
            ),
            content_angle=content_angle,
            saveable_tool=saveable_tool,
            comment_prompt=comment_prompt,
            avoid=avoid,
            lane_affinity=(lane_name,),
            scene_keywords=facets,
            base_priority=7,
            diversity_key=f"open-scene:{mechanism}",
            direction_type="open_scene",
            format_recommendation=_format_recommendation_for_open_scene(
                scene=scene,
                lane_name=lane_name,
                facets=facets,
                mechanism=mechanism,
            ),
        ),
        facets,
    )


def public_topic_direction(
    direction: TopicDirection,
    *,
    scene_fit: str = "",
) -> dict[str, Any]:
    data = {
        field: _serialize_topic_direction_public_field(getattr(direction, field))
        for field in TOPIC_DIRECTION_PUBLIC_FIELDS
    }
    data["best_scenes"] = list(direction.best_scenes)
    data["scene_fit"] = scene_fit or "补充视角：给当前场景一个不同表达角度。"
    return data


def _serialize_topic_direction_public_field(value: object) -> object:
    if isinstance(value, FormatRecommendation):
        return {
            "format_archetype": value.format_archetype,
            "cover_role": value.cover_role,
            "body_shape": value.body_shape,
            "visual_evidence_need": value.visual_evidence_need,
            "avoid_format": list(value.avoid_format),
        }
    return value


def _format_recommendation_for_open_scene(
    *,
    scene: str,
    lane_name: str,
    facets: tuple[str, ...],
    mechanism: str,
) -> FormatRecommendation:
    text = f"{scene} {lane_name} {' '.join(facets)}".lower()
    if any(
        keyword in text
        for keyword in (
            "书桌",
            "角落",
            "工位",
            "床头",
            "玄关",
            "手作",
            "材料",
            "平铺",
            "路线",
            "colorwalk",
            "颜色",
            "拍照",
        )
    ):
        return FormatRecommendation(
            format_archetype="provider_scene",
            cover_role="evidence_or_scene",
            body_shape="visual scene / low-cost variable / saved action / comment assignment",
            visual_evidence_need="high",
            avoid_format=("dense_text_poster", "fake_before_after"),
        )
    if mechanism in {"copyable_line", "comment_pattern"}:
        return FormatRecommendation(
            format_archetype="chat_screenshot",
            cover_role="comment_prompt",
            body_shape="one copyable line / two response variants / comment continuation",
            visual_evidence_need="low",
            avoid_format=("dense_text_poster", "private_chat_leak"),
        )
    if mechanism in {"micro_task", "watch_checklist"}:
        return FormatRecommendation(
            format_archetype="carousel",
            cover_role="save_tool",
            body_shape="task card / 2-3 checklist pages / comment assignment",
            visual_evidence_need="low",
            avoid_format=("dense_text_poster",),
        )
    return FormatRecommendation(
        format_archetype="note_card",
        cover_role="save_tool",
        body_shape="scene hook / 3-grid save card / comment handoff",
        visual_evidence_need="low",
        avoid_format=("dense_text_poster",),
    )


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = text.lower()
    return sum(
        1
        for keyword in keywords
        if keyword.lower() in normalized_text
        and not _is_keyword_negated(normalized_text, keyword)
    )


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    normalized_text = text.lower()
    return tuple(
        keyword
        for keyword in keywords
        if keyword and keyword.lower() in normalized_text
        and not _is_keyword_negated(normalized_text, keyword)
    )


def _is_keyword_negated(normalized_text: str, keyword: str) -> bool:
    compact_text = "".join(normalized_text.split())
    compact_keyword = "".join(keyword.lower().split())
    if not compact_keyword:
        return False
    return any(
        f"{prefix}{compact_keyword}" in compact_text
        for prefix in _NEGATED_KEYWORD_PREFIXES
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


def _select_dynamic_breadth_topic_directions(
    *,
    scored: list[_ScoredTopicDirection],
    limit: int,
) -> list[_ScoredTopicDirection]:
    if limit <= 0 or not scored:
        return []

    ordered = sorted(scored, key=lambda item: (-item.score, item.rotation, item.index))
    selected: list[_ScoredTopicDirection] = []
    selected_indexes: set[int] = set()

    first = next(
        (item for item in ordered if item.direction.direction_type != "open_scene"),
        ordered[0],
    )
    selected.append(first)
    selected_indexes.add(first.index)

    while len(selected) < limit:
        remaining = [item for item in ordered if item.index not in selected_indexes]
        if not remaining:
            break
        next_item = min(
            remaining,
            key=lambda item: (
                -_dynamic_breadth_score(item=item, selected=selected),
                item.rotation,
                item.index,
            ),
        )
        selected.append(next_item)
        selected_indexes.add(next_item.index)

    return selected


def _dynamic_breadth_score(
    *,
    item: _ScoredTopicDirection,
    selected: list[_ScoredTopicDirection],
) -> int:
    score = item.score
    direction_type = item.direction.direction_type
    same_type_count = sum(
        1
        for selected_item in selected
        if selected_item.direction.direction_type == direction_type
    )
    if direction_type == "curated":
        score -= same_type_count * 14
        if same_type_count >= 3:
            score -= 20
    elif direction_type == "open_scene":
        score -= same_type_count * 14
        if same_type_count == 0:
            score += 8

    diversity_key = _topic_diversity_key(item.direction)
    used_diversity_keys = {
        _topic_diversity_key(selected_item.direction) for selected_item in selected
    }
    if diversity_key in used_diversity_keys:
        score -= 30

    covered_facets = {
        facet for selected_item in selected for facet in selected_item.scene_matches
    }
    item_facets = set(item.scene_matches)
    if item_facets:
        score += len(item_facets - covered_facets) * 5
        score -= len(item_facets & covered_facets) * 2

    mechanism = _open_scene_mechanism(item.direction)
    if mechanism:
        used_mechanisms = {
            selected_mechanism
            for selected_item in selected
            if (selected_mechanism := _open_scene_mechanism(selected_item.direction))
        }
        if mechanism in used_mechanisms:
            score -= 25

    return score


def _topic_diversity_key(direction: TopicDirection) -> str:
    return direction.diversity_key or direction.id


def _open_scene_mechanism(direction: TopicDirection) -> str:
    if direction.direction_type != "open_scene":
        return ""
    prefix = "open_scene_"
    if not direction.id.startswith(prefix):
        return ""
    return direction.id[len(prefix) :].rsplit("_", 1)[0]


def _build_scene_fit(item: _ScoredTopicDirection) -> str:
    if item.direction.direction_type == "open_scene":
        return _build_open_scene_fit(item.scene_matches)
    if item.scene_matches:
        terms = "、".join(item.scene_matches[:3])
        return f"匹配当前场景信号：{terms}"
    if item.lane_matches:
        lanes = "、".join(item.lane_matches[:2])
        return f"贴合当前选题 lane：{lanes}"
    return "补充视角：给当前场景一个不同表达角度。"


def _build_open_scene_fit(facets: tuple[str, ...]) -> str:
    if facets:
        terms = "、".join(facets[:3])
        return f"开放探索：围绕当前场景信号 {terms} 现场组合，不来自固定候选池。"
    return "开放探索：围绕当前 scene/lane 现场组合，不来自固定候选池。"


def _extract_scene_facets(*, scene: str, lane_name: str) -> tuple[str, ...]:
    text = (scene or "").lower()
    facets: list[str] = []
    for keyword in _OPEN_SCENE_KEYWORDS:
        if keyword.lower() in text and keyword not in facets:
            facets.append(keyword)
        if len(facets) >= 3:
            return tuple(facets)

    lane_head = (lane_name or "").split("/")[0].strip()
    if lane_head and lane_head not in facets:
        facets.append(lane_head)
    return tuple(facets[:3])


def _open_scene_label(*, facets: tuple[str, ...], lane_name: str) -> str:
    if facets:
        return "、".join(facets[:2])
    lane_head = (lane_name or "").split("/")[0].strip()
    return lane_head or "当前场景"


def _choose_open_scene_mechanism(*, scene: str, lane_name: str) -> str:
    return _rank_open_scene_mechanisms(scene=scene, lane_name=lane_name)[0]


def _rank_open_scene_mechanisms(
    *,
    scene: str,
    lane_name: str,
    allowed_mechanisms: Iterable[str] | None = None,
) -> tuple[str, ...]:
    text = f"{scene} {lane_name}".lower()
    mechanism_pool = _validated_open_scene_mechanisms(allowed_mechanisms)
    scores = {mechanism: 0 for mechanism in _OPEN_SCENE_MECHANISMS}
    if _contains_any(text, ("世界杯", "看球", "比赛", "赛前", "赛后", "决赛")):
        scores["watch_checklist"] += 50
        scores["comment_pattern"] += 12
    if _contains_any(text, ("reddit", "外网", "评论区", "两派", "热搜", "热点")):
        scores["comment_pattern"] += 50
        scores["save_card"] += 10
    if _contains_any(text, ("ai", "agent", "模型", "工具", "gemini")):
        scores["tool_handoff"] += 50
        scores["save_card"] += 10
    if _contains_any(
        text,
        (
            "回复",
            "消息",
            "群聊",
            "拒绝",
            "边界",
            "为你好",
            "英文",
            "英语",
            "话",
        ),
    ):
        scores["copyable_line"] += 50
        scores["comment_pattern"] += 14
        scores["save_card"] += 10
    if _contains_any(
        text,
        (
            "书桌",
            "角落",
            "床头",
            "通勤",
            "下班路",
            "路线",
            "colorwalk",
            "手作",
            "材料",
        ),
    ):
        scores["micro_task"] += 50
        scores["save_card"] += 14
    if _contains_any(
        text,
        (
            "苏轼",
            "东坡",
            "古诗词",
            "诗词金句",
            "经典诗句",
            "金句",
            "李白",
            "李清照",
            "王维",
            "杜甫",
            "长风破浪",
            "怀民",
            "定风波",
            "赤壁",
            "赤壁赋",
            "黄州",
            "被贬",
            "东坡肉",
            "荔枝",
            "诗",
            "词",
            "月亮",
            "中秋",
            "水调歌头",
            "旧友",
            "旧物",
            "旷达",
            "自救",
            "夜里",
            "半夜",
        ),
    ):
        scores["save_card"] += 24
        scores["comment_pattern"] += 20
        scores["copyable_line"] += 16
        scores["micro_task"] += 10

    scores["save_card"] += 4
    return tuple(
        sorted(
            mechanism_pool,
            key=lambda mechanism: (
                -scores[mechanism],
                _stable_topic_rotation(
                    scene=scene,
                    lane_name=lane_name,
                    direction_id=f"open_scene:{mechanism}",
                ),
            ),
        )
    )


def _validated_open_scene_mechanisms(
    allowed_mechanisms: Iterable[str] | None,
) -> tuple[str, ...]:
    if allowed_mechanisms is None:
        return _OPEN_SCENE_MECHANISMS
    if isinstance(allowed_mechanisms, (str, bytes)):
        raise ValueError(
            "allowed_mechanisms must be a non-empty iterable of mechanism names"
        )

    requested = tuple(dict.fromkeys(allowed_mechanisms))
    unknown = tuple(
        mechanism
        for mechanism in requested
        if mechanism not in _OPEN_SCENE_MECHANISMS
    )
    if not requested or unknown:
        detail = f"; unknown: {', '.join(unknown)}" if unknown else ""
        raise ValueError(
            "allowed_mechanisms must contain only known open-scene mechanisms"
            f"{detail}"
        )
    requested_set = set(requested)
    return tuple(
        mechanism
        for mechanism in _OPEN_SCENE_MECHANISMS
        if mechanism in requested_set
    )


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


def _stable_topic_rotation(*, scene: str, lane_name: str, direction_id: str) -> int:
    digest = hashlib.sha256(f"{scene}|{lane_name}|{direction_id}".encode()).hexdigest()
    return int(digest[:8], 16)


_OPEN_SCENE_KEYWORDS = (
    "半夜",
    "睡前",
    "周末",
    "下班路",
    "朋友",
    "家人",
    "同事",
    "伴侣",
    "领导",
    "客户",
    "群聊",
    "评论区",
    "消息",
    "回复",
    "拒绝",
    "边界",
    "为你好",
    "感受",
    "AI",
    "agent",
    "模型",
    "工具",
    "Gemini",
    "短视频",
    "朋友圈",
    "书桌",
    "角落",
    "床头",
    "通勤",
    "colorwalk",
    "绿色",
    "手作",
    "材料",
    "世界杯",
    "看球",
    "比赛",
    "赛前",
    "赛后",
    "决赛",
    "英语",
    "英文",
    "Reddit",
    "外网",
    "热搜",
    "热点",
    "会议",
    "工牌",
    "丝瓜汤",
    "黄州",
    "被贬",
    "低谷",
    "旷达",
    "自救",
    "重新开始",
    "赤壁",
    "赤壁赋",
    "大江",
    "大月",
    "江月",
    "东坡肉",
    "荔枝",
    "滋味",
    "烟火",
    "水调歌头",
    "中秋",
    "但愿人长久",
    "苏轼",
    "定风波",
    "怀民",
    "古诗词",
    "诗词金句",
    "经典诗句",
    "金句",
    "李白",
    "李清照",
    "王维",
    "杜甫",
    "长风破浪",
    "人比黄花瘦",
    "空山",
    "令狐冲",
    "郭靖",
)


_OPEN_SCENE_MECHANISMS = (
    "copyable_line",
    "micro_task",
    "watch_checklist",
    "tool_handoff",
    "comment_pattern",
    "save_card",
)

_NEGATED_KEYWORD_PREFIXES = (
    "不要再写",
    "不要写",
    "不想写",
    "别再写",
    "别写",
    "不再写",
    "不要再",
    "不要",
    "不想",
    "别再",
    "别",
)
