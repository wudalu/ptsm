from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = PROJECT_ROOT / "docs"
CORE_DOCS = [
    DOCS_ROOT / "harness-engineering.md",
    DOCS_ROOT / "index.md",
    DOCS_ROOT / "architecture.md",
    DOCS_ROOT / "runtime.md",
    DOCS_ROOT / "playbooks.md",
    DOCS_ROOT / "skills.md",
    DOCS_ROOT / "observability.md",
    DOCS_ROOT / "operations.md",
    DOCS_ROOT / "shared-contracts.md",
]
REQUIRED_KEYS = {
    "status",
    "owner",
    "last_verified",
    "source_of_truth",
    "related_paths",
}
FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def test_core_docs_have_required_front_matter() -> None:
    for path in CORE_DOCS:
        metadata = _load_front_matter(path)
        assert REQUIRED_KEYS.issubset(metadata)
        assert metadata["status"] in {"active", "historical", "draft"}
        assert isinstance(metadata["owner"], str) and metadata["owner"].strip()
        date.fromisoformat(str(metadata["last_verified"]))
        assert isinstance(metadata["source_of_truth"], bool)
        assert isinstance(metadata["related_paths"], list)
        assert metadata["related_paths"]


def test_active_core_docs_are_recently_verified() -> None:
    stale_cutoff = date.today() - timedelta(days=90)

    for path in CORE_DOCS:
        metadata = _load_front_matter(path)
        if metadata["status"] != "active":
            continue
        last_verified = date.fromisoformat(str(metadata["last_verified"]))
        assert last_verified >= stale_cutoff


def test_docs_index_links_every_core_doc() -> None:
    index_text = (DOCS_ROOT / "index.md").read_text(encoding="utf-8")

    for path in CORE_DOCS:
        if path.name == "index.md":
            continue
        assert path.name in index_text


def test_operations_and_shared_contracts_docs_link_expected_targets() -> None:
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    shared_contracts_text = (DOCS_ROOT / "shared-contracts.md").read_text(
        encoding="utf-8"
    )

    assert "operations/local-runbook.md" in operations_text
    assert "operations/task-completion-automation.md" in operations_text
    assert "../shared_contracts/README.md" in shared_contracts_text
    assert (
        "../shared_contracts/planning/planning_brief.schema.yaml"
        in shared_contracts_text
    )
    assert (
        "../shared_contracts/playbook_policies/content_drafting.policy.yaml"
        in shared_contracts_text
    )


def _load_front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    assert match, f"{path.name} must start with YAML front matter"
    payload = yaml.safe_load(match.group(1)) or {}
    assert isinstance(payload, dict)
    return payload
