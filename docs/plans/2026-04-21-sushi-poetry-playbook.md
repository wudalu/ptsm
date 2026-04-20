# Su Shi Poetry Playbook Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a second Xiaohongshu publish type for Su Shi poetry appreciation that can be developed and verified through the same harnessed workflow as the existing `fengkuang` slice.

**Architecture:** First generalize the current single-slice entrypoints so `ptsm` can run arbitrary playbooks without cloning the whole `run-fengkuang` stack per feature. Then add one narrow `sushi_poetry_daily_post` vertical slice: account profile, playbook assets, builtin skills, deterministic/deepseek drafting behavior, smoke coverage, and operator docs. Keep `run-fengkuang` as a compatibility command, but make future playbooks land on the generic path.

**Tech Stack:** Python 3.12, argparse, pydantic, pytest, LangGraph, local YAML/Markdown playbook assets, filesystem artifacts, existing harness gates (`docs-sync`, `harness-check`, `run-plan`)

## Recommended Execution

Use a dedicated worktree and let the harness verify after every task:

```bash
git worktree add ../ptsm-sushi-poetry -b feat/sushi-poetry-playbook
cd ../ptsm-sushi-poetry
uv run python -m ptsm.bootstrap install-git-hooks --base-ref origin/main
uv run python -m ptsm.bootstrap run-plan \
  --plan docs/plans/2026-04-21-sushi-poetry-playbook.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m ptsm.bootstrap doctor"
```

### Task 1: Add a Generic `run-playbook` CLI Entry Point

```yaml
verify:
  - uv run pytest tests/unit/test_bootstrap.py tests/unit/interfaces/cli/test_main.py -q
done_when:
  - the CLI exposes a generic run-playbook command with the same publish-related flags as run-fengkuang
  - run-fengkuang remains a thin compatibility wrapper around the generic use case
  - rerun instructions can preserve an explicit playbook_id when the generic command is used
```

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `tests/unit/test_bootstrap.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write the failing parser and dispatch tests**

Add coverage for:
- `ptsm run-playbook --scene ... --account-id ...`
- `--playbook-id`, `--publish-mode`, `--publish-image-path`, `--auto-generate-image`, `--publish-visibility`, `--open-browser-if-needed`, `--wait-for-publish-status`, and `--login-qrcode-output`
- dispatching `PlaybookRequest` through the generic path
- preserving `run-fengkuang` behavior unchanged

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/test_bootstrap.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: FAIL because the parser does not yet expose `run-playbook`.

**Step 3: Implement the minimal CLI**

- Import `PlaybookRequest` and `run_playbook(...)`.
- Add `run-playbook` to `build_parser()`.
- Dispatch it in `main(...)` and print the JSON result just like the existing run commands.
- Keep `run-fengkuang` mapped to `FengkuangRequest` so old commands and tests still work.
- Update `_build_rerun_command(...)` so a generic rerun includes `--playbook-id <id>` when the original request explicitly used one.

**Step 4: Re-run the targeted tests**

Run:

```bash
uv run pytest tests/unit/test_bootstrap.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptsm/interfaces/cli/main.py src/ptsm/application/use_cases/run_playbook.py tests/unit/test_bootstrap.py tests/unit/interfaces/cli/test_main.py
git commit -m "feat: add generic run-playbook cli"
```

### Task 2: Generalize the Runtime and Drafting Backend Beyond Fengkuang

```yaml
verify:
  - uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py tests/integration/test_playbook_selection.py -q
done_when:
  - run_playbook chooses a runtime from the selected playbook instead of only supporting fengkuang_daily_post
  - the deterministic and deepseek drafting backends no longer hardcode fengkuang-only wording
  - existing fengkuang regression coverage stays green
```

**Files:**
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `tests/integration/test_fengkuang_workflow.py`
- Modify: `tests/integration/test_playbook_selection.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Write the failing tests**

Add tests that prove:
- a non-fengkuang playbook can build and execute through the generic `run_playbook(...)` path
- `build_fengkuang_workflow()` still works by delegating to a generic builder instead of owning the only supported domain
- the deterministic backend can produce a non-fengkuang draft when planner/skill context asks for Su Shi poetry appreciation
- the deepseek path uses a generic system prompt and hard requirements derived from playbook context instead of the literal phrase “发疯文学文案”

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py tests/integration/test_playbook_selection.py -q
```

Expected: FAIL because the runtime and drafting layer are still fengkuang-specific.

**Step 3: Implement the minimal generalization**

- Add a generic workflow builder in `runtime.py`, for example `build_playbook_workflow(domain=..., ...)`, and keep `build_fengkuang_workflow()` as a thin wrapper over it.
- Update `run_playbook(...)` so runtime selection uses the chosen playbook definition rather than raising for every id except `fengkuang_daily_post`.
- Make the system prompt in `factory.py` generic to Xiaohongshu drafting.
- Keep the deterministic backend offline-safe, but branch from playbook context so it can still deterministically emit:
  - fengkuang-style copy for `fengkuang_daily_post`
  - Su Shi appreciation copy for `sushi_poetry_daily_post`
- Preserve the existing fengkuang assertions around `#发疯文学` and “也算”.

**Step 4: Re-run the targeted tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py tests/integration/test_playbook_selection.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptsm/agent_runtime/runtime.py src/ptsm/application/use_cases/run_playbook.py src/ptsm/infrastructure/llm/factory.py tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py tests/integration/test_playbook_selection.py tests/unit/infrastructure/llm/test_factory.py
git commit -m "feat: generalize playbook runtime and drafting"
```

### Task 3: Add the `sushi_poetry_daily_post` Vertical Slice

```yaml
verify:
  - uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py -q
done_when:
  - PlaybookRegistry can load sushi_poetry_daily_post
  - acct-sushi-local can default-select the new playbook on xiaohongshu
  - the skill selector exposes only the Su Shi scoped skills for this playbook
```

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-sushi-local.yaml`
- Create: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/reflection.md`
- Create: `src/ptsm/skills/builtin/sushi_poetry_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_poetry_hashtagging/SKILL.md`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`
- Modify: `tests/integration/test_playbook_selection.py`

**Step 1: Write the failing registry, loader, and selector tests**

Cover:
- a second account profile `acct-sushi-local`
- registry lookup by id and default selection by account domain
- loader access to the new planner/reflection markdown
- skill discovery and request-scoped selection for the new playbook

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py -q
```

Expected: FAIL because the new account, playbook, and skills do not exist yet.

**Step 3: Add the minimal playbook slice**

Create `acct-sushi-local.yaml` with:

```yaml
account_id: acct-sushi-local
nickname: 苏轼诗词赏析实验号
platform: xiaohongshu
domain: 苏轼诗词赏析
publish_mode: dry-run
```

Create `playbook.yaml` with a narrow reflection contract that the current reflector can already enforce:

```yaml
playbook_id: sushi_poetry_daily_post
version: 1
domain: 苏轼诗词赏析
platforms:
  - xiaohongshu
required_skills:
  - sushi_poetry_style
  - xhs_poetry_hashtagging
optional_skills: []
reflection:
  must_include_phrase: 苏轼
  required_hashtag: "#苏轼"
```

Keep the markdown assets short and operational:
- `planner.md`: require one clear life scene, one Su Shi line or image, one appreciation angle, one Xiaohongshu-friendly title/body/hashtags structure
- `reflection.md`: require the body to mention `苏轼`, require hashtag `#苏轼`, and reject academic or overly essay-like tone

Create two builtin skills:
- `sushi_poetry_style`: guide the draft toward approachable赏析 instead of stiff论文语气
- `xhs_poetry_hashtagging`: require `#苏轼` plus 2-3 scene or阅读标签

**Step 4: Re-run the targeted tests**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptsm/accounts/definitions/acct-sushi-local.yaml src/ptsm/playbooks/definitions/sushi_poetry_daily_post src/ptsm/skills/builtin/sushi_poetry_style/SKILL.md src/ptsm/skills/builtin/xhs_poetry_hashtagging/SKILL.md tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/integration/test_playbook_selection.py
git commit -m "feat: add sushi poetry playbook slice"
```

### Task 4: Add CLI Smoke Coverage and Operator Docs

```yaml
verify:
  - uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_sushi_poetry_publish_dry_run.py -q
done_when:
  - there is one dry-run smoke test for the new playbook through the CLI
  - operator docs explain how to run the generic playbook command and the new account
  - source-of-truth docs cover runtime, playbook, skill, and operations changes
```

**Files:**
- Create: `tests/e2e/test_sushi_poetry_publish_dry_run.py`
- Modify: `docs/playbooks.md`
- Modify: `docs/runtime.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `tests/unit/interfaces/cli/test_main.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write the failing smoke and doc-adjacent tests**

Add one CLI smoke that runs the generic entrypoint against `acct-sushi-local` and asserts:
- `playbook_id == "sushi_poetry_daily_post"`
- the result is `completed`
- the generated tags include `#苏轼`

If the existing unit tests are a better place to assert request plumbing, add those first and keep the e2e smoke very small.

**Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_sushi_poetry_publish_dry_run.py -q
```

Expected: FAIL because there is not yet a Su Shi smoke path.

**Step 3: Update the operator docs**

Sync the source-of-truth docs that the new code touches:
- `docs/playbooks.md`: note that the repo now has more than one playbook and that default selection depends on account domain
- `docs/runtime.md`: note that the generic runtime builder can execute more than the fengkuang slice
- `docs/skills.md`: mention scoped builtin skills per playbook
- `docs/operations.md`: add `run-playbook` to stable commands and note when to use it instead of `run-fengkuang`
- `docs/operations/local-runbook.md`: add one Su Shi dry-run example

Use this as the local smoke command:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "加班后读到《定风波》，突然想把今天的狼狈也写成一段赏析" \
  --account-id acct-sushi-local
```

**Step 4: Re-run the targeted tests**

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_sushi_poetry_publish_dry_run.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tests/e2e/test_sushi_poetry_publish_dry_run.py docs/playbooks.md docs/runtime.md docs/skills.md docs/operations.md docs/operations/local-runbook.md tests/unit/interfaces/cli/test_main.py tests/unit/application/use_cases/test_run_playbook.py
git commit -m "docs: document generic playbook and sushi workflow"
```

### Task 5: Run Final Harness Verification

```yaml
verify:
  - uv run pytest -q
  - uv run python -m ptsm.bootstrap doctor
  - uv run python -m ptsm.bootstrap run-playbook --scene "夜里读到《定风波》，觉得这一天的风雨也可以拿来慢慢赏析" --account-id acct-sushi-local
done_when:
  - full pytest passes
  - doctor stays green enough for local development
  - the new playbook can complete one end-to-end dry-run through the generic CLI
```

**Files:**
- Modify: `docs/plans/2026-04-21-sushi-poetry-playbook.md`

**Step 1: Run the full suite**

Run:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
```

Expected: PASS.

**Step 2: Run the final dry-run smoke**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "夜里读到《定风波》，觉得这一天的风雨也可以拿来慢慢赏析" \
  --account-id acct-sushi-local
```

Record the artifact path and confirm the output is the Su Shi playbook, not fengkuang.

**Step 3: Run the docs gate on the touched paths before the final commit if there are uncommitted changes**

Run:

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/interfaces/cli/main.py \
  --changed-path src/ptsm/application/use_cases/run_playbook.py \
  --changed-path src/ptsm/agent_runtime/runtime.py \
  --changed-path src/ptsm/infrastructure/llm/factory.py \
  --changed-path src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml \
  --changed-path src/ptsm/skills/builtin/sushi_poetry_style/SKILL.md \
  --changed-path src/ptsm/skills/builtin/xhs_poetry_hashtagging/SKILL.md \
  --changed-path docs/playbooks.md \
  --changed-path docs/runtime.md \
  --changed-path docs/skills.md \
  --changed-path docs/operations.md \
  --changed-path docs/operations/local-runbook.md
```

Expected: PASS.

**Step 4: Run the unified harness gate against committed work before opening the PR**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

If local harness artifacts are noisy and you need the exact CI behavior too, also run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

**Step 5: Commit**

```bash
git add .
git commit -m "feat: add sushi poetry playbook workflow"
```
