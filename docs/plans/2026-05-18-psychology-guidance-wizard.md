# Psychology Guidance Wizard

**Goal:** Add a guided operator flow that helps produce a high-quality
`modern_psychology_post` brief before running the existing Xiaohongshu
playbook.

**Architecture:** Keep content generation inside the existing `run-playbook`
workflow. Add a read-only `guide-post` CLI use case that collects or accepts
topic inputs, maps them to the established psychology lanes, returns a
structured guidance brief, and prints a dry-run `run-playbook` command. Do not
publish, call external providers, or mutate run artifacts from the wizard.

## Current Docs Summary

- `docs/index.md` says feature work starts from active source-of-truth docs, and
  code/runtime changes must stay in sync with those docs.
- `docs/development-workflow.md` requires larger product/runtime changes to use
  a feature branch and isolated worktree, define a plan under `docs/plans`, use
  task-level `verify:` and `done_when:` checks, update source-of-truth docs, and
  finish with harness validation before merging back to `main`.
- `docs/operations.md` is the active source-of-truth for stable CLI commands and
  maps `src/ptsm/interfaces/cli/main.py` plus application use cases to operator
  docs.
- `docs/playbooks.md` defines `modern_psychology_post` as a psychology
  education playbook with first-person micro-scene, one mechanism, non-diagnostic
  reframe, saveable tool, example-style comment prompt, and professional-help
  boundary.
- `docs/skills.md` says `psychology_style`, `psychology_safety`, and
  `xhs_psychology_hashtagging` define the psychology surface, with six lanes and
  low-density `iphone_notes` / `save_tool` image defaults.

## Task 1: Add RED Tests For The Guidance Brief

- Create: `tests/unit/application/use_cases/test_guide_post.py`
- Assert a partially supplied psychology request resolves lane defaults,
  produces a concrete brief, includes safety notes, and builds a dry-run
  `run-playbook` command for `acct-psychology-local`.
- Assert unknown playbooks are rejected so the wizard does not silently generate
  guidance for unsupported domains.

**verify:** `uv run pytest tests/unit/application/use_cases/test_guide_post.py -q`

**done_when:** Tests fail because the guide-post use case does not exist yet.

## Task 2: Add RED Tests For The CLI Wizard

- Modify: `tests/unit/interfaces/cli/test_main.py`
- Assert `guide-post` accepts non-interactive flags and prints JSON.
- Assert missing values can be collected through prompts using mocked `input()`.

**verify:** `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

**done_when:** Tests fail because the parser and dispatch path do not expose
`guide-post`.

## Task 3: Implement The Guidance Use Case And CLI

- Create: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Support `--playbook-id`, `--account-id`, `--lane`, `--scene`,
  `--mechanism`, `--save-tool`, `--image-style`, `--comment-prompt`,
  `--non-interactive`, and `--format json|markdown`.
- In interactive mode, prompt only for missing core fields and accept numbered
  lane choices.
- Output a stable payload with `brief`, `quality_checklist`, `safety_notes`,
  `recommended_scene`, and `run_playbook_command`.

**verify:** `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q`

**done_when:** The CLI and use case tests pass without touching publish or LLM
runtime code.

## Task 4: Update Operator Docs

- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Mention the psychology wizard as a pre-run helper and keep `run-playbook` as
  the generation path.

**verify:** `uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/interfaces/cli/main.py --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md`

**done_when:** Source-of-truth docs describe the new command and docs-sync
reports `status=ok`.

## Task 5: Final Validation And Merge

- Run targeted tests, bootstrap parser coverage, docs metadata/map tests, a
  smoke invocation of `guide-post`, and strict harness validation in the
  worktree.
- Commit the feature branch, merge it back to `main`, then run a minimal sanity
  check on `main`.

**verify:** `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`

**done_when:** The feature is committed, merged into local `main`, and the
verification results are recorded for handoff.
