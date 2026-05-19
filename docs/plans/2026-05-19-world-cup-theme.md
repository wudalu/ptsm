# World Cup Theme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a World Cup themed Xiaohongshu playbook that can be selected by a local account, activates request-scoped World Cup skills, passes deterministic dry-run checks, and is documented as the eighth PTSM vertical domain.

**Architecture:** Implement the theme mostly as additive assets: one account YAML, one playbook definition directory, and three builtin skill directories. The only runtime code change is extending the deterministic contextual draft helper so local dry-runs can prove World Cup mechanics without external LLM calls.

**Tech Stack:** Python 3.12, YAML playbook/account/evaluation definitions, Markdown prompt assets, pytest, PTSM generic `run-playbook` CLI, `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`.

## Current Docs Summary

- `AGENTS.md` / `CLAUDE.md`: larger feature work must start from `main`, use an isolated `.worktrees/<feature>` worktree, read current docs, write a plan under `docs/plans/`, define `verify:` and `done_when:`, update source-of-truth docs, run `harness-check`, then merge back.
- `docs/development-workflow.md`: new domains/playbooks are major work. Prefer additive files over runtime edits; if code must change, keep the change small and covered by tests. Verification must include targeted tests plus an end-to-end CLI dry-run.
- `docs/harness-engineering.md`: repository docs are the system of record. The harness gate combines docs-sync, drift checks, and pytest, so docs updates must accompany code/assets.
- `docs/playbooks.md`: each playbook directory needs `playbook.yaml`, `planner.md`, `persona.md`, `reflection.md`, and may include `evaluation.yaml`. Routing is account domain + platform unless `playbook_id` is explicit.
- `docs/skills.md`: builtin skills are discovered from `src/ptsm/skills/builtin/*/SKILL.md` front matter and selected by domain/platform/playbook tags.
- `docs/architecture.md` / `docs/runtime.md`: domains should register through account + playbook + skills. Deterministic offline drafts live in `src/ptsm/infrastructure/llm/contextual_drafts.py` for domain-specific harness checks.

## Scope

- Add domain: `世界杯主题`
- Add account: `acct-world-cup-local`
- Add playbook: `world_cup_daily_post`
- Add skills: `world_cup_style`, `xhs_world_cup_visuals`, `xhs_world_cup_hashtagging`
- Add deterministic dry-run support for match-preview / post-match / fan-culture scenes.

## Non-Goals

- No real Xiaohongshu publish.
- No live sports data fetches or scores. Content must make it clear when a score is operator-provided scene context.
- No betting, gambling, guaranteed prediction, injury diagnosis, or impersonation of official FIFA/media sources.

### Task 1: Write Registration And Contract Tests

**Files:**
- Modify: `tests/unit/accounts/test_account_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/playbooks/test_playbook_loader.py`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Steps:**
1. Add tests expecting `acct-world-cup-local` to load with domain `世界杯主题`.
2. Add tests expecting `world_cup_daily_post` to load and select for the account with required skills:
   `xhs_trend_scan`, `topic_research`, `xhs_image_strategy`, `world_cup_style`, `xhs_world_cup_visuals`, `xhs_world_cup_hashtagging`.
3. Add loader tests expecting the playbook prompts to contain `世界杯`, `赛事情绪`, `看球清单`, and `#世界杯`.
4. Add skill discovery/selector tests expecting the three skills to be tagged to `世界杯主题`, `xiaohongshu`, and `world_cup_daily_post`.
5. Add evaluation contract tests expecting required hashtags, safe body mechanics, forbidden gambling/prediction/score-fabrication terms, and required content-quality judge.

**verify:** `uv run pytest -q tests/unit/accounts/test_account_registry.py tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/evaluations/test_playbook_contracts.py`

**done_when:** Tests fail because the World Cup account/playbook/skills/evaluation assets do not exist yet, not because of syntax errors.

### Task 2: Add Additive Account, Playbook, Skill, And Evaluation Assets

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-world-cup-local.yaml`
- Create: `src/ptsm/playbooks/definitions/world_cup_daily_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/world_cup_daily_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/world_cup_daily_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/world_cup_daily_post/reflection.md`
- Create: `src/ptsm/playbooks/definitions/world_cup_daily_post/evaluation.yaml`
- Create: `src/ptsm/skills/builtin/world_cup_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_world_cup_visuals/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_world_cup_hashtagging/SKILL.md`

**Implementation notes:**
- `playbook.yaml` requires `#世界杯`, match context, viewing note/checklist/comment mechanics, and forbids betting and fake live-score claims.
- `evaluation.yaml` executor constraints should require body terms such as `赛前`, `看点`, `看球`, `评论区`, `清单`, and block `稳赚`, `下注`, `盘口`, `预测比分`, `内部消息`, `官方消息`, `变体要求`, `comment_chain`, `save_tool`, `identity_conflict`.
- Skills should encode: fan-first tone, tactical detail in plain language, no gambling advice, no invented scores or official sourcing, and XHS-native cover/carousel forms.

**verify:** Same targeted unit command from Task 1.

**done_when:** All targeted registration, selector, loader, and evaluation contract tests pass.

### Task 3: Add Deterministic Draft Tests

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Create: `tests/e2e/test_world_cup_publish_dry_run.py`

**Steps:**
1. Add a unit test calling `DeterministicDraftBackend().draft(...)` with World Cup prompt context and asserting:
   `#世界杯` hashtag, match context, fan note/checklist, comment prompt, no gambling terms, no fake official live score claim.
2. Add e2e CLI dry-run test using:
   `run-playbook --scene "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点" --account-id acct-world-cup-local --playbook-id world_cup_daily_post --thread-id thread-world-cup-cli`
3. Assert completed status, account/playbook ids, `#世界杯`, and required mechanics in final content.

**verify:** `uv run pytest -q tests/unit/infrastructure/llm/test_factory.py -k world_cup tests/e2e/test_world_cup_publish_dry_run.py`

**done_when:** Tests fail because deterministic World Cup drafting is missing, not because the CLI cannot route the new playbook.

### Task 4: Implement Deterministic World Cup Draft Support

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`

**Implementation notes:**
- Add `_is_world_cup_context(scene, extra_context)` using strong markers from the new playbook/skills and common scene words like `世界杯`, `决赛`, `小组赛`, `淘汰赛`, `看球`.
- Add `_build_world_cup_draft(scene, feedback)` with at least three scene branches:
  match preview, post-match replay, and fan viewing checklist.
- Return title, image_text, body, and hashtags. Keep the copy deterministic and safe: no betting, no invented score, no official-source claim.

**verify:** `uv run pytest -q tests/unit/infrastructure/llm/test_factory.py -k world_cup tests/e2e/test_world_cup_publish_dry_run.py`

**done_when:** Targeted deterministic unit and e2e dry-run tests pass.

### Task 5: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/xhs-topics/image-forms-by-domain.md`

**Steps:**
1. Update domain count from seven to eight where applicable.
2. Document `world_cup_daily_post`, `acct-world-cup-local`, and World Cup skill behavior.
3. Mention deterministic World Cup dry-run coverage in runtime/harness docs.
4. Update `last_verified` to `2026-05-19` on docs whose claims were reverified.

**verify:** `uv run pytest -q tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py`

**done_when:** Docs tests pass and docs mention the World Cup domain in the current source-of-truth surfaces.

### Task 6: End-To-End And Harness Verification

**Files:**
- No new files expected.

**Commands:**
- `uv run pytest -q tests/unit/accounts/test_account_registry.py tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/infrastructure/llm/test_factory.py -k "world_cup or World Cup or playbook or skill or contract or account"`
- `uv run pytest -q tests/e2e/test_world_cup_publish_dry_run.py`
- `uv run pytest -q`
- `uv run python -m ptsm.bootstrap run-playbook --scene "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点" --account-id acct-world-cup-local --playbook-id world_cup_daily_post --thread-id thread-world-cup-manual`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`

**done_when:** All commands pass, dry-run response has `status == completed`, and final content contains `#世界杯`, a fan-readable match angle, a save/checklist mechanic, and a comment prompt.

### Task 7: Merge Back To Main

**Files:**
- No source file edits.

**Steps:**
1. Check worktree status.
2. Commit feature work if not already committed.
3. Merge `feat/world-cup-theme` into `main` after harness passes.
4. Preserve unrelated dirty files in the primary checkout.

**verify:** `git status --short --branch` in worktree and main after merge.

**done_when:** `main` contains the World Cup theme commits and unrelated primary-checkout local edits remain untouched.
