# DeepSeek JSON Publish Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make DeepSeek-backed drafting robust to non-strict JSON responses, keep the generated copy free of internal system phrases, and use the repaired path to publish one private Xiaohongshu post successfully.

**Architecture:** Keep the fix local to the drafting backend. Reproduce the exact DeepSeek response shape, add parser regression tests for fenced or prose-wrapped JSON, then harden the existing JSON extraction helper instead of redesigning the LLM contract. Reuse the current publish harness so the final verification is a real `run-fengkuang` execution plus post-run diagnostics.

**Tech Stack:** Python 3.12, pytest, LangChain/DeepSeek, argparse, filesystem artifacts

### Task 1: Capture the Failing Response Shape

**Files:**
- Modify: `docs/plans/2026-04-18-deepseek-json-publish-fix.md`

**Step 1: Reproduce the failure outside the publish flow**

Run a focused command that calls the DeepSeek drafting backend and prints a safe representation of the raw response payload.

**Step 2: Verify the failure shape**

Confirm whether the response is wrapped in markdown fences, prefixed prose, or another non-strict JSON form.

### Task 2: Add Parser Regression Tests

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Write the failing tests**

Add tests that prove `_parse_json_payload(...)` accepts:
- plain JSON
- fenced JSON
- prose-wrapped fenced JSON

Add one integration-level backend test if needed to prove the DeepSeek path uses the hardened parser.

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py -q`
Expected: FAIL because the current parser only accepts strict JSON.

### Task 3: Implement the Minimal Parser Fix

**Files:**
- Modify: `src/ptsm/infrastructure/llm/factory.py`

**Step 1: Write minimal implementation**

Harden JSON extraction so the drafting backend can parse common LLM response wrappers without changing the surrounding draft-generation flow.

**Step 2: Run targeted tests to verify they pass**

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py -q`
Expected: PASS.

### Task 4: Verify the Repaired Flow and Publish

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Run focused verification**

Run targeted tests for the DeepSeek backend and any publish-status parsing paths touched by the change.

**Step 2: Run full verification**

Run: `uv run pytest -q`
Expected: PASS.

**Step 3: Execute one real publish**

Run `run-fengkuang` with:
- a weekend-layflat scene
- `--publish-mode mcp-real`
- `--publish-visibility "仅自己可见"`
- `--wait-for-publish-status`

**Step 4: Inspect the result**

Record:
- run id
- artifact path
- whether publish status is fully verified or still falls back to manual confirmation

**Step 5: Update docs only if operator-facing behavior changed**

If the fix changes how operators should reason about DeepSeek or publish diagnostics, sync `docs/observability.md` and `docs/operations/local-runbook.md`.
