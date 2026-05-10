---
title: topic-radar integration into posting flow
status: in-progress
---

# topic-radar integration into posting flow

## Goal

Wire `--fresh-topic-research` flag on `run-fengkuang` and `run-playbook` so that topic-radar scans hot topics, presents them interactively for user selection, then feeds the chosen topic context into the posting workflow.

## Scope

- `run_playbook.py`: add `_run_topic_radar_scan()` and `_interactive_topic_selection()` helpers
- `run_playbook.py`: inject selected topic into workflow state
- `main.py`: make `--scene` optional when `--fresh-topic-research` is set
- topic-radar remains an independent package, called programmatically

## Non-goals

- No changes to topic-radar internals
- No changes to the LangGraph runtime nodes
- No new CLI commands

## Tech stack

topic-radar is called as an async function (not subprocess). The selection is a synchronous terminal prompt using `input()`.

### Task 1: Wire `_run_topic_radar_scan()`

File: `src/ptsm/application/use_cases/run_playbook.py`

Add a sync wrapper that runs `topic_radar.cli._scan` programmatically to produce a `TopicScanResult`. Import topic-radar modules directly.

verify:
```bash
cd .worktrees/feat-topic-radar-integration && uv run python -c "
from ptsm.application.use_cases.run_playbook import _run_topic_radar_scan
# dry-run test
"
```

### Task 2: Add `_interactive_topic_selection()`

File: `src/ptsm/application/use_cases/run_playbook.py`

Present discovered verticals and recommended angles as a numbered menu, accept user input, return selected vertical + angle + scan_summary.

verify:
- unit test: mock input, verify selection parsing

### Task 3: Integrate into run_playbook flow

File: `src/ptsm/application/use_cases/run_playbook.py`

When `fresh_topic_research=True`:
1. Call `_run_topic_radar_scan()` (with platform from account)
2. Call `_interactive_topic_selection()` to let user pick
3. Build enriched scene from selection
4. Override `request.scene` in workflow input

verify:
```bash
uv run pytest -q tests/unit/ -k "topic_radar"
```

### Task 4: Make --scene optional with --fresh-topic-research

File: `src/ptsm/interfaces/cli/main.py`

When `--fresh-topic-research` is set, `--scene` is not required. Add argparse-level validation.

verify:
```bash
uv run pytest -q tests/unit/ -k "cli"
```

### Task 5: Update docs

- Update `docs/topic-radar.md` with integration details
- Update `docs/operations.md` with new workflow
- Update `docs/harness-engineering.md` last_verified

done_when:
- `uv run pytest -q` passes
- `uv run python -m ptsm.bootstrap harness-check` passes
- docs updated with integration details
