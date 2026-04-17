# Harness Evals Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local `harness-evals` surface that aggregates run summaries, run events, and plan-run evidence into machine-readable eval-style summaries for recent reliability trends.

**Architecture:** Keep the eval layer as an application use case over existing filesystem artifacts. Do not introduce a database, dashboard, or new artifact schema. Where needed, widen existing query helpers so the eval layer can aggregate full matching datasets instead of sampling a truncated subset.

**Tech Stack:** Python 3.12, argparse, pytest, local JSON/JSONL artifacts under `.ptsm/runs` and `.ptsm/plan_runs`

### Task 1: Full-Dataset Query Helpers

**Files:**
- Modify: `src/ptsm/infrastructure/observability/run_store.py`
- Modify: `src/ptsm/application/use_cases/plan_runs.py`
- Test: `tests/unit/infrastructure/observability/test_run_store.py`
- Test: `tests/unit/application/use_cases/test_plan_runs.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `RunStore.list_runs(limit=None)` returns all filtered runs without truncation
- `run_plan_runs(limit=None)` returns all matching evidence summaries without truncation

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_plan_runs.py -q`
Expected: FAIL because the current helpers require integer limits and truncate results.

**Step 3: Write minimal implementation**

Implement:
- optional `limit: int | None` in `RunStore.list_runs()`
- optional `limit: int | None` in `run_plan_runs()`
- preserve existing CLI behavior for integer limits

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_plan_runs.py -q`
Expected: PASS.

### Task 2: Harness Eval Summary Use Case

**Files:**
- Create: `src/ptsm/application/use_cases/harness_evals.py`
- Test: `tests/unit/application/use_cases/test_harness_evals.py`

**Step 1: Write the failing test**

Add tests that prove:
- eval summaries aggregate filtered run summaries into:
  - total runs
  - completion rate
  - counts by status, platform, and playbook
- eval summaries aggregate plan-run evidence into:
  - total plan runs
  - completion rate
  - counts by status and `failure_reason`
- eval summaries aggregate events into counts by event and event status
- the result includes a recent-failures slice that combines failed runs and failed plan runs

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_evals.py -q`
Expected: FAIL because the eval use case does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `run_harness_evals(...)`
- filesystem-backed aggregation over `RunStore` and `run_plan_runs(...)`
- JSON-only result structure with:
  - `filters`
  - `runs`
  - `events`
  - `plan_runs`
  - `recent_failures`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_evals.py -q`
Expected: PASS.

### Task 3: CLI Surface, Docs, And Strategy Updates

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/plans/2026-04-18-harness-roadmap.md`
- Test: `tests/unit/test_bootstrap.py`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing tests**

Add tests that prove:
- CLI parser exposes `harness-evals`
- CLI dispatch passes filter flags through correctly
- operations doc indexes the new command

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL because the new command and docs references do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `ptsm harness-evals`
- filters for `account_id`, `platform`, `playbook_id`
- document the eval surface in observability and operations
- update harness strategy docs so Phase 2 moves from “next” to “already has”
- update the roadmap doc to reflect Phase 2 delivery status

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_plan_runs.py tests/unit/application/use_cases/test_harness_evals.py tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: add harness eval summaries"
```
