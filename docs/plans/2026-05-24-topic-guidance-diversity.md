# Topic Guidance Diversity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the two OpenClaw/Codex topic-selection skills produce meaningfully different PTSM guidance for different user scenes instead of repeatedly showing the same topic set.

**Architecture:** Keep `guide-post` as the only source of truth for topic directions. Fix the deterministic selector in `ptsm.domain.topic_guidance`, enlarge generic topic packs so a playbook has more than four candidate directions, and update the OpenClaw wrapper skills to display PTSM's scene-fit guidance without copying topic logic into the skill files.

**Tech Stack:** Python dataclasses, pytest, PTSM CLI (`uv run python -m ptsm.bootstrap`), source-of-truth docs and harness-check.

## Current Docs Summary

- `docs/index.md` says active truth starts from architecture/runtime/playbooks/skills/operations/harness docs, not historical research notes.
- `docs/development-workflow.md` classifies new skill/runtime behavior as major work: isolated worktree, current-doc review, plan with task-level `verify:` and `done_when:`, TDD, docs updates, final harness gate, then merge.
- `docs/runtime.md` defines `guide-post` as a read-only pre-post guide. It must not start workflow, create runs, publish, or expose research paths.
- `docs/playbooks.md` and `docs/skills.md` say OpenClaw wrappers are thin; psychology and cross-domain topic logic must stay inside PTSM `guide-post`.
- `docs/harness-engineering.md` expects deterministic guide-post tests, docs tests, and `harness-check` for this surface.
- Baseline in `.worktrees/topic-diversity-guidance`: `uv run pytest -q --ignore=tests/e2e` passed.

## Root Cause

1. `select_topic_directions()` currently scores `scene_keywords` against `f"{lane_name} {scene}"`. Lane labels such as `关系边界` therefore count as scene evidence and push broad boundary directions above more scene-specific directions.
2. Every non-psychology `TopicPack` currently has exactly four directions while `guide-post` returns four. That means the generic topic skill can only reorder the same set for each playbook; it cannot actually offer a different set across scenes.
3. The selector has no explicit diversity pass. High-priority or same-family candidates can crowd the top four even when lower-ranked candidates would give the user a more useful alternative angle.
4. The wrapper skills tell the agent to show returned directions, but the payload does not explain why a direction matched the current scene. OpenClaw/Codex can over-trust the first repeated candidate.

## Non-Goals

- Do not add a new playbook, external service, live research call, or publish side effect.
- Do not expose research docs, source URLs, provenance, or raw notes.
- Do not move OpenClaw/Codex skills into PTSM `SkillRegistry`; they remain integration wrappers.
- Do not change the runtime hard gate scope: only psychology OpenClaw calls require `--guidance-ack`.

### Task 1: Selector Regression Tests

**Files:**
- Modify: `tests/unit/domain/test_topic_guidance.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Add failing selector tests**

Add tests proving:
- `scene_keywords` are matched against the user scene, not the lane name.
- directions can declare a diversity family, and selection keeps distinct families before filling duplicates.

**Step 2: Add failing guide-post diversity tests**

Add tests proving:
- Relationship psychology scenes such as coworker boundary, friend emotional dumping, and "为你好" communication no longer all match `boundary_sandwich_refusal`.
- For each non-psychology pack, two representative scenes return different direction sets, not only a different order.
- Every generic pack has more than four candidate directions.
- Returned public directions include a user-facing scene-fit explanation and still omit internal fields and source leakage.

**verify:**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py -q
```

Expected red: new assertions fail under the current selector/data.

**done_when:** Tests fail for the current issue, not because of syntax or fixture errors.

### Task 2: Selector Fix And Diversity Metadata

**Files:**
- Modify: `src/ptsm/domain/topic_guidance.py`

**Implementation:**
- Add optional `diversity_key` to `TopicDirection`.
- Score `scene_keywords` against `scene` only.
- Keep `lane_affinity` matching against `lane_name` only.
- Add a deterministic diversity pass: first pick the highest-scoring candidate, then prefer candidates with unused `diversity_key` values before filling duplicates.
- Add `scene_fit` to public direction payload. It should explain scene keyword fit, lane fit, or "supplementary angle" in user-facing language without leaking source/provenance.

**verify:**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

**done_when:** Domain tests prove lane labels no longer inflate scene keyword scores, diversity keys affect selection, and public output stays deterministic.

### Task 3: Expand Generic Topic Packs

**Files:**
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`

**Implementation:**
- Add at least two additional `TopicDirection` candidates to each non-psychology pack:
  `fengkuang_daily_post`, `human_enrichment_daily_post`, `sushi_poetry_daily_post`, `wuxia_character_post`, `ai_tech_daily_post`, `daily_english_post`, `world_cup_daily_post`, and `reddit_curation_daily_post`.
- Assign `diversity_key` values so the four returned suggestions do not collapse into the same hook family.
- Keep directions productized: trend signal, viral hook, why it may work, best scenes, content angle, saveable tool, comment prompt, avoid note.
- Keep all content user-facing; no research paths, URLs, raw source references, or provenance fields.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py -q
```

**done_when:** Generic packs have larger candidate pools and representative scenes for every supported playbook return different guidance sets.

### Task 4: Psychology Guidance Adjustment

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`

**Implementation:**
- Add or tune psychology direction keywords and `diversity_key` values where needed after the selector fix.
- Ensure friend emotional dumping, "为你好" invalid care, coworker boundary, AI over-analysis, sleep scrolling, comparison anxiety, and hot-search overload map to distinct first recommendations when their scene signals are clear.
- Keep the OpenClaw `topic_guidance_required` preflight payload using the same builder.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py -q
```

**done_when:** Psychology scene clusters no longer collapse into a single boundary topic, and the OpenClaw psychology gate still returns guidance before workflow startup.

### Task 5: Wrapper Skill Contracts

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `tests/unit/docs/test_openclaw_skill.py`
- Modify: `tests/unit/docs/test_openclaw_topic_guide_skill.py`

**Implementation:**
- Update both wrappers to show `scene_fit` with each returned direction.
- Make clear that if the user changes the scene, the agent must call `guide-post` again instead of reusing previous directions.
- Keep wrappers thin: no hard-coded direction IDs or copied topic logic.
- Preserve psychology safety and non-psychology wrapper routing boundaries.

**verify:**

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

**done_when:** Docs tests prove wrapper instructions cover scene-fit display and re-query behavior without embedding PTSM direction IDs.

### Task 6: Source-Of-Truth Docs

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`
- Review: `docs/operations/`

**Implementation:**
- Document that `guide-post` selects four directions from a larger pack and includes a `scene_fit` explanation.
- Document the fixed selector boundaries: scene keywords come from user scene; lane affinity comes from lane.
- Document that generic packs must maintain more than four candidates so different scenes can diverge.
- Record if `docs/operations/` runbooks are unchanged because stable operator commands remain in `docs/operations.md`.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/domain/topic_guidance.py --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py --changed-path src/ptsm/application/use_cases/guide_post.py
```

**done_when:** Active docs describe the new selector/data contract and docs-sync accepts the code/docs pairing.

### Task 7: End-To-End Verification

**Files:**
- Modify: `docs/plans/2026-05-24-topic-guidance-diversity.md`

**Implementation:**
- Run targeted CLI smokes for representative scenes:
  - psychology boundary, friend dumping, invalid care, AI over-analysis
  - generic topic guide examples for `fengkuang_daily_post` and `human_enrichment_daily_post`
- Record command evidence in this plan.

**verify:**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap guide-post --scene "朋友半夜把情绪都倒给我，我不知道怎么回" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id fengkuang_daily_post --account-id acct-fk-local --scene "群聊里那句没发出去的话在脑子里加班" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "下班路上想做一次绿色 colorwalk" --non-interactive --format json
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Targeted and full tests pass, CLI outputs distinct scene-matched direction sets with `scene_fit`, and harness-check returns ok.

## Implementation Evidence

- Baseline: `uv run pytest -q --ignore=tests/e2e` passed in `.worktrees/topic-diversity-guidance` before edits.
- Task 1 red: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py -q` failed on lane text being scored as scene keywords, missing `diversity_key`, missing `scene_fit`, psychology relationship scenes collapsing to `boundary_sandwich_refusal`, and generic packs returning the same 4-direction set.
- Task 2 green: `uv run pytest tests/unit/domain/test_topic_guidance.py -q` passed after selector changes.
- Tasks 3-4 green: `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py -q` passed after expanding generic packs and fixing psychology matching.
- Task 5 red/green: wrapper docs tests first failed for missing `scene_fit` and re-query instructions, then `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q` passed after wrapper updates.
- Task 6 docs: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q` passed. `docs-sync` first failed when only code paths were supplied; rerun with code plus `docs/architecture.md`, `docs/runtime.md`, `docs/playbooks.md`, `docs/skills.md`, `docs/operations.md`, `docs/operations/local-runbook.md`, and `docs/harness-engineering.md` returned `status: ok`.
- CLI smoke: psychology friend-dumping scene returned `matched_direction_id == real_support_role_pair` with `scene_fit` matching `半夜、朋友`.
- CLI smoke: psychology invalid-care scene returned `matched_direction_id == loofah_soup_communication` with `scene_fit` matching `为你好、感受`.
- CLI smoke: `fengkuang_daily_post` group-chat scene returned `matched_direction_id == fk_unsent_group_chat_aftertaste`.
- CLI smoke: `human_enrichment_daily_post` Colorwalk scene returned `matched_direction_id == enrichment_commute_color_mission`.
- Full verification before commit: `uv run pytest -q --ignore=tests/e2e` passed.
- Pre-commit harness dry run: `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main` returned top-level `status: ok`; because this was before commit, docs-sync saw no committed changed paths, while the explicit `docs-sync --changed-path ...` command above covered the working-tree docs gate.
- Post-commit harness: `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main` returned top-level `status: ok`; docs-sync saw all committed code/docs/test/integration paths and reported no missing updates.
