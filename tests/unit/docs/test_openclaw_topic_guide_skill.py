from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = PROJECT_ROOT / "integrations" / "openclaw" / "ptsm-xhs-topic-guide" / "SKILL.md"


def test_openclaw_topic_guide_skill_documents_generic_two_step_flow() -> None:
    assert SKILL_PATH.exists()

    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "guide-post" in text
    assert "run-playbook" in text
    assert text.index("guide-post") < text.index("run-playbook")
    assert "--caller openclaw" in text
    assert "--publish-mode dry-run" in text
    assert "--playbook-id" in text


def test_openclaw_topic_guide_skill_auto_maps_intent_and_clarifies_ambiguity() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "自动" in text
    for playbook_id in (
        "fengkuang_daily_post",
        "human_enrichment_daily_post",
        "sushi_poetry_daily_post",
        "wuxia_character_post",
        "ai_tech_daily_post",
        "daily_english_post",
        "world_cup_daily_post",
        "reddit_curation_daily_post",
    ):
        assert playbook_id in text
    for keyword in (
        "武侠",
        "AI",
        "每日英语",
        "世界杯",
        "Reddit",
    ):
        assert keyword in text
    assert "ptsm-xhs-psychology" in text
    assert "模糊" in text or "ambiguous" in text
    assert "澄清" in text or "clarification" in text


def test_openclaw_topic_guide_skill_shows_only_returned_direction_fields() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "topic_guidance.directions" in text
    for phrase in (
        "direction name",
        "trend signal",
        "viral hook",
        "best scenes",
        "content angle",
        "saveable tool",
        "comment prompt",
        "avoid note",
        "scene_fit",
        "direction_type",
        "open_scene",
    ):
        assert phrase in text

    assert "call `guide-post` again" in text
    assert "PTSM-returned open_scene" in text
    assert "不要展示内部研究路径" in text
    assert "不要展示原始研究笔记" in text
    assert "raw source URLs" in text
    assert "provenance" in text
    assert "Do not copy topic logic" in text
    assert "fk_work_object_vent" not in text
    assert "enrichment_desk_corner_variable" not in text
    assert "sushi_role_pair_huimin" not in text
