# Harness Runtime State And Events Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add durable runtime state and event-level observability to the harness branch so agents can resume state across process restarts and query run events directly.

**Architecture:** Keep the current filesystem-first harness shape. Add a file-backed LangGraph checkpointer and a file-backed execution-memory store under `.ptsm/agent_runtime`, then expose filtered event queries and aggregates through a dedicated application use case and CLI command. Update the source-of-truth docs to reflect the new runtime and observability surface.

**Tech Stack:** Python 3.12, pytest, LangGraph, argparse, local filesystem JSON/pickle persistence

### Task 1: Durable Runtime State

**Files:**
- Create: `src/ptsm/infrastructure/memory/checkpoint.py`
- Modify: `src/ptsm/infrastructure/memory/store.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/infrastructure/memory/test_checkpoint.py`
- Test: `tests/unit/infrastructure/memory/test_store.py`
- Test: `tests/integration/test_fengkuang_workflow.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `FileExecutionMemory` persists lessons across fresh instances.
- `FileCheckpointSaver` persists checkpoints and pending writes across fresh instances.
- `run_playbook()` defaults to durable runtime state rooted under `.ptsm/agent_runtime` when no explicit memory/checkpointer is injected.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/infrastructure/memory/test_store.py tests/unit/infrastructure/memory/test_checkpoint.py tests/integration/test_fengkuang_workflow.py -q`
Expected: FAIL because file-backed runtime state does not exist yet.

**Step 3: Write the minimal implementation**

Implement:
- A file-backed execution memory store that keeps the same `record/search` behavior as the in-memory version.
- A file-backed checkpoint saver that subclasses LangGraph's in-memory saver and flushes checkpoint state to disk after mutations.
- Runtime helpers so `build_fengkuang_workflow()` accepts injected checkpointers and `run_playbook()` can construct durable defaults under `.ptsm/agent_runtime`.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/infrastructure/memory/test_store.py tests/unit/infrastructure/memory/test_checkpoint.py tests/integration/test_fengkuang_workflow.py -q`
Expected: PASS.

### Task 2: Event Query And Aggregation

**Files:**
- Modify: `src/ptsm/infrastructure/observability/run_store.py`
- Create: `src/ptsm/application/use_cases/run_events.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/infrastructure/observability/test_run_store.py`
- Test: `tests/unit/application/use_cases/test_run_events.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

Add tests that prove:
- `RunStore` can list filtered events across runs.
- `RunStore` can aggregate event counts by a supported field.
- The new `run-events` use case and CLI command pass filters through correctly.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_events.py tests/unit/test_bootstrap.py -q`
Expected: FAIL because event query and aggregation APIs do not exist yet.

**Step 3: Write the minimal implementation**

Implement:
- `RunStore.list_events(...)`
- `RunStore.aggregate_events(...)`
- `run_run_events(...)`
- `ptsm run-events` with run-level filters, event-level filters, `--group-by`, and `--limit`

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_events.py tests/unit/test_bootstrap.py -q`
Expected: PASS.

### Task 3: Docs Alignment

**Files:**
- Modify: `docs/harness-engineering.md`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `README.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs assertions**

Add or update docs tests only if needed to reflect any new command or source-of-truth pointer.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL only if doc references or required links are missing.

**Step 3: Write the minimal documentation updates**

Document:
- durable runtime state location and thread-id behavior
- new `ptsm run-events` command
- the updated harness-engineering status so completed work is not still listed as "next"

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: End-To-End Verification

**Files:**
- Modify: `docs/plans/2026-04-17-harness-engineering-runtime-state-and-events.md`

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/infrastructure/memory/test_store.py tests/unit/infrastructure/memory/test_checkpoint.py tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_events.py tests/unit/test_bootstrap.py tests/integration/test_fengkuang_workflow.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs README.md src tests
git commit -m "feat: add durable runtime state and run event queries"
```
