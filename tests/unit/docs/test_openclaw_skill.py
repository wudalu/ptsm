from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = PROJECT_ROOT / "integrations" / "openclaw" / "ptsm-xhs-psychology" / "SKILL.md"


def test_openclaw_psychology_skill_documents_two_step_guidance_flow() -> None:
    assert SKILL_PATH.exists()

    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "guide-post" in text
    assert "run-playbook" in text
    assert text.index("guide-post") < text.index("run-playbook")
    assert "--caller openclaw" in text
    assert "--guidance-ack" in text
    assert "--topic-direction-id" in text
    assert "trend signal" in text
    assert "viral hook" in text
    assert "scene_fit" in text
    assert "direction_type" in text
    assert "open_scene" in text
    assert "PTSM-returned open_scene" in text
    assert "topic_guidance.image_recommendation" in text
    assert "recommended_backend" in text
    assert "local_social_screenshot" in text
    assert "provider_image" in text
    assert "model" in text
    assert "Do not invent, expand, or replace PTSM-returned image recommendation" in text
    assert "call `guide-post` again" in text
    assert "睡眠恢复" in text
    assert "轻养生" in text
    assert "PTSM-returned psychology sublane" in text
    assert "提高浏览量" in text
    assert "xhs-record-metrics" in text
    assert "xhs-metrics-report" in text
    assert "--group-by topic_direction_id" in text
    assert "--group-by image_style" in text
    assert "Do not invent views, likes, saves, comments, shares" in text
    assert "不要展示内部研究路径" in text
    assert "不要展示原始研究笔记" in text
    assert "ptsm-xhs-topic-guide" in text
    assert "psychology-specific wrapper" in text
