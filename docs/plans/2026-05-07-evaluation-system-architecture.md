# Evaluation System Architecture Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:writing-plans before turning this design into an implementation plan, and use superpowers:test-driven-development for runtime behavior changes.

**Goal:** Build a local-first evaluation system that scores important PTSM execution steps and artifacts using rule, contract, and LLM-based evaluators.

**Architecture:** Treat every runtime step and artifact slice as an `EvalTarget`, run typed `Evaluator`s over those targets, persist structured `EvalResult`s under `.ptsm/evals`, and aggregate them into `harness-evals` / `harness-report`. Deterministic rule/contract checks may gate. LLM judges remain warning/manual-review until calibrated.

**Tech Stack:** Python, pytest, local JSON/JSONL stores, existing `RunStore`, existing artifact store, dataclass contracts, optional LLM judge backend through explicit injection.

## Current Implementation Review

The first implementation in `feat/evaluation-system` established the deterministic skeleton:

- shared schema templates under `shared_contracts/evaluation/`
- `EvalTarget`, `EvalResult`, `EvaluatorSpec`, `EvalSuite`
- artifact target extraction
- rule and contract evaluators
- local `.ptsm/evals/<eval_run_id>/summary.json` and `results.jsonl`
- `ptsm eval-artifact`
- `run_playbook()` online eval invocation after artifact creation
- `harness-evals`, `harness-report`, and `harness-check` aggregation/gating

This is enough for Phase 1 structure, but not enough for full online quality evaluation.

## Gaps Found In Review

### Playbook Contracts Were Loaded But Not Enforced

`src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml` defines planner, executor, reflector, and finalize contracts, but the initial `run_eval_artifact()` path ran hard-coded evaluator maps. The loader existed, but no runtime evaluator read `node_contracts`.

Required direction: evaluator suite resolution must combine shared evaluator specs with playbook-local `evaluation.yaml` bindings and constraints.

### Online Eval Evidence Was Too Shallow

The initial online path evaluated only the final artifact. Target extraction produced planner skill activation, executor final content, and final artifact completeness targets, but did not evaluate planner selection, draft outcome, reflection decision, image generation, publish, or post-publish evidence.

Required direction: runtime must persist step-level evidence into artifacts and target extraction must produce phase-specific targets from that evidence.

### Gate Semantics Did Not Support Warning-Only LLM Judges

`EvalResult` initially did not carry `gate_level`, and gate counts treated every failed/error result as a required failure.

Required direction: persist `gate_level` on each result and calculate `required_failed` only from required evaluators. LLM judge failures should count as warnings/manual-review unless explicitly promoted.

### Publish Mode Rule Was Inconsistent With Runtime

The initial `publish_mode.valid` evaluator allowed `dry-run`, `private`, and `public`, while `build_publisher()` supports `dry-run` and `mcp-real`.

Required direction: align deterministic contract values with actual runtime values and keep visibility checks separate from publish mode checks.

### Harness Eval Aggregation Ignored Eval Run Scope

`harness-evals` filtered runs and events, but eval result aggregation initially read all `.ptsm/evals` summaries without filtering by account/platform/playbook/run.

Required direction: eval summaries must include source metadata and `harness-evals` must filter eval runs consistently with run filters.

## LLM Judge Direction

LLM evaluation should be introduced as step-aware and contract-bound, not as one final-artifact judge:

- planner judge: selected playbook/skills fit the request and account
- executor judge: content satisfies scene, persona, platform, and runtime context
- reflector judge: reflection identifies meaningful issues and feedback was addressed
- final judge: artifact is publish-ready for the platform and account

Implementation rules:

- LLM judge evaluators are opt-in and warning-only by default.
- Judge rubrics live in playbook-local `evaluation.yaml` and reference shared contract IDs.
- Judge prompts use small phase-specific evidence slices, not full artifacts.
- Judge responses must be structured JSON with score, label, reason, evidence, and confidence.
- Parse errors become `error` results with `gate_level=warning`, never required failures by default.
- Promotion to required gates requires offline dataset agreement and human calibration.

## Recommended Implementation Order

1. Fix deterministic correctness: publish mode rule, gate-level accounting, eval summary metadata, scoped harness filtering, and eval error observability.
2. Enforce playbook-local contracts for deterministic constraints.
3. Persist richer runtime step evidence and extract planner/executor/reflector/image/publish/post_publish targets.
4. Add a warning-only LLM judge adapter with fake backend tests and structured JSON parsing.
5. Wire playbook-local judge specs into suite resolution behind an explicit flag.
6. Add offline datasets and human review queue after online warning signals exist.

## Non-Goals For The Next Batch

- Do not make LLM judges block `harness-check`.
- Do not add external dashboard dependency.
- Do not require network/model credentials for tests or default harness.
- Do not build offline dataset execution before online evidence is rich enough.
