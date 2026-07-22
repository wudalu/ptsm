from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SKILL_PATH = (
    PROJECT_ROOT
    / "integrations"
    / "openclaw"
    / "ptsm-xhs-domain-opportunity"
    / "SKILL.md"
)


def test_openclaw_domain_opportunity_skill_wraps_ptsm_cli() -> None:
    assert SKILL_PATH.exists()

    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "xhs-domain-opportunity" in text
    assert "uv run python -m ptsm.bootstrap xhs-domain-opportunity" in text
    assert "--keywords" in text
    assert "--sample-limit-per-keyword" in text
    assert "--skip-login-check" in text
    assert "Only add `--skip-login-check`" in text
    assert "--tool-timeout-seconds" in text
    assert "domain-opportunity-<date>.md" in text
    assert "domain-opportunity-<date>.json" in text
    assert "at least one explicit keyword" in text


def test_openclaw_domain_opportunity_skill_documents_thin_wrapper_boundaries() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    for phrase in (
        "Do not copy scoring logic",
        "Do not generate or publish posts",
        "Do not expose raw feed ids",
        "Do not treat search-level evidence as a full trend ranking",
        "PTSM owns the scan",
        "Do not call `run-playbook`",
    ):
        assert phrase in text

    assert "likes + comments * 4" not in text
    assert "uv run python -m ptsm.bootstrap run-playbook" not in text


def test_openclaw_domain_opportunity_skill_routes_next_actions() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    for phrase in (
        "existing_playbook_fit",
        "sublane_first",
        "new_domain_candidate",
        "guide-post",
        "collect-xhs-patterns",
        "new domain plan",
    ):
        assert phrase in text

    assert "ptsm-xhs-topic-guide" in text
    assert "ptsm-xhs-psychology" in text


def test_openclaw_domain_opportunity_skill_does_not_turn_generic_hotspot_requests_into_keywords() -> None:
    text = SKILL_PATH.read_text(encoding="utf-8")

    assert "If the request is broad, include current PTSM domains" not in text
    assert "ptsm-topic-radar-discovery" in text
    assert "hotspot-discovery" in text
    assert "explicit candidate domains or keywords" in text
