# Reddit Curation Domain Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a Xiaohongshu playbook that can turn current high-engagement English Reddit discussions into Chinese posts selected for Chinese-reader appeal.

**Architecture:** Add a read-only Reddit runtime context builder and client, then wire it as a scoped builtin skill for a new `reddit_curation_daily_post` playbook. The domain stays inside the existing playbook + skill + account registry path; dry-runs remain deterministic when Reddit credentials are missing, while live runs use Reddit app-only OAuth through configured environment variables.

**Tech Stack:** Python 3.12, `httpx`, Pydantic settings, existing PTSM playbooks/skills/evaluation/runtime graph, pytest.

## Current Docs Summary

- `docs/development-workflow.md` requires a feature branch/worktree, current docs first, a plan with `verify:` and `done_when:`, task-level checks, full source-of-truth docs updates for every new domain, and final `harness-check` inside the worktree.
- `docs/architecture.md` says new domains should be additive through playbook/account/skill/evaluation assets and should not add runtime domain branches unless a shared extension point is missing.
- `docs/runtime.md` says dynamic research enters drafting through `runtime_skill_contents`, and deterministic fallback drafts are used for offline dry-run and harness evidence.
- `docs/playbooks.md` says each real XHS playbook needs `playbook.yaml`, `planner.md`, `persona.md`, `reflection.md`, and a playbook-local `evaluation.yaml`.
- `docs/skills.md` says builtin skills are selected by tags and dynamic resources should be traceable in `runtime_skill_details`.
- `docs/harness-engineering.md` requires the new-domain full docs surface and deterministic local verification.
- `docs/operations.md` and `docs/operations/local-runbook.md` are the discoverable operator command surfaces for dry-run, image, publish, and external credential setup.

## Requirement Notes

- Reddit data access is read-only. The implementation will prefer Reddit app-only OAuth (`REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`) and will not require a Reddit username/password for reading public discussions. If Reddit app creation is blocked by reCAPTCHA or approval friction, it can use `REDDIT_PUBLIC_JSON_FALLBACK=true` plus a non-placeholder `REDDIT_USER_AGENT` to read Reddit public `.json` listing pages at low volume.
- If credentials are absent, the runtime context will explicitly say Reddit scan is not configured. Deterministic dry-runs can still pass for local harness, but real “latest Reddit” operation requires the env vars.
- The generated post must not pretend the author personally experienced the Reddit discussion. It should frame sources as “Reddit英文讨论里...”, translate/adapt the insight, avoid long verbatim Reddit quotes, and include a Chinese-facing comment/save mechanic.

### Task 1: Reddit Runtime Context Tests

**Files:**
- Create: `tests/unit/infrastructure/reddit/test_client.py`
- Create: `tests/unit/skills/test_reddit_discussion_context.py`
- Modify later: `src/ptsm/infrastructure/reddit/client.py`
- Modify later: `src/ptsm/skills/runtime_context.py`
- Modify later: `src/ptsm/config/settings.py`

**Step 1: Write failing tests**

Add tests for:
- Reddit listing JSON parsing returns normalized post objects and skips stickied/NSFW items.
- `RedditDiscussionContextBuilder` renders an `available` context with ranked AI/psychology posts, source URLs, and Chinese-audience fit notes.
- Missing Reddit credentials render a `missing_credentials` context that names `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, and `REDDIT_USER_AGENT`.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/reddit/test_client.py tests/unit/skills/test_reddit_discussion_context.py -q
```

Expected: FAIL because the Reddit client module and context builder do not exist.

**Step 3: Implement minimal code**

Implement:
- `RedditDiscussion`, `RedditAccessConfig`, and `RedditClient` in `src/ptsm/infrastructure/reddit/client.py`.
- Env settings for Reddit credentials, subreddits, query terms, sort/time/limit defaults.
- `RedditDiscussionContextBuilder` in `src/ptsm/skills/runtime_context.py`.
- Register `reddit_discussion_scan` in `build_skill_context_resolver()` and the deterministic/local resolver path.

**Step 4: Verify GREEN**

Run the same pytest command.

Expected: PASS.

**done_when:** Tests prove parsing, ranking/context rendering, and missing-credential guidance without external network calls.

### Task 2: Playbook, Account, Skills, And Contracts

**Files:**
- Create: `src/ptsm/playbooks/definitions/reddit_curation_daily_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/reddit_curation_daily_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/reddit_curation_daily_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/reddit_curation_daily_post/reflection.md`
- Create: `src/ptsm/playbooks/definitions/reddit_curation_daily_post/evaluation.yaml`
- Create: `src/ptsm/accounts/definitions/acct-reddit-curation-local.yaml`
- Create: `src/ptsm/skills/builtin/reddit_discussion_scan/SKILL.md`
- Create: `src/ptsm/skills/builtin/reddit_curation_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_reddit_curation_hashtagging/SKILL.md`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/accounts/test_account_registry.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Write failing tests**

Add tests that:
- The registry loads `reddit_curation_daily_post` with required skills `reddit_discussion_scan`, `xhs_image_strategy`, `reddit_curation_style`, `xhs_reddit_curation_hashtagging`.
- The account registry loads `acct-reddit-curation-local`.
- The playbook eval contract requires Reddit/source framing, Chinese translation/adaptation, save/comment mechanics, `#Reddit`, and blocks instruction leakage and fake first-hand claims.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/accounts/test_account_registry.py tests/unit/evaluations/test_playbook_contracts.py -q
```

Expected: FAIL because the playbook/account/skills/contracts are missing.

**Step 3: Add assets**

Create additive YAML/Markdown assets for the new domain. The planner should require source-aware Chinese adaptation from Reddit discussions. The persona should sound like a bilingual editor, not a scraper. The reflection/evaluation contract should require source framing, adaptation, save trigger, comment prompt, and safe handling of psychology/AI claims.

**Step 4: Verify GREEN**

Run the same pytest command.

Expected: PASS.

**done_when:** Registries and eval contract can load the new domain without touching runtime branch logic.

### Task 3: Deterministic Draft And CLI Dry-Run

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Create: `tests/e2e/test_reddit_curation_publish_dry_run.py`

**Step 1: Write failing tests**

Add tests that:
- `DeterministicDraftBackend` recognizes Reddit curation context and emits Chinese content with `Reddit`, `英文讨论`, `翻成中文` or equivalent adaptation language, a save trigger, a comment prompt, and `#Reddit`.
- CLI dry-run for `acct-reddit-curation-local` + `reddit_curation_daily_post` completes and returns the new playbook id, account id, required hashtags, and source-aware body.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_reddit_curation_publish_dry_run.py -q
```

Expected: FAIL because deterministic drafting does not yet know the new context and the playbook is not complete.

**Step 3: Implement minimal deterministic draft**

Add `_is_reddit_curation_context()` and `_build_reddit_curation_draft()` to `contextual_drafts.py`. Branch between AI-hotspot and psychology discussion scenes using simple keyword cues. Include source framing, Chinese adaptation, non-medical/non-investment boundaries, a saveable summary, and a comment prompt.

**Step 4: Verify GREEN**

Run the same pytest command.

Expected: PASS.

**done_when:** The end-to-end CLI dry-run proves the new domain can run offline through the real operator surface.

### Task 4: Complete Docs Surface

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `.env.example`
- Modify: `tests/unit/docs/test_docs_map.py`

**Step 1: Write/adjust docs tests**

Add a docs test that `operations.md` and `local-runbook.md` mention `acct-reddit-curation-local`, `reddit_curation_daily_post`, and `REDDIT_CLIENT_ID`.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

Expected: FAIL until docs are updated.

**Step 3: Update docs**

Update the full new-domain docs surface. Record why unaffected operations runbooks are not changed if any are intentionally left alone. Add operator env guidance for Reddit app-only OAuth and a representative dry-run command.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS.

**done_when:** The full docs surface is discoverable and docs tests cover the new operator contract.

### Task 5: Final Verification

**Files:**
- No new files unless failures require fixes.

**Step 1: Targeted checks**

Run:

```bash
uv run pytest tests/unit/infrastructure/reddit/test_client.py tests/unit/skills/test_reddit_discussion_context.py tests/unit/playbooks/test_playbook_registry.py tests/unit/accounts/test_account_registry.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_reddit_curation_publish_dry_run.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**Step 2: End-to-end dry-run evidence**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook --scene "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度" --account-id acct-reddit-curation-local --playbook-id reddit_curation_daily_post
```

Expected: JSON with `status == "completed"` and `publish_result.status == "dry_run"`.

**Step 3: Full local gates**

Run:

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Targeted tests, full pytest, doctor, and harness-check pass, or any non-passing command has a documented external cause and next action.
