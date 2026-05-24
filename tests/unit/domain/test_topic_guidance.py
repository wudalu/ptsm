from __future__ import annotations

from ptsm.domain.topic_guidance import (
    TopicDirection,
    TopicLane,
    resolve_topic_lane,
    select_topic_directions,
)


def test_select_topic_directions_scores_scene_keywords_before_priority() -> None:
    directions = (
        TopicDirection(
            id="general",
            name="General",
            trend_signal="evergreen",
            viral_hook="save",
            why_it_may_work="general",
            best_scenes=("general",),
            content_angle="general",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            base_priority=9,
        ),
        TopicDirection(
            id="desk",
            name="Desk",
            trend_signal="desk",
            viral_hook="before_after",
            why_it_may_work="desk",
            best_scenes=("书桌",),
            content_angle="desk",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("书桌",),
            base_priority=1,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="想写书桌角落改造",
        lane_name="一平米角落",
    )

    assert [item["id"] for item in result] == ["desk", "general"]


def test_select_topic_directions_omits_internal_fields() -> None:
    result = select_topic_directions(
        directions=(
            TopicDirection(
                id="desk",
                name="Desk",
                trend_signal="desk",
                viral_hook="save",
                why_it_may_work="desk",
                best_scenes=("书桌",),
                content_angle="desk",
                saveable_tool="tool",
                comment_prompt="prompt",
                avoid="avoid",
                lane_affinity=("一平米",),
                scene_keywords=("书桌",),
                base_priority=9,
            ),
        ),
        scene="想写书桌角落改造",
        lane_name="一平米角落",
    )

    direction = result[0]
    assert "lane_affinity" not in direction
    assert "scene_keywords" not in direction
    assert "base_priority" not in direction


def test_select_topic_directions_is_stable_and_limited() -> None:
    directions = tuple(
        TopicDirection(
            id=f"direction_{idx}",
            name=f"Direction {idx}",
            trend_signal="signal",
            viral_hook="hook",
            why_it_may_work="why",
            best_scenes=("scene",),
            content_angle="angle",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            base_priority=1,
        )
        for idx in range(8)
    )

    first = select_topic_directions(
        directions=directions,
        scene="same scene",
        lane_name="same lane",
        limit=4,
    )
    second = select_topic_directions(
        directions=directions,
        scene="same scene",
        lane_name="same lane",
        limit=4,
    )

    assert first == second
    assert len(first) == 4


def test_resolve_topic_lane_matches_number_name_and_scene_keywords() -> None:
    lanes = (
        TopicLane(
            name="一平米角落 / 低成本变量",
            default_scene="书桌太像工位",
            default_content_angle="给一个角落加下班信号",
            default_saveable_tool="三步变量清单",
            default_comment_prompt="你先想丰容哪个角落？",
            keywords=("书桌", "角落"),
        ),
        TopicLane(
            name="通勤路线 / 感官变量",
            default_scene="下班路上换一条路",
            default_content_angle="给路线加一个颜色任务",
            default_saveable_tool="路线观察卡",
            default_comment_prompt="你会先换哪一段路？",
            keywords=("通勤", "路线"),
        ),
    )

    assert resolve_topic_lane(lanes=lanes, lane="2").name == "通勤路线 / 感官变量"
    assert resolve_topic_lane(lanes=lanes, lane="一平米").name == "一平米角落 / 低成本变量"
    assert resolve_topic_lane(lanes=lanes, scene="想写书桌角落").name == "一平米角落 / 低成本变量"
