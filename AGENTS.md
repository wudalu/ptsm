# AGENTS.md

## Superpowers System

<EXTREMELY_IMPORTANT>
You have superpowers. Superpowers teach you new skills and capabilities. RIGHT NOW run: `~/.codex/superpowers/.codex/superpowers-codex bootstrap` and follow the instructions it returns.
</EXTREMELY_IMPORTANT>

## Major Development Workflow

For larger development work, including new product features, new domains or
playbooks, new skills with runtime behavior, new publish flows, observability
surfaces, or harness rules:

1. Read `docs/index.md`.
2. Read `docs/development-workflow.md`.
3. Summarize the relevant current docs before planning or coding.
4. Create or update a `docs/plans/YYYY-MM-DD-<topic>.md` plan.
5. Include task-level `verify:` and `done_when:` checks.
6. Do not implement before the plan and verification path are clear.

This does not apply to small bug fixes, typo fixes, docs-only cleanup, or narrow
test maintenance. Those should use a smaller workflow when one is defined.
