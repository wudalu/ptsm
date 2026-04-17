from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_architecture_doc_declares_dependency_rules() -> None:
    text = (PROJECT_ROOT / "docs/architecture.md").read_text(encoding="utf-8")

    assert "Dependency Direction" in text
    assert "dependency direction" in text
    assert "mechanical enforcement" in text
    assert "tests/unit/architecture/" in text
    assert "interfaces" in text
    assert "application" in text
    assert "agent_runtime" in text
    assert "infrastructure" in text
    assert "playbooks" in text
    assert "skills" in text
