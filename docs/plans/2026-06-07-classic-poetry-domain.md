# Classic Poetry Quote Domain Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Su Shi-only Xiaohongshu poetry vertical with a broader 古诗词金句领域 that drafts posts from classic ancient-poetry quotes and keeps Su Shi as one optional sub-direction, not the hard requirement.

**Architecture:** Keep this as a playbook/account/skill/topic-guidance asset change, not a new runtime branch. Rename the current operator-facing poetry vertical from `sushi_poetry_daily_post` / `acct-sushi-local` to `classic_poetry_quote_post` / `acct-classic-poetry-local`, update the deterministic drafting helper and prompt requirements to support classic quote posts, and update source-of-truth docs plus OpenClaw wrapper guidance.

**Tech Stack:** Python 3.12, pytest, YAML/Markdown playbook assets, PTSM topic-guidance pack, deterministic drafting backend, docs-sync and harness-check.

## Current Docs Summary

- `docs/architecture.md` says domain behavior belongs in playbook, skill, account, topic-guidance, evaluation, and deterministic-helper assets; avoid domain-specific runtime orchestration branches.
- `docs/runtime.md` says `guide-post` is read-only and injects confirmed `topic_direction_id` payloads into `run-playbook`; deterministic drafting exists only to prove dry-run contracts locally.
- `docs/playbooks.md` says XHS playbooks share title/body contracts and playbook-local `evaluation.yaml`; the current poetry vertical is still Su Shi-specific.
- `docs/skills.md` says the poetry skills currently require Su Shi and `#苏轼`; these must become classic-poetry quote mechanics.
- `docs/harness-engineering.md` requires new/changed domain work to update the full doc surface, with tests for guide-post, deterministic dry-run, contracts, docs, and harness.
- `docs/operations.md` and `docs/operations/local-runbook.md` expose stable operator commands and must show the new account/playbook ids.

## Requirements

- Current operator-facing poetry domain is `古诗词金句`, not `苏轼诗词赏析`.
- Posts are built around a named or recognizable classic quote, such as 李白《行路难》“长风破浪会有时”, 李清照词句, 王维山水句, 杜甫现实感, 月亮/乡愁句, or 苏轼作为一个可选分支.
- Generated final content must not require `#苏轼` or body text `苏轼` unless the scene/direction specifically chooses Su Shi.
- Generated final content must include `#古诗词` and a quote-driven body with save/comment mechanics.
- `guide-post` for classic-poetry scenes returns relevant quote directions and no longer defaults generic poetry scenes to Su Shi/Huangzhou/Huimin.
- OpenClaw topic-guide maps 古诗词 / 诗词金句 / 经典诗句 / 苏轼 to the new playbook, with Su Shi described as a sub-direction.
- Complete doc surface is updated: `architecture.md`, `runtime.md`, `playbooks.md`, `skills.md`, `harness-engineering.md`, `docs/operations.md`, and affected `docs/operations/` runbooks.

### Task 1: Add Failing Tests For Classic Poetry Identity

**Files:**
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`
- Modify: `tests/unit/test_bootstrap.py`
- Modify: `tests/integration/test_playbook_selection.py`
- Modify: `tests/integration/test_multi_account_publisher_resolution.py`

**Step 1: Write the failing tests**

Update expectations from `sushi_poetry_daily_post`, `acct-sushi-local`, `苏轼诗词赏析`, `#苏轼`, `sushi_poetry_style`, and `xhs_poetry_hashtagging` to `classic_poetry_quote_post`, `acct-classic-poetry-local`, `古诗词金句`, `#古诗词`, `classic_poetry_style`, and `xhs_classic_poetry_hashtagging`.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py tests/integration/test_playbook_selection.py tests/integration/test_multi_account_publisher_resolution.py -q
```

Expected: FAIL because repo assets still use the Su Shi ids and hard `#苏轼` contract.

**done_when:** These tests fail for missing/old ids or Su Shi-only expectations before implementation.

### Task 2: Add Failing Tests For Topic Guidance And Drafting

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/e2e/test_sushi_poetry_publish_dry_run.py`
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`

**Step 1: Write the failing tests**

Add or update tests proving:
- `guide-post --playbook-id classic_poetry_quote_post --account-id acct-classic-poetry-local` for a 李白/长风破浪 scene returns a classic quote lane and `classic_tang_resilience_quote`.
- A generic `古诗词金句` scene surfaces multiple curated families and does not match a Su Shi/Huimin default.
- deterministic backend can draft a classic quote post with `#古诗词`, quote/save/comment mechanics, and no forced `#苏轼`.
- repo asset dry-run completes for `classic_poetry_quote_post`.
- body scene signal markers cover classic-poetry quote signals rather than Su Shi-only signals.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_sushi_poetry_publish_dry_run.py tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

Expected: FAIL because topic packs and deterministic drafts still emit Su Shi-only content.

**done_when:** The tests fail specifically because classic-poetry ids/directions/drafts are not implemented yet.

### Task 3: Replace Poetry Playbook, Account, Skills, Contracts

**Files:**
- Move/modify: `src/ptsm/accounts/definitions/acct-sushi-local.yaml` -> `src/ptsm/accounts/definitions/acct-classic-poetry-local.yaml`
- Move/modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/` -> `src/ptsm/playbooks/definitions/classic_poetry_quote_post/`
- Move/modify: `src/ptsm/skills/builtin/sushi_poetry_style/` -> `src/ptsm/skills/builtin/classic_poetry_style/`
- Move/modify: `src/ptsm/skills/builtin/xhs_poetry_hashtagging/` -> `src/ptsm/skills/builtin/xhs_classic_poetry_hashtagging/`

**Step 1: Implement minimal asset replacement**

Change YAML/Markdown assets to:
- domain `古诗词金句`
- required hashtag `#古诗词`
- reflection `must_include_phrase: 这一句`
- skill rules requiring one classic quote, author/work when known, one saveable reading, comment prompt, and no fabricated source.

**Step 2: Verify GREEN for Task 1**

Run the Task 1 pytest command.

Expected: PASS.

**done_when:** Registries, selector, loader, account routing, CLI parsing, and contracts all expose the new classic-poetry identity.

### Task 4: Implement Topic Guidance And Deterministic Drafting

**Files:**
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `src/ptsm/domain/topic_guidance.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/skills/runtime_context.py`

**Step 1: Implement minimal behavior**

Replace `SUSHI_POETRY_PACK` with a `CLASSIC_POETRY_PACK` containing curated lanes/directions for 唐诗低谷金句、宋词情绪安放、月亮乡愁、山水松弛、女性词人清醒、节气四季, plus a Su Shi/定风波 optional direction. Add classic-poetry keywords to open-scene scoring and image recommendations. Update deterministic draft detection and prompt requirements from Su Shi-only to classic quote context.

**Step 2: Verify GREEN for Task 2**

Run the Task 2 pytest command.

Expected: PASS.

**done_when:** Guide-post and dry-run behavior prove classic quote posting works without forcing Su Shi.

### Task 5: Update Source-Of-Truth Docs And OpenClaw Wrapper

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify tests if needed under `tests/unit/docs/`

**Step 1: Update docs**

Replace current active Su Shi-only statements with the classic-poetry quote domain, new ids, new operator commands, guide-post examples, and explicit note that Su Shi remains only one direction inside the broader domain.

**Step 2: Verify docs**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py --changed-path src/ptsm/infrastructure/llm/contextual_drafts.py --changed-path src/ptsm/playbooks/definitions/classic_poetry_quote_post/playbook.yaml --changed-path src/ptsm/skills/builtin/classic_poetry_style/SKILL.md --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md
```

Expected: PASS.

**done_when:** Active docs and wrapper no longer describe the current poetry domain as Su Shi-only.

### Task 6: End-To-End Verification And Harness Gate

**Files:**
- No new files unless verification reveals a targeted test gap.

**Step 1: Run focused command smoke**

Run:

```bash
uv run python -m ptsm.bootstrap guide-post --playbook-id classic_poetry_quote_post --account-id acct-classic-poetry-local --scene "读到李白长风破浪会有时，想写给低谷里的自己" --non-interactive --format json
uv run python -m ptsm.bootstrap run-playbook --scene "读到李白长风破浪会有时，想写给低谷里的自己" --account-id acct-classic-poetry-local --playbook-id classic_poetry_quote_post --publish-mode dry-run
```

Expected: both complete; guide-post returns classic quote directions; dry-run final content includes `#古诗词`, a classic quote, save/comment mechanics, and no forced `#苏轼`.

**Step 2: Run test and harness gates**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
uv run pytest -q tests/e2e/test_sushi_poetry_publish_dry_run.py tests/e2e/test_xhs_title_body_quality_contracts.py
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: PASS.

**done_when:** Targeted tests, full non-e2e pytest, relevant e2e tests, doctor, docs-sync, and harness-check pass in the worktree.
