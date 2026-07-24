# Psychology Custom Learning Series Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Let an operator define a psychology learning-series topic and lesson outline, receive a safe recommended publication order, explicitly confirm an immutable curriculum revision, then generate one selected lesson at a time.

**Architecture:** Keep the existing `learning_series` runtime boundary closed. A trusted, explicit provisioning command creates the fixed private storage tree before any custom-series mutation; normal plan/confirm/run paths only use that existing tree. A new proposal command accepts only safe topic/outline intent and produces a reviewable curriculum proposal plus a separate publication plan. Confirmation persists an append-only, user-confirmed catalog snapshot. `guide-post`, `run-playbook`, runtime revalidation, offline eval, and metrics all resolve the same frozen snapshot; no proposal input, raw source, free scene, or manual image override enters a lesson run.

**Tech Stack:** Python 3.12, Pydantic contracts, JSON local stores under `outputs/artifacts/`, argparse CLI, pytest.

## User Flow and Invariants

1. During trusted setup only, while all writers are stopped and the storage parent is exclusively controlled, `provision-psychology-learning-storage` creates/verifies the private fixed `proposals` / `confirmations` / `catalogs` / `progress` tree.
2. `plan-psychology-series --topic ... [--curriculum-outline-file ...]` returns a proposal, a structural/safety review, suggested publication order, and a proposal fingerprint. It does not create a runnable catalog or provision/repair storage.
3. `confirm-psychology-series --proposal-id ... --proposal-fingerprint ... --confirm` creates an immutable custom curriculum revision. Changing a topic, lesson contract, or order requires another proposal and a new revision.
4. `guide-post --psychology-content-mode learning_series --psychology-series-id ...` returns `selection_required`, the frozen roadmap, the recommended next lesson based on operator production progress, and the publication order. It never auto-selects or generates a lesson.
5. The user explicitly selects a lesson. `guide-post` returns the exact run command; `run-playbook` re-resolves the frozen catalog and renders the existing controlled template.
6. A completed run records only operator content-production progress in the local store; it never infers reader learning progress or auto-publishes the next lesson. A post-rename progress boundary failure is at-least-once and must be retried idempotently, never path-cleaned online.

`lesson_number` is immutable curriculum identity and reader-facing badge data. `publication_order` is a separate, immutable plan field. A reorder must never mutate an existing catalog revision, receipt, checkpoint namespace, or historical metric record.

## Task 1: Specify safe proposal, catalog, and publication-plan contracts

**Files:**
- Modify: `src/ptsm/domain/psychology_learning.py`
- Create: `src/ptsm/application/use_cases/psychology_learning_series.py`
- Test: `tests/unit/domain/test_psychology_learning.py`
- Test: `tests/unit/application/use_cases/test_psychology_learning_series.py`

**Step 1: Write failing tests**

Add tests for a safe custom topic plus an outline; assert that planning returns a stable proposal ID/fingerprint, recommendations, and a distinct publication order without changing canonical lesson identities. Add failing tests for URLs/source text, diagnosis/treatment/self-harm markers, duplicate lesson IDs, and invalid lesson counts.

**Step 2: Run the focused tests to verify RED**

Run: `uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py -q`

Expected: FAIL because proposal and custom-catalog APIs do not exist.

**Step 3: Implement minimal safe proposal logic**

Define explicit proposal/catalog/publication-plan Pydantic contracts. Accept a narrow outline schema (`title`, optional `id`, optional `goal`) or synthesize a four-step outline from a topic. Validate all operator text before it is stored; reject URLs, source references, clinical/dangerous topics, and unsupported claims. Compute deterministic recommendations using pedagogical stages (`notice`, `understand`, `practice`, `apply`, `review`, `support`) while preserving an immutable canonical lesson identity.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py -q`

**verify:** Focused domain/use-case tests pass with deterministic proposal and rejection results.

**done_when:** A proposal contains no runnable catalog selection, no raw provenance, and clearly distinguishes canonical lesson number from recommended publication order.

## Task 2: Persist confirmation snapshots and expose one resolver

**Files:**
- Modify: `src/ptsm/domain/psychology_learning.py`
- Modify: `src/ptsm/application/use_cases/psychology_learning_series.py`
- Test: `tests/unit/domain/test_psychology_learning.py`
- Test: `tests/unit/application/use_cases/test_psychology_learning_series.py`
- Test: `tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py`

**Step 1: Write failing tests**

Add tests that an unconfirmed proposal cannot resolve, confirmation creates an append-only catalog revision, builtin `after_work_rumination` remains unchanged, a tampered/missing custom snapshot fails closed, and a newly proposed revision cannot rewrite a prior snapshot.

**Step 2: Run RED**

Run: `uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py -q`

Expected: FAIL because no custom catalog persistence/resolution exists.

**Step 3: Implement the store and resolver**

Persist sanitized proposals and confirmed snapshots below `outputs/artifacts/psychology-learning-series/`, with a confirmation ledger independent of the snapshot directory so revisions cannot be reused after partial deletion. Provision the fixed private directory tree explicitly before mutation. Create immutable records directly with private `O_EXCL` / no-follow leaves, validate identity/payload, fsync the leaf and parent before reporting success, and leave unsafe/unfinished residues for trusted offline maintenance rather than removing a mutable name online. Use the same pinning and durability discipline for the replaceable production-progress sidecar; its post-rename failure boundary is at-least-once. Freeze a `controlled_template_version` in every confirmed catalog and ledger record; retain a versioned v1 builder/validator so later controlled-copy changes cannot invalidate an intact historic revision. Make the existing selection/list APIs resolve either the builtin catalog or a confirmed snapshot and reconstruct exact lesson contracts/manifests from the snapshot. Expose origin/fingerprint/approval and publication-plan metadata through the confirmed catalog/bundle only; Task 4 binds that metadata into opaque runtime/artifact receipts without exposing proposal text or local file paths.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py -q`

**verify:** Resolver tests cover builtin compatibility, custom revision integrity, and runtime reconstruction.

**done_when:** A confirmed custom curriculum is immutable, durably written, and re-resolvable by the catalog selection/list boundary under its frozen controlled-template version; unconfirmed, missing, stale, or tampered data fails before drafting. Task 4 extends the same guarantee to runtime, artifact, evaluation, and metrics receipt consumers.

## Task 3: Add proposal/confirmation CLI and guide-post sequence advice

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/interfaces/cli/test_main.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write failing tests**

Add CLI and guide tests for planning a topic-only series, planning a custom outline file, requiring the exact proposal fingerprint and `--confirm`, returning `selection_required` after confirmation, showing `publication_plan` and `recommended_next_lesson_id`, and refusing to auto-select an out-of-order lesson.

**Step 2: Run RED**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_guide_post.py -q`

Expected: FAIL because the lifecycle commands and guide fields do not exist.

**Step 3: Implement CLI and guide integration**

Add `provision-psychology-learning-storage`, `plan-psychology-series` and `confirm-psychology-series` commands. Provisioning is an explicit trusted setup action; plan/confirm do not create missing directories. Add a safe JSON outline loader at the CLI boundary. Reuse the existing learning-series flags for confirmed custom IDs. Extend the roadmap response with the confirmed catalog origin, recommendation rationale, immutable publication plan, production progress, and a recommended next lesson; retain explicit user selection as a hard requirement.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_guide_post.py -q`

**verify:** CLI outputs exact JSON lifecycle states and guide still rejects missing/mismatched selection.

**done_when:** The full interaction can be driven from the CLI without hand-editing internal store files.

## Task 4: Bind custom catalogs through run, runtime, eval, and metrics

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Modify: `src/ptsm/application/use_cases/xhs_post_metrics.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py`
- Test: `tests/unit/evaluations/test_contract_evaluators.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`
- Test: `tests/unit/application/use_cases/test_xhs_post_metrics.py`
- Test: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Write failing tests**

Add tests for custom confirmation → guide selection → dry-run completion, exact receipt reconstruction, no proposal/private outline leakage in runtime/checkpoint/artifact, local production-progress update only after completion, and metrics/eval failure when the immutable snapshot is missing or changed.

**Step 2: Run RED**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/application/use_cases/test_xhs_post_metrics.py tests/e2e/test_modern_psychology_publish_dry_run.py -q`

Expected: FAIL because custom catalog receipts/progress are not yet bound.

**Step 3: Implement runtime integration**

Route custom selection through the same resolver in preflight, runtime contract verification, artifact receipt validation, offline evaluation, and metrics. Preserve the exact-template and catalog-owned image gates. Record production progress only after a completed run; recommendation may change, but manual lesson confirmation remains mandatory. Keep publication-plan metadata out of reader-visible content and do not use it as a reader-progress tracker.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/application/use_cases/test_xhs_post_metrics.py tests/e2e/test_modern_psychology_publish_dry_run.py -q`

**verify:** Custom and builtin series both complete deterministic dry-runs and reject tampering before external side effects.

**done_when:** No free topic/outline text bypasses the confirmation boundary; historic receipts remain auditable by their immutable revision.

## Task 5: Update assets, complete docs surface, and OpenClaw wrapper

**Files:**
- Modify as needed: `src/ptsm/playbooks/definitions/modern_psychology_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Sync: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`
- Modify: `docs/architecture.md`, `docs/runtime.md`, `docs/playbooks.md`, `docs/skills.md`, `docs/harness-engineering.md`, `docs/observability.md`, `docs/operations.md`, `docs/operations/local-runbook.md`, `docs/operations/content-experiment-runbook.md`
- Review unchanged: `docs/operations/topic-radar-runbook.md`
- Modify: `tests/unit/docs/test_docs_map.py`, `tests/unit/docs/test_openclaw_skill.py`

**Step 1: Write failing docs/skill contract tests**

Update tests to require proposal, confirmation, immutable revision, publication-plan, and explicit-per-lesson wrapper language.

**Step 2: Run RED**

Run: `uv run pytest tests/unit/docs -q`

Expected: FAIL because current docs describe only a closed builtin catalog and declare custom series a non-goal.

**Step 3: Update docs and skills**

Document the lifecycle, operator commands, safe failure states, and the distinction between production progress and reader learning progress. State that Topic Radar remains discovery-only: hotspot text cannot become custom psychology lesson facts. Sync the installed OpenClaw skill byte-for-byte.

**Step 4: Verify GREEN**

Run: `uv run pytest tests/unit/docs -q`

Run: `diff -u integrations/openclaw/ptsm-xhs-psychology/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

**verify:** Complete source-of-truth documentation and wrapper contract coverage pass.

**done_when:** Operators can discover, confirm, resume, and audit a custom series without reading source code.

## Task 6: End-to-end verification and merge gate

**Files:**
- No planned production files beyond verification-driven fixes.

**Step 1: Run a complete custom-series smoke path**

Run `provision-psychology-learning-storage`, then `plan-psychology-series` with a safe topic/outline, confirm its exact fingerprint, query its guide roadmap, explicitly select the returned recommended lesson, and run a deterministic `--publish-mode dry-run --eval`. Inspect JSON for `status == completed`.

**Step 2: Run full verification**

Run:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**Step 3: Review and integrate**

Review the diff, commit focused changes, push the feature branch, fast-forward/merge it to `main`, rerun the appropriate post-merge verification, and push `main` only after the gate passes.

**verify:** Every command exits successfully and smoke JSON reports `status == completed`.

**done_when:** The feature is documented, verified, committed, merged to `main`, and pushed without touching unrelated user files.

## Execution Record — 2026-07-24 (in progress)

- Tasks 1–4 implementation is present on `feat/custom-psychology-learning-series`: safe proposal/outline validation, immutable `user_confirmed` revision snapshots, explicit confirmation and lesson selection, and receipt-bound runtime/eval/metrics integration.
- The storage security pass replaced online cleanup/staged-link assumptions with explicit trusted provisioning, direct private `O_EXCL` immutable writes, no-follow descriptor/identity checks, and fail-closed retained residues. It detects substitution races within each transaction; it does not claim permanent at-rest protection from a process that continuously has the same UID and may modify an inode after the final check.
- Progress uses a pinned per-series lock and idempotent updates. A failure after atomic replacement can be at-least-once, so `psychology_learning_progress_persist_failed` is retried idempotently or handled through trusted offline maintenance, never by an online rollback/delete.
- Targeted implementation evidence currently includes: the psychology learning store suite (`58 passed`), file artifact store suite (`18 passed`), CLI suite (`44 passed`), E2E psychology dry-run (`6 passed`), and the cross-layer learning-series group (`478 passed`).
- Task 5 documentation synchronization and Task 6 final gates are still in progress at the time of this record. Before integration, the branch must still run the complete docs suite, full `pytest`, compile/doctor/docs-sync/harness-check, a fresh provision-first CLI smoke path, independent final review, and `git diff --check`. No completed/full-suite/harness claim is made until those command outputs are recorded.
