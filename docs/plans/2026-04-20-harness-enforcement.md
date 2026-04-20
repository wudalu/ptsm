# 2026-04-20 Harness Enforcement

## Goal

Make the existing harness rules run the same way in day-to-day development and CI so they are harder to bypass by accident.

## Design

- Add one machine entrypoint, `ptsm harness-check`, that composes:
  - `docs-sync`
  - a local `harness-report` with publish preflight explicitly skipped
  - deterministic `uv run pytest -q`
- Add one local installation command, `ptsm install-git-hooks`, that writes a `pre-push` hook to run `harness-check`.
- Add one CI workflow, `.github/workflows/harness.yml`, that runs the same `harness-check` command on pull requests and `main` pushes.
- Keep `docs-sync.yml` as a faster, narrower doc-specific signal, but treat `harness` as the main required branch-protection check.

## Tasks

1. Create `run_harness_check()` and expose `ptsm harness-check`.
   Verify: `uv run pytest tests/unit/application/use_cases/test_harness_check.py tests/unit/test_bootstrap.py -q`

2. Create `install_git_hooks()` and expose `ptsm install-git-hooks`.
   Verify: `uv run pytest tests/unit/application/use_cases/test_install_git_hooks.py tests/unit/test_bootstrap.py -q`

3. Add repository automation and update operator docs.
   Verify: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`

## Acceptance

- Developers can install a local `pre-push` hook with one command.
- CI runs the same harness entrypoint instead of re-encoding the checks ad hoc.
- `harness-check` fails when docs drift, harness drift, or deterministic pytest fails.
- GitHub branch protection can require the `harness` workflow without extra manual scripting.
