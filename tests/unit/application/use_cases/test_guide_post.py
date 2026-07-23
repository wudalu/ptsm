from __future__ import annotations

import json
from pathlib import Path

import pytest

import ptsm.domain.psychology_learning as psychology_learning_domain
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.domain.psychology_learning import resolve_psychology_learning_selection
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
        "classic_poetry_quote_post",
        "acct-classic-poetry-local",
        "读到李白长风破浪会有时，想写给低谷里的自己",
        "深夜读到李清照，想写一句能安放情绪的词",
    ),
    (
        "wuxia_character_post",
        "acct-wuxia-local",
        "想用令狐冲写一种当代职场里的自由人格",
        "想写郭靖那种慢慢长出来的笨拙可靠",
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


def _image_recommendation(result: dict[str, object]) -> dict[str, object]:
    guidance = result["topic_guidance"]
    assert isinstance(guidance, dict)
    recommendation = guidance["image_recommendation"]
    assert isinstance(recommendation, dict)
    assert recommendation["status"] == "available"
    assert recommendation["decision_stage"] == "after_topic_direction_confirmation"
    return recommendation


def _format_recommendation(direction: dict[str, object]) -> dict[str, object]:
    recommendation = direction["format_recommendation"]
    assert isinstance(recommendation, dict)
    assert recommendation["format_archetype"]
    assert recommendation["cover_role"]
    assert recommendation["body_shape"]
    assert recommendation["visual_evidence_need"] in {"none", "low", "high"}
    assert "dense_text_poster" in recommendation["avoid_format"]
    return recommendation


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
    assert any(item["item"] == "角色认领评论" for item in result["quality_checklist"])
    assert not any(item["item"] == "例子型评论" for item in result["quality_checklist"])
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
    boundary_format = _format_recommendation(boundary)
    assert boundary_format["format_archetype"] == "note_card"
    assert boundary_format["cover_role"] == "save_tool"
    assert boundary_format["visual_evidence_need"] == "low"

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized


def test_ai_tech_topic_guidance_routes_prompt_test_replay_with_explicit_mode() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="ai_tech_daily_post",
            account_id="acct-ai-tech-local",
            scene="同一任务补背景后输出有没有变，想复盘一次提示词测试",
            ai_content_mode="hands_on",
            ai_evidence_file_path="inputs/ai-evidence.json",
        )
    )

    guidance = result["topic_guidance"]
    assert guidance["matched_direction_id"] == "ai_prompt_context_card"
    first_direction = guidance["directions"][0]
    assert first_direction["id"] == "ai_prompt_context_card"
    assert first_direction["content_mode"] == "hands_on"
    assert (
        "prompt" in first_direction["name"].lower()
        or "提示词" in first_direction["name"]
    )
    assert "直接复制" not in first_direction["viral_hook"]
    assert "直接复制" not in first_direction["saveable_tool"]
    assert "测试任务" in first_direction["saveable_tool"]
    assert "输入摘要" in first_direction["saveable_tool"]
    assert "局限" in first_direction["saveable_tool"]
    assert "内容模式：hands_on" in result["recommended_scene"]
    assert any(
        marker in first_direction["comment_prompt"]
        for marker in ("prompt", "提示词", "失败")
    )
    assert "失败" in first_direction["comment_prompt"]
    assert "我帮" not in first_direction["comment_prompt"]
    assert "帮你改" not in first_direction["comment_prompt"]
    prompt_format = _format_recommendation(first_direction)
    assert prompt_format["format_archetype"] == "note_card"
    assert prompt_format["cover_role"] == "evidence_or_scene"
    assert "test" in prompt_format["body_shape"].lower() or "测试" in prompt_format["body_shape"]

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "note_card"
    assert recommendation["role"] == "cover_hook"
    assert recommendation["command_hint"] == "--local-image-style note_card"

    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_recommends_wechat_for_message_reply_assets() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="朋友半夜发来一大段消息，我想写一版不被掏空的回复")
    )

    recommendation = _image_recommendation(result)

    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "wechat_chat"
    assert recommendation["provider"] == ""
    assert recommendation["model"] == ""
    assert recommendation["role"] == "comment_prompt"
    assert recommendation["text_density"] == "low"
    assert recommendation["max_text_units"] == 2
    assert recommendation["command_hint"] == "--local-image-style wechat_chat"
    assert "消息" in recommendation["reason"] or "回复" in recommendation["reason"]
    assert "wechat_chat" in result["recommended_scene"]
    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_routes_romantic_waiting_to_uncertainty() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="他3小时没回消息，我已经想好分手后猫归谁了")
    )

    brief = result["brief"]
    assert brief["lane"] == "亲密关系 / 不确定感"
    assert brief["mechanism"] == "关系不确定感"
    assert brief["save_tool"] == "事实 / 脑补 / 我需要什么"

    guidance = result["topic_guidance"]
    assert (
        guidance["matched_direction_id"]
        == "relationship_uncertainty_waiting_message"
    )
    assert guidance["directions"][0]["id"] == guidance["matched_direction_id"]
    assert guidance["directions"][0]["id"] != "message_boundary_reply_draft"
    assert "事实 / 脑补 / 我需要什么" in guidance["directions"][0]["saveable_tool"]
    assert "职场" in guidance["directions"][0]["avoid"]

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "iphone_notes"
    assert recommendation["role"] == "save_tool"
    assert recommendation["command_hint"] == "--local-image-style iphone_notes"

    assert "事实 / 脑补 / 我需要什么" in result["recommended_scene"]
    assert not any(
        term in result["recommended_scene"]
        for term in ("我现在不方便", "我会在什么时间处理", "处理")
    )
    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_routes_sleep_recovery_growth_sublane() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复")
    )

    brief = result["brief"]
    assert brief["lane"] == "睡眠恢复 / 轻养生"

    guidance = result["topic_guidance"]
    assert guidance["matched_direction_id"] == "sleep_recovery_shutdown_card"
    first_direction = guidance["directions"][0]
    assert first_direction["id"] == "sleep_recovery_shutdown_card"
    assert "睡眠恢复" in first_direction["name"] or "办公室恢复" in first_direction["name"]
    assert "5 分钟" in first_direction["saveable_tool"] or "下班信号" in first_direction["saveable_tool"]
    assert any(
        marker in first_direction["comment_prompt"]
        for marker in ("A.", "B.", "____")
    )
    sleep_format = _format_recommendation(first_direction)
    assert sleep_format["format_archetype"] == "note_card"
    assert sleep_format["cover_role"] == "save_tool"
    assert sleep_format["visual_evidence_need"] == "low"

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "iphone_notes"
    assert recommendation["role"] == "save_tool"

    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_routes_relationship_mixed_signal_camp_vote() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="对方忽冷忽热，我想问清楚又怕显得烦，想让评论区站队")
    )

    guidance = result["topic_guidance"]
    assert guidance["matched_direction_id"] == "relationship_mixed_signal_camp_vote"
    first_direction = guidance["directions"][0]
    assert first_direction["id"] == "relationship_mixed_signal_camp_vote"
    assert "A." in first_direction["comment_prompt"]
    assert "B." in first_direction["comment_prompt"]
    assert "事实" in first_direction["saveable_tool"]
    assert "问" in first_direction["saveable_tool"]
    assert first_direction["scene_fit"]

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "iphone_notes"
    assert recommendation["role"] == "save_tool"
    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_routes_social_battery_cancel_plan_boundary() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="约好的局临时不想去了，怕扫兴又很累，想写社交电量边界")
    )

    brief = result["brief"]
    assert brief["lane"] == "孤独 / 比较焦虑"

    guidance = result["topic_guidance"]
    assert guidance["matched_direction_id"] == "social_battery_cancel_plan_boundary"
    first_direction = guidance["directions"][0]
    assert first_direction["id"] == "social_battery_cancel_plan_boundary"
    assert "A." in first_direction["comment_prompt"]
    assert "B." in first_direction["comment_prompt"]
    assert "取消" in first_direction["saveable_tool"]
    assert "社交" in first_direction["trend_signal"]

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "iphone_notes"
    assert recommendation["role"] == "save_tool"
    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_routes_after_hours_message_body_alarm() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="领导18:57发来一句在吗，下班后身体被消息拉回工位")
    )

    guidance = result["topic_guidance"]
    assert guidance["matched_direction_id"] == "after_hours_message_body_alarm"
    first_direction = guidance["directions"][0]
    assert first_direction["id"] == "after_hours_message_body_alarm"
    assert "A." in first_direction["comment_prompt"]
    assert "B." in first_direction["comment_prompt"]
    assert "C." in first_direction["comment_prompt"]
    assert "下班消息" in first_direction["saveable_tool"]
    assert "身体" in first_direction["trend_signal"]

    recommendation = _image_recommendation(result)
    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] in {"iphone_notes", "wechat_chat"}
    assert recommendation["role"] in {"save_tool", "comment_prompt"}
    _assert_no_internal_source_leakage(result)


def test_psychology_topic_guidance_recommends_notes_for_boundary_tools() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="同事临时加需求，想练一版边界句")
    )

    recommendation = _image_recommendation(result)

    assert recommendation["recommended_backend"] == "local_social_screenshot"
    assert recommendation["local_style"] == "iphone_notes"
    assert recommendation["provider"] == ""
    assert recommendation["model"] == ""
    assert recommendation["role"] == "save_tool"
    assert recommendation["max_text_units"] == 3
    assert recommendation["command_hint"] == "--local-image-style iphone_notes"
    assert "边界句" in recommendation["reason"] or "工具卡" in recommendation["reason"]
    assert "iphone_notes" in result["recommended_scene"]
    _assert_no_internal_source_leakage(result)


def test_generic_topic_guidance_recommends_provider_for_visual_evidence_domains() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="human_enrichment_daily_post",
            account_id="acct-enrichment-local",
            scene="想把书桌角落改成十分钟适我主义手作位",
        )
    )

    recommendation = _image_recommendation(result)

    assert recommendation["recommended_backend"] == "provider_image"
    assert recommendation["local_style"] == ""
    assert recommendation["provider"] == "bailian"
    assert recommendation["model"] == "qwen-image-2.0-pro"
    assert recommendation["role"] == "evidence_or_scene"
    assert recommendation["text_density"] == "low"
    assert recommendation["max_text_units"] <= 1
    assert recommendation["command_hint"] == "--auto-generate-image"
    assert "空间" in recommendation["reason"] or "物件" in recommendation["reason"]
    assert "provider_image" in result["recommended_scene"]
    assert "qwen-image-2.0-pro" in result["recommended_scene"]
    _assert_no_internal_source_leakage(result)


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
        if playbook_id == "ai_tech_daily_post":
            continue
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
        assert _image_recommendation(result)["command_hint"]
        assert open_slots[0]["id"] not in curated_ids
        assert open_slots[0]["scene_fit"].startswith("开放探索")
        _assert_no_internal_source_leakage(result)


def test_classic_poetry_topic_guidance_same_lane_scene_changes_do_not_keep_fixed_curated_anchors() -> None:
    scenes = (
        "读到李白长风破浪会有时，想写给低谷里的自己",
        "深夜读到李清照，想写一句能安放情绪的词",
        "下班路上看到月亮，想写一句古诗词金句给没联系很久的人",
    )

    results = [
        run_guide_post(
            GuidePostRequest(
                playbook_id="classic_poetry_quote_post",
                account_id="acct-classic-poetry-local",
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
        "classic_tang_resilience_quote",
        "classic_song_emotion_quote",
        "classic_moon_longing_quote",
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


@pytest.mark.parametrize(
    ("scene", "expected_lane_fragment", "expected_matched_direction_id"),
    (
        (
            "读到李白长风破浪会有时，想写给低谷里的自己",
            "唐诗金句",
            "classic_tang_resilience_quote",
        ),
        (
            "想用李清照的词写深夜里那种瘦下来的情绪",
            "宋词清醒",
            "classic_song_emotion_quote",
        ),
        (
            "想写王维山水诗，给下班后的自己一点松弛",
            "山水松弛",
            "classic_landscape_ease_quote",
        ),
    ),
)
def test_classic_poetry_topic_guidance_matches_quote_families(
    scene: str,
    expected_lane_fragment: str,
    expected_matched_direction_id: str,
) -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="classic_poetry_quote_post",
            account_id="acct-classic-poetry-local",
            scene=scene,
        )
    )

    guidance = result["topic_guidance"]
    first_direction = guidance["directions"][0]

    assert expected_lane_fragment in result["brief"]["lane"]
    assert "怀民关系" not in result["brief"]["lane"]
    assert "黄州自救" not in result["brief"]["lane"]
    assert guidance["matched_direction_id"] == expected_matched_direction_id
    assert first_direction["id"] == expected_matched_direction_id
    assert first_direction["direction_type"] == "curated"
    assert first_direction["id"].startswith("classic_")
    assert "怀民" not in first_direction["name"]
    assert "怀民" not in first_direction["scene_fit"]
    assert "sushi_role_pair_huimin" not in [
        direction["id"] for direction in guidance["directions"]
    ]
    assert not any(
        direction["name"].startswith("开放探索：怀民")
        for direction in guidance["directions"]
    )


def test_classic_poetry_topic_guidance_generic_prompt_surfaces_multiple_curated_families() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="classic_poetry_quote_post",
            account_id="acct-classic-poetry-local",
            scene="想做一期古诗词金句，先给我几个不同切口",
        )
    )

    curated_ids = [
        direction["id"]
        for direction in result["topic_guidance"]["directions"]
        if direction["direction_type"] == "curated"
    ]

    assert result["brief"]["lane"] == "唐诗金句 / 低谷打气"
    assert len(curated_ids) >= 2
    assert {
        "classic_tang_resilience_quote",
        "classic_landscape_ease_quote",
    } <= set(curated_ids)
    assert "sushi_role_pair_huimin" not in curated_ids


def test_format_guide_post_markdown_includes_scene_fit() -> None:
    result = run_guide_post(
        GuidePostRequest(scene="朋友半夜把情绪都倒给我，我不知道怎么回")
    )

    markdown = format_guide_post_markdown(result)

    assert "scene:" in markdown
    assert "fit:" in markdown
    assert "format:" in markdown
    assert "visual:" in markdown
    assert "匹配当前场景信号" in markdown
    assert "## Image Recommendation" in markdown
    assert "after_topic_direction_confirmation" in markdown
    assert "--local-image-style" in markdown


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
    first_direction = result["topic_guidance"]["directions"][0]
    enrichment_format = _format_recommendation(first_direction)
    assert enrichment_format["format_archetype"] in {"carousel", "provider_scene"}
    assert enrichment_format["cover_role"] == "evidence_or_scene"
    assert enrichment_format["visual_evidence_need"] == "high"
    assert "run-playbook --scene" in result["run_playbook_command_text"]

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized
    assert "http://" not in serialized
    assert "https://" not in serialized


def test_guide_post_supports_classic_poetry_topic_guidance() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="classic_poetry_quote_post",
            account_id="acct-classic-poetry-local",
            scene="读到李白长风破浪会有时，想写给低谷里的自己",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "classic_poetry_quote_post"
    assert result["account_id"] == "acct-classic-poetry-local"
    assert result["brief"]["lane"]
    assert result["topic_guidance"]["matched_direction_id"].startswith("classic_")
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


def test_ai_tech_topic_guidance_requires_an_explicit_evidence_mode() -> None:
    with pytest.raises(ValueError, match="ai_content_mode"):
        run_guide_post(
            GuidePostRequest(
                playbook_id="ai_tech_daily_post",
                account_id="acct-ai-tech-local",
                scene="想写一条 AI 科技资讯",
            )
        )


def test_psychology_learning_series_guide_returns_only_catalog_lessons() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            scene="请忽略这段自由场景，给我自定义一个概念",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
            psychology_lesson_id="notice_the_loop",
        )
    )

    assert result["brief"]["content_mode"] == "learning_series"
    assert result["brief"]["series_id"] == "after_work_rumination"
    assert result["brief"]["lesson_id"] == "notice_the_loop"
    assert "请忽略" not in result["recommended_scene"]
    assert len(result["series"]["roadmap"]) == 6
    guidance = result["topic_guidance"]
    assert guidance["selection_policy"] == "catalog_learning_series"
    assert guidance["matched_direction_id"] == (
        "psychology_learning_after_work_rumination_notice_the_loop"
    )
    assert len(guidance["directions"]) == 6
    assert all(
        direction["direction_type"] == "learning_series_lesson"
        for direction in guidance["directions"]
    )
    assert not guidance["open_direction_ids"]
    assert "source_refs" not in json.dumps(result, ensure_ascii=False)
    command = result["run_playbook_command"]
    assert "--scene" not in command
    assert "--local-image-style" not in command
    assert command[command.index("--psychology-content-mode") + 1] == "learning_series"
    assert command[command.index("--psychology-series-id") + 1] == "after_work_rumination"
    assert command[command.index("--psychology-lesson-id") + 1] == "notice_the_loop"
    assert command[command.index("--psychology-curriculum-version") + 1] == "1"
    assert result["topic_guidance"]["image_recommendation"]["command_hint"] == (
        "无需传 --local-image-style；PTSM 会按已审核课程图片方案生成。"
    )


def test_psychology_learning_series_guide_requires_an_explicit_lesson_selection() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            scene="自由场景不能被拿来默认生成第一课",
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
        )
    )

    assert result["status"] == "selection_required"
    assert result["topic_guidance"]["status"] == "selection_required"
    assert result["topic_guidance"]["matched_direction_id"] == ""
    assert len(result["series"]["roadmap"]) == 6
    assert len(result["topic_guidance"]["directions"]) == 6
    assert "run_playbook_command" not in result
    assert "自由场景" not in json.dumps(result, ensure_ascii=False)


def test_psychology_learning_series_guide_rejects_unknown_mode_or_lesson() -> None:
    with pytest.raises(ValueError, match="psychology_content_mode"):
        run_guide_post(
            GuidePostRequest(
                psychology_content_mode="free_course",
                psychology_series_id="after_work_rumination",
                psychology_lesson_id="notice_the_loop",
            )
        )

    with pytest.raises(ValueError, match="lesson"):
        run_guide_post(
            GuidePostRequest(
                psychology_content_mode="learning_series",
                psychology_series_id="after_work_rumination",
                psychology_lesson_id="fake_lesson",
            )
        )


def test_psychology_learning_series_guide_rejects_other_playbooks() -> None:
    with pytest.raises(ValueError, match="only supported by modern_psychology_post"):
        run_guide_post(
            GuidePostRequest(
                playbook_id="daily_english_post",
                psychology_content_mode="learning_series",
                psychology_series_id="after_work_rumination",
                psychology_lesson_id="notice_the_loop",
                psychology_curriculum_version="1",
            )
        )


@pytest.mark.parametrize(
    ("mode", "scene"),
    (
        ("news_brief", "今天想做一条 AI 科技热点快讯"),
        ("hands_on", "复盘一次让 AI 先追问再输出的提示词测试"),
        ("fact_translation", "解释一项 AI 模型更新到底影响谁"),
    ),
)
def test_ai_tech_topic_guidance_only_returns_directions_for_requested_mode(
    mode: str,
    scene: str,
) -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="ai_tech_daily_post",
            account_id="acct-ai-tech-local",
            scene=scene,
            ai_content_mode=mode,
            ai_evidence_file_path="inputs/ai-evidence.json",
        )
    )

    guidance = result["topic_guidance"]
    directions = guidance["directions"]
    command = result["run_playbook_command"]

    assert result["brief"]["content_mode"] == mode
    assert result["brief"]["evidence_required"]
    assert directions
    assert all(direction["content_mode"] == mode for direction in directions)
    assert not any(direction["direction_type"] == "open_scene" for direction in directions)
    assert "第一人称微场景" not in result["recommended_scene"]
    assert "--scene" not in command
    assert command[command.index("--ai-content-mode") + 1] == mode
    assert command[command.index("--ai-evidence-file") + 1] == "inputs/ai-evidence.json"
    assert command[command.index("--topic-direction-id") + 1] == guidance["matched_direction_id"]


def test_ai_prompt_direction_is_a_hands_on_test_replay_not_a_copyable_lane() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="ai_tech_daily_post",
            account_id="acct-ai-tech-local",
            scene="复盘一次让 AI 先追问再输出的提示词测试",
            ai_content_mode="hands_on",
        )
    )

    prompt_direction = next(
        direction
        for direction in result["topic_guidance"]["directions"]
        if direction["id"] == "ai_prompt_context_card"
    )

    assert prompt_direction["content_mode"] == "hands_on"
    assert "实测" in prompt_direction["name"] or "复盘" in prompt_direction["name"]
    assert "直接复制" not in prompt_direction["viral_hook"]
    assert "直接复制" not in prompt_direction["saveable_tool"]


def _confirm_custom_psychology_series(
    *,
    store: PsychologyLearningSeriesStore,
    outline: tuple[dict[str, str], ...],
    topic: str = "下班后的脑内回放",
):
    proposal = plan_psychology_learning_series(
        topic=topic,
        outline=outline,
    )
    store.persist_proposal(proposal)
    return store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )


def test_custom_learning_series_guide_recommends_publication_order_without_autoselecting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "series-store"
    monkeypatch.setattr(
        psychology_learning_domain,
        "DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT",
        store_root,
    )
    store = PsychologyLearningSeriesStore()
    catalog = _confirm_custom_psychology_series(
        store=store,
        outline=(
            {"id": "review", "title": "回顾已有线索", "goal": "整理一个发现"},
            {"id": "notice", "title": "先识别触发时刻", "goal": "看见一个瞬间"},
            {"id": "practice", "title": "练习一个小动作", "goal": "今天尝试一次"},
        ),
    )
    runtime_bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="review",
        curriculum_version=catalog.curriculum_version,
    )

    result = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=catalog.series_id,
        )
    )

    series = result["series"]
    assert result["status"] == "selection_required"
    assert result["topic_guidance"]["matched_direction_id"] == ""
    assert "run_playbook_command" not in result
    assert [item["lesson_id"] for item in series["publication_plan"]] == [
        "notice",
        "practice",
        "review",
    ]
    assert series["publication_plan"][0]["canonical_lesson_number"] == 2
    assert series["production_progress"] == {
        "kind": "operator_content_production",
        "completed_lesson_ids": [],
        "completed_count": 0,
        "total_lessons": 3,
    }
    assert series["origin"] == "user_confirmed"
    assert series["recommended_next_lesson"]["lesson_id"] == "notice"
    assert series["recommended_next_lesson_id"] == "notice"
    assert series["recommended_next_lesson"]["publication_order"] == 1
    serialized = json.dumps(result, ensure_ascii=False)
    assert "整理一个发现" not in serialized
    assert "source_refs" not in serialized
    assert "proposal_fingerprint" not in serialized
    assert "catalog_digest" not in serialized
    assert str(store_root) not in serialized
    assert "整理一个发现" not in json.dumps(
        {
            "runtime_contract": runtime_bundle.runtime_contract,
            "manifest": runtime_bundle.manifest,
        },
        ensure_ascii=False,
    )

    markdown = format_guide_post_markdown(result)
    assert "## Recommended Publication Order" in markdown
    assert "## Recommended Next Lesson" in markdown
    assert "第2课" in markdown
    assert "整理一个发现" not in markdown

    store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=["notice"],
    )
    after_one_completed = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=catalog.series_id,
        )
    )
    assert after_one_completed["series"]["recommended_next_lesson"]["lesson_id"] == (
        "practice"
    )
    assert after_one_completed["series"]["production_progress"]["completed_count"] == 1
    assert after_one_completed["series"]["production_progress"]["total_lessons"] == 3

    store.write_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
        completed_lesson_ids=["review", "notice", "practice"],
    )
    all_completed = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=catalog.series_id,
        )
    )
    assert all_completed["series"]["recommended_next_lesson"] is None
    assert all_completed["series"]["recommended_next_lesson_id"] is None
    assert all_completed["series"]["recommendation_status"] == "all_completed"
    assert "没有下一课" in all_completed["series"]["recommendation_message"]
    assert all_completed["series"]["production_progress"]["completed_count"] == 3
    assert "没有下一课" in format_guide_post_markdown(all_completed)


def test_custom_learning_series_guide_uses_requested_historical_version_and_allows_nonrecommended_lesson(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "series-store"
    monkeypatch.setattr(
        psychology_learning_domain,
        "DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT",
        store_root,
    )
    store = PsychologyLearningSeriesStore()
    first_catalog = _confirm_custom_psychology_series(
        store=store,
        outline=(
            {"id": "review", "title": "回顾已有线索", "goal": "整理一个发现"},
            {"id": "notice", "title": "先识别触发时刻", "goal": "看见一个瞬间"},
            {"id": "practice", "title": "练习一个小动作", "goal": "今天尝试一次"},
        ),
    )
    second_catalog = _confirm_custom_psychology_series(
        store=store,
        outline=(
            {"id": "notice", "title": "先识别触发时刻", "goal": "看见一个瞬间"},
            {"id": "support", "title": "安排支持资源", "goal": "留一个支持选择"},
        ),
    )

    historic = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=first_catalog.series_id,
            psychology_curriculum_version="1",
        )
    )
    current = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=second_catalog.series_id,
            psychology_curriculum_version="2",
        )
    )
    selected_nonrecommended = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=first_catalog.series_id,
            psychology_curriculum_version="1",
            psychology_lesson_id="review",
        )
    )

    with pytest.raises(ValueError, match="custom psychology learning selection requires"):
        run_guide_post(
            GuidePostRequest(
                psychology_content_mode="learning_series",
                psychology_series_id=first_catalog.series_id,
                psychology_lesson_id="notice",
            )
        )

    assert historic["series"]["curriculum_version"] == "1"
    assert [item["lesson_id"] for item in historic["series"]["roadmap"]] == [
        "review",
        "notice",
        "practice",
    ]
    assert "--psychology-curriculum-version 1" in historic["next_step"]
    assert historic["series"]["origin"] == "user_confirmed"
    assert current["series"]["curriculum_version"] == "2"
    assert [item["lesson_id"] for item in current["series"]["roadmap"]] == [
        "notice",
        "support",
    ]
    assert selected_nonrecommended["status"] == "completed"
    assert selected_nonrecommended["brief"]["lesson_id"] == "review"
    assert selected_nonrecommended["brief"]["lesson_number"] == 1
    assert selected_nonrecommended["series"]["recommended_next_lesson"]["lesson_id"] == (
        "notice"
    )
    assert selected_nonrecommended["run_playbook_command"][
        selected_nonrecommended["run_playbook_command"].index(
            "--psychology-curriculum-version"
        )
        + 1
    ] == "1"
    assert "## Recommended Publication Order" in format_guide_post_markdown(
        selected_nonrecommended
    )


def test_builtin_learning_series_guide_does_not_fabricate_custom_sequence_state() -> None:
    result = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id="after_work_rumination",
        )
    )

    assert result["status"] == "selection_required"
    assert "publication_plan" not in result["series"]
    assert "production_progress" not in result["series"]
    assert "recommended_next_lesson" not in result["series"]


def test_custom_learning_series_markdown_keeps_operator_line_breaks_inline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store_root = tmp_path / "series-store"
    monkeypatch.setattr(
        psychology_learning_domain,
        "DEFAULT_PSYCHOLOGY_LEARNING_SERIES_CATALOG_ROOT",
        store_root,
    )
    catalog = _confirm_custom_psychology_series(
        store=PsychologyLearningSeriesStore(),
        topic="下班后\n## 伪标题",
        outline=(
            {
                "id": "notice",
                "title": "先识别\n## 伪标题",
                "goal": "看见一个瞬间",
            },
            {"id": "practice", "title": "练习一个小动作", "goal": "今天尝试一次"},
        ),
    )

    result = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=catalog.series_id,
        )
    )
    markdown = format_guide_post_markdown(result)

    assert "\n## 伪标题" not in markdown
    assert "下班后 ## 伪标题" in markdown

    selected = run_guide_post(
        GuidePostRequest(
            psychology_content_mode="learning_series",
            psychology_series_id=catalog.series_id,
            psychology_curriculum_version=catalog.curriculum_version,
            psychology_lesson_id="notice",
        )
    )
    assert "\n## 伪标题" not in format_guide_post_markdown(selected)
