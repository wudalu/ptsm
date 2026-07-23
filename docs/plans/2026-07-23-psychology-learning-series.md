---
title: Psychology Learning Series Mode
status: active
owner: ptsm
last_verified: 2026-07-23
related_paths:
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/application/models.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/application/use_cases/xhs_post_metrics.py
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
---

# Psychology Learning Series Mode

## Goal

Extend the existing `modern_psychology_post` playbook with a controlled
`learning_series` mode. It must support a short, useful Xiaohongshu learning
series without turning ordinary psychology posts into numbered lectures or
allowing arbitrary psychological claims into the drafting path.

The first shipped curriculum is a six-lesson series, **“下班后脑子停不下来”**,
about noticing rumination and low-control work moments. Each lesson is a
concrete life scene plus one approved concept, one bounded micro-exercise, an
applicability limit, and a professional-help boundary.

## Design Decision

Three approaches were considered:

1. Add a lesson number to ordinary psychology directions.
   Rejected: the current selector intentionally produces dynamic/open-scene
   directions, so it cannot prove which concept, boundary, or exercise was
   approved.
2. Create a new psychology-learning playbook.
   Deferred: the account, platform, safety policy, publish flow, and general
   psychology evaluation contract are unchanged. A new playbook would duplicate
   these assets before there is evidence that it needs a distinct account.
3. Add an evidence-bound `learning_series` submode to
   `modern_psychology_post`.
   Selected: it preserves the existing domain while giving lessons a closed,
   versioned source of truth and an AI-tech-style preflight/runtime/artifact
   boundary.

The curriculum catalog is the only knowledge root. Operators select a
`series_id` and `lesson_id`; they never submit free-form concepts, source text,
or clinical claims. The catalog stores opaque reference IDs for audit. Raw
source details remain in a human-review research note and never enter prompts,
checkpoints, reader-visible content, or artifacts.

## Scope

- Add a strict domain contract and closed six-lesson catalog.
- Add explicit CLI and `guide-post` selection for `learning_series`.
- Fail closed before `RunStore.start`, workflow, image generation, or publish
  when the mode, series, lesson, or direction is missing or mismatched.
- Isolate the runtime to a validated lesson contract; disable live topic
  research and recent-post memory for a series lesson.
- Gate drafts, artifacts, publish continuation, offline evaluation, and metrics
  using the selected lesson receipt.
- Keep output compact and native to Xiaohongshu; update the stale psychology
  style length guidance to match the current 200–380-character contract.

## Non-goals

- No diagnosis, treatment plan, medication advice, self-test, crisis handling,
  or promise of symptom improvement.
- No user-defined series, free-form evidence bundle, automatic lesson-progress
  inference, or automatic real publish.
- No new account, new playbook, or fresh-hotspot-to-lesson factual handoff.

## Task 1: Add the closed curriculum contract and preflight selection

Files:

- Create `src/ptsm/domain/psychology_learning.py`.
- Modify `src/ptsm/application/models.py`.
- Modify `src/ptsm/interfaces/cli/main.py`.
- Modify `src/ptsm/application/use_cases/guide_post.py`.
- Add `tests/unit/domain/test_psychology_learning.py`.
- Extend `tests/unit/application/use_cases/test_guide_post.py` and
  `tests/unit/interfaces/cli/test_main.py`.

Implementation:

- Model a strict, immutable curriculum catalog, a safe runtime contract, and
  an opaque manifest.
- Ship exactly one versioned series with six explicit lessons.
- Expose only curated lesson directions in this mode; no `open_scene` fallback
  and no scene-driven lesson substitution.
- Require explicit `--psychology-content-mode learning_series`,
  `--psychology-series-id`, `--psychology-lesson-id`, and a matching lesson
  direction before generation. `guide-post` may show the roadmap and selected
  lesson, but it must not create lesson text from user input.

verify:

```bash
uv run pytest tests/unit/domain/test_psychology_learning.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

done_when:

- Valid catalog lessons produce a safe contract and opaque manifest.
- Invalid IDs, cross-series lessons, free-form/malformed values, or mismatched
  direction IDs are rejected deterministically.
- Guide output shows a roadmap and one selected, curated lesson without raw
  references or open-scene directions.

## Task 2: Bind the selected lesson outside runtime state and gate drafts

Files:

- Modify `src/ptsm/application/use_cases/run_playbook.py`.
- Modify `src/ptsm/agent_runtime/runtime.py`.
- Modify `src/ptsm/agent_runtime/nodes/planner.py`.
- Modify `src/ptsm/agent_runtime/nodes/memory.py`.
- Modify `src/ptsm/agent_runtime/nodes/executor.py`.
- Modify `src/ptsm/agent_runtime/nodes/reflector.py`.
- Extend `tests/unit/application/use_cases/test_run_playbook.py`.
- Add/extend runtime boundary tests under `tests/unit/agent_runtime/`.

Implementation:

- Follow the AI evidence pattern with a bound workflow facade that reconstructs
  the initial input from the catalog contract before LangGraph checkpoints it.
- Render only the approved lesson fields to planner context; skip live context
  builders and historical memory for a learning lesson.
- Validate concept, approved explanation, micro-exercise, applicability,
  limitation, series/lesson badge, compact format, and professional boundary at
  executor, reflector, and finalize stages.
- Treat `--fresh-topic-research` as a separate discovery path for this mode;
  it may not supply lesson facts or text.

verify:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/agent_runtime/test_runtime_ai_evidence_boundary.py tests/unit/agent_runtime/test_planner_node.py tests/unit/agent_runtime/test_memory_node.py tests/unit/agent_runtime/test_reflector_node.py tests/unit/agent_runtime/test_finalize_node.py -q
```

done_when:

- All invalid selections stop before a run, workflow, artifact, image, or
  publisher exists.
- Checkpoint history and runtime context contain only catalog-approved lesson
  fields, never raw source details or operator scene text.
- Unsafe or incomplete lesson drafts never become final artifacts or publish
  payloads.

## Task 3: Make deterministic and model drafting respect the lesson contract

Files:

- Modify `src/ptsm/infrastructure/llm/contextual_drafts.py`.
- Modify `src/ptsm/infrastructure/llm/factory.py`.
- Extend deterministic drafting tests under `tests/unit/infrastructure/llm/`.
- Extend `tests/e2e/test_modern_psychology_publish_dry_run.py`.

Implementation:

- Detect the lesson contract before the generic psychology fallback.
- Produce a short scene-first Xiaohongshu post that preserves the approved
  teaching fields exactly and satisfies the existing psychology safety and
  compact-copy contracts.
- Give the hosted drafting prompt the same hard lesson constraints.

verify:

```bash
uv run pytest tests/unit/infrastructure/llm tests/e2e/test_modern_psychology_publish_dry_run.py -q
```

done_when:

- A deterministic dry-run completes for the first lesson with a 200–380
  character body, one approved concept, one micro-exercise, a natural comment
  handoff, and the professional-help boundary.
- Generic psychology drafts cannot masquerade as a selected lesson.

## Task 4: Persist series receipts, audit them, and support series metrics

Files:

- Modify `src/ptsm/agent_runtime/runtime.py`.
- Modify `src/ptsm/application/use_cases/run_playbook.py`.
- Modify `src/ptsm/evaluations/contracts_eval.py`.
- Modify `src/ptsm/application/use_cases/eval_artifact.py`.
- Modify `src/ptsm/application/use_cases/xhs_post_metrics.py`.
- Extend `tests/unit/application/use_cases/test_eval_artifact.py`,
  `tests/unit/evaluations/test_contract_evaluators.py`, and
  `tests/unit/application/use_cases/test_xhs_post_metrics.py`.

Implementation:

- Write only `series_id`, curriculum version, lesson ID/number, opaque
  reference manifest, and a passed lesson-gate receipt to the artifact.
- Rebuild the expected contract from the closed catalog during offline
  evaluation; reject tampered receipts or visible drafts that no longer match.
- Include series and lesson fields in metric rows, and allow grouping by either
  field without changing existing direction/image reports.

verify:

```bash
uv run pytest tests/unit/application/use_cases/test_eval_artifact.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/application/use_cases/test_xhs_post_metrics.py -q
```

done_when:

- A completed series artifact has an audit-safe receipt and evaluates cleanly.
- Tampered, missing, or cross-lesson receipts fail offline evaluation.
- Metrics can compare a learning series and individual lessons with the
  existing `needs_more_data` guard.

## Task 5: Update psychology assets, wrapper, source-of-truth docs, and docs tests

Files:

- Modify `src/ptsm/playbooks/definitions/modern_psychology_post/{planner.md,persona.md,reflection.md}` as needed.
- Modify `src/ptsm/skills/builtin/psychology_style/SKILL.md`.
- Modify `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` and sync
  `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`.
- Create `docs/research/2026-07-23-psychology-learning-series-sources.md`.
- Modify `docs/architecture.md`, `docs/runtime.md`, `docs/playbooks.md`,
  `docs/skills.md`, `docs/harness-engineering.md`, `docs/observability.md`,
  `docs/operations.md`, `docs/operations/local-runbook.md`, and
  `docs/operations/content-experiment-runbook.md`.
- Review `docs/operations/topic-radar-runbook.md`; leave it unchanged only if
  the existing discovery-first contract already fully covers the new separate
  path, and record that decision here.
- Extend `tests/unit/docs/test_openclaw_skill.py` and any focused docs test
  needed for the new operator command/skill contract.

Implementation:

- Teach the wrapper to show the PTSM-returned roadmap and selected lesson,
  collect an explicit confirmation, then pass the exact matching IDs. It must
  not invent lessons, sources, exercises, or claim stronger outcomes.
- Record human-review references separately from runtime-safe opaque refs.
- Explain why the mode is a psychology submode rather than a new playbook.

verify:

```bash
uv run pytest tests/unit/docs -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/domain/psychology_learning.py --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/harness-engineering.md --changed-path docs/observability.md --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md --changed-path docs/operations/content-experiment-runbook.md
```

done_when:

- Operator and wrapper documentation contain one representative safe dry-run
  and a metrics readout command.
- The installed OpenClaw psychology skill is byte-for-byte synchronized with
  the repository copy.
- All required source-of-truth surfaces are updated; `topic-radar-runbook.md`
  remains unchanged because it already describes discovery-only routing and
  does not expose any playbook-specific fact path.

## Task 6: End-to-end and harness verification

Files:

- No planned production files beyond fixes required by verification.

verify:

```bash
uv run python -m ptsm.bootstrap guide-post --playbook-id modern_psychology_post --account-id acct-psychology-local --psychology-content-mode learning_series --psychology-series-id after_work_rumination --psychology-lesson-id notice_the_loop --non-interactive --format json
uv run python -m ptsm.bootstrap run-playbook --account-id acct-psychology-local --playbook-id modern_psychology_post --psychology-content-mode learning_series --psychology-series-id after_work_rumination --psychology-lesson-id notice_the_loop --psychology-curriculum-version 1 --topic-direction-id psychology_learning_after_work_rumination_notice_the_loop --publish-mode dry-run --eval
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when:

- Inspect the smoke JSON for `status == completed` (the CLI's process exit code
  alone is not a business-success signal), a safe series receipt, and zero
  required eval failures.
- Full tests, doctor, docs sync, and harness-check pass inside this worktree.

## Progress Notes

- Tasks 1–4 are implemented with focused unit coverage. Task 5 now includes the
  psychology assets, OpenClaw wrapper, installed-skill synchronization, source
  note, and complete source-of-truth documentation surface.
- The guide now requires explicit lesson selection instead of silently choosing
  lesson one. Each catalog lesson owns a distinct title/cover hook and fixed
  image plan; manual image overrides are rejected. Metrics validate the closed
  receipt before recording, derive learning identity from the catalog, upsert a
  repeated artifact/checkpoint, and group series, curriculum version, or lesson
  without mixing ordinary psychology rows.
- Reviewed `docs/operations/topic-radar-runbook.md` on 2026-07-23 and left it
  unchanged: it is a discovery-only runbook and does not hand Topic Radar text
  into a playbook. `learning_series` independently rejects inline
  `--fresh-topic-research`, so no new exception or operator command belongs in
  that runbook.
