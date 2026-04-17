# Side Effect Ledger Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a durable side-effect ledger so `run_playbook()` can resume with the same `thread_id` without duplicating successful publish-side actions.

**Architecture:** Keep the ledger local-file-first and scoped by `thread_id`. Store successful side-effect outcomes under `.ptsm/agent_runtime/side-effects.json` and let `run_playbook()` consult that ledger before re-executing side-effecting steps. Do not cache read-only status checks. Do not let failures permanently block retries.

**Tech Stack:** Python 3.12, pytest, local JSON storage, existing `run_playbook()` workflow path

### Task 1: Side Effect Ledger Service

**Files:**
- Create: `src/ptsm/application/services/__init__.py`
- Create: `src/ptsm/application/services/side_effect_ledger.py`
- Test: `tests/unit/application/services/test_side_effect_ledger.py`

**Step 1: Write the failing test**

Add tests that prove:
- a ledger record can be written and read back by `thread_id` + `step`
- the ledger enforces `idempotency_key` matching
- records persist across fresh instances

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/services/test_side_effect_ledger.py -q`
Expected: FAIL because the ledger service does not exist yet.

**Step 3: Write minimal implementation**

Implement:
- a file-backed ledger service
- `read(...)`
- `record(...)`
- stable JSON persistence under a caller-provided path

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/services/test_side_effect_ledger.py -q`
Expected: PASS.

### Task 2: `run_playbook()` Resume Guard

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Create: `tests/integration/test_thread_memory_resume.py`

**Step 1: Write the failing tests**

Add tests that prove:
- successful publish results are recorded into the ledger
- rerunning `run_fengkuang_playbook()` with the same `thread_id` reuses the recorded publish result instead of calling `publisher.publish()` again
- the default ledger path lands under `.ptsm/agent_runtime/side-effects.json`
- the reuse behavior survives across separate invocations in an integration-style test

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_thread_memory_resume.py -q`
Expected: FAIL because `run_playbook()` has no side-effect ledger yet.

**Step 3: Write minimal implementation**

Implement:
- optional injected `side_effect_ledger`
- default file-backed ledger path under `.ptsm/agent_runtime/side-effects.json`
- idempotency key generation for the publish step
- reuse only successful publish outcomes
- no ledger-based reuse for failed publish attempts or read-only status checks

**Step 4: Run tests to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_thread_memory_resume.py -q`
Expected: PASS.

### Task 3: Docs And Strategy Updates

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/operations/task-completion-automation.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/architecture.md`
- Modify: `docs/plans/2026-04-18-harness-roadmap.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing docs assertion**

Add or adjust docs tests so the updated runtime/automation surface is indexed.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: FAIL only if the new ledger surface is not documented.

**Step 3: Write minimal docs updates**

Document:
- `.ptsm/agent_runtime/side-effects.json`
- successful publish reuse on same `thread_id`
- the architectural choice that side-effect replay control stays in `application`, not `agent_runtime`
- roadmap progress for Phase 3

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

### Task 4: Verification

**Step 1: Run targeted verification**

Run: `uv run pytest tests/unit/application/services/test_side_effect_ledger.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_thread_memory_resume.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Commit**

```bash
git add docs src tests
git commit -m "feat: add side effect ledger"
```
