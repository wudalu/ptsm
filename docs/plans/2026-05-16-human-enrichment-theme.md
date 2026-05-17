# Human Enrichment Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new Xiaohongshu theme, `human_enrichment_daily_post`, for "人类丰容 / 零成本日常变量实验", while fixing the current main-branch harness import slowdown and encoding native post/image forms into the project.

**Architecture:** Keep the change additive. New domain behavior lives in account YAML, playbook assets, builtin skills, playbook-local evaluation contract, and a deterministic drafting helper. Shared runtime changes are limited to harness-safe lazy imports and reusable content-review image-form metadata. No domain-specific CLI branch is required.

**Tech Stack:** Python 3.12, uv, pytest, YAML playbooks/accounts/evaluation contracts, Markdown docs/skills, existing LangGraph runtime, existing artifact/eval/harness surfaces.

## Current Docs Summary

- `AGENTS.md` and `docs/development-workflow.md` require large domain/playbook work to use a branch, isolated worktree, current docs, a plan with `verify:` and `done_when:`, docs updates, and final `harness-check`.
- `docs/harness-engineering.md` says local deterministic pytest and `harness-check` are the gate; default harness should not depend on external XHS login or live MCP.
- `docs/architecture.md` defines the layering; new domains should be additive playbook/skill/account files.
- `docs/runtime.md` says planner injects `runtime_skill_contents`, and finalize persists artifacts, memory, step evidence, and `content_review`.
- `docs/playbooks.md` defines playbook assets and optional `evaluation.yaml`.
- `docs/skills.md` defines request-scoped builtin skill discovery/selection.
- `docs/topic-radar.md` says XHS scans depend on local MCP health and should degrade cleanly.
- `docs/observability.md` says artifacts and eval results are local evidence.

## Current Main Diagnosis

1. Latest `main` matches `origin/main` at `e9f5168`.
2. `uv sync` succeeds in `.worktrees/xhs-new-theme-optimization`.
3. `uv run pytest -q --ignore=tests/e2e` was unhealthy. A faulthandler run showed test collection blocked in `mcp/types.py` through top-level import of `langchain_mcp_adapters.client` from `xiaohongshu_mcp_publisher.py`.
4. `topic-radar` can list XHS MCP tools, but keyword scans fail without a healthy login/session. Live XHS research must remain optional and bounded.
5. Current `xhs_trend_scan` has title/content-mechanic inference, but no image/carousel form signal.
6. Current image generation produces a single 3:4 cover prompt; it does not expose structured carousel/image-form guidance in artifacts.

## Research Summary

Use `docs/research/2026-05-16-xhs-new-theme-research.md` as the evidence note.

Recommended new theme: **人类丰容 / 零成本日常变量实验**.

Native post forms to encode:

- `before -> variable -> after`
- `零成本清单`
- `一周变量日记`
- `工位/卧室/通勤动线微改`
- `Colorwalk / sensory walk`
- `手作心流`

Native image forms to encode:

- 3:4 vertical cover.
- Real-life creator look, not polished poster.
- Carousel brief: cover, before state, variable/material flat lay, checklist card, after state, comment invitation.

## Scope

In scope:

- Lazy-load MCP adapter imports so deterministic pytest collection is fast and offline-safe.
- Add `acct-enrichment-local`.
- Add `human_enrichment_daily_post`.
- Add scoped builtin skills for enrichment style, visual form, and hashtags.
- Add deterministic offline draft support.
- Add playbook-local deterministic evaluation constraints.
- Add source-of-truth docs updates.
- Add optional `content_review.image_form` guidance for human review and future carousel generation.

Out of scope:

- Real Xiaohongshu publish.
- Automatic multi-image carousel generation.
- New dashboard.
- Replacing existing playbooks.

---

### Task 1: Make Harness Collection Lazy And Offline-Safe

**Files:**
- Modify: `src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py`
- Create: `tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_imports.py`
- Modify: `tests/integration/test_fengkuang_workflow.py`

**Steps:**

1. Add a failing import test that blocks `langchain_mcp_adapters.client` and imports `ptsm.infrastructure.publishers.xiaohongshu_mcp_publisher`.
2. Move `from langchain_mcp_adapters.client import MultiServerMCPClient` inside `LangChainMcpToolRunner._load_tools()`.
3. Keep `MultiServerMCPClient` behavior unchanged when real tools are loaded.
4. Make non-live integration tests pass `FakeTrendContextResolver()` explicitly when building workflows.

verify:

```bash
uv run pytest tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_imports.py tests/integration/test_fengkuang_workflow.py -q
```

done_when:

- Publisher module import does not require `langchain_mcp_adapters.client`.
- Fengkuang integration tests do not depend on XHS MCP login.

---

### Task 2: Record Research And Update XHS Topic Map

**Files:**
- Created: `docs/research/2026-05-16-xhs-new-theme-research.md`
- Modify: `docs/xhs-topics/verticals.md`

**Steps:**

1. Add `人类丰容 / 零成本日常变量实验` to recommended focus lanes.
2. Link the research note.
3. Explain why it is a standalone playbook rather than a fengkuang/psychology scene variant.

verify:

```bash
rg -n "人类丰容|零成本日常变量|2026-05-16-xhs-new-theme-research" docs/xhs-topics docs/research
```

done_when:

- Topic map links the research evidence and states the playbook rationale.

---

### Task 3: Add Account And Playbook Assets

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-enrichment-local.yaml`
- Create: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/reflection.md`
- Create: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/evaluation.yaml`
- Modify: `tests/unit/accounts/test_account_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/integration/test_playbook_selection.py`

**Steps:**

1. Add failing tests for account discovery, playbook discovery, loader assets, and account-to-playbook routing.
2. Add account YAML with `domain: 人类丰容实验`.
3. Add playbook YAML with required skills:

```yaml
required_skills:
  - xhs_trend_scan
  - topic_research
  - human_enrichment_style
  - xhs_enrichment_visuals
  - xhs_enrichment_hashtagging
```

4. Add planner/persona/reflection prompts requiring concrete object/place, one variable, saveable checklist, comment prompt, and image/carousel brief.
5. Add `evaluation.yaml` requiring `#人类丰容计划` or `#家的丰容计划`, variable/checklist/comment/save triggers, and forbidding medical/cure/meta-instruction leakage.

verify:

```bash
uv run pytest tests/unit/accounts/test_account_registry.py tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/integration/test_playbook_selection.py -q
```

done_when:

- New account routes to `human_enrichment_daily_post`.
- Playbook loader reads all new markdown assets.
- Existing playbook selection remains unchanged.

---

### Task 4: Add Scoped Skills

**Files:**
- Create: `src/ptsm/skills/builtin/human_enrichment_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_enrichment_visuals/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_enrichment_hashtagging/SKILL.md`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`

**Steps:**

1. Add failing registry/selector tests.
2. Add skill markdown with domain/platform/playbook tags.
3. Encode post forms, visual forms, hashtag rules, and anti-patterns.

verify:

```bash
uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py -q
```

done_when:

- New skills are request-scoped to the new playbook.
- Existing skill orders remain unchanged.

---

### Task 5: Add Deterministic Drafting Support

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Create: `tests/e2e/test_human_enrichment_publish_dry_run.py`

**Steps:**

1. Add failing deterministic draft test for `人类丰容实验`.
2. Implement `_is_human_enrichment_context()` and `_build_human_enrichment_draft()`.
3. Add an e2e dry-run test asserting completed status, variable/checklist/comment trigger, safety, tags, and zero required eval failures when `--eval` is used.

verify:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

done_when:

- New theme can produce offline dry-run content with no real LLM and no XHS login.
- Deterministic evaluation passes.

---

### Task 6: Preserve Image/Form Strategy In Content Review

**Files:**
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/agent_runtime/test_finalize_node.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `docs/observability.md`

**Steps:**

1. Add failing artifact/content-review test for enrichment `image_form`.
2. Add optional `content_review.image_form` with `primary_ratio: 3:4`, cover style, and recommended sequence.
3. Update image generation prompt to preserve image form guidance when present, while keeping the single-cover path.

verify:

```bash
uv run pytest tests/unit/agent_runtime/test_finalize_node.py tests/unit/application/use_cases/test_run_playbook.py -q
```

done_when:

- Artifacts expose image/form guidance for human review.
- Existing single-cover publish path remains compatible.

---

### Task 7: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/xhs-topics/verticals.md`

verify:

```bash
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
```

done_when:

- Docs-sync reports `status=ok`.
- Source-of-truth docs describe the new domain, skills, and artifact behavior.

---

### Task 8: Final Verification

verify:

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when:

- Full non-e2e tests do not hang.
- `docs-sync` and `harness-check` pass.
- A new-theme dry-run reaches `status == completed` with required eval failures at 0.
