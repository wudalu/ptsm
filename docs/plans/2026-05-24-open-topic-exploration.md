# Open Topic Exploration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep `guide-post` open-ended beyond curated candidate packs by returning one deterministic open-scene exploration direction alongside curated topic candidates.

**Architecture:** Keep `guide-post` as the only source of truth for OpenClaw/Codex topic guidance. Extend `ptsm.domain.topic_guidance` with an optional open-scene composer that derives one productized direction from the user's current scene and lane, then let `guide_post.py` request a hybrid `3 curated + 1 open_scene` set. Wrapper skills display the returned open slot but do not invent directions themselves.

**Tech Stack:** Python dataclasses, deterministic text heuristics, pytest, PTSM CLI (`uv run python -m ptsm.bootstrap`), source-of-truth docs and harness-check.

## Current Docs Summary

- `docs/index.md` says active source-of-truth docs start from architecture/runtime/playbooks/skills/operations/harness maps, not historical research notes.
- `docs/development-workflow.md` classifies this as major work because it changes runtime-visible `guide-post` behavior and wrapper skill contracts: use a worktree, plan, task-level `verify:` and `done_when:`, TDD, docs updates, final harness gate, then merge.
- `docs/architecture.md` and `docs/runtime.md` place cross-domain topic guidance in `ptsm.domain.topic_guidance`, `application/use_cases/topic_guidance_packs.py`, and `application/use_cases/guide_post.py`; it must stay read-only and outside `agent_runtime`.
- `docs/playbooks.md` and `docs/skills.md` say topic logic belongs to PTSM `guide-post`; OpenClaw wrapper skills are thin and must not copy direction IDs, research docs, raw URLs, or provenance.
- `docs/operations.md` exposes stable `guide-post` commands and says JSON/Markdown output contains four topic directions with `scene_fit`.
- `docs/harness-engineering.md` expects deterministic selector tests, application tests for all packs, docs tests for wrapper contracts, and `harness-check` before merge.
- Baseline in `.worktrees/open-topic-exploration`: `uv run pytest -q --ignore=tests/e2e` passed before edits.

## Product Decision

The previous diversity pass fixed candidate repetition, but it still depends on a finite authored pool. This change keeps that pool as the stable anchor while reserving one output slot for controlled openness:

- Return four public directions as `3 curated + 1 open_scene`.
- Keep `matched_direction_id` pointing to the first curated direction so existing run guidance remains stable.
- Build the open direction from scene facets, lane text, and reusable XHS content mechanisms such as copyable lines, save cards, comment-chain prompts, micro tasks, and checklist-style tools.
- Keep all output user-facing. Do not expose research documents, source URLs, raw provenance, or internal scoring metadata.
- Do not call live LLMs, live XHS, topic-radar, Reddit, or publishing surfaces.

## Non-Goals

- Do not add a new playbook, new external provider, or live research call.
- Do not let OpenClaw/Codex generate open directions independently.
- Do not remove curated topic packs or candidate diversity selection.
- Do not add a runtime hard gate for non-psychology playbooks.
- Do not expose source paths, raw docs, URLs, provenance, or internal ranking fields.

### Task 1: RED Tests For Open Slot Contract

**Files:**
- Modify: `tests/unit/domain/test_topic_guidance.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Add domain tests**

Add tests proving:
- `select_topic_directions(..., include_open_slot=True)` appends exactly one `direction_type == "open_scene"` direction outside the curated candidate ids.
- The open direction has stable output for the same scene and a different id/name for a different scene.
- Open direction public output includes `scene_fit`, trend signal, viral hook, content angle, saveable tool, comment prompt, and avoid note, while omitting `scene_keywords`, `lane_affinity`, `base_priority`, `diversity_key`, and source/provenance fields.

**Step 2: Add application tests**

Add tests proving:
- Psychology `guide-post` returns exactly four directions with three curated directions and one open-scene direction.
- Generic packs return the same hybrid shape for all supported non-psychology playbooks.
- `matched_direction_id` remains the first curated direction and is never the open-scene id.
- The open slot id is not present in `PSYCHOLOGY_TOPIC_DIRECTIONS` or the current pack candidate ids.
- Representative scenes still have different curated direction sets, so the open slot does not mask candidate-pool diversity.

**Step 3: Add CLI tests**

Add tests proving JSON and Markdown output expose the open-scene slot and keep the public shape deterministic.

**verify:**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

Expected red: tests fail because `include_open_slot` / `direction_type` / open-scene output do not exist.

**done_when:** New tests fail for missing open-scene behavior, not syntax, fixture, or import errors.

### Task 2: Domain Open-Scene Composer

**Files:**
- Modify: `src/ptsm/domain/topic_guidance.py`

**Implementation:**
- Add public field `direction_type` to `TopicDirection`, defaulting to `"curated"`.
- Add optional `include_open_slot: bool = False` to `select_topic_directions()`.
- When `include_open_slot` is true and `limit > 0`, select up to `limit - 1` curated directions, then append a deterministic open-scene direction.
- Compose the open direction from:
  - scene/lane facets such as relationship, object, channel, event, time, emotion, and action keywords
  - a deterministic content mechanism: copyable line, save card, comment pattern, micro task, watch checklist, tool handoff, or role-pair prompt
  - a stable hash suffix so ids are deterministic and do not collide with curated ids
- Build `scene_fit` for open-scene directions as a user-facing explanation that says it is a scene-composed exploration angle, not a fixed candidate.
- Keep source/provenance/URL fields out of public payloads.

**verify:**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

**done_when:** Domain tests prove deterministic open-slot composition, candidate preservation, and no internal-field leakage.

### Task 3: Guide-Post Hybrid Selection

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Implementation:**
- Make `build_psychology_topic_guidance()` and `build_topic_guidance()` call `select_topic_directions(..., include_open_slot=True)`.
- Add `selection_policy: "hybrid_curated_plus_open_scene"` and `open_direction_id` to `topic_guidance`.
- Keep `matched_direction_id` equal to the first curated direction.
- Update Markdown formatting so open-scene direction labels remain visible without copying internal logic.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

**done_when:** All supported playbooks return `3 curated + 1 open_scene`; JSON and Markdown expose the open slot; existing topic guidance behavior remains read-only.

### Task 4: Wrapper Skill Contract

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `tests/unit/docs/test_openclaw_skill.py`
- Modify: `tests/unit/docs/test_openclaw_topic_guide_skill.py`

**Implementation:**
- In both wrappers, instruct agents to show returned `direction_type` and clearly identify the open-scene direction when present.
- Say the open-scene direction is returned by PTSM and must not be invented by OpenClaw/Codex.
- Preserve existing constraints: call `guide-post` first, re-call it when scene changes, display only returned fields, no source docs/raw notes/URLs/provenance, no copied direction IDs.

**verify:**

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

**done_when:** Docs tests prove wrapper skills surface open-scene guidance without embedding PTSM topic logic.

### Task 5: Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/harness-engineering.md`

**Implementation:**
- Document the hybrid contract: `guide-post` returns `3 curated + 1 open_scene` within four public directions.
- Document that open-scene composition is deterministic, local, read-only, and based on scene/lane facets plus reusable content mechanisms.
- Document that wrapper skills display PTSM-returned open slots and do not invent directions.
- Update local runbook command notes to mention `direction_type`, `open_direction_id`, and rerun-on-scene-change behavior.
- Review docs/operations runbooks and record that publish, login, browser, and real side-effect steps remain unchanged.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/domain/topic_guidance.py --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md --changed-path integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md --changed-path docs/harness-engineering.md
```

**done_when:** Active docs describe the new hybrid contract and docs-sync accepts the code/docs pairing.

### Task 6: End-To-End Verification And Merge

**Files:**
- Modify: `docs/plans/2026-05-24-open-topic-exploration.md`

**Implementation:**
- Run targeted CLI smokes:
  - psychology friend emotional dumping scene
  - psychology invalid-care scene
  - `fengkuang_daily_post` group-chat scene
  - `human_enrichment_daily_post` colorwalk scene
- Confirm each JSON response contains one open-scene direction, `selection_policy`, `open_direction_id`, no source leakage, and a stable first curated `matched_direction_id`.
- Update installed Codex skill copies if the local `~/.codex/skills/ptsm-xhs-*` files exist.
- Run full verification, commit, harness-check, merge back to `main`, clean worktree, and push only if requested.

**verify:**

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap guide-post --scene "朋友半夜把情绪都倒给我，我不知道怎么回" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --scene "家人总说为你好，但我的感受完全没有被接住" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id fengkuang_daily_post --account-id acct-fk-local --scene "群聊里那句没发出去的话在脑子里加班" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "下班路上想做一次绿色 colorwalk" --non-interactive --format json
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Full tests pass, CLI smoke outputs show the hybrid contract, harness-check returns ok, and the branch is merged cleanly.

## Implementation Evidence

- Baseline: `uv run pytest -q --ignore=tests/e2e` passed in `.worktrees/open-topic-exploration` before edits.
- Task 1 red: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q` failed because `select_topic_directions()` did not accept `include_open_slot`, `topic_guidance` lacked `selection_policy`, and Markdown did not expose `open_scene`.
- Tasks 2-3 green: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q` passed after adding `direction_type`, deterministic open-scene composition, `hybrid_curated_plus_open_scene`, and Markdown `type:` output. One intermediate failure showed daily English curated sets became equal once only 3 curated slots were shown; root cause was missing `英文回复`/`句子` scene keywords for the interaction-practice candidate, fixed in `topic_guidance_packs.py`.
- Task 4 red/green: wrapper docs tests first failed for missing `direction_type`, `open_scene`, and PTSM-returned open-scene constraints, then `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q` passed.
- Task 5 docs: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q` passed. Explicit `docs-sync --changed-path ...` with code, integration skills, and source-of-truth docs returned `status: ok`.
- Targeted regression: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q` passed.
- CLI smoke: psychology friend-dumping scene returned `matched_direction_id == real_support_role_pair` and `open_direction_id == open_scene_copyable_line_487a78f3`.
- CLI smoke: psychology invalid-care scene returned `matched_direction_id == loofah_soup_communication` and `open_direction_id == open_scene_copyable_line_42ca405e`.
- CLI smoke: `fengkuang_daily_post` group-chat scene returned `matched_direction_id == fk_unsent_group_chat_aftertaste` and `open_direction_id == open_scene_comment_pattern_955a6ba7`.
- CLI smoke: `human_enrichment_daily_post` Colorwalk scene returned `matched_direction_id == enrichment_commute_color_mission` and `open_direction_id == open_scene_micro_task_b657db88`.
- Full verification: `uv run pytest -q --ignore=tests/e2e` passed.
- Installed Codex skill copies updated and verified at `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md` and `/Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md`; both mention `direction_type`, `open_scene`, and `PTSM-returned open_scene`.
- Post-commit final gate: `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main` returned top-level `status: ok`; `docs_sync.status == ok`, `harness_report.status == ok`, and embedded pytest returned `status: ok`.
