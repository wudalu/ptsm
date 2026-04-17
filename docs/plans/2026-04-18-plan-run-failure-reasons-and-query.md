# Plan Run Failure Reasons And Query Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add normalized failure reasons to `run-plan` verification evidence and expose a CLI query surface for recent plan-run evidence artifacts.

**Architecture:** Keep all new behavior anchored on `.ptsm/plan_runs/*.evidence.json`. Extend plan-runner attempt history with stable `failure_reason` values derived from codex failures and known verify-command classes, then add a lightweight use case plus `ptsm plan-runs` CLI command that scans evidence artifacts and returns filtered summaries. Avoid introducing a new database or global index.

**Tech Stack:** Python 3.12, pytest, argparse, local filesystem JSON artifacts

### Task 1: Failure Reason Normalization

**Files:**
- Modify: `src/ptsm/plan_runner/runner.py`
- Test: `tests/unit/plan_runner/test_runner.py`

**Step 1: Write the failing test**

Add tests that prove:
- codex execution failures get a stable `failure_reason`
- verify-command failures get normalized reasons such as `pytest_failed` and `doctor_failed`
- the task-level evidence summary exposes the latest normalized failure reason

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: FAIL because evidence records do not include normalized failure reasons yet.

**Step 3: Write minimal implementation**

Implement:
- stable failure-reason classifier for codex and verify-command failures
- `failure_reason` on attempt-history entries
- task-level latest `failure_reason` in evidence artifacts

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: PASS.

### Task 2: Evidence Query Use Case And CLI

**Files:**
- Create: `src/ptsm/application/use_cases/plan_runs.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/application/use_cases/test_plan_runs.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing test**

Add tests that prove:
- evidence artifacts can be listed and filtered by `status`, `failure_reason`, and `plan_path`
- the CLI parser exposes `plan-runs`
- CLI dispatch passes filters through correctly

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_plan_runs.py tests/unit/test_bootstrap.py -q`
Expected: FAIL because the use case and CLI do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- evidence artifact scanner under `.ptsm/plan_runs`
- summary projection with failure-reason list per run
- `ptsm plan-runs --status ... --failure-reason ... --plan-path ... --limit ...`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_plan_runs.py tests/unit/test_bootstrap.py -q`
Expected: PASS.

### Task 3: Docs Alignment

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs assertion**

Add or adjust docs tests only if needed to make the new `plan-runs` command part of the indexed operator surface.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL only if docs references are missing.

**Step 3: Write minimal docs updates**

Document:
- normalized `failure_reason`
- new `ptsm plan-runs` command
- why this closes the loop between evidence capture and evidence query

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Files:**
- Modify: `docs/plans/2026-04-18-plan-run-failure-reasons-and-query.md`

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py tests/unit/application/use_cases/test_plan_runs.py tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: add plan run failure queries"
```
