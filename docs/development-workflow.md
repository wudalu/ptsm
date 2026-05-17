---
title: PTSM Development Workflow
status: active
owner: ptsm
last_verified: 2026-05-17
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
maintenance. Docs-only cleanup uses the smaller workflow in section 10.

## Principle

Major development starts from the repository's current source-of-truth docs and
ends with machine-checkable evidence. Do not rely on memory, informal notes, or
"remember to run this" instructions.

All major development MUST use an isolated git worktree:

- create a feature branch from `main`
- create a worktree (e.g. `.worktrees/<feature-name>`) on that branch
- develop and run all tests inside the worktree
- merge back to `main` only after harness-check passes inside the worktree

This keeps `main` clean and avoids polluting the primary workspace with
in-progress changes.

The expected path is:

1. create branch + worktree from `main`
2. read the current docs
3. clarify the user need
4. write the design or implementation plan
5. define verification before implementation
6. implement in small tasks
7. run task-level and end-to-end verification
8. update source-of-truth docs
9. run the harness gate
10. merge back to `main` and clean up worktree

## 1. Create Branch + Worktree

```bash
# Create feature branch from main in an isolated worktree
git worktree add .worktrees/<feature-name> -b feat/<feature-name> main
cd .worktrees/<feature-name>

# Verify clean baseline
uv sync
uv run pytest -q --ignore=tests/e2e
```

Worktree directory is gitignored (`.worktrees/` in `.gitignore`). After merge:

```bash
cd /path/to/main/repo
git checkout main
git merge feat/<feature-name>
git worktree remove .worktrees/<feature-name>
git branch -d feat/<feature-name>
```

## 2. Read Current Docs First

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

## 3. Clarify The User Need

Before writing a plan, reduce the request to:

- goal: what user-visible or operator-visible behavior changes
- scope: which domains, playbooks, commands, or publish paths are affected
- non-goals: what should not be solved in this change
- constraints: architecture boundaries, side effects, provider limits, or manual approval points
- success criteria: what evidence will prove the work is done

If the request touches external side effects such as real publishing, make the
safe path explicit: dry-run first, real publish only with intentional visibility
and verification choices.

## 4. Write The Plan

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

## 5. Define Verification Before Implementation

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

## 6. Implement In Small Tasks

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

## 7. End-To-End Validation

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

## 8. Keep Docs In Sync

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

## 9. Final Handoff

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

## 10. Docs-Only Cleanup Workflow

Use this smaller flow when the change only edits docs, runbooks, plans, or
research notes and does not alter runtime behavior.

1. Identify the active source-of-truth doc surface first. Start at
   [`docs/index.md`](index.md), then open the most specific linked doc or runbook.
2. State whether the cleanup changes an operational contract or only wording.
   If it changes a contract, add or update a docs test under `tests/unit/docs/`
   before editing the prose.
3. Keep the cleanup scoped to the stale or unclear area. Do not bundle unrelated
   historical note cleanup with current operator instructions.
4. If touching an active core source-of-truth doc and revalidating its claims,
   update `last_verified`.
5. Run docs-focused verification before handoff:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/<changed-doc>.md
```

6. For operator, harness, or publish docs, also run the relevant targeted unit
   tests or `harness-check --changed-path ...`:

```bash
uv run python -m ptsm.bootstrap harness-check --changed-path docs/<changed-doc>.md
```

`docs-sync` intentionally treats docs-only changes as ok because it only blocks
code changes that omit matching docs. Semantic docs-only drift must be covered by
targeted docs tests and review of the relevant source-of-truth page.
