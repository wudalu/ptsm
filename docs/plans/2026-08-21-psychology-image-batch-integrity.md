# Psychology Image Batch Integrity Implementation Plan

**Goal:** Prevent an OpenClaw psychology-image request from silently repeating one 4–7 page carousel, and make each committed carousel safe for an external attachment relay to count, order, and deduplicate.

**Architecture:** A normal `modern_psychology_post` remains one topic and one 4–7 page carousel; it does not become a 12-page or 12-asset batch API. The OpenClaw wrapper must route requests above that range to an explicit choice instead of looping `run-playbook`. For supported carousel runs, reserve an inner-page semantic fingerprint before the artifact write, then durably persist an immutable receipt intent before writing the asset ledger. Commit it to account memory only after local rendering, canonical receipt verification, a complete page-aware ledger projection check, and owner-fenced artifact handling all succeed. An expired intent is reconciled only by the application with the durable ledger verifier; unknown legacy pending markers remain blocked for trusted maintenance. The fingerprint varies deterministic fallback inner pages and rejects a repeated complete carousel. The image transaction also rejects identical rendered PNG bytes within a set and emits a relay-ready ordered receipt. PTSM still does not own the external chat attachment sender.

**Tech Stack:** Python 3.12, Pydantic, LangGraph runtime nodes, Pillow local renderer, pytest, Markdown source-of-truth docs.

**Non-goals:** Implementing a generic 12-image batch API, calling an external image provider, or sending attachments through an external chat relay. Those systems are not present in this repository.

### Task 1: Define and retain a carousel inner-page identity

**Files:**
- Modify: `src/ptsm/domain/psychology_carousel.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/agent_runtime/nodes/memory.py`
- Modify: `src/ptsm/agent_runtime/nodes/executor.py`
- Test: `tests/unit/domain/test_psychology_carousel.py`
- Test: `tests/unit/agent_runtime/test_executor_node.py`
- Test: `tests/unit/agent_runtime/test_finalize_node.py`

**Step 1: Write failing tests**

Add a domain test for a stable SHA-256 fingerprint of only the visible inner cards, proving that changing only the cover does not change the identity and changing an inner card does. Add runtime tests proving a matching recent fingerprint rejects a candidate before draft state/artifact persistence, while legacy plans without a stored fingerprint remain valid.

**Step 2: Run the focused tests to verify failure**

Run: `uv run pytest tests/unit/domain/test_psychology_carousel.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_finalize_node.py -q`

Expected: the new tests fail because there is no inner-page fingerprint or recent-memory duplicate gate.

**Step 3: Implement the smallest closed contract**

Add a canonical, JSON-stable inner-page fingerprint helper beside `normalize_psychology_carousel_plan`. Reserve its 64-character value only for ordinary psychology carousel drafts, expose only validated hashes from the most recent twelve *successful complete-carousel* account receipts in recent memory, and retain that bounded window. Pass execution state to the ordinary carousel gate in executor, reflector, and finalizer; reject a candidate when its inner-page fingerprint appears in that context. A private reservation handoff must survive finalization without leaking into an artifact or user response; `run_playbook` commits it only after renderer + receipt verification + asset-ledger success, releases it for every pre-success failure/non-carousel exit, and supports bounded stale-lease recovery under the file store's cross-process lock.

**Step 4: Run the focused tests to verify success**

Run: `uv run pytest tests/unit/domain/test_psychology_carousel.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_finalize_node.py -q`

Expected: PASS, with a cover-only change still detected as an inner-page repeat.

**Step 5: Commit**

```bash
git add src/ptsm/domain/psychology_carousel.py src/ptsm/agent_runtime/runtime.py src/ptsm/agent_runtime/nodes/memory.py src/ptsm/agent_runtime/nodes/executor.py tests/unit/domain/test_psychology_carousel.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_finalize_node.py
git commit -m "feat: reject repeated psychology carousel inner pages"
```

verify: `uv run pytest tests/unit/domain/test_psychology_carousel.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_finalize_node.py -q`

done_when: A cover-only rotation cannot bypass the bounded recent-inner-page duplicate gate; only the latest twelve successfully rendered, receipt-verified, ledger-projected ordinary carousels consume it; known pre-ledger failures can abort their owner-held intent, expired intents reconcile only against a complete durable ledger projection, unknown legacy pending markers fail closed, and invalid/untrusted memory values cannot be injected into the drafting context.

### Task 2: Make deterministic fallback pages genuinely vary across a supported run sequence

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Write failing tests**

Build the same deterministic modern-psychology draft once without history and once with one prior inner-page fingerprint. Assert that the cover contract remains valid and that the complete sequence of inner visible cards differs. Add a retry-feedback case to prove a duplicate rejection chooses the next variation rather than rendering the same pages again.

**Step 2: Run the focused test to verify failure**

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py -q`

Expected: the new test fails because the fallback keeps fixed inner slide copy.

**Step 3: Implement the smallest deterministic variation policy**

Use the number of validated recent inner-page fingerprints plus an explicit duplicate-retry signal to choose one of twelve bounded, psychology-safe card phrasings. Apply the selected variation to the scene, mechanism, tool, boundary, and comment cards while preserving validated roles, line limits, and professional-help boundary. Do not change the learning-series controlled template path.

**Step 4: Run the focused test to verify success**

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py -q`

Expected: PASS, with a valid but different inner-card fingerprint for the next supported slot.

**Step 5: Commit**

```bash
git add src/ptsm/infrastructure/llm/contextual_drafts.py tests/unit/infrastructure/llm/test_factory.py
git commit -m "fix: vary deterministic psychology carousel inner cards"
```

verify: `uv run pytest tests/unit/infrastructure/llm/test_factory.py -q`

done_when: The deterministic preview no longer only rotates a cover; every non-cover card changes across the first twelve retained variants, and an exhausted or duplicate candidate fails closed rather than silently repeating.

### Task 3: Fail closed on duplicate rendered files and emit a relay-ready receipt

**Files:**
- Modify: `src/ptsm/application/services/image_carousel_transaction.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/services/test_image_carousel_transaction.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add a renderer fixture that writes byte-identical PNGs to two distinct expected paths; assert that no set commits, including when an existing manifest is reverified. Add a normal psychology run assertion for an ordinary-only `carousel_delivery` receipt with expected/generated/unique counts and exact ordered attachment/path/hash records, and assert that PTSM still requires an external relay.

**Step 2: Run the focused tests to verify failure**

Run: `uv run pytest tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py -q`

Expected: the duplicate files currently commit and ordinary responses do not contain a delivery receipt.

**Step 3: Implement the smallest integrity boundary**

Reject duplicate `file_sha256` values while rendering and while revalidating a committed manifest. Persist an immutable receipt intent before calling the ledger (and retain it if ledger append may have reached durable storage); immediately verify the complete ordered ledger projection before atomically committing memory and adding an ordinary-only response/artifact `carousel_delivery` receipt. The receipt contains the committed `set_id`, expected/generated/unique counts, ordered attachment/page/file hashes, `status=ready`, and `external_relay_required` status. A per-invocation artifact ownership tracker must reject/scrub forged workflow `carousel_delivery` fields without touching foreign artifacts, and fence every later ordinary-artifact merge and publish consumption against replacement. Omit a ready delivery receipt on every failure. Keep learning-series responses sealed and do not add paths to their sanitized receipt.

**Step 4: Run the focused tests to verify success**

Run: `uv run pytest tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py -q`

Expected: PASS; byte-identical pages fail atomically and normal carousel output has one complete relay-ready receipt.

**Step 5: Commit**

```bash
git add src/ptsm/application/services/image_carousel_transaction.py src/ptsm/application/use_cases/run_playbook.py tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py
git commit -m "feat: add psychology carousel delivery integrity receipt"
```

verify: `uv run pytest tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py -q`

done_when: A committed normal-carousel result cannot contain duplicate PNG bytes and only a fully ledgered result gives an outer relay all data needed to verify `expected == generated == unique == forwarded`, without claiming PTSM already forwarded files.

### Task 4: Make the agent/skill contract explicit and document operations

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/operations/content-experiment-runbook.md`
- Modify: `docs/operations/publish-quickstart.md`
- Modify: `docs/operations/cloud-bootstrap.md`
- Test: `tests/unit/docs/test_openclaw_skill.py`
- Test: `tests/unit/docs/test_docs_map.py`

**Step 1: Write failing documentation tests**

Add assertions that the wrapper says one normal carousel is 4–7 pages, treats `max_text_units` as density rather than image count, requires clarification for 8+ / 12-image language, and requires ordered receipt verification before external forwarding.

**Step 2: Run the focused tests to verify failure**

Run: `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py -q`

Expected: the wrapper has no count-intent router or relay integrity wording.

**Step 3: Update contracts and source-of-truth docs**

Document the three required interpretations of a large count (independent assets, one overlong post, or multiple separately approved carousels), and prohibit looping one `run-playbook` call or reusing old attachments. Describe the optional external batch fields (`batch_id`, target count, slot index, variation brief/fingerprint, retry-of), but state that they belong to the outer relay rather than today’s PTSM command. State the normal receipt’s exact count/order/hash contract using the canonical `pages.order`, `page_sha256`, `file_sha256`, `generated_image_paths`, and `manifest_sha256` fields; only a committed receipt can be forwarded. Document commit-after-render/ledger and the external sender boundary.

Update the full required source-of-truth surface: architecture placement and non-goal; runtime memory/duplicate/receipt behavior; playbook and builtin skill constraints; OpenClaw wrapper behavior; harness coverage; operations and affected local/content-experiment/publish/cloud runbooks. `docs/operations/task-completion-automation.md` is intentionally unchanged because it does not own image generation, attachment relay, or publish verification behavior.

**Step 4: Run the focused tests to verify success**

Run: `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py -q`

Expected: PASS.

**Step 5: Commit**

```bash
git add integrations/openclaw/ptsm-xhs-psychology/SKILL.md src/ptsm/skills/builtin/psychology_style/SKILL.md docs/architecture.md docs/runtime.md docs/playbooks.md docs/skills.md docs/harness-engineering.md docs/operations.md docs/operations/local-runbook.md docs/operations/content-experiment-runbook.md tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py
git commit -m "docs: define psychology image count and relay contract"
```

verify: `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py -q`

done_when: The agent cannot reasonably interpret “12 张” as permission to resend one four-page set, and an operator can identify the external relay boundary and required evidence.

### Task 5: Verify, review, and hand off the isolated branch

**Files:**
- Modify: `docs/plans/2026-08-21-psychology-image-batch-integrity.md` (evidence only, if needed)

**Step 1: Run focused regression tests**

Run:

```bash
uv run pytest \
  tests/unit/domain/test_psychology_carousel.py \
  tests/unit/agent_runtime/test_executor_node.py \
  tests/unit/agent_runtime/test_reflector_node.py \
  tests/unit/agent_runtime/test_finalize_node.py \
  tests/unit/infrastructure/llm/test_factory.py \
  tests/unit/application/services/test_image_carousel_transaction.py \
  tests/unit/application/use_cases/test_run_playbook.py \
  tests/unit/infrastructure/artifacts/test_file_store.py \
  tests/unit/infrastructure/images/test_asset_ledger.py \
  tests/unit/infrastructure/memory/test_store.py \
  tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py \
  tests/unit/docs/test_openclaw_skill.py \
  tests/unit/docs/test_docs_map.py \
  tests/unit/docs/test_docs_metadata.py -q
```

**Step 2: Run repository verification**

Run:

```bash
uv run pytest -q
uv run pytest tests/e2e/test_modern_psychology_publish_dry_run.py -q
uv run python -m ptsm.bootstrap docs-sync --base-ref main
uv run python -m ptsm.bootstrap harness-check --base-ref main
uv run python -m ptsm.bootstrap doctor
```

**Step 3: Review and finish the branch**

Use the two-stage subagent review process (spec compliance then code quality), inspect `git diff --check` and `git status --short`, merge only this clean feature branch into `main`, then preserve the user’s pre-existing untracked main-worktree files.

verify: focused, end-to-end, full-suite, docs-sync, and harness commands above exit 0, and `git diff --check` is clean. `doctor` must be recorded separately if a locally configured external MCP endpoint is unavailable.

done_when: The branch contains only the planned changes, full tests and harness evidence pass, reviewers approve, immutable receipt-intent recovery and tracked-artifact fencing are covered by regression tests, and the change is merged back to `main` without touching pre-existing user files.

## Verification Evidence

- `uv run pytest tests/unit/domain/test_psychology_carousel.py tests/unit/agent_runtime/test_executor_node.py tests/unit/agent_runtime/test_reflector_node.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/infrastructure/llm/test_factory.py tests/unit/application/services/test_image_carousel_transaction.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/artifacts/test_file_store.py tests/unit/infrastructure/images/test_asset_ledger.py tests/unit/infrastructure/memory/test_store.py tests/unit/agent_runtime/test_runtime_psychology_learning_boundary.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q` — PASS.
- `uv run pytest tests/e2e/test_modern_psychology_publish_dry_run.py -q` — PASS (9 tests).
- `uv run pytest -q` — PASS.
- `uv run python -m ptsm.bootstrap docs-sync --base-ref main` — PASS; no missing or unmapped documentation updates.
- `uv run python -m ptsm.bootstrap harness-check --base-ref main` — PASS.
- `uv run python -m compileall -q src` and `git diff --check` — PASS.
- Independent review approved the final reservation/receipt/artifact-root changes with no blockers or important findings.
- `uv run python -m ptsm.bootstrap doctor` completed, but reports the expected environmental diagnostic: the locally configured `xiaohongshu-mcp` endpoint at `http://localhost:18060/mcp` is not running. Settings, artifact directory, documentation freshness, run store, and plan-run checks are OK.
