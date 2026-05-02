from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = PROJECT_ROOT / "docs"


def test_readme_links_docs_index() -> None:
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/index.md" in readme_text


def test_harness_engineering_doc_exists_with_key_sections() -> None:
    doc_text = (DOCS_ROOT / "harness-engineering.md").read_text(encoding="utf-8")

    assert "system of record" in doc_text
    assert "agent readability" in doc_text
    assert "observability" in doc_text
    assert "threshold" in doc_text
    assert "diagnostic" in doc_text


def test_task_completion_automation_mentions_verification_evidence() -> None:
    doc_text = (DOCS_ROOT / "operations" / "task-completion-automation.md").read_text(
        encoding="utf-8"
    )

    assert ".evidence.json" in doc_text
    assert "attempt history" in doc_text
    assert "side-effects.json" in doc_text


def test_operations_doc_mentions_plan_runs_command() -> None:
    doc_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")

    assert "plan-runs" in doc_text
    assert "gc" in doc_text
    assert "harness-evals" in doc_text
    assert "harness-report" in doc_text
    assert "diagnose-publish" in doc_text
    assert "--auto-generate-image" in doc_text


def test_docs_cover_image_generation_provider_paths() -> None:
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")

    assert "PIC_MODEL_API_KEY" in runbook_text
    assert "JIMENG_API_KEY" in runbook_text
    assert "JIMENG_SECRET_KEY" in runbook_text
    assert "outputs/generated_images" in observability_text


def test_docs_index_links_core_maps() -> None:
    index_text = (DOCS_ROOT / "index.md").read_text(encoding="utf-8")

    assert "harness-engineering.md" in index_text
    assert "architecture.md" in index_text
    assert "runtime.md" in index_text
    assert "playbooks.md" in index_text
    assert "skills.md" in index_text
    assert "observability.md" in index_text
    assert "operations.md" in index_text
    assert "shared-contracts.md" in index_text
