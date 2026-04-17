# Run Plan Verification Evidence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist structured verification evidence artifacts for `ptsm run-plan` so verify loops produce auditable files instead of only embedding the latest records inside runner state.

**Architecture:** Keep the current `state_path` as the run anchor. Extend plan-runner task state to retain attempt history, write a deterministic sibling evidence artifact next to the state file, and expose the evidence path through `PlanRunResult`, persisted state, and CLI output. Keep the feature local to the plan-runner flow rather than introducing a new global evidence subsystem.

**Tech Stack:** Python 3.12, pytest, argparse, local filesystem JSON artifacts

### Task 1: Evidence Artifact Shape

**Files:**
- Modify: `src/ptsm/plan_runner/runner.py`
- Test: `tests/unit/plan_runner/test_runner.py`

**Step 1: Write the failing test**

Add tests that prove:
- when `state_path` is provided, `PlanRunner.run()` writes a deterministic evidence artifact next to the state file
- the evidence artifact captures per-task attempt history and per-command verification records
- failed verification attempts remain visible after a later retry passes

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: FAIL because no evidence artifact or attempt history exists yet.

**Step 3: Write minimal implementation**

Implement:
- task-state `attempt_history`
- evidence path derivation from `state_path`
- evidence payload writer invoked whenever persisted state is updated
- `PlanRunResult.verification_artifact_path`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: PASS.

### Task 2: CLI Wiring

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write the failing test**

Add tests that prove `run_plan_cli()` returns the verification artifact path emitted by the runner and that the default state-path flow still works.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`
Expected: FAIL because the CLI/result contract does not include the evidence artifact path yet.

**Step 3: Write minimal implementation**

Keep the current CLI contract and only pass through the new runner field.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`
Expected: PASS.

### Task 3: Docs Alignment

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations/task-completion-automation.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs assertions**

Add or adjust docs tests only if the new evidence artifact must be indexed or linked from source-of-truth docs.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL only if required links or references are missing.

**Step 3: Write minimal documentation updates**

Document:
- where verification evidence artifacts live
- how they relate to `state_path`
- why they exist in the harness story

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Files:**
- Modify: `docs/plans/2026-04-18-run-plan-verification-evidence.md`

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: persist run-plan verification evidence"
```
