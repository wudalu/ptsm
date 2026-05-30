# XHS Domain Opportunity Workflow

Date: 2026-05-30

## Current Docs Summary

- `docs/topic-radar.md` defines topic-radar as the bounded research surface. Normal `run-playbook` does not live-scan XHS; it consumes local topic packs and pattern snapshots unless an explicit research command is used.
- `docs/operations/topic-radar-runbook.md` is the operator runbook for periodic XHS sampling and pattern analysis.
- `docs/runtime.md` and `docs/operations.md` describe `guide-post` as the pre-post topic direction helper and `run-playbook` as the generation/publish path.
- OpenClaw wrappers must stay thin: call `guide-post`, display returned directions only, then call `run-playbook`.

## Goal

Add a repeatable, bounded way to compare XHS domain opportunities and tighten the topic-guidance handoff so selected directions are preserved in generated artifacts.

## Tasks

1. Make `collect-xhs-patterns` easier to run in operator scans by supporting a skipped login preflight and per-tool timeout.
   - verify: targeted collect use-case, CLI, and XHS platform tests pass.
   - done_when: output metadata records skipped login and timeout settings, and the CLI forwards both flags.

2. Add `xhs-domain-opportunity` as a search-level opportunity scanner.
   - verify: unit tests cover deterministic domain ranking and CLI dispatch.
   - done_when: the command writes a dated JSON artifact with keyword samples, score formula, domain recommendations, playbook fit, and collection metadata.

3. Add a Markdown operator brief and docs.
   - verify: Markdown test asserts operator headings and hides raw feed ids/tokens; docs-sync passes for touched code/docs.
   - done_when: operators can run the command from the topic-radar runbook and read the generated brief without exposing raw source identifiers.

4. Preserve `guide-post` direction identity through generation.
   - verify: run-playbook unit and CLI tests pass; OpenClaw wrapper doc tests pass.
   - done_when: `run-playbook --topic-direction-id` writes `topic_selection.topic_direction_id` into response and artifact metadata.

5. Final verification.
   - verify: `git diff --check`, targeted tests, docs tests, non-e2e pytest, docs-sync, and harness-check.
   - done_when: branch is green and ready to merge after the main worktree's pre-existing dirty changes are reconciled.

6. Add a thin Codex/OpenClaw wrapper skill for the domain opportunity scan.
   - verify: docs tests assert the wrapper calls `xhs-domain-opportunity`, reads JSON/Markdown outputs, preserves thin-wrapper boundaries, and routes next actions by recommendation type.
   - done_when: `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md` exists, source-of-truth docs mention it, and the skill does not duplicate scan/scoring/publish logic.
