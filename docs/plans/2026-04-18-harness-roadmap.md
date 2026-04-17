# Harness Roadmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the current PTSM harness into a more maintainable, inspectable, and recoverable system by adding lifecycle management, eval-ready evidence aggregation, safer resume contracts, and richer observability only where justified.

**Architecture:** Keep the existing local-file-first harness model. Extend the current CLI and use-case surface instead of adding a separate service. Phase 1 adds harness drift checks and safe garbage collection around `.ptsm/runs`, `.ptsm/plan_runs`, and active docs. Later phases build on that same artifact layer for eval summaries and safer resume semantics.

**Tech Stack:** Python 3.12, argparse, pytest, local filesystem JSON/JSONL artifacts, existing `doctor` / `run-plan` / `runs` / `run-events` / `plan-runs` commands

### Phase 1: Harness Hygiene (`doctor` + `gc`)

**Outcome:** Add mechanical drift checks to `doctor` and a safe `gc` command for stale local harness artifacts.

**Files:**
- Create: `src/ptsm/application/use_cases/harness_gc.py`
- Modify: `src/ptsm/application/use_cases/doctor.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Test: `tests/unit/application/use_cases/test_doctor.py`
- Test: `tests/unit/application/use_cases/test_harness_gc.py`
- Test: `tests/unit/test_bootstrap.py`
- Test: `tests/unit/docs/test_docs_map.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `doctor` reports harness drift for orphan plan-run evidence, malformed run dirs, and stale active docs
- `gc` returns removable candidates in dry-run mode
- `gc --apply` removes only safe stale artifacts
- the CLI parser exposes `gc`
- CLI dispatch passes `--apply`, run retention, and plan-run retention through correctly

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_harness_gc.py tests/unit/test_bootstrap.py -q`
Expected: FAIL because harness drift checks and `gc` do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- a shared harness inspection layer for:
  - stale active docs based on front matter `last_verified`
  - orphan `.ptsm/plan_runs/*.evidence.json`
  - malformed `.ptsm/runs/<run_id>/` directories missing `summary.json`
  - stale completed `.ptsm/runs/` and completed `.ptsm/plan_runs/` artifacts
- `run_doctor()` integration that appends harness checks without breaking current MCP readiness checks
- `ptsm gc` with safe defaults:
  - dry-run by default
  - `--apply` to delete candidates
  - retention flags for completed run dirs and completed plan-run artifacts
  - no deletion of active/running runtime state under `.ptsm/agent_runtime/`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_harness_gc.py tests/unit/test_bootstrap.py -q`
Expected: PASS.

**Step 5: Update docs**

Document:
- new `doctor` harness checks
- new `ptsm gc` operator command
- what is considered safe for cleanup and what is intentionally retained

**Step 6: Run docs tests**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Phase 2: Evidence-Based Eval Summaries

**Outcome:** Turn run evidence into a lightweight local eval surface.

**Files:**
- Create: `src/ptsm/application/use_cases/harness_evals.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/application/use_cases/test_harness_evals.py`
- Test: `tests/unit/test_bootstrap.py`

**Implementation Notes:**
- Aggregate `runs`, `run-events`, and `plan-runs` into summary slices by `playbook_id`, `platform`, `status`, and `failure_reason`
- Keep output machine-readable JSON only
- Start with local filesystem scans, not a database
- Add regression-oriented summaries such as recent failure breakdown and completion rate

### Phase 3: Resume Contract And Side-Effect Ledger

**Outcome:** Make resume safer for side-effecting workflows.

**Files:**
- Create: `src/ptsm/application/services/side_effect_ledger.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `docs/runtime.md`
- Modify: `docs/operations/task-completion-automation.md`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/integration/test_thread_memory_resume.py`

**Implementation Notes:**
- Record side-effect checkpoints with idempotency keys
- distinguish resumable vs manual-confirmation steps
- surface reconciliation data in artifacts and operator commands

### Phase 4: Optional Traces And Metrics

**Outcome:** Add richer observability only if file-level querying stops being enough.

**Files:**
- Modify: `docs/observability.md`
- Create: `docs/plans/<future traces plan>.md`

**Implementation Notes:**
- do not start here until Phase 1 and Phase 2 are stable
- prefer a local index or export layer before adding external stacks

### Verification And Delivery

**Step 1: Run targeted verification for the active phase**

Run the active phase test set and confirm green before moving on.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Keep docs current**

Every phase must update:
- `docs/harness-engineering.md`
- the relevant source-of-truth doc (`observability.md`, `runtime.md`, or `operations.md`)
- tests for CLI surface and docs map where applicable

**Step 4: Commit phase-by-phase**

Use one commit per finished phase, for example:

```bash
git add docs src tests
git commit -m "feat: add harness gc checks"
```
