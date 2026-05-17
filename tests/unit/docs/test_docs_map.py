from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCS_ROOT = PROJECT_ROOT / "docs"


def test_readme_links_docs_index() -> None:
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/index.md" in readme_text


def test_agent_entrypoints_link_major_development_workflow() -> None:
    agents_text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    claude_text = (PROJECT_ROOT / "CLAUDE.md").read_text(encoding="utf-8")

    assert "docs/development-workflow.md" in agents_text
    assert "new product features" in agents_text
    assert "new domains or" in agents_text
    assert "verify:" in agents_text
    assert "done_when:" in agents_text
    assert "docs/development-workflow.md" in claude_text


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


def test_publish_quickstart_covers_operator_switches_and_watermark_policy() -> None:
    quickstart_text = (DOCS_ROOT / "operations" / "publish-quickstart.md").read_text(
        encoding="utf-8"
    )
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")

    assert "publish-quickstart.md" in operations_text
    assert "--publish-mode mcp-real" in quickstart_text
    assert "--auto-generate-image" in quickstart_text
    assert "--no-auto-generate-image" in quickstart_text
    assert "--publish-image-path" in quickstart_text
    assert "--local-image-style" in quickstart_text
    assert "final_content.image_plan" in quickstart_text
    assert "watermark_removal" in quickstart_text
    assert "真实发布" in quickstart_text
    assert "必须" in quickstart_text


def test_local_runbook_does_not_reintroduce_stale_publish_flow_claims() -> None:
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "Dry-run (Content Generation Only)" not in runbook_text
    assert "without publishing or generating images" not in runbook_text
    assert "deterministic local fallback cover style" not in runbook_text
    assert "Watermark Removal (Optional)" not in runbook_text
    assert "Watermark removal** (optional)" not in runbook_text


def test_docs_cover_image_generation_provider_paths() -> None:
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")

    assert "PIC_MODEL_API_KEY" in runbook_text
    assert "JIMENG_API_KEY" in runbook_text
    assert "JIMENG_SECRET_KEY" in runbook_text
    assert "outputs/generated_images" in observability_text


def test_docs_cover_xhs_image_strategy_skill_and_active_local_selection() -> None:
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "xhs_image_strategy" in skills_text
    assert "final_content.image_plan" in runtime_text
    assert "--local-image-style" in runbook_text
    assert "explicit local override" in runbook_text


def test_docs_index_links_core_maps() -> None:
    index_text = (DOCS_ROOT / "index.md").read_text(encoding="utf-8")

    assert "harness-engineering.md" in index_text
    assert "development-workflow.md" in index_text
    assert "architecture.md" in index_text
    assert "runtime.md" in index_text
    assert "playbooks.md" in index_text
    assert "skills.md" in index_text
    assert "observability.md" in index_text
    assert "operations.md" in index_text
    assert "shared-contracts.md" in index_text
    assert "xhs-topics/index.md" in index_text


def test_playbooks_doc_mentions_persona_assets() -> None:
    playbooks_text = (DOCS_ROOT / "playbooks.md").read_text(encoding="utf-8")
    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")

    assert "persona.md" in playbooks_text
    assert "persona prompt" in runtime_text
    assert "runtime_skill_contents" in runtime_text
    assert "runtime_skill_contents" in skills_text


def test_skills_doc_links_xhs_topic_index() -> None:
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")

    assert "xhs-topics/index.md" in skills_text


def test_xhs_docs_record_trend_scan_as_builtin_skill() -> None:
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    harness_text = (DOCS_ROOT / "xhs-topics" / "harness-integration.md").read_text(
        encoding="utf-8"
    )

    assert "xhs_trend_scan" in skills_text
    assert "builtin skill" in harness_text


def test_development_workflow_doc_scopes_major_development() -> None:
    workflow_text = (DOCS_ROOT / "development-workflow.md").read_text(encoding="utf-8")

    assert "new product features" in workflow_text
    assert "new domains or playbooks" in workflow_text
    assert "new publish, verification, observability, or harness surfaces" in workflow_text
    assert "It does not cover small bug fixes" in workflow_text
    assert "verify:" in workflow_text
    assert "harness-check" in workflow_text
