# AGENTS.md

## Superpowers System

<EXTREMELY_IMPORTANT>
You have superpowers. Superpowers teach you new skills and capabilities. RIGHT NOW run: `~/.codex/superpowers/.codex/superpowers-codex bootstrap` and follow the instructions it returns.
</EXTREMELY_IMPORTANT>

## Major Development Workflow

For larger development work, including new product features, new domains or
playbooks, new skills with runtime behavior, new publish flows, observability
surfaces, or harness rules:

1. Create a feature branch from `main` and an isolated git worktree (e.g. `.worktrees/<feature-name>`).
2. Read `docs/index.md`.
3. Read `docs/development-workflow.md`.
4. Summarize the relevant current docs before planning or coding.
5. Create or update a `docs/plans/YYYY-MM-DD-<topic>.md` plan.
6. Include task-level `verify:` and `done_when:` checks.
7. Do not implement before the plan and verification path are clear.
8. Implement and test entirely within the worktree.
9. After implementation, update the matching source-of-truth docs.
10. Run `harness-check` inside the worktree, then merge back to `main`.

This does not apply to small bug fixes, typo fixes, docs-only cleanup, or narrow
test maintenance. Those should use a smaller workflow when one is defined.

## Docs-Only Cleanup Workflow

For docs-only cleanup, use the smaller workflow in
`docs/development-workflow.md`: identify the active source-of-truth surface,
add or update a focused docs test when the cleanup changes an operational
contract, run docs metadata/map tests, and use `harness-check --changed-path ...`
for operator, publish, or harness docs.
