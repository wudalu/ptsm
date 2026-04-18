# Publish Diagnostics Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a local `diagnose-publish` surface that turns XiaoHongShu publish troubleshooting into a single read-only diagnostic report with likely cause classification, evidence, and next actions.

**Architecture:** Keep diagnostics in `application/use_cases` and compose existing primitives instead of inventing a new store. The new use case should read an artifact path or run id, reuse `doctor`, `logs`, and `xhs-check-publish`, then classify the most likely failure mode into a small finite taxonomy such as `login_required`, `publish_execution_error`, `publish_status_unsupported`, or `publish_identifiers_missing`.

**Tech Stack:** Python 3.12, argparse, pytest, local JSON/JSONL artifacts under `.ptsm/` and `outputs/artifacts/`, existing `doctor` / `logs` / `xhs-check-publish` commands

### Task 1: Publish Diagnostics Use Case

**Files:**
- Create: `src/ptsm/application/use_cases/diagnose_publish.py`
- Test: `tests/unit/application/use_cases/test_diagnose_publish.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `run_diagnose_publish(...)` accepts either `artifact_path` or `run_id`
- the report returns:
  - `status`
  - `likely_cause`
  - `subject`
  - `doctor`
  - `artifact`
  - `run`
  - `publish_status`
  - `evidence`
  - `next_actions`
- a run with `publish_result.error` is classified as `publish_execution_error`
- missing publish identifiers produce `publish_identifiers_missing`
- `xhs_preflight.status == login_required` overrides downstream ambiguity and classifies as `login_required`
- an MCP status result of `unsupported` is classified as `publish_status_unsupported`
- a verified publish result is classified as `publish_status_verified`

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/use_cases/test_diagnose_publish.py -q`
Expected: FAIL because the diagnostics use case does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- artifact resolution from:
  - explicit `artifact_path`
  - `run_id -> .ptsm/runs/<run>/summary.json -> artifact_path`
- doctor composition for current MCP readiness and harness drift
- run summary + publish-related event extraction
- artifact summarization over:
  - `publish_result`
  - `post_publish_checks`
- publish status probing via `check_xhs_publish_status(...)`
- a small stable taxonomy for `likely_cause`
- actionable `next_actions` strings per likely cause

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/application/use_cases/test_diagnose_publish.py -q`
Expected: PASS.

### Task 2: CLI Surface

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

Add tests that prove:
- CLI parser exposes `diagnose-publish`
- it accepts:
  - `--artifact`
  - `--run-id`
  - `--server-url`
- CLI dispatch passes those values through correctly

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: FAIL because the parser and dispatch path do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- `ptsm diagnose-publish --artifact outputs/artifacts/<artifact>.json`
- `ptsm diagnose-publish --run-id <run_id>`
- JSON output only

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: PASS.

### Task 3: Docs And Strategy Updates

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/architecture.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs tests**

Add or tighten docs tests so they prove:
- `operations.md` indexes `diagnose-publish`
- the runbook documents how to use it for publish troubleshooting
- harness/observability docs mention a read-only self-diagnosis surface

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL because the new command and docs references do not exist yet.

**Step 3: Write minimal documentation updates**

Document:
- when to use `diagnose-publish`
- how it relates to `xhs-check-publish`, `doctor`, and `logs`
- what “likely cause” means and what it does not guarantee

**Step 4: Run docs tests to verify they pass**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/application/use_cases/test_diagnose_publish.py tests/unit/test_bootstrap.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: add publish diagnostics"
```
