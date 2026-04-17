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
REQUIRED_FRONT_MATTER_KEYS = {
    "status",
    "owner",
    "last_verified",
    "source_of_truth",
    "related_paths",
}
FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def test_core_docs_exist_and_have_required_front_matter() -> None:
    for path in CORE_DOCS:
        assert path.exists(), f"Missing core doc: {_rel(path)}"
        metadata = _load_front_matter(path)
        assert REQUIRED_FRONT_MATTER_KEYS.issubset(metadata), (
            f"{_rel(path)} is missing one of {sorted(REQUIRED_FRONT_MATTER_KEYS)}"
        )
        assert metadata["status"] in {"active", "historical", "draft"}
        assert isinstance(metadata["owner"], str) and metadata["owner"].strip()
        date.fromisoformat(str(metadata["last_verified"]))
        assert isinstance(metadata["source_of_truth"], bool)
        assert isinstance(metadata["related_paths"], list)
        assert metadata["related_paths"], f"{_rel(path)} must list related_paths"
        assert metadata["related_paths"], f"{_rel(path)} must list related_paths"


def test_active_core_docs_are_recently_verified() -> None:
    stale_cutoff = date.today() - timedelta(days=90)

    for path in CORE_DOCS:
        metadata = _load_front_matter(path)
        if metadata["status"] != "active":
            continue
        last_verified = date.fromisoformat(str(metadata["last_verified"]))
        assert last_verified >= stale_cutoff, (
            f"{_rel(path)} is stale: {last_verified.isoformat()}"
        )


def test_docs_index_links_every_core_doc() -> None:
    index_path = DOCS_ROOT / "index.md"
    index_text = index_path.read_text(encoding="utf-8")

    for path in CORE_DOCS:
        if path == index_path:
            continue
        relative_target = path.relative_to(DOCS_ROOT).as_posix()
        assert relative_target in index_text, (
            f"docs/index.md must link {_rel(path)}"
        )


def test_operations_doc_indexes_existing_runbooks() -> None:
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")

    assert "operations/local-runbook.md" in operations_text
    assert "operations/task-completion-automation.md" in operations_text


def test_shared_contracts_doc_indexes_contract_assets() -> None:
    shared_contracts_text = (DOCS_ROOT / "shared-contracts.md").read_text(
        encoding="utf-8"
    )

    assert "../shared_contracts/README.md" in shared_contracts_text
    assert "../shared_contracts/planning/planning_brief.schema.yaml" in (
        shared_contracts_text
    )
    assert (
        "../shared_contracts/playbook_policies/content_drafting.policy.yaml"
        in shared_contracts_text
    )


def _load_front_matter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    assert match, f"{_rel(path)} must start with YAML front matter"
    payload = yaml.safe_load(match.group(1)) or {}
    assert isinstance(payload, dict), f"{_rel(path)} front matter must be a mapping"
    return payload


def _rel(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()
