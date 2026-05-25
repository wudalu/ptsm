from __future__ import annotations

import json

import pytest

from ptsm.application.use_cases.topic_guidance_packs import TOPIC_GUIDANCE_PACKS
from ptsm.application.use_cases.guide_post import (
    GuidePostRequest,
    PSYCHOLOGY_TOPIC_DIRECTIONS,
    format_guide_post_markdown,
    run_guide_post,
)


NEW_TOPIC_GUIDANCE_CASES = (
    (
        "wuxia_character_post",
        "acct-wuxia-local",
        "想用令狐冲写一种当代职场里的自由人格",
        "wuxia_",
    ),
    (
        "ai_tech_daily_post",
        "acct-ai-tech-local",
        "Google 发布 Gemini 3，想写普通人能懂的 AI 工具变化",
        "ai_",
    ),
    (
        "daily_english_post",
        "acct-daily-english-local",
        "学一个表示坚持的高级词汇，想配真实职场例句",
        "english_",
    ),
    (
        "world_cup_daily_post",
        "acct-world-cup-local",
        "阿根廷和法国决赛前，想写普通球迷看球清单",
        "worldcup_",
    ),
    (
        "reddit_curation_daily_post",
        "acct-reddit-curation-local",
        "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度",
        "reddit_",
    ),
)


GENERIC_DIVERSE_TOPIC_CASES = (
    (
        "fengkuang_daily_post",
        "acct-fk-local",
        "领导18:57发来一句在吗，工牌想替我发疯",
        "群聊里那句没发出去的话在脑子里加班",
    ),
    (
        "human_enrichment_daily_post",
        "acct-enrichment-local",
        "想把书桌角落改成十分钟适我主义手作位",
        "下班路上想做一次绿色 colorwalk",
    ),
    (
        "sushi_poetry_daily_post",
        "acct-sushi-local",
        "夜里读到怀民亦未寝，想写一种旧友关系",
        "今天被风雨淋得很狼狈，想重读定风波",
    ),
    (
        "wuxia_character_post",
        "acct-wuxia-local",
        "想用令狐冲写一种当代职场里的自由人格",
        "想写郭靖那种慢慢长出来的笨拙可靠",
    ),
    (
        "ai_tech_daily_post",
        "acct-ai-tech-local",
        "Google 发布 Gemini 3，想写普通人能懂的 AI 工具变化",
        "想写 AI agent 自动执行任务时普通人该怎么交接",
    ),
    (
        "daily_english_post",
        "acct-daily-english-local",
        "学一个表示坚持的高级词汇，想配真实职场例句",
        "想学一句委婉拒绝临时会议的英文回复",
    ),
    (
        "world_cup_daily_post",
        "acct-world-cup-local",
        "阿根廷和法国决赛前，想写普通球迷看球清单",
        "朋友约了看球局，想写熬夜前的准备和氛围",
    ),
    (
        "reddit_curation_daily_post",
        "acct-reddit-curation-local",
        "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度",
        "外网评论区吵成两派，想转成中文读者能参与的观察",
    ),
)


def _assert_no_internal_source_leakage(result: dict[str, object]) -> None:
    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert "source_url" not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def _direction_ids(result: dict[str, object]) -> set[str]:
    guidance = result["topic_guidance"]
    assert isinstance(guidance, dict)
    return {direction["id"] for direction in guidance["directions"]}


def _curated_direction_ids(result: dict[str, object]) -> set[str]:
    guidance = result["topic_guidance"]
    assert isinstance(guidance, dict)
    return {
        direction["id"]
        for direction in guidance["directions"]
        if direction.get("direction_type", "curated") == "curated"
    }


def _open_directions(result: dict[str, object]) -> list[dict[str, object]]:
    guidance = result["topic_guidance"]
    assert isinstance(guidance, dict)
    return [
        direction
        for direction in guidance["directions"]
        if direction.get("direction_type") == "open_scene"
    ]


def test_run_guide_post_builds_psychology_brief_with_scene_defaults() -> None:
    result = run_guide_post(
        GuidePostRequest(
            scene="睡前刷短视频停不下来，越刷越焦虑",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "modern_psychology_post"
    assert result["account_id"] == "acct-psychology-local"

    brief = result["brief"]
    assert brief["lane"] == "数字生活 / 信息过载"
    assert brief["mechanism"] == "信息过载"
    assert brief["image_style"] == "iphone_notes"
    assert "睡前刷短视频" in brief["scene"]
    assert "诊断" in brief["safety_boundary"]

    assert "心理机制" in result["recommended_scene"]
    assert result["run_playbook_command"][:4] == ["uv", "run", "python", "-m"]
    assert "--publish-mode" in result["run_playbook_command"]
    assert "--auto-generate-image" in result["run_playbook_command"]
    assert "--local-image-style" in result["run_playbook_command"]
    assert "run-playbook --scene" in result["run_playbook_command_text"]
    assert any(item["item"] == "第一人称微场景" for item in result["quality_checklist"])
    assert any("危机" in note for note in result["safety_notes"])


def test_run_guide_post_returns_productized_topic_directions_without_internal_sources() -> None:
    result = run_guide_post(
        GuidePostRequest(
            scene="同事临时加需求，想练一版边界句",
        )
    )

    topic_guidance = result["topic_guidance"]
    assert topic_guidance["status"] == "available"
    direction_ids = {direction["id"] for direction in topic_guidance["directions"]}
    assert len(direction_ids) == 4
    assert "boundary_sandwich_refusal" in direction_ids

    boundary = next(
        direction
        for direction in topic_guidance["directions"]
        if direction["id"] == "boundary_sandwich_refusal"
    )
    assert boundary["name"] == "边界感：三明治拒绝法"
    assert boundary["trend_signal"]
    assert boundary["viral_hook"]
    assert "收藏" in boundary["why_it_may_work"]
    assert boundary["best_scenes"]
    assert "责任" in boundary["content_angle"]
    assert "先确认" in boundary["saveable_tool"]
    assert "边界句" in boundary["comment_prompt"]
    assert "万能" in boundary["avoid"]
    assert boundary["scene_fit"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized


def test_psychology_topic_guidance_returns_dynamic_open_scene_directions() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="朋友半夜把情绪都倒给我，我不知道怎么回")
    )

    guidance = result["topic_guidance"]
    directions = guidance["directions"]
    open_slots = _open_directions(result)
    curated_ids = {direction.id for direction in PSYCHOLOGY_TOPIC_DIRECTIONS}

    assert guidance["selection_policy"] == "dynamic_scene_diversity_rerank"
    assert len(directions) == 4
    assert len(open_slots) >= 1
    assert len(_curated_direction_ids(result)) <= 2
    assert directions[0]["direction_type"] == "curated"
    assert guidance["matched_direction_id"] == directions[0]["id"]
    assert guidance["matched_direction_id"] != open_slots[0]["id"]
    assert guidance["open_direction_ids"] == [slot["id"] for slot in open_slots]
    assert guidance["open_direction_id"] == open_slots[0]["id"]
    assert guidance["direction_type_counts"]["open_scene"] == len(open_slots)
    assert guidance["direction_type_counts"]["curated"] == len(_curated_direction_ids(result))
    assert open_slots[0]["id"] not in curated_ids
    assert open_slots[0]["scene_fit"].startswith("开放探索")
    _assert_no_internal_source_leakage(result)


def test_generic_topic_guidance_returns_dynamic_open_scene_metadata_for_all_packs() -> None:
    for playbook_id, pack in TOPIC_GUIDANCE_PACKS.items():
        result = run_guide_post(
            GuidePostRequest(
                playbook_id=playbook_id,
                account_id=pack.default_account_id,
                scene=pack.lanes[0].default_scene,
            )
        )

        guidance = result["topic_guidance"]
        open_slots = _open_directions(result)
        curated_ids = {direction.id for direction in pack.directions}

        assert guidance["selection_policy"] == "dynamic_scene_diversity_rerank"
        assert len(guidance["directions"]) == 4
        assert len(open_slots) >= 1
        assert 1 <= len(_curated_direction_ids(result)) <= 3
        assert guidance["matched_direction_id"] == guidance["directions"][0]["id"]
        assert guidance["matched_direction_id"] != open_slots[0]["id"]
        assert guidance["open_direction_ids"] == [slot["id"] for slot in open_slots]
        assert guidance["open_direction_id"] == open_slots[0]["id"]
        assert guidance["direction_type_counts"]["open_scene"] == len(open_slots)
        assert guidance["direction_type_counts"]["curated"] == len(_curated_direction_ids(result))
        assert open_slots[0]["id"] not in curated_ids
        assert open_slots[0]["scene_fit"].startswith("开放探索")
        _assert_no_internal_source_leakage(result)


def test_sushi_topic_guidance_same_lane_scene_changes_do_not_keep_fixed_curated_anchors() -> None:
    scenes = (
        "夜里读到怀民亦未寝，想写一种旧友关系",
        "半夜一个人走在城市夜路上，突然想起怀民亦未寝",
        "下班路上看到月亮，想写苏轼和一个没联系很久的人",
    )

    results = [
        run_guide_post(
            GuidePostRequest(
                playbook_id="sushi_poetry_daily_post",
                account_id="acct-sushi-local",
                scene=scene,
            )
        )
        for scene in scenes
    ]

    direction_id_sets = [
        tuple(direction["id"] for direction in result["topic_guidance"]["directions"])
        for result in results
    ]
    curated_id_sets = [
        tuple(
            direction["id"]
            for direction in result["topic_guidance"]["directions"]
            if direction["direction_type"] == "curated"
        )
        for result in results
    ]
    fixed_curated_set = {
        "sushi_role_pair_huimin",
        "sushi_city_night_walk",
        "sushi_old_friend_note",
    }

    assert len(set(direction_id_sets)) > 1
    assert len(set(curated_id_sets)) > 1
    for result, curated_ids in zip(results, curated_id_sets, strict=True):
        guidance = result["topic_guidance"]
        open_slots = _open_directions(result)
        assert guidance["selection_policy"] == "dynamic_scene_diversity_rerank"
        assert guidance["direction_type_counts"]["curated"] <= 2
        assert len(open_slots) >= 1
        assert set(curated_ids) != fixed_curated_set


def test_format_guide_post_markdown_includes_scene_fit() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="朋友半夜把情绪都倒给我，我不知道怎么回")
    )

    markdown = format_guide_post_markdown(result)

    assert "scene:" in markdown
    assert "fit:" in markdown
    assert "匹配当前场景信号" in markdown


def test_run_guide_post_varies_topic_directions_by_scene() -> None:
    boundary_result = run_guide_post(
        GuidePostRequest(scene="同事临时加需求，想练一版边界句")
    )
    ai_result = run_guide_post(
        GuidePostRequest(scene="晚上只想让 AI 帮我分析关系，结果越聊越空")
    )
    comparison_result = run_guide_post(
        GuidePostRequest(scene="看到别人周末都在聚会，突然觉得自己很失败")
    )

    boundary_guidance = boundary_result["topic_guidance"]
    ai_guidance = ai_result["topic_guidance"]
    comparison_guidance = comparison_result["topic_guidance"]

    boundary_ids = [direction["id"] for direction in boundary_guidance["directions"]]
    ai_ids = [direction["id"] for direction in ai_guidance["directions"]]
    comparison_ids = [
        direction["id"] for direction in comparison_guidance["directions"]
    ]

    assert ai_result["brief"]["lane"] == "数字生活 / 信息过载"
    assert len(boundary_ids) == 4
    assert len(ai_ids) == 4
    assert len(comparison_ids) == 4
    assert boundary_ids != ai_ids
    assert ai_ids != comparison_ids

    assert boundary_guidance["matched_direction_id"] == "boundary_sandwich_refusal"
    assert ai_guidance["matched_direction_id"] in {
        "ai_companion_boundary",
        "ai_overanalysis_stop_rule",
    }
    assert comparison_guidance["matched_direction_id"] in {
        "self_compassion_laoji",
        "comparison_pause_card",
    }

    for result in (boundary_result, ai_result, comparison_result):
        topic_guidance = result["topic_guidance"]
        assert topic_guidance["directions"][0]["id"] == topic_guidance["matched_direction_id"]
        for direction in topic_guidance["directions"]:
            assert direction["trend_signal"]
            assert direction["viral_hook"]
            assert direction["scene_fit"]

        serialized = json.dumps(result, ensure_ascii=False)
        assert "docs/research" not in serialized
        assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
        assert '"source"' not in serialized
        assert "http://" not in serialized
        assert "https://" not in serialized


def test_psychology_topic_guidance_does_not_collapse_relationship_scenes() -> None:
    coworker = run_guide_post(
        GuidePostRequest(scene="同事临时加需求，想练一版边界句")
    )
    friend = run_guide_post(
        GuidePostRequest(scene="朋友半夜把情绪都倒给我，我不知道怎么回")
    )
    invalid_care = run_guide_post(
        GuidePostRequest(scene="家人总说为你好，但我的感受完全没有被接住")
    )

    matched_ids = [
        coworker["topic_guidance"]["matched_direction_id"],
        friend["topic_guidance"]["matched_direction_id"],
        invalid_care["topic_guidance"]["matched_direction_id"],
    ]

    assert matched_ids[0] == "boundary_sandwich_refusal"
    assert matched_ids[1] in {
        "real_support_role_pair",
        "message_boundary_reply_draft",
        "emotion_grounding_90s",
    }
    assert matched_ids[2] == "loofah_soup_communication"
    assert len(set(matched_ids)) == 3

    for result in (coworker, friend, invalid_care):
        assert result["topic_guidance"]["directions"][0]["scene_fit"]
        _assert_no_internal_source_leakage(result)


def test_generic_topic_packs_have_larger_candidate_pools_than_public_limit() -> None:
    for playbook_id, pack in TOPIC_GUIDANCE_PACKS.items():
        assert len(pack.directions) > 4, playbook_id


@pytest.mark.parametrize(
    ("playbook_id", "account_id", "first_scene", "second_scene"),
    GENERIC_DIVERSE_TOPIC_CASES,
)
def test_generic_topic_guidance_varies_direction_sets_by_scene(
    playbook_id: str,
    account_id: str,
    first_scene: str,
    second_scene: str,
) -> None:
    first = run_guide_post(
        GuidePostRequest(
            playbook_id=playbook_id,
            account_id=account_id,
            scene=first_scene,
        )
    )
    second = run_guide_post(
        GuidePostRequest(
            playbook_id=playbook_id,
            account_id=account_id,
            scene=second_scene,
        )
    )

    assert _direction_ids(first) != _direction_ids(second)
    assert _curated_direction_ids(first) != _curated_direction_ids(second)
    assert first["topic_guidance"]["directions"][0]["scene_fit"]
    assert second["topic_guidance"]["directions"][0]["scene_fit"]
    _assert_no_internal_source_leakage(first)
    _assert_no_internal_source_leakage(second)


def test_guide_post_supports_fengkuang_topic_guidance() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="fengkuang_daily_post",
            account_id="acct-fk-local",
            scene="领导18:57发来一句在吗，工牌想替我发疯",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "fengkuang_daily_post"
    assert result["account_id"] == "acct-fk-local"
    assert result["brief"]["lane"]
    assert result["topic_guidance"]["matched_direction_id"].startswith("fk_")
    assert len(result["topic_guidance"]["directions"]) == 4
    assert "run-playbook --scene" in result["run_playbook_command_text"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_guide_post_supports_human_enrichment_topic_guidance() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="human_enrichment_daily_post",
            account_id="acct-enrichment-local",
            scene="想把书桌角落改成十分钟适我主义手作位",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "human_enrichment_daily_post"
    assert result["account_id"] == "acct-enrichment-local"
    assert result["brief"]["lane"]
    assert result["topic_guidance"]["matched_direction_id"].startswith("enrichment_")
    assert len(result["topic_guidance"]["directions"]) == 4
    assert "run-playbook --scene" in result["run_playbook_command_text"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_guide_post_supports_sushi_poetry_topic_guidance() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="sushi_poetry_daily_post",
            account_id="acct-sushi-local",
            scene="夜里读到怀民亦未寝，想写一种旧友关系",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "sushi_poetry_daily_post"
    assert result["account_id"] == "acct-sushi-local"
    assert result["brief"]["lane"]
    assert result["topic_guidance"]["matched_direction_id"].startswith("sushi_")
    assert len(result["topic_guidance"]["directions"]) == 4
    assert "run-playbook --scene" in result["run_playbook_command_text"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


@pytest.mark.parametrize(
    ("playbook_id", "account_id", "scene", "expected_prefix"),
    NEW_TOPIC_GUIDANCE_CASES,
)
def test_guide_post_supports_remaining_xhs_topic_guidance(
    playbook_id: str,
    account_id: str,
    scene: str,
    expected_prefix: str,
) -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id=playbook_id,
            account_id=account_id,
            scene=scene,
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == playbook_id
    assert result["account_id"] == account_id
    assert result["brief"]["lane"]
    assert result["brief"]["scene"] == scene
    assert result["topic_guidance"]["matched_direction_id"].startswith(expected_prefix)
    assert len(result["topic_guidance"]["directions"]) == 4
    assert result["topic_guidance"]["directions"][0]["id"] == result["topic_guidance"]["matched_direction_id"]
    assert "run-playbook --scene" in result["run_playbook_command_text"]
    _assert_no_internal_source_leakage(result)


def test_run_guide_post_rejects_unsupported_playbook() -> None:
    with pytest.raises(ValueError, match="guide-post supports"):
        run_guide_post(
            GuidePostRequest(
                playbook_id="unknown_daily_post",
                scene="想写一条看球笔记",
            )
        )
