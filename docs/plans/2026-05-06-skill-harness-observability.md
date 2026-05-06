# Skill Harness Observability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add skill-aware observability and harness evals so PTSM can explain which skills and dynamic resources a run used, and can aggregate reliability by skill.

**Architecture:** Extend the planner/finalize/run surfaces to persist structured skill activation metadata into workflow artifacts and run summaries, then teach `harness-evals` to aggregate that metadata into a skill-level eval view. Keep the design additive: no skill routing changes, only better traceability and queryability for existing request-scoped skills plus runtime contexts.

**Tech Stack:** Python, pytest, local JSON run store, filesystem artifacts, existing PTSM skill registry/runtime.

### Task 1: Persist structured skill activation metadata in workflow state and artifacts

**Files:**
- Modify: `src/ptsm/agent_runtime/state.py`
- Modify: `src/ptsm/agent_runtime/nodes/planner.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Test: `tests/unit/agent_runtime/test_planner_node.py`
- Test: `tests/integration/test_fengkuang_workflow.py`

**Step 1: Write the failing tests**

Add assertions that planner/finalize output now includes:
- static skill metadata for each activated skill
- runtime skill metadata for each generated dynamic context block
- artifact payload fields that preserve both summaries and full runtime context text

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/agent_runtime/test_planner_node.py tests/integration/test_fengkuang_workflow.py -q`
Expected: FAIL because the state/artifact does not yet expose structured skill metadata.

**Step 3: Write the minimal implementation**

Add structured state fields for:
- `activated_skill_details`
- `runtime_skill_details`

Planner should populate static skill details from loaded skills and runtime skill details from resolver output. Finalize should persist those details into the artifact while keeping the existing plain text fields for backward compatibility.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/agent_runtime/test_planner_node.py tests/integration/test_fengkuang_workflow.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/agent_runtime/state.py src/ptsm/agent_runtime/nodes/planner.py src/ptsm/agent_runtime/runtime.py tests/unit/agent_runtime/test_planner_node.py tests/integration/test_fengkuang_workflow.py
git commit -m "feat: persist structured skill metadata in artifacts"
```

**verify:** `uv run pytest tests/unit/agent_runtime/test_planner_node.py tests/integration/test_fengkuang_workflow.py -q`

**done_when:** Workflow artifacts contain structured skill activation metadata and the narrow tests pass.

### Task 2: Persist skill metadata into run summaries for queryable observability

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write the failing test**

Add a run-playbook test asserting the finished run summary includes:
- activated skill names
- static skill detail records
- runtime skill detail records
- artifact path and publish status as before

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`
Expected: FAIL because the summary only includes artifact/publish metadata.

**Step 3: Write the minimal implementation**

When a workflow completes, propagate skill metadata from workflow result into `run_store.finish(...)` payload so `summary.json` becomes the lightweight query surface for skill usage without re-reading artifacts.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/application/use_cases/run_playbook.py tests/unit/application/use_cases/test_run_playbook.py
git commit -m "feat: record skill metadata in run summaries"
```

**verify:** `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`

**done_when:** Finished run summaries expose skill metadata directly and run-playbook tests pass.

### Task 3: Add skill-level harness eval aggregation

**Files:**
- Modify: `src/ptsm/application/use_cases/harness_evals.py`
- Test: `tests/unit/application/use_cases/test_harness_evals.py`

**Step 1: Write the failing test**

Add expectations for a new `skills` section that aggregates:
- total runs per activated skill
- completed runs per activated skill
- completion rate per activated skill
- runtime context usage counts per skill

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_evals.py -q`
Expected: FAIL because `run_harness_evals()` has no skill-level view yet.

**Step 3: Write the minimal implementation**

Aggregate run summaries by activated skill and runtime skill detail records. Keep the shape simple and deterministic so it stays suitable for local harness gating or future threshold checks.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_harness_evals.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/application/use_cases/harness_evals.py tests/unit/application/use_cases/test_harness_evals.py
git commit -m "feat: add skill-level harness evals"
```

**verify:** `uv run pytest tests/unit/application/use_cases/test_harness_evals.py -q`

**done_when:** `harness-evals` returns a skill-level aggregation section and the targeted tests pass.

### Task 4: Update source-of-truth docs and run final harness checks

**Files:**
- Modify: `docs/skills.md`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_docs_map.py`
- Test: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Update docs**

Document:
- the new structured skill metadata persisted in artifacts and runs
- the new `harness-evals` skill aggregation surface
- how this strengthens harness engineering for skill regression analysis

**Step 2: Run docs checks**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`
Expected: PASS

**Step 3: Run final verification**

Run: `uv run pytest -q --ignore=tests/e2e`
Expected: PASS

Run: `uv run python -m ptsm.bootstrap harness-check`
Expected: PASS

**Step 4: Commit**

```bash
git add docs/skills.md docs/observability.md docs/harness-engineering.md
git commit -m "docs: describe skill harness observability surfaces"
```

**verify:** `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q && uv run pytest -q --ignore=tests/e2e && uv run python -m ptsm.bootstrap harness-check`

**done_when:** Source-of-truth docs are updated and end-to-end harness verification passes.
