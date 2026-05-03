---
title: PTSM Development Workflow
status: active
owner: ptsm
last_verified: 2026-05-03
source_of_truth: true
related_paths:
  - AGENTS.md
  - CLAUDE.md
  - docs/index.md
  - docs/harness-engineering.md
  - docs/operations/task-completion-automation.md
  - docs/operations/local-runbook.md
  - docs/plans
---

# Development Workflow

This workflow applies to larger development work only:

- new product features
- new domains or playbooks
- new skills with runtime behavior
- new publish, verification, observability, or harness surfaces

It does not cover small bug fixes, typo fixes, docs-only cleanup, or narrow test
maintenance. Those should get a smaller workflow later.

## Principle

Major development starts from the repository's current source-of-truth docs and
ends with machine-checkable evidence. Do not rely on memory, informal notes, or
"remember to run this" instructions.

The expected path is:

1. read the current docs
2. clarify the user need
3. write the design or implementation plan
4. define verification before implementation
5. implement in small tasks
6. run task-level and end-to-end verification
7. update source-of-truth docs
8. run the harness gate

## 1. Read Current Docs First

Start at [`docs/index.md`](index.md), then read the most specific active docs for
the change:

- architecture changes: [`architecture.md`](architecture.md)
- runtime changes: [`runtime.md`](runtime.md)
- playbook or account changes: [`playbooks.md`](playbooks.md)
- skill changes: [`skills.md`](skills.md)
- observability or artifact changes: [`observability.md`](observability.md)
- operator or publish workflow changes: [`operations.md`](operations.md)
- harness rules: [`harness-engineering.md`](harness-engineering.md)

Historical plans in [`docs/plans/`](plans/) are useful context, but they are not
current truth when they conflict with code or active docs.

## 2. Clarify The User Need

Before writing a plan, reduce the request to:

- goal: what user-visible or operator-visible behavior changes
- scope: which domains, playbooks, commands, or publish paths are affected
- non-goals: what should not be solved in this change
- constraints: architecture boundaries, side effects, provider limits, or manual approval points
- success criteria: what evidence will prove the work is done

If the request touches external side effects such as real publishing, make the
safe path explicit: dry-run first, real publish only with intentional visibility
and verification choices.

## 3. Write The Plan

Major work should have a plan under `docs/plans/YYYY-MM-DD-<topic>.md`.

Use the current plan style:

- state the goal, architecture, and tech stack
- split work into small `### Task N` sections
- list exact files to create or modify
- define `verify:` commands per task
- define `done_when:` conditions per task
- include docs updates in the relevant task, not as an afterthought
- include a final harness verification task

For new domains, prefer additive files over runtime edits. If an existing file
must change, make it an extension point rather than a domain-specific branch.

## 4. Define Verification Before Implementation

Each task should say how it will be checked before the implementation starts.

Default verification layers:

- targeted tests for the changed behavior
- docs tests when source-of-truth docs or docs map change
- `uv run pytest -q` before final completion
- `uv run python -m ptsm.bootstrap doctor` for runtime, operations, or harness changes
- `uv run python -m ptsm.bootstrap docs-sync ...` when code and docs change together
- `uv run python -m ptsm.bootstrap harness-check ...` before merge or handoff

Task-specific smoke checks are required for runtime-visible behavior. Examples:

- new playbook: `run-playbook` dry-run through the generic CLI
- new publish behavior: dry-run plus artifact or publish-status verification
- new observability surface: command output and artifact/query tests
- new harness rule: failing and passing cases for the gate

Browser-opening commands and real external writes should stay manual or
conditional unless the task explicitly requires them.

## 5. Implement In Small Tasks

Work task by task. A task should be small enough that its verification can run
immediately after the change.

Expected loop:

1. write or update the failing test/check
2. run it and confirm the expected failure when practical
3. implement the smallest coherent change
4. run the task's `verify:` commands
5. update related docs in the same task
6. record evidence or command output in the handoff

Do not mark a task complete because the code "looks right". Completion requires
the planned checks to pass, or a clear explanation of why a check could not run.

## 6. End-To-End Validation

Every major change needs one final validation path that crosses the real user or
operator surface.

Use the narrowest end-to-end proof that matches the change:

- feature or domain: CLI dry-run that reaches `status == completed`
- content playbook: generated content contains the required domain signals
- image path: generated image metadata appears in the artifact
- publish path: artifact-based publish check or `diagnose-publish`
- harness path: `harness-check` or the specific gate returning the expected status

For real Xiaohongshu publishing, follow
[`docs/operations/local-runbook.md`](operations/local-runbook.md): preflight,
dry-run, private or public publish path, then publish verification.

## 7. Keep Docs In Sync

When code changes affect a source-of-truth area, update the matching active doc
in the same change. `docs-sync` uses `related_paths` to enforce this for
`src/ptsm/**` and `shared_contracts/**`.

Common mappings:

- runtime code -> `docs/runtime.md`
- playbook/account definitions -> `docs/playbooks.md`
- skill registry, selector, or builtin skills -> `docs/skills.md`
- artifact, logs, runs, evals, diagnostics -> `docs/observability.md`
- CLI/operator flows -> `docs/operations.md` or a linked runbook
- harness gates and policy -> `docs/harness-engineering.md`

When touching an active source-of-truth doc, update `last_verified` if the change
also revalidates the doc's claims.

## 8. Final Handoff

A major development handoff should include:

- what changed
- which docs were updated
- which verification commands ran
- where the end-to-end evidence lives, if artifacts were produced
- any checks that could not run and why
- any remaining manual approval or real-publish step

The preferred final gate is:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Use `--strict` when matching CI or branch-protection behavior locally.
