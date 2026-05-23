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
    assert {
        "boundary_sandwich_refusal",
        "self_compassion_laoji",
        "loofah_soup_communication",
        "ai_companion_boundary",
    } <= direction_ids

    boundary = next(
        direction
        for direction in topic_guidance["directions"]
        if direction["id"] == "boundary_sandwich_refusal"
    )
    assert boundary["name"] == "边界感：三明治拒绝法"
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


def test_run_guide_post_rejects_unsupported_playbook() -> None:
    with pytest.raises(ValueError, match="guide-post only supports"):
        run_guide_post(
            GuidePostRequest(
                playbook_id="sushi_poetry_daily_post",
                scene="夜里读到定风波",
            )
        )
