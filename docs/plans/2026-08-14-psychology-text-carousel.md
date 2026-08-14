# Psychology Text Carousel Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Generate and publish one psychology topic as an ordered 4–7 image carousel of locally rendered text cards, for both ordinary `modern_psychology_post` content and catalog-bound psychology learning-series lessons.

**Architecture:** Keep `final_content.image_plan` backward compatible and add a strict ordered `slides` contract only for psychology text carousels. Ordinary psychology drafting emits the semantic pages in its existing drafting pass; learning-series pages are reconstructed deterministically from the frozen controlled lesson template. A local `psychology_text_card_v1` renderer writes every page into a runtime-owned staging directory, verifies an ordered manifest, and atomically renames the directory into a committed image set. Only a complete committed set may reach the asset ledger or publisher. Historic learning template v1 remains verifiable; builtin lessons and newly confirmed custom curricula use version 2.

**Tech Stack:** Python 3.12, Pydantic contracts, Pillow, local JSON/JSONL artifacts, LangGraph runtime nodes, argparse CLI, pytest.

## Locked User Contract

- This is one psychology topic expressed across multiple text images, not multiple independent psychology subjects or characters.
- Ordinary psychology posts may use 4–7 semantic cards: cover hook, concrete scene, light mechanism, saveable tool, boundary, and comment prompt.
- Learning-series cards contain only catalog-approved fields and are part of exact draft/receipt validation.
- The carousel is created in the same drafting pass; there is no second model rewrite and no blind body-length pagination.
- `slides` order is the publish order. Each slide has exactly `slide_id`, `order`, `role`, `headline`, and `body_lines`.
- The parent plan keeps existing routing fields and adds `carousel_style: psychology_text_card_v1` plus `slides`.
- Any invalid or failed page makes the whole generation fail with `psychology_carousel_generation_failed`. No partial set reaches watermark processing, the asset ledger, or the publisher.
- When learning-series image generation is requested, production progress advances only after the complete carousel and sealed artifact remain valid. Without image generation, the existing safe content-artifact progress behavior remains unchanged.
- Explicit ordinary-post image overrides and non-carousel plans retain their current single-image behavior. Learning-series manual image/style overrides remain forbidden.

## Compatibility and Security Notes

- The existing ordered `generated_image_paths` field remains the publisher-facing compatibility surface.
- The existing image backend protocol remains single-image; the application service owns carousel orchestration.
- Provider image generation is not expanded into carousel generation in this change. Psychology text carousels are local-only.
- Committed image sets retain an immutable manifest and page hashes. External publishing itself is not atomic and cannot be rolled back; a publish failure preserves the committed set for retry.
- Sealed learning artifacts record only safe carousel evidence (`status`, renderer, style, count, manifest hash), never local image paths or catalog source references.
- `shared_contracts/evaluation/final_content.schema.yaml` remains unchanged because it is the cross-domain minimum content schema; the carousel is a psychology-specific optional extension validated at stricter domain/runtime boundaries.
- Topic Radar and task-completion automation are intentionally unchanged because this work does not alter discovery or completion semantics.

## Baseline Evidence

- `uv sync` succeeds in the feature worktree.
- `uv run pytest -q --ignore=tests/e2e` currently reports 1443 passed and one unrelated pre-existing docs freshness failure: `docs/shared-contracts.md` has `last_verified=2026-05-09`, older than the test threshold `2026-05-15`.
- The feature must not conceal that baseline failure. If it remains at final verification, report it separately from feature regressions; update the file only if this feature genuinely changes its contract.

## Task 1: Define and enforce the psychology carousel domain contract

**Files:**

- Create: `src/ptsm/domain/psychology_carousel.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Test: `tests/unit/domain/test_psychology_carousel.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Write failing contract tests**

Cover a valid 4-slide and 7-slide plan, exact closed fields, contiguous one-based order, unique stable IDs, first-page `cover_hook`, allowed roles, cover/inner text budgets, no hashtags/URLs/source locators, and psychology risk/instruction-leakage markers. Add failures for missing/reordered/duplicate pages, unknown fields, overlong lines, whole-body paragraphs, diagnoses, treatment promises, medication advice, and prompt instructions.

Add deterministic drafting expectations for representative relationship, workplace, sleep-recovery, and boundary-tool scenes. Assert that each draft carries a semantic `psychology_text_card_v1` plan, uses one topic throughout, and does not simply split at fixed character counts. Assert non-psychology deterministic drafts keep their existing image plan.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_carousel.py tests/unit/infrastructure/llm/test_factory.py -q
```

Expected: FAIL because the carousel contract and deterministic plan do not exist.

**Step 3: Implement the minimal contract**

Add frozen Pydantic models/constants and public helpers to normalize and validate the closed `slides` structure. Keep legacy non-carousel plans valid. Make the deterministic psychology backend build pages from the already selected semantic beats (scene, mechanism, tool, boundary, comment handoff) in the same drafting pass. Do not introduce a second model call or derive pages by raw character count.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/domain/psychology_carousel.py src/ptsm/infrastructure/llm/contextual_drafts.py tests/unit/domain/test_psychology_carousel.py tests/unit/infrastructure/llm/test_factory.py
git commit -m "feat(psychology): define semantic text carousel contract"
```

**verify:** Focused tests prove valid plans normalize identically and every malformed/unsafe nested slide fails closed while unrelated playbooks retain single-image behavior.

**done_when:** Ordinary deterministic psychology drafts can carry one strict ordered 4–7-card plan with no new unreviewed psychology claims or cross-domain behavior change.

## Task 2: Version and bind learning-series carousel templates

**Files:**

- Modify: `src/ptsm/domain/psychology_learning.py`
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Test: `tests/unit/domain/test_psychology_learning.py`
- Test: `tests/unit/application/use_cases/test_psychology_learning_series.py`
- Test: `tests/unit/evaluations/test_contract_evaluators.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`

**Step 1: Write failing version and exactness tests**

Add exact snapshots for the builtin v2 lesson carousel and a newly confirmed custom v2 catalog. Assert every visible page is derived only from approved lesson fields. Mutate a letter, role, order, ID, line, page count, or unknown nested field and require rejection.

Create/load a historical controlled-template-v1 fixture and assert its digest, approval receipt, lesson copy, single-card image plan, offline evaluation, and artifact evaluation remain valid. Assert newly confirmed revisions use controlled template version `2`, while unsupported versions fail closed.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py -q
```

Expected: FAIL because only controlled template v1 and a single `iphone_notes` plan exist.

**Step 3: Implement the versioned catalog renderer**

Register immutable template v1 and v2 behavior. Preserve the historic v1 digest material exactly, including omission/default treatment of any newly introduced template marker. Bind the controlled template version through lesson runtime contract and opaque manifest/receipt verification. Builtin lessons and new confirmations use v2; already persisted custom v1 snapshots remain v1 and are never silently rewritten.

Render v2 learning pages deterministically from `cover_text`, `scene_anchor`, `concept_label`, `learning_goal`, `approved_explanation`, `applicability`, `micro_exercise`, `scope_limit`, `professional_boundary`, and `comment_prompt`. Keep v1 rendering byte-compatible. Update exact draft validation, artifact nested allowlists, list-element validation, and evaluator reconstruction together.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/domain/psychology_learning.py src/ptsm/evaluations/contracts_eval.py src/ptsm/application/use_cases/eval_artifact.py tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_psychology_learning_series.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py
git commit -m "feat(psychology): bind learning carousels to template v2"
```

**verify:** Both historic v1 and current v2 receipts reconstruct exactly; any page tampering fails at the domain and offline-evaluation boundaries.

**done_when:** Learning-series carousels are catalog-owned, versioned, auditable, and backward compatible without accepting model-authored pages.

## Task 3: Preserve and gate nested slides through drafting and runtime

**Files:**

- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/agent_runtime/nodes/executor.py`
- Modify: `src/ptsm/agent_runtime/nodes/reflector.py`
- Modify: `src/ptsm/agent_runtime/state.py`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`
- Test: `tests/unit/infrastructure/llm/test_factory.py`
- Test: `tests/unit/agent_runtime/test_executor_node.py`
- Test: `tests/unit/agent_runtime/test_reflector_node.py`
- Test: `tests/unit/agent_runtime/test_finalize_node.py`
- Test: `tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py`

**Step 1: Write failing propagation and checkpoint-safety tests**

Assert hosted JSON normalization preserves only the exact nested slide fields and rejects malformed nested data. Assert ordinary psychology runtime validation happens before unsafe carousel text can enter `draft_content`, checkpoint state, content review, or the artifact. Assert valid slides survive executor, reflector, finalize, and review unchanged. Assert a missing carousel remains a backward-compatible ordinary single-image draft.

For learning series, assert hosted/deterministic backends return the exact versioned catalog draft and that no retry prompt can revise its pages. Assert `content_review.image_plan` contains safe ordered slide summaries, while sealed learning receipts expose no local path or source reference.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_reflector_node.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py -q
```

Expected: FAIL because nested plans are currently flattened/dropped and ordinary psychology has no carousel draft gate.

**Step 3: Implement strict propagation**

Replace the two flat image-plan allowlists with explicit nested normalization. Update the hosted hard requirements to request 4–7 semantic cards only for ordinary modern psychology. Bind an optional ordinary psychology carousel gate into executor, reflector, and finalize; the gate is a no-op when no slides are present and is not applied to unrelated playbooks. Include slide text in content-quality and safety review. Keep the stricter exact learning-series gate authoritative when a catalog contract is bound.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/infrastructure/llm/factory.py src/ptsm/agent_runtime/runtime.py src/ptsm/agent_runtime/nodes/executor.py src/ptsm/agent_runtime/nodes/reflector.py src/ptsm/agent_runtime/state.py src/ptsm/playbooks/definitions/modern_psychology_post/planner.md src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md tests/unit/infrastructure/llm/test_factory.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_reflector_node.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py
git commit -m "feat(runtime): preserve and gate psychology carousel slides"
```

**verify:** Nested pages survive every intended layer, unsafe pages never enter checkpointed state, and legacy/non-psychology drafts remain compatible.

**done_when:** A valid carousel is one validated draft artifact—not an unreviewed post-processing payload—and learning exactness remains stronger than the ordinary gate.

## Task 4: Render a dedicated text-card style and commit image sets atomically

**Files:**

- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`
- Create: `src/ptsm/application/services/image_carousel_transaction.py`
- Test: `tests/unit/infrastructure/images/test_note_card_backend.py`
- Create: `tests/unit/application/services/test_image_carousel_transaction.py`

**Step 1: Write failing renderer and transaction tests**

Renderer tests cover 1080×1440 output, nonblank pixels, Chinese wrapping, cover versus inner role variants, counter/role accents, maximum legal text, and no hashtags or clipped overflow. Existing `note_card`, `iphone_notes`, `wechat_chat`, and unknown-style fallback behavior must remain unchanged.

Transaction tests cover stable zero-padded ordered names, an ordered manifest with page/file SHA-256 values, a content-addressed set ID, strict output-path containment, regular/readable PNG validation, duplicate/missing/unreadable/escaped paths, renderer failure on the middle page, exact cleanup of runtime-owned staging, no visible final directory on failure, idempotent reuse of an identical committed set, and fail-closed handling of a conflicting manifest.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/application/services/test_image_carousel_transaction.py -q
```

Expected: FAIL because `psychology_text_card_v1` and the set transaction do not exist.

**Step 3: Implement the renderer and set transaction**

Add role-aware, fake-UI-free psychology text cards that render only supplied `headline` and `body_lines`. In the application service, validate the full plan first, generate every page inside a uniquely owned staging directory located on the destination filesystem, validate outputs, write/fsync the canonical manifest, and atomically rename the directory to the immutable set destination. Return ordered `generated_image_paths`, safe `pages` evidence, set/manifest identifiers, provenance, style, and count. Never expose a staging path as a generated path.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/infrastructure/images/note_card_backend.py src/ptsm/application/services/image_carousel_transaction.py tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/application/services/test_image_carousel_transaction.py
git commit -m "feat(images): render atomic psychology text carousels"
```

**verify:** The complete set is the smallest visible unit: all ordered pages and a verified manifest exist, or no committed set exists.

**done_when:** `psychology_text_card_v1` produces readable bounded cards and the transaction cannot return or publish a partial group.

## Task 5: Integrate all-or-nothing generation, receipts, ledger, and progress

**Files:**

- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/infrastructure/images/asset_ledger.py`
- Modify: `src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/infrastructure/images/test_asset_ledger.py`
- Test: `tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py`
- Test: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Write failing orchestration tests**

Add ordinary and builtin/custom learning cases that request image generation and assert exact publisher order, stable page filenames, set/page evidence, local-renderer watermark skip, page-aware ledger rows, and artifact output. Assert no-slides and explicit ordinary overrides still use the existing single-image path.

Inject a middle-page exception, wrong returned path, missing page, unreadable image, manifest mismatch, and ledger failure. Require stable failure status `psychology_carousel_generation_failed`, zero publisher calls, no watermark calls, no partial ledger projection, a non-running final run summary, and a persisted bounded failure receipt. Assert publisher preflight rejects duplicate, missing, non-regular, or unreadable paths before the MCP call.

For learning series, assert sanitized artifact evidence includes only safe status/renderer/carousel style/count/manifest hash, never paths/page text. Assert requested-image runs mark production progress only after the complete set and strict artifact are valid; no-image runs preserve the current progress timing.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py tests/e2e/test_modern_psychology_publish_dry_run.py -q
```

Expected: FAIL because the run use case invokes one cover renderer and cannot represent/abort a carousel set.

**Step 3: Integrate the transaction**

Detect a validated local carousel before the existing single-image branch and invoke the transaction service. Treat generation plus manifest verification as one guarded phase. On failure, set the stable result status, persist safe diagnostics, emit failed run events, skip ledger/watermark/publish, and still finish the run record.

After a successful commit, append page-aware asset entries in manifest order and only then continue. The immutable manifest is the authoritative set receipt; JSONL is its operational projection. Fail closed before publish if the projection cannot be recorded, but retain the committed set for repair/retry. Preserve ordered paths through idempotency and publisher input. Local carousel sets skip watermark removal as a group.

Extend the learning artifact sanitizer/allowlist with safe carousel evidence and no filesystem paths. Do not weaken artifact ownership or provenance validation. Because the existing progress block is conditioned on final `completed` status, ensure every requested-image failure changes status before that block.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/application/use_cases/run_playbook.py src/ptsm/infrastructure/images/asset_ledger.py src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py tests/e2e/test_modern_psychology_publish_dry_run.py
git commit -m "feat(run): publish complete psychology carousel sets"
```

**verify:** Every successful run publishes exactly the manifest order; every induced page/set/ledger failure produces no external publish side effect and no false learning progress.

**done_when:** The application supports safe retryable whole-set generation without changing generic manual multi-path publication or provider single-cover behavior.

## Task 6: Expose carousel guidance and experiment metrics

**Files:**

- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `src/ptsm/application/use_cases/xhs_post_metrics.py`
- Modify: `src/ptsm/interfaces/cli/main.py` only if formatter/group-by plumbing requires it
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/application/use_cases/test_xhs_post_metrics.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write failing guide and metrics tests**

Assert ordinary psychology guidance recommends `format_archetype=text_carousel`, local `psychology_text_card_v1`, a 4–7 page range, and ordered semantic roles, while the run command continues to use only `--auto-generate-image`. Assert learning roadmap selection returns the exact catalog-derived carousel recommendation and still refuses to invent/select a lesson.

Assert metric rows record `image_count` and `carousel_style`; old/single artifacts normalize to count 1 and an empty/single style as documented. Add supported grouping by `carousel_style` and prove single covers remain distinguishable from carousels even when their parent image role is similar. A tampered learning receipt must still reject metric recording.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_xhs_post_metrics.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: FAIL because guidance and metrics only expose one image style/role.

**Step 3: Implement the public guidance and metric fields**

Add bounded carousel recommendation fields to JSON and Markdown guide output. Keep carousel shape separate from manual `--local-image-style`; do not add a carousel CLI style override. Resolve learning recommendations from the exact rendered template. Add backward-compatible metric extraction/grouping from verified artifacts.

**Step 4: Verify GREEN and commit**

Run the focused command from Step 2, then:

```bash
git diff --check
git add src/ptsm/application/use_cases/guide_post.py src/ptsm/application/use_cases/xhs_post_metrics.py src/ptsm/interfaces/cli/main.py tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_xhs_post_metrics.py tests/unit/interfaces/cli/test_main.py
git commit -m "feat(psychology): guide and measure text carousels"
```

**verify:** Operators can see the intended page structure before running, and metrics can compare carousel versus single-cover output without breaking historic rows.

**done_when:** The feature is discoverable and observable through existing guide/metrics commands with no new manual pagination interface.

## Task 7: Update skills, OpenClaw wrapper, and the complete docs surface

**Files:**

- Modify: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Sync: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/operations/publish-quickstart.md`
- Modify: `docs/operations/content-experiment-runbook.md`
- Modify: `docs/operations/cloud-bootstrap.md`
- Modify: `docs/xhs-topics/image-forms-by-domain.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_openclaw_skill.py`
- Test: relevant skill registry/loader tests discovered by `rg`

**Step 1: Write failing docs and skill-contract tests**

Require documentation of the exact parent/slide fields, 4–7 semantic roles, local-only renderer, set transaction, failure status, learning v1/v2 behavior, no-override rule, safe artifact evidence, guide flow, and `image_count`/`carousel_style` metrics. Require the wrapper to show only PTSM-returned learning pages and never author its own page copy.

Before changing skill text, capture a baseline scenario demonstrating that the current image-strategy/psychology skills still insist on a single low-density cover. After the edit, forward-test with a fresh subagent using only the revised skill plus a representative psychology request.

**Step 2: Run focused RED**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_openclaw_skill.py -q
```

Expected: FAIL because active docs currently say automatic generation produces one cover and the existing carousel brief is advisory only.

**Step 3: Update skills and source-of-truth docs**

Limit automatic carousel instructions to modern psychology; keep all other domain defaults intact. State that the cover remains low-density while inner text cards are bounded, and that one carousel carries one topic. Document old confirmed v1 curricula as immutable and new/builtin v2 behavior. Update operator commands, troubleshooting, cloud output persistence, asset/manifest inspection, experiment grouping, and harness expectations.

Review and explicitly record as unchanged: `shared_contracts/evaluation/final_content.schema.yaml`, Topic Radar docs, and task-completion automation docs. Update active-doc metadata only for files genuinely verified/changed. Sync the installed OpenClaw psychology skill byte-for-byte from the repository copy.

**Step 4: Verify GREEN and commit**

Run:

```bash
uv run pytest tests/unit/docs -q
diff -u integrations/openclaw/ptsm-xhs-psychology/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
git diff --check
git add src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md src/ptsm/skills/builtin/psychology_style/SKILL.md integrations/openclaw/ptsm-xhs-psychology/SKILL.md docs tests/unit/docs
git commit -m "docs(psychology): document text carousel workflow"
```

**verify:** Docs/skill tests and docs sync pass; repository and installed wrapper match exactly; a fresh skill-only forward test selects bounded text carousels without inventing learning content.

**done_when:** Operators can guide, generate, inspect, retry, publish, and measure both ordinary and learning-series carousels without reading implementation code.

## Task 8: Regression, smoke, review, and integration gate

**Files:**

- No planned production files beyond verification-driven fixes.

**Step 1: Run targeted cross-layer regressions**

Run:

```bash
uv run pytest \
  tests/unit/domain/test_psychology_carousel.py \
  tests/unit/domain/test_psychology_learning.py \
  tests/unit/infrastructure/llm/test_factory.py \
  tests/unit/agent_runtime \
  tests/unit/application/services/test_image_carousel_transaction.py \
  tests/unit/application/use_cases/test_run_playbook.py \
  tests/unit/application/use_cases/test_guide_post.py \
  tests/unit/application/use_cases/test_xhs_post_metrics.py \
  tests/unit/infrastructure/images \
  tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py \
  tests/e2e/test_modern_psychology_publish_dry_run.py -q
```

**Step 2: Run three smoke paths**

Use isolated temporary output roots and execute:

1. An ordinary psychology dry-run with `--auto-generate-image`.
2. A builtin learning lesson dry-run with explicit series/lesson and `--auto-generate-image`.
3. Provision → plan → exact confirm of a new safe custom series → explicit lesson selection → dry-run with `--auto-generate-image`.

Inspect each JSON result and committed manifest. Require status `completed`, 4–7 ordered readable images, matching hashes, and no staging directory. Also inject one controlled renderer failure in a focused test/smoke and confirm `psychology_carousel_generation_failed` with no publish/progress side effect.

**Step 3: Run full gates**

Run:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
git diff --check
git status --short
```

If the known docs freshness baseline still fails unchanged, rerun the suite excluding only that exact test to prove no additional regression, preserve its evidence, and do not describe the full suite as green.

**Step 4: Independent review**

Request a spec-compliance review, then a code-quality/security review. Resolve every finding and rerun the affected focused tests plus full gates. Inspect the final diff for accidental changes to unrelated domains, provider image behavior, user files, and historic learning fixtures.

**Step 5: Integrate**

Use `superpowers:finishing-a-development-branch`. Merge the feature branch back to `main` only after the review/gates are satisfied. Preserve unrelated untracked files in the main worktree and rerun the proportional post-merge verification before reporting completion.

**verify:** Focused tests, smoke paths, doctor, docs sync, and harness check pass; the full-suite result has no new failures beyond any explicitly preserved baseline; independent reviews are clean.

**done_when:** The feature is committed, reviewed, documented, merged to `main`, and demonstrably publishes only complete ordered psychology text-card sets for ordinary and current learning-series content while keeping historic v1 receipts valid.
