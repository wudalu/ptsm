from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = (
    PROJECT_ROOT
    / "integrations"
    / "openclaw"
    / "ptsm-topic-radar-discovery"
    / "SKILL.md"
)


def test_openclaw_topic_radar_discovery_skill_uses_unfiltered_discovery_cli() -> None:
    assert SKILL_PATH.exists()

    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "ptsm-topic-radar-discovery" in text
    assert "全平台" in text
    assert "热点" in text
    assert "uv run python -m ptsm.bootstrap hotspot-discovery" in text
    assert "--keywords" not in text
    assert "--playbook-id" not in text
    assert "--account-id" not in text
    assert "outputs/artifacts/hotspot-discovery/" in text


def test_openclaw_topic_radar_discovery_skill_requires_status_aware_selection() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    for phrase in (
        "completed",
        "partial",
        "insufficient_evidence",
        "existing_playbook_fit",
        "ambiguous",
        "unmapped",
        "new_domain_candidate",
        "operator_headline",
        "ptsm-xhs-topic-guide",
        "ptsm-xhs-psychology",
        "choose",
    ):
        assert phrase in text

    for phrase in (
        "Do not generate or publish posts",
        "Do not expose raw feed ids",
        "Do not call `run-playbook`",
        "Do not describe a partial scan as all-platform",
    ):
        assert phrase in text
