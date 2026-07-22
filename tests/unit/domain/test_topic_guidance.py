from __future__ import annotations

import json

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


def test_select_topic_directions_does_not_score_lane_text_as_scene_keyword() -> None:
    directions = (
        TopicDirection(
            id="lane_echo",
            name="Lane Echo",
            trend_signal="boundary",
            viral_hook="save",
            why_it_may_work="lane echo",
            best_scenes=("boundary",),
            content_angle="lane echo",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("边界",),
            base_priority=1,
        ),
        TopicDirection(
            id="neutral",
            name="Neutral",
            trend_signal="neutral",
            viral_hook="comment",
            why_it_may_work="neutral",
            best_scenes=("neutral",),
            content_angle="neutral",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            base_priority=2,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="朋友半夜把情绪都倒给我，我不知道怎么回",
        lane_name="关系边界 / 消息压力",
        limit=2,
    )

    assert [item["id"] for item in result] == ["neutral", "lane_echo"]


def test_select_topic_directions_prefers_unused_diversity_families() -> None:
    directions = (
        TopicDirection(
            id="same_a",
            name="Same A",
            trend_signal="same",
            viral_hook="save",
            why_it_may_work="same",
            best_scenes=("same",),
            content_angle="same",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            diversity_key="same_family",
            base_priority=10,
        ),
        TopicDirection(
            id="same_b",
            name="Same B",
            trend_signal="same",
            viral_hook="save",
            why_it_may_work="same",
            best_scenes=("same",),
            content_angle="same",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            diversity_key="same_family",
            base_priority=9,
        ),
        TopicDirection(
            id="other",
            name="Other",
            trend_signal="other",
            viral_hook="comment",
            why_it_may_work="other",
            best_scenes=("other",),
            content_angle="other",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            diversity_key="other_family",
            base_priority=1,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="same scene",
        lane_name="same lane",
        limit=2,
    )

    assert [item["id"] for item in result] == ["same_a", "other"]


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
    assert "diversity_key" not in direction
    assert direction["scene_fit"]


def test_select_topic_directions_returns_public_format_recommendation() -> None:
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
                scene_keywords=("书桌",),
                base_priority=9,
            ),
        ),
        scene="想写书桌角落改造",
        lane_name="一平米角落",
    )

    format_recommendation = result[0]["format_recommendation"]

    assert format_recommendation["format_archetype"] in {
        "note_card",
        "carousel",
        "chat_screenshot",
        "provider_scene",
    }
    assert format_recommendation["cover_role"]
    assert format_recommendation["body_shape"]
    assert format_recommendation["visual_evidence_need"] in {"none", "low", "high"}
    assert "dense_text_poster" in format_recommendation["avoid_format"]


def test_select_topic_directions_can_append_open_scene_slot() -> None:
    directions = (
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
            scene_keywords=("书桌",),
            base_priority=9,
        ),
        TopicDirection(
            id="general",
            name="General",
            trend_signal="evergreen",
            viral_hook="comment",
            why_it_may_work="general",
            best_scenes=("general",),
            content_angle="general",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            base_priority=1,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="想把书桌角落改成十分钟适我主义手作位",
        lane_name="一平米角落 / 低成本变量",
        limit=3,
        include_open_slot=True,
    )

    assert [item["id"] for item in result[:2]] == ["desk", "general"]
    open_slot = result[-1]
    assert open_slot["direction_type"] == "open_scene"
    assert open_slot["id"] not in {"desk", "general"}
    assert open_slot["scene_fit"].startswith("开放探索")
    assert open_slot["trend_signal"]
    assert open_slot["viral_hook"]
    assert open_slot["content_angle"]
    assert open_slot["saveable_tool"]
    assert open_slot["comment_prompt"]
    assert open_slot["avoid"]
    assert open_slot["format_recommendation"]["format_archetype"] in {
        "note_card",
        "carousel",
        "chat_screenshot",
        "provider_scene",
    }

    serialized = json.dumps(open_slot, ensure_ascii=False)
    assert "scene_keywords" not in serialized
    assert "lane_affinity" not in serialized
    assert "base_priority" not in serialized
    assert "diversity_key" not in serialized
    assert '"source"' not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_select_topic_directions_dynamic_breadth_does_not_reserve_curated_slots() -> None:
    directions = (
        TopicDirection(
            id="primary_huimin",
            name="Primary Huimin",
            trend_signal="role-pair",
            viral_hook="comment",
            why_it_may_work="primary",
            best_scenes=("怀民",),
            content_angle="primary",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("怀民", "夜里"),
            diversity_key="role_pair",
            base_priority=9,
        ),
        TopicDirection(
            id="same_family_huimin",
            name="Same Family Huimin",
            trend_signal="role-pair",
            viral_hook="comment",
            why_it_may_work="same",
            best_scenes=("怀民",),
            content_angle="same",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("怀民", "朋友"),
            diversity_key="role_pair",
            base_priority=8,
        ),
        TopicDirection(
            id="old_friend",
            name="Old Friend",
            trend_signal="old-friend",
            viral_hook="save",
            why_it_may_work="old",
            best_scenes=("旧友",),
            content_angle="old",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("旧友", "朋友"),
            diversity_key="old_friend",
            base_priority=7,
        ),
        TopicDirection(
            id="city_night",
            name="City Night",
            trend_signal="night",
            viral_hook="scene",
            why_it_may_work="night",
            best_scenes=("夜路",),
            content_angle="night",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("夜路", "月亮"),
            diversity_key="city_night",
            base_priority=6,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="夜里读到怀民亦未寝，想写一种旧友关系",
        lane_name="怀民关系 / 角色认领",
        limit=4,
        include_open_slot=True,
        dynamic_breadth=True,
        open_candidate_count=3,
    )

    open_slots = [item for item in result if item["direction_type"] == "open_scene"]
    curated_slots = [item for item in result if item["direction_type"] == "curated"]

    assert len(result) == 4
    assert result[0]["id"] == "primary_huimin"
    assert len(open_slots) >= 1
    assert len(curated_slots) <= 3
    assert len({item["id"] for item in open_slots}) == len(open_slots)
    assert len({item["name"] for item in open_slots}) == len(open_slots)


def test_open_scene_slot_is_stable_for_same_scene_and_changes_by_scene() -> None:
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
            base_priority=1,
        ),
    )

    first = select_topic_directions(
        directions=directions,
        scene="朋友半夜把情绪都倒给我，我不知道怎么回",
        lane_name="关系边界 / 消息压力",
        limit=2,
        include_open_slot=True,
    )
    second = select_topic_directions(
        directions=directions,
        scene="朋友半夜把情绪都倒给我，我不知道怎么回",
        lane_name="关系边界 / 消息压力",
        limit=2,
        include_open_slot=True,
    )
    different_scene = select_topic_directions(
        directions=directions,
        scene="下班路上想做一次绿色 colorwalk",
        lane_name="通勤路线 / Colorwalk",
        limit=2,
        include_open_slot=True,
    )

    assert first == second
    assert first[-1]["direction_type"] == "open_scene"
    assert different_scene[-1]["direction_type"] == "open_scene"
    assert first[-1]["id"] != different_scene[-1]["id"]
    assert first[-1]["name"] != different_scene[-1]["name"]



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


def test_select_topic_directions_filters_and_serializes_explicit_content_mode() -> None:
    directions = (
        TopicDirection(
            id="news",
            name="News",
            trend_signal="signal",
            viral_hook="hook",
            why_it_may_work="why",
            best_scenes=("scene",),
            content_angle="angle",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            content_mode="news_brief",
            base_priority=9,
        ),
        TopicDirection(
            id="hands",
            name="Hands",
            trend_signal="signal",
            viral_hook="hook",
            why_it_may_work="why",
            best_scenes=("scene",),
            content_angle="angle",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            content_mode="hands_on",
            base_priority=8,
        ),
        TopicDirection(
            id="translation",
            name="Translation",
            trend_signal="signal",
            viral_hook="hook",
            why_it_may_work="why",
            best_scenes=("scene",),
            content_angle="angle",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            content_mode="fact_translation",
            base_priority=7,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="想复盘一次提示词测试",
        lane_name="AI 科技",
        content_mode="hands_on",
        include_open_slot=False,
    )

    assert result == [
        {
            "id": "hands",
            "name": "Hands",
            "direction_type": "curated",
            "content_mode": "hands_on",
            "trend_signal": "signal",
            "viral_hook": "hook",
            "why_it_may_work": "why",
            "best_scenes": ["scene"],
            "content_angle": "angle",
            "saveable_tool": "tool",
            "comment_prompt": "prompt",
            "avoid": "avoid",
            "format_recommendation": {
                "format_archetype": "note_card",
                "cover_role": "save_tool",
                "body_shape": "scene hook / 3-step save tool / comment handoff",
                "visual_evidence_need": "low",
                "avoid_format": ["dense_text_poster"],
            },
            "scene_fit": "补充视角：给当前场景一个不同表达角度。",
        }
    ]
