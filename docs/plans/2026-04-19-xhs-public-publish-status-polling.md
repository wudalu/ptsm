# XHS Public Publish Status Polling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `run-fengkuang --wait-for-publish-status` tolerate short public-search indexing delay so successful public posts can settle into `published_search_verified` during the initial run.

**Architecture:** Keep the existing `check_xhs_publish_status()` fallback logic, but let callers opt into a bounded retry window for the public `search_feeds` path. `run_playbook()` will enable that retry window only when waiting for publish status, so one-off manual checks stay fast.

**Tech Stack:** Python, pytest, existing XHS MCP publisher integration.

### Task 1: Add the failing retry test

**Files:**
- Modify: `tests/unit/application/use_cases/test_xhs_publish_status.py`

**Step 1: Write the failing test**

Add a test where the public-search fallback returns `None` on the first call and a located note on the second call.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py::test_check_xhs_publish_status_retries_public_search_fallback -q`
Expected: FAIL because the current implementation only checks once.

**Step 3: Commit**

Do not commit yet.

### Task 2: Implement bounded polling

**Files:**
- Modify: `src/ptsm/application/use_cases/xhs_publish_status.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`

**Step 1: Write minimal implementation**

Add optional retry parameters to `check_xhs_publish_status()` for the public-search fallback only, and have `run_playbook()` pass a short bounded retry window when `wait_for_publish_status=True`.

**Step 2: Run targeted tests**

Run: `uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_run_playbook.py -q`
Expected: PASS.

### Task 3: Update docs and verify

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Document the new behavior**

Explain that public verification now includes a short polling window for search indexing, while private posts still require manual verification without upstream identifiers.

**Step 2: Run broader verification**

Run: `uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/application/use_cases/test_diagnose_publish.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.
