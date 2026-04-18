# Harness Report Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local `harness-report` surface that composes `doctor`, `gc`, and `harness-evals` into one machine-readable snapshot with optional threshold checks for automation.

**Architecture:** Keep the report layer in `application/use_cases` and build it entirely from existing local artifact stores and existing use cases. Do not add a new database, scheduler, or background service. The new command should stay read-only, use the same filesystem-backed sources as the current harness, and optionally turn warnings into a non-zero CLI exit code when the operator asks for it.

**Tech Stack:** Python 3.12, argparse, pytest, local JSON/JSONL artifacts under `.ptsm/`, existing `doctor` / `gc` / `harness-evals` commands

### Task 1: Report Use Case Tests

**Files:**
- Create: `src/ptsm/application/use_cases/harness_report.py`
- Modify: `src/ptsm/application/use_cases/doctor.py`
- Test: `tests/unit/application/use_cases/test_harness_report.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `run_harness_report(...)` returns one JSON-ready payload containing:
  - `generated_at`
  - `status`
  - `filters`
  - `retention`
  - `doctor`
  - `gc`
  - `evals`
  - `thresholds`
- the report runs `doctor`, `gc` in dry-run mode, and `harness-evals` against the same project root
- threshold evaluation reports violations for:
  - stale docs count
  - gc candidate count
  - run completion rate
  - plan-run completion rate
- overall report `status` escalates to `warning` when thresholds are violated even if the composed use cases are otherwise valid

Example assertion shape:

```python
assert result["thresholds"]["violations"] == [
    {
        "name": "max_stale_docs",
        "actual": 1,
        "expected": "<= 0",
    }
]
assert result["status"] == "warning"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_report.py -q`
Expected: FAIL because the report use case does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `run_harness_report(...)`
- composition over:
  - `run_doctor(...)`
  - `run_harness_gc(..., apply=False)`
  - `run_harness_evals(...)`
- threshold normalization with optional parameters:
  - `max_stale_docs`
  - `max_gc_candidates`
  - `min_run_completion_rate`
  - `min_plan_completion_rate`
- consistent `project_root` handling so report queries the target worktree instead of the caller's cwd
- any small `run_doctor(...)` signature widening needed so the report and gc use the same retention settings

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_report.py -q`
Expected: PASS.

### Task 2: CLI Surface And Operator Gate

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

Add tests that prove:
- CLI parser exposes `harness-report`
- CLI accepts:
  - `--server-url`
  - `--account-id`
  - `--platform`
  - `--playbook-id`
  - `--plan-path`
  - `--runs-retention-days`
  - `--plan-runs-retention-days`
  - `--max-stale-docs`
  - `--max-gc-candidates`
  - `--min-run-completion-rate`
  - `--min-plan-completion-rate`
  - `--fail-on-warning`
- CLI dispatch passes those values through correctly
- `main(["harness-report", "--fail-on-warning"])` returns `1` when the report status is `warning`

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: FAIL because the parser and dispatch path do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- a new `ptsm harness-report` command
- JSON output only
- optional `--fail-on-warning` gate that returns `1` when report status is `warning` or `error`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: PASS.

### Task 3: Docs And Strategy Sync

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/architecture.md`
- Modify: `docs/plans/2026-04-18-harness-roadmap.md`
- Modify: `tests/unit/docs/test_docs_map.py`
- Modify: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs tests**

Add or tighten docs tests so they prove:
- `operations.md` indexes `harness-report`
- `observability.md` and `harness-engineering.md` mention the new composed report surface
- architecture guidance still points composed report/eval/inspection surfaces at `application/use_cases`

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL because the docs do not mention the new report surface yet.

**Step 3: Write minimal documentation updates**

Document:
- what `harness-report` includes
- how threshold checks work
- when to use `harness-report` instead of calling `doctor`, `gc`, and `harness-evals` separately
- that the current next step after this phase remains traces/metrics only if file-backed observability stops being enough

**Step 4: Run docs tests to verify they pass**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_report.py tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: add harness report snapshot"
```
