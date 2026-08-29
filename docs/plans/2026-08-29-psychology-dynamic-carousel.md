# Psychology Dynamic Carousel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace fixed psychology carousel counts with content-derived 1–18 page sets, strip unsupported emoji from image-visible copy, and preserve end-to-end page order.

**Architecture:** Widen the strict psychology carousel domain contract while retaining one-topic, contiguous-order, bounded-page validation. Introduce a new frozen learning controlled-template revision for deterministic semantic pagination, then propagate the dynamic contract through guidance, prompts, rendering, receipts, skills, documentation, and harness coverage without mutating historical templates.

**Tech Stack:** Python 3.12, Pydantic, Pillow, pytest, PTSM CLI/harness, Markdown skills and source-of-truth docs.

### Task 1: Lock the dynamic carousel domain contract

**Files:**
- Modify: `tests/unit/domain/test_psychology_carousel.py`
- Modify: `src/ptsm/domain/psychology_carousel.py`

**Steps:**
1. Add tests accepting one and eighteen contiguous slides.
2. Add a test rejecting nineteen slides with a stable single-post limit error.
3. Change existing emoji tests to require normalization/removal and retain an emoji-only rejection test.
4. Run the tests and confirm RED against the current 4–7/reject-emoji contract.
5. Implement `PSYCHOLOGY_CAROUSEL_MIN_SLIDES=1`, `MAX_SLIDES=18`, before-validation emoji cleanup, and stable overflow validation.
6. Run the focused tests and commit.

verify: `uv run pytest -q tests/unit/domain/test_psychology_carousel.py`

done_when: 1 and 18 pages normalize, 19 fails closed, emoji is removed before all existing safety checks, and order remains contiguous.

### Task 2: Add frozen learning template v4 with semantic pagination

**Files:**
- Modify: `tests/unit/domain/test_psychology_learning.py`
- Modify: `tests/unit/application/use_cases/test_psychology_learning_series.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `src/ptsm/domain/psychology_learning.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`

**Steps:**
1. Add tests proving historic builtin curriculum v2/template v3 remains seven pages.
2. Add tests for current builtin curriculum v3/template v4 and at least two content-derived page counts.
3. Add custom-confirmation tests pinning new template v4 while retaining v1–v3 registry behavior.
4. Confirm RED before production changes.
5. Add version mappings, current builtin v3 snapshots, deterministic semantic unit packing/splitting, exact dynamic guide structure, and v4 artifact allowlists.
6. Run focused domain/use-case tests and commit.

verify: `uv run pytest -q tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/application/use_cases/test_guide_post.py`

done_when: historical versions rebuild unchanged, current lessons derive exact pages without a model rewrite, all approved fields remain present, and no result exceeds 18 pages.

### Task 3: Propagate dynamic ordinary drafting and overflow behavior

**Files:**
- Modify: `tests/unit/agent_runtime/test_executor_node.py`
- Modify: `tests/unit/agent_runtime/test_finalize_node.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `tests/unit/infrastructure/llm/test_contextual_drafts.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`
- Modify: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`

**Steps:**
1. Add failing tests for ordinary 1/18-page draft acceptance, 19-page stable failure, and dynamic prompt wording.
2. Update deterministic/model drafting instructions to select semantic count within one XHS post and never pad or mechanically split.
3. Ensure overflow produces no render/publish/ready side effects.
4. Run focused runtime and application tests and commit.

verify: `uv run pytest -q tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/llm/test_contextual_drafts.py`

done_when: ordinary carousels use content-derived 1–18 pages and a 19-page plan cannot reach image generation or delivery readiness.

### Task 4: Strengthen renderer and relay order evidence

**Files:**
- Modify: `tests/unit/infrastructure/images/test_note_card_backend.py`
- Modify: `tests/unit/application/services/test_image_carousel_transaction.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `src/ptsm/infrastructure/images/note_card_backend.py` only if tests reveal a dynamic-total defect
- Modify: `src/ptsm/application/services/image_carousel_transaction.py` only if required
- Modify: `src/ptsm/application/use_cases/run_playbook.py`

**Steps:**
1. Add failing coverage for `01 / 01`, `09 / 18`, `18 / 18`, progress width, manifest total/order, and exact receipt attachment order.
2. Require receipt `expected_image_count`, attachment order, and page/file hashes to agree with the manifest total.
3. Keep relay sending outside PTSM but document/test the sequential-ACK fallback contract.
4. Run focused tests and commit.

verify: `uv run pytest -q tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py`

done_when: visible numbering, canonical manifest order, and relay handoff order agree for dynamic totals.

### Task 5: Update wrapper skill and complete source-of-truth docs

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `tests/unit/docs/test_openclaw_skill.py`
- Modify: `tests/unit/docs/test_docs_map.py`
- Modify: `tests/unit/skills/test_skill_loader.py`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/operations/publish-quickstart.md`

**Steps:**
1. Add failing docs/skill tests for content-derived 1–18 pages, >18 stop/choice, emoji removal, visible page numbers, ordered multi-image preference, and sequential ACK fallback.
2. Update the wrapper without adding a manual count flag or automatic multi-post authorization.
3. Update all active architecture/runtime/playbook/skill/harness/observability/operator surfaces and `last_verified` metadata.
4. Run docs and skill tests.
5. Mechanically synchronize the installed skill mirror and verify byte equality.
6. Commit.

verify: `uv run pytest -q tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/unit/skills/test_skill_loader.py`

done_when: repository and installed skills match, and every source-of-truth surface describes the same dynamic and ordered-delivery contract.

### Task 6: End-to-end visual and harness verification

**Files:**
- Modify: tests only if a real uncovered regression is found

**Steps:**
1. Run two deterministic dry-runs that produce different dynamic page totals.
2. Inspect cover, middle, and final pages; verify `NN / TT`, progress, emoji-free copy, manifest order, and hashes.
3. Run targeted psychology suites, then full pytest.
4. Run `doctor`, `docs-sync --base-ref origin/main`, and `harness-check --base-ref origin/main`.
5. Review `git diff --check`, the full base diff, and installed-skill parity.
6. Merge to local `main`, rerun full pytest, clean the worktree/branch, and push `main` as explicitly requested by the user.

verify:
- `uv run pytest -q`
- `uv run python -m ptsm.bootstrap doctor`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`
- `cmp -s integrations/openclaw/ptsm-xhs-psychology/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

done_when: both dynamic visual samples are correct, all gates pass or any external-only preflight limitation is reported, local `main` is verified, and Git remote contains the final commit.

