from __future__ import annotations

import json

import pytest

from ptsm.application.use_cases.guide_post import GuidePostRequest, run_guide_post


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

    serialized = json.dumps(result, ensure_ascii=False)
    assert "docs/research" not in serialized
    assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
    assert '"source"' not in serialized


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

        serialized = json.dumps(result, ensure_ascii=False)
        assert "docs/research" not in serialized
        assert "2026-05-23-xhs-viral-meme-product-hooks.md" not in serialized
        assert '"source"' not in serialized
        assert "http://" not in serialized
        assert "https://" not in serialized


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


def test_run_guide_post_rejects_unsupported_playbook() -> None:
    with pytest.raises(ValueError, match="guide-post supports"):
        run_guide_post(
            GuidePostRequest(
                playbook_id="world_cup_daily_post",
                scene="想写一条看球笔记",
            )
        )
