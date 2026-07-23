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
    assert "format_recommendation" in text
    assert "format_archetype" in text
    assert "cover_role" in text
    assert "body_shape" in text
    assert "visual_evidence_need" in text
    assert "avoid_format" in text
    assert "open_scene" in text
    assert "PTSM-returned open_scene" in text
    assert "topic_guidance.image_recommendation" in text
    assert "recommended_backend" in text
    assert "local_social_screenshot" in text
    assert "provider_image" in text
    assert "model" in text
    assert "Do not invent, expand, or replace PTSM-returned format recommendation" in text
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
    assert "--psychology-content-mode learning_series" in text
    assert "--psychology-series-id" in text
    assert "--psychology-lesson-id" in text
    assert "--psychology-curriculum-version" in text
    assert "catalog_learning_series" in text
    assert "learning_series_lesson" in text
    assert "selection_required" in text
    assert "不会默认生成第一课" in text
    assert "catalog-owned image plan" in text
    assert "--local-image-style" in text
    assert "--group-by psychology_learning_series_id" in text
    assert "--group-by psychology_learning_curriculum_version" in text
    assert "--group-by psychology_learning_lesson_id" in text
    assert "Do not run a lesson outside the PTSM plan" in text
    assert "fresh-topic-research" in text
    assert "Do not invent views, likes, saves, comments, shares" in text
    assert "不要展示内部研究路径" in text
    assert "不要展示原始研究笔记" in text
    assert "ptsm-xhs-topic-guide" in text
    assert "psychology-specific wrapper" in text


def test_openclaw_psychology_skill_documents_confirmed_custom_learning_series() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    assert "plan-psychology-series" in text
    assert "--curriculum-outline-file" in text
    assert "confirm-psychology-series" in text
    assert "--confirm" in text
    assert "user_confirmed" in text
    assert "proposal response has `series.lessons`" in text
    assert "`publication_plan`" in text
    assert "it does not have a roadmap" in normalized_text
    assert "`series.publication_plan`" in text
    assert "`series.production_progress`" in text
    assert "`kind` is `operator_content_production`" in text
    assert "only apply to `user_confirmed` custom catalogs" in normalized_text
    assert "explicit frozen curriculum version" in text
    assert "recommended_next_lesson" in text
    assert "recommendation is not an auto-selection" in text
    assert "operator_content_production" in text
    assert "not reader learning progress" in normalized_text
    assert "after_work_rumination" in text
    assert "不会默认生成第一课" in text
