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


def test_new_domain_workflow_requires_complete_docs_surface() -> None:
    agents_text = (PROJECT_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    workflow_text = (DOCS_ROOT / "development-workflow.md").read_text(
        encoding="utf-8"
    )
    harness_text = (DOCS_ROOT / "harness-engineering.md").read_text(encoding="utf-8")

    required_markers = [
        "完整文档面",
        "docs/operations.md",
        "docs/operations/",
        "architecture.md",
        "runtime.md",
        "playbooks.md",
        "skills.md",
        "harness-engineering.md",
    ]

    for text in [agents_text, workflow_text, harness_text]:
        for marker in required_markers:
            assert marker in text


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


def test_operations_doc_records_required_eval_harness_gate() -> None:
    doc_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")

    assert "required_failed > 0" in doc_text
    assert "阻塞" in doc_text


def test_operations_docs_include_world_cup_domain_commands() -> None:
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    for text in [operations_text, runbook_text]:
        assert "acct-world-cup-local" in text
        assert "world_cup_daily_post" in text
        assert "世界杯主题" in text


def test_operations_docs_include_reddit_curation_domain_commands_and_credentials() -> None:
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    for text in [operations_text, runbook_text]:
        assert "acct-reddit-curation-local" in text
        assert "reddit_curation_daily_post" in text
        assert "Reddit英文讨论转译" in text
        assert "REDDIT_CLIENT_ID" in text
        assert "REDDIT_PUBLIC_JSON_FALLBACK" in text
        assert "Responsible Builder Policy" in text
        assert "explicit approval" in text


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


def test_publish_quickstart_includes_conversational_guidance() -> None:
    quickstart_text = (DOCS_ROOT / "operations" / "publish-quickstart.md").read_text(
        encoding="utf-8"
    )

    assert "对话式发布引导" in quickstart_text
    assert "用户:" in quickstart_text
    assert "助手:" in quickstart_text
    assert "先 dry-run" in quickstart_text
    assert "仅自己可见" in quickstart_text
    assert "公开发布" in quickstart_text
    assert "不要跳过" in quickstart_text


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
    assert "no provider watermark" in runbook_text
    assert "outputs/generated_images" in observability_text
    assert "watermark_policy" in observability_text
    assert "no_provider_watermark" in observability_text


def test_docs_cover_xhs_image_strategy_skill_and_active_local_selection() -> None:
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")
    xhs_image_skill_text = (
        PROJECT_ROOT / "src" / "ptsm" / "skills" / "builtin" / "xhs_image_strategy" / "SKILL.md"
    ).read_text(encoding="utf-8")
    xhs_index_text = (DOCS_ROOT / "xhs-topics" / "index.md").read_text(encoding="utf-8")
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "xhs_image_strategy" in skills_text
    assert "final_content.image_plan" in runtime_text
    assert "role" in xhs_image_skill_text
    assert "text_density" in xhs_image_skill_text
    assert "max_text_units" in xhs_image_skill_text
    assert "role" in runtime_text
    assert "text_density" in runtime_text
    assert "max_text_units" in observability_text
    assert "image-forms-by-domain.md" in xhs_index_text
    assert "--local-image-style" in runbook_text
    assert "explicit local override" in runbook_text


def test_docs_cover_wechat_local_renderer_transcript_contract() -> None:
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")

    assert "wechat_chat" in operations_text
    assert "无头部、无底部、无头像" in runbook_text
    assert "content-only" in runbook_text
    assert "theme" in runbook_text
    assert "chat_title" in runbook_text
    assert "chat_times" in runbook_text
    assert "theme" in observability_text
    assert "chat_title" in observability_text
    assert "chat_times" in observability_text


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


def test_docs_cover_psychology_learning_series_contract() -> None:
    required_markers = {
        "architecture.md": "psychology_learning.py",
        "runtime.md": "psychology_learning_draft_contract",
        "playbooks.md": "learning_series",
        "skills.md": "catalog_learning_series",
        "harness-engineering.md": "psychology.learning_receipt",
        "observability.md": "psychology_learning_series_id",
        "operations.md": "--psychology-content-mode learning_series",
        "operations/local-runbook.md": "--psychology-content-mode learning_series",
        "operations/content-experiment-runbook.md": "psychology_learning_lesson_id",
    }

    for relative_path, marker in required_markers.items():
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in doc_text, f"{relative_path} must document {marker}"


def test_docs_cover_ordinary_psychology_carousel_batch_integrity() -> None:
    required_markers = {
        "architecture.md": "recent 12 successful complete ordinary carousel receipts",
        "runtime.md": "committed only after the complete local receipt and asset ledger",
        "playbooks.md": "per-page text density, not image count",
        "skills.md": "carousel_delivery.status=ready",
        "harness-engineering.md": "stale lease recovery",
        "observability.md": "carousel_delivery",
        "operations.md": "carousel_delivery.status=ready",
        "operations/local-runbook.md": "carousel_delivery.status=ready",
        "operations/content-experiment-runbook.md": "recent 12 successful complete ordinary carousel receipts",
        "operations/publish-quickstart.md": "more than 7 pages/images",
        "operations/cloud-bootstrap.md": ".ptsm/agent_runtime",
    }

    for relative_path, marker in required_markers.items():
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert marker in doc_text, f"{relative_path} must document {marker}"


def test_psychology_carousel_oversize_router_and_relay_contract_are_documented() -> None:
    router_paths = [
        PROJECT_ROOT
        / "integrations"
        / "openclaw"
        / "ptsm-xhs-psychology"
        / "SKILL.md",
        DOCS_ROOT / "skills.md",
        DOCS_ROOT / "operations.md",
        DOCS_ROOT / "operations" / "local-runbook.md",
        DOCS_ROOT / "operations" / "publish-quickstart.md",
    ]

    for document_path in router_paths:
        text = document_path.read_text(encoding="utf-8")
        assert "one_carousel" in text, document_path
        assert "multiple_posts" in text, document_path
        assert "independent_assets" in text, document_path
        assert "independent image assets" in text, document_path
        assert "unsupported" in text, document_path

    wrapper_text = router_paths[0].read_text(encoding="utf-8")
    for marker in (
        "not a PTSM response schema",
        "batch_id",
        "target_count",
        "slot_index",
        "variation_brief",
        "variation_fingerprint",
        "relay_attempt_id",
        "relay_idempotency_key",
        "acknowledged_at",
        "retry_of",
        "relay_outcome",
        "pending",
        "partial",
        "delivered",
        "failed",
    ):
        assert marker in wrapper_text

    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")
    assert "external_relay_required" in observability_text
    assert "not a relay acknowledgement" in observability_text
    assert "run summary" in observability_text

    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    for marker in (
        "not a PTSM response schema",
        "batch_id",
        "target_count",
        "slot_index",
        "variation_brief",
        "variation_fingerprint",
        "retry_of",
    ):
        assert marker in operations_text

    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    skills_summary = skills_text.split(
        "- `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`", 1
    )[1].split("- `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`", 1)[0]
    playbooks_text = (DOCS_ROOT / "playbooks.md").read_text(encoding="utf-8")
    playbooks_summary = playbooks_text.split(
        "- `modern_psychology_post` 专门输出", 1
    )[1].split("- `PlaybookRegistry`", 1)[0]
    for summary in (skills_summary, playbooks_summary):
        assert "one_carousel" in summary
        assert "multiple_posts" in summary
        assert "independent_assets" in summary

    for marker in (
        "batch_id",
        "target_count",
        "slot_index",
        "variation_brief",
        "variation_fingerprint",
        "retry_of",
        "not PTSM response fields",
    ):
        assert marker in skills_summary

    assert "澄清一组 4–7 页普通 carousel 与多个分别确认帖子" not in skills_summary
    assert "澄清为这一组普通轮播或多个分别确认的帖子" not in playbooks_summary

    quickstart_text = (DOCS_ROOT / "operations" / "publish-quickstart.md").read_text(
        encoding="utf-8"
    )
    local_runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    cloud_bootstrap_text = (DOCS_ROOT / "operations" / "cloud-bootstrap.md").read_text(
        encoding="utf-8"
    )
    for text in (quickstart_text, local_runbook_text, cloud_bootstrap_text):
        normalized_text = " ".join(text.split())
        assert "relay ACK/outcome is authoritative" in normalized_text
        assert "emitted no ready handoff" in normalized_text
        assert "invoked no external chat/IM sender" in normalized_text

    assert "publisher/relay 尚未收到部分 set" not in quickstart_text
    assert (
        "no partial page\nreaches watermark processing, XHS MCP, an outer relay"
        not in local_runbook_text
    )
    assert "不会把部分图片交给 XHS MCP 或外层 relay" not in cloud_bootstrap_text


def test_psychology_publication_mode_router_is_discoverable_in_skill_and_operator_docs() -> None:
    document_paths = [
        PROJECT_ROOT
        / "integrations"
        / "openclaw"
        / "ptsm-xhs-psychology"
        / "SKILL.md",
        DOCS_ROOT / "skills.md",
        DOCS_ROOT / "operations.md",
        DOCS_ROOT / "operations" / "local-runbook.md",
    ]

    for document_path in document_paths:
        text = document_path.read_text(encoding="utf-8")
        assert "单篇心理学帖" in text, document_path
        assert "内置学习系列" in text, document_path
        assert "自定义学习系列" in text, document_path


def test_learning_series_docs_cover_selection_image_and_metrics_integrity() -> None:
    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")
    experiment_text = (
        DOCS_ROOT / "operations" / "content-experiment-runbook.md"
    ).read_text(encoding="utf-8")

    assert "selection_required" in runtime_text
    assert "不会默认生成第一课" in runtime_text
    assert "catalog-owned image plan" in operations_text
    assert "--local-image-style" in operations_text
    assert "同一 artifact + checkpoint" in observability_text
    assert "psychology_learning_curriculum_version" in experiment_text

    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")
    assert "controlled lesson template" in runtime_text
    assert "checkpoint-isolated" in runtime_text
    assert "entire artifact" in observability_text


def test_psychology_learning_docs_cover_current_editorial_template_and_ordered_relay() -> None:
    required_markers = {
        "architecture.md": ("builtin curriculum v2", "controlled template v3", "emoji-free"),
        "runtime.md": ("builtin curriculum v2", "controlled template v3", "attachments[].order"),
        "playbooks.md": ("builtin curriculum v2", "controlled template v3", "emoji-free"),
        "skills.md": ("controlled template v3", "attachments[].order", "emoji-free"),
        "harness-engineering.md": ("controlled-template-v3", "emoji-free", "attachments[].order"),
        "observability.md": ("builtin curriculum v2", "controlled template v3", "attachments[].order"),
        "operations.md": ("builtin curriculum v2", "controlled template v3", "attachments[].order"),
        "operations/local-runbook.md": (
            "builtin curriculum v2",
            "controlled template v3",
            "attachments[].order",
        ),
    }

    for relative_path, markers in required_markers.items():
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in doc_text, f"{relative_path} must document {marker}"


def test_docs_cover_confirmed_custom_psychology_learning_series_lifecycle() -> None:
    architecture_text = (DOCS_ROOT / "architecture.md").read_text(encoding="utf-8")
    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    playbooks_text = (DOCS_ROOT / "playbooks.md").read_text(encoding="utf-8")
    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    harness_text = (DOCS_ROOT / "harness-engineering.md").read_text(encoding="utf-8")
    observability_text = (DOCS_ROOT / "observability.md").read_text(
        encoding="utf-8"
    )
    operations_text = (DOCS_ROOT / "operations.md").read_text(encoding="utf-8")
    local_runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    experiment_text = (
        DOCS_ROOT / "operations" / "content-experiment-runbook.md"
    ).read_text(encoding="utf-8")
    topic_radar_text = (
        DOCS_ROOT / "operations" / "topic-radar-runbook.md"
    ).read_text(encoding="utf-8")

    assert "user_confirmed" in architecture_text
    assert "psychology_learning_catalog_receipt" in runtime_text
    assert "immutable" in playbooks_text
    assert "plan-psychology-series" in skills_text
    assert "psychology_learning_catalog_receipt" in harness_text
    assert "operator_content_production" in observability_text
    assert "plan-psychology-series" in operations_text
    assert "confirm-psychology-series" in operations_text
    assert "proposal_fingerprint" in operations_text
    assert "recommended_next_lesson" in operations_text
    assert "--curriculum-outline-file" in local_runbook_text
    assert "operator_content_production" in experiment_text
    assert "Topic Radar" in topic_radar_text
    assert "learning-series lesson facts" in topic_radar_text


def test_custom_learning_series_docs_cover_trusted_storage_and_recovery_boundary() -> None:
    document_paths = [
        "architecture.md",
        "runtime.md",
        "playbooks.md",
        "skills.md",
        "harness-engineering.md",
        "observability.md",
        "operations.md",
        "operations/local-runbook.md",
        "operations/content-experiment-runbook.md",
    ]

    for relative_path in document_paths:
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "provision-psychology-learning-storage" in doc_text, relative_path

    for relative_path in [
        "architecture.md",
        "runtime.md",
        "harness-engineering.md",
        "observability.md",
        "operations.md",
        "operations/local-runbook.md",
        "operations/content-experiment-runbook.md",
    ]:
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "trusted offline maintenance" in doc_text, relative_path

    for relative_path in [
        "runtime.md",
        "observability.md",
        "operations.md",
        "operations/local-runbook.md",
    ]:
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "psychology_learning_progress_persist_failed" in doc_text, relative_path
        assert "at-least-once" in doc_text, relative_path

    observability_text = (DOCS_ROOT / "observability.md").read_text(encoding="utf-8")
    assert "应用层会先删除它" not in observability_text


def test_custom_learning_series_docs_name_progress_field_and_kind() -> None:
    required_documents = [
        "runtime.md",
        "playbooks.md",
        "skills.md",
        "observability.md",
        "operations.md",
        "operations/local-runbook.md",
        "operations/content-experiment-runbook.md",
        "harness-engineering.md",
    ]

    for relative_path in required_documents:
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "production_progress" in doc_text, relative_path

    runtime_text = (DOCS_ROOT / "runtime.md").read_text(encoding="utf-8")
    local_runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "`kind` is `operator_content_production`" in runtime_text
    assert "`kind` is `operator_content_production`" in local_runbook_text
    assert "builtin roadmap omits `series.publication_plan`" in runtime_text
    assert "`series.lessons` plus top-level `publication_plan`" in local_runbook_text

    skills_text = (DOCS_ROOT / "skills.md").read_text(encoding="utf-8")
    assert (
        "custom guide 明确返回 `selection_required`、`series.roadmap`"
        in skills_text
    )

    for relative_path in ("operations.md", "playbooks.md", "skills.md"):
        doc_text = (DOCS_ROOT / relative_path).read_text(encoding="utf-8")
        assert "proposal 不返回 roadmap" in doc_text, relative_path


def test_local_runbook_shows_both_custom_learning_series_guide_commands() -> None:
    local_runbook_text = (DOCS_ROOT / "operations" / "local-runbook.md").read_text(
        encoding="utf-8"
    )
    custom_section = local_runbook_text.split("#### Custom topic / outline", 1)[1].split(
        "#### Builtin catalog", 1
    )[0]
    guide_commands = custom_section.split("uv run python -m ptsm.bootstrap guide-post")[
        1:
    ]

    assert len(guide_commands) == 2
    assert "--psychology-lesson-id" not in guide_commands[0].split("```", 1)[0]
    assert '--psychology-series-id "<returned series_id>"' in guide_commands[0]
    assert '--psychology-lesson-id "<chosen lesson_id>"' in guide_commands[1]
    assert '--psychology-curriculum-version "<returned curriculum_version>"' in (
        guide_commands[1]
    )


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
