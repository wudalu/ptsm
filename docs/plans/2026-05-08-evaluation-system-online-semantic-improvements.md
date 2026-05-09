# Evaluation System Online Semantic Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Upgrade the current evaluation skeleton so online evals can safely grow from deterministic artifact checks into step-aware semantic evaluation.

**Architecture:** Keep evaluation outside `agent_runtime` orchestration. Runtime emits richer step evidence into artifacts and run events; `src/ptsm/evaluations` extracts phase-specific `EvalTarget`s; deterministic rule/contract evaluators can gate; LLM judges are opt-in, structured, and warning-only.

**Tech Stack:** Python, pytest, dataclasses, local JSON/JSONL stores, existing `RunStore`, existing artifact store, optional fake/real LLM judge backend.

## Source-Of-Truth Context

- `docs/architecture.md`: evaluation domain code belongs in `src/ptsm/evaluations`; local store belongs in `src/ptsm/infrastructure/evaluations`; application use cases orchestrate reporting and harness surfaces.
- `docs/runtime.md`: `run_playbook()` owns application-level image/publish/post-publish orchestration after LangGraph runtime completes.
- `docs/observability.md`: `.ptsm/runs`, `.ptsm/plan_runs`, artifacts, generated images, and `.ptsm/evals` are the local-first evidence sources.
- `docs/harness-engineering.md`: `harness-check` is the local gate; deterministic checks can block, subjective checks start as reporting signals.

## Task 1: Fix Gate Semantics, Publish Mode Contract, And Eval Run Scope

**Files:**
- Modify: `src/ptsm/evaluations/contracts.py`
- Modify: `src/ptsm/evaluations/rules.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Modify: `src/ptsm/infrastructure/evaluations/eval_store.py`
- Modify: `src/ptsm/application/use_cases/harness_evals.py`
- Modify: `src/ptsm/application/use_cases/harness_report.py`
- Modify: `src/ptsm/application/use_cases/harness_check.py`
- Test: `tests/unit/evaluations/test_rules.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`
- Test: `tests/unit/application/use_cases/test_harness_evals.py`
- Test: `tests/unit/application/use_cases/test_harness_report.py`
- Test: `tests/unit/application/use_cases/test_harness_check.py`
- Test: `tests/unit/infrastructure/test_eval_store.py`

**verify:** `uv run pytest tests/unit/evaluations/test_rules.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/application/use_cases/test_harness_evals.py tests/unit/application/use_cases/test_harness_report.py tests/unit/application/use_cases/test_harness_check.py tests/unit/infrastructure/test_eval_store.py -q`

**done_when:** Deterministic gates distinguish required vs warning failures, `mcp-real` passes publish mode validation, and scoped harness evals only aggregate matching eval runs.

## Task 2: Enforce Playbook-Local Evaluation Contracts

**Files:**
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/evaluations/playbook_contracts.py`
- Test: `tests/unit/evaluations/test_contract_evaluators.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`

**verify:** `uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_eval_artifact.py -q`

**done_when:** `run_eval_artifact()` applies playbook-local node contracts when present and records evidence paths for violations.

## Task 3: Persist And Extract Step-Level Evidence

**Files:**
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/evaluations/targets.py`
- Test: `tests/unit/agent_runtime/test_finalize_node.py`
- Test: `tests/unit/evaluations/test_targets.py`

**verify:** `uv run pytest tests/unit/agent_runtime/test_finalize_node.py tests/unit/evaluations/test_targets.py -q`

**done_when:** Online artifacts contain enough bounded evidence for deterministic and future LLM step evaluators.

## Task 4: Add Warning-Only LLM Judge Adapter Scaffold

**Files:**
- Create: `src/ptsm/evaluations/llm_judge.py`
- Modify: `src/ptsm/application/use_cases/eval_artifact.py`
- Test: `tests/unit/evaluations/test_llm_judge.py`
- Test: `tests/unit/application/use_cases/test_eval_artifact.py`

**verify:** `uv run pytest tests/unit/evaluations/test_llm_judge.py tests/unit/application/use_cases/test_eval_artifact.py -q`

**done_when:** The codebase can run structured warning-only LLM judge evaluators in tests without network or credentials, and default harness remains deterministic-only.

## Task 5: Update Active Docs And Final Harness

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/shared-contracts.md`

**verify:** `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q && uv run pytest tests/unit/evaluations tests/unit/agent_runtime/test_finalize_node.py tests/unit/application/use_cases/test_eval_artifact.py tests/unit/application/use_cases/test_harness_evals.py tests/unit/application/use_cases/test_harness_report.py tests/unit/application/use_cases/test_harness_check.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/test_eval_store.py -q && uv run python -m ptsm.bootstrap harness-check`

**done_when:** Docs match behavior, targeted tests pass, and `harness-check` returns `status: ok`.
