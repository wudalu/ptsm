# Codex Plan Runner

`codex-plan-runner` is a small Python wrapper around `codex exec`. It reads a markdown implementation plan, executes tasks one by one, runs verification commands after each task, and persists run state so you can resume later.

It is intentionally generic. You run it from the root of any target project that already has:

- a checked-out codebase
- the `codex` CLI installed and authenticated
- a markdown plan file
- one or more verification commands that prove progress

## What It Does

- Parses markdown plans with `### Task ...` or `### 里程碑 ...` headings
- Supports optional task-level YAML metadata blocks
- Calls `codex exec` for each task
- Adds `--skip-git-repo-check` so Codex can run in non-git project directories
- Runs verification commands after each task
- Writes state files under `.codex-plan-runner/runs/` by default
- Supports `--resume` from a previous state file

## Install

### Run from this source checkout

```bash
uv run --project codex-plan-runner codex-plan-runner --help
```

### Install as a local tool

```bash
uv tool install ./codex-plan-runner
codex-plan-runner --help
```

## Requirements

- Python 3.11+
- `uv`
- `codex` CLI available on `PATH`
- a target project directory you want Codex to modify

## Use It In Any Project

1. `cd` into the target project root.
2. Make sure `codex` works there.
3. Create a plan file.
4. Run `codex-plan-runner`.

Example:

```bash
cd /path/to/your-project
codex-plan-runner \
  --plan docs/plans/feature.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m compileall src"
```

The runner executes from your current working directory. That matters because it passes `-C $(pwd)` to `codex exec`, default state files also live under the current project root, and it automatically adds `--skip-git-repo-check` for non-git directories.

## Plan Format

At minimum, tasks are discovered from headings like:

```md
### Task 1: Add parser

- create parser module

### Task 2: Add runner

- create execution loop
```

You can also attach a task-level YAML block immediately under a task heading:

````md
### Task 1: Add parser

```yaml
prompt: |
  Implement the parser conservatively.
verify:
  - uv run pytest tests/test_parser.py -q
done_when:
  - parser reads task metadata
max_attempts: 2
```

- Parse headings
- Parse metadata
````

Supported metadata keys:

- `prompt`: extra instructions for Codex
- `verify`: task-specific verification commands
- `done_when`: completion checklist injected into the prompt
- `max_attempts`: task-specific retry limit

If a task does not provide `verify`, the CLI-level `--verify-command` values are used.

## Commands

### Dry-run

Use this first to confirm task parsing and state file generation:

```bash
codex-plan-runner \
  --plan docs/plans/feature.md \
  --verify-command "uv run pytest -q" \
  --dry-run
```

### Execute

```bash
codex-plan-runner \
  --plan docs/plans/feature.md \
  --verify-command "uv run pytest -q"
```

### Resume

```bash
codex-plan-runner \
  --plan docs/plans/feature.md \
  --state-path .codex-plan-runner/runs/feature-20260316T000000Z-abcd1234.json \
  --resume \
  --verify-command "uv run pytest -q"
```

## Options

- `--plan`: markdown plan file
- `--verify-command`: repeatable verification command
- `--max-attempts`: global retry limit
- `--state-path`: explicit JSON state file path
- `--resume`: continue from an existing state file
- `--dry-run`: parse and emit state without calling Codex
- `--codex-bin`: alternate Codex binary name/path
- `--sandbox`: passed through to `codex exec`
- `--full-auto` / `--no-full-auto`: toggle Codex full-auto mode

## State Files

If you do not pass `--state-path`, the runner creates one automatically:

```text
.codex-plan-runner/runs/<plan-stem>-<timestamp>-<run-id>.json
```

State files record:

- plan path
- overall run status
- task status
- attempts
- last failure text
- verification records

## Limits

- It does not automatically split large milestone tasks into smaller steps.
- It trusts your verification commands more than your prose. If your checks are weak, the gate is weak.
- It is not a native Codex hook system. It is an external orchestration layer around `codex exec`.
- It assumes the plan is stable while a run is in progress. If you rewrite task headings, old state files may no longer match.
