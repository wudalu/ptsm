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


def test_openclaw_psychology_skill_routes_publication_modes_before_detail() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    router = text.split("## Choose a publication mode", 1)[1].split(
        "## Psychology Learning Series", 1
    )[0]
    normalized_router = " ".join(router.split())

    assert "单篇心理学帖" in router
    assert "内置学习系列" in router
    assert "自定义学习系列" in router
    assert "If the request is ambiguous, show these three choices and wait." in normalized_router
    assert "Do not default to a custom series, generate a post, or publish." in normalized_router
    assert "after_work_rumination" in router
    assert "selection_required" in router
    assert "explicit lesson choice" in normalized_router
    assert "provision → plan → review → exact confirmation → roadmap" in normalized_router
    assert "继续下一课" in router
    assert "看系列进度" in router
    assert "re-query the roadmap" in normalized_router
    assert "series.roadmap" in router
    assert "series.recommended_next_lesson" in router
    assert "series.production_progress" in router
    assert "not automatic selection, generation, or publishing" in normalized_router
    assert "改目录" in router
    assert "new proposal and immutable version" in normalized_router


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


def test_openclaw_psychology_skill_documents_trusted_custom_series_provisioning() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    assert "provision-psychology-learning-storage" in text
    assert text.index("provision-psychology-learning-storage") < text.index(
        "plan-psychology-series"
    )
    assert "trusted offline maintenance" in normalized_text
    assert "path-based cleanup" in text


def test_openclaw_psychology_skill_uses_only_ptsm_returned_carousel_structure() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    for field in (
        "format_archetype",
        "carousel_style",
        "page_count",
        "ordered_roles",
        "image_count",
    ):
        assert field in text
    assert "psychology_text_card_v1" in text
    assert "4–7" in text
    assert "one topic" in normalized_text
    assert "--auto-generate-image" in text
    assert "--group-by carousel_style" in text
    assert "Show only the PTSM-returned `page_count` and `ordered_roles`" in normalized_text
    assert "Do not claim that `guide-post` returned `slides` or page copy" in normalized_text
    assert "Only show carousel pages returned by PTSM" not in normalized_text
    assert "Never write, rewrite, split, reorder, or fill a carousel page" in normalized_text
    assert "historic controlled-template-v1" in normalized_text
    assert "builtin and newly confirmed v2" in normalized_text
    assert "psychology_carousel_generation_failed" in text


def test_openclaw_psychology_skill_clarifies_oversized_carousels_and_relay_boundary() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())

    assert "more than 7 pages/images" in normalized_text
    assert "for example 12" in normalized_text
    assert "one 4–7-page carousel for one topic" in normalized_text
    assert "Do not silently split, loop, repeat, or promise" in normalized_text
    assert "max_text_units" in normalized_text
    assert "per-page copy, not page count" in normalized_text
    assert "carousel_delivery.status=ready" in text
    assert "attachments" in text
    assert "page_sha256" in text
    assert "file_sha256" in text
    assert "PTSM does not own external chat/IM delivery" in normalized_text
