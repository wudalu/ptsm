# Topic Guidance Breadth Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace fixed `3 curated + 1 open_scene` topic guidance slots with a deterministic diversity-aware reranker so PTSM can return broader, scene-sensitive directions without OpenClaw or Codex inventing options outside PTSM.

**Architecture:** Keep `guide-post` as the only source of truth and keep the path read-only. `TopicDirection.direction_type` remains a source label (`curated` or `open_scene`), while selection becomes a dynamic rerank across authored curated candidates and multiple locally generated open-scene candidates. The first visible direction stays a strong scene/lane match for backwards compatibility, then later slots are chosen by relevance plus novelty across source type, diversity family, scene facets, and open-scene mechanism.

**Tech Stack:** Python 3.12, dataclasses, deterministic SHA256 rotation, pytest, PTSM CLI `guide-post`, `harness-check`.

## Current Docs Summary

- `docs/index.md` maps source-of-truth docs and points topic guidance work to architecture, runtime, playbooks, skills, operations, and harness docs.
- `docs/development-workflow.md` requires a worktree, a plan, task-level `verify:` and `done_when:`, implementation inside the worktree, docs updates, tests, and `harness-check` before merging.
- `docs/architecture.md` currently says `ptsm.domain.topic_guidance` owns deterministic lane/direction selection and an open-scene composer outside `agent_runtime`.
- `docs/runtime.md`, `docs/playbooks.md`, `docs/operations.md`, and `docs/harness-engineering.md` currently document `selection_policy == "hybrid_curated_plus_open_scene"` and a fixed `3 curated + 1 open_scene` public shape.
- `docs/skills.md` and `integrations/openclaw/*/SKILL.md` correctly require wrappers to show only PTSM-returned directions and not expose research notes, paths, URLs, or provenance. They need language updates because PTSM may now return more than one `open_scene`.

## Root Cause

The existing selector scores curated candidates, selects `limit - 1` of them, and appends exactly one generated `open_scene`. This means a strong lane such as Sushi's "怀民关系" can keep returning the same visible curated anchors even when the scene text changes. `stable_topic_rotation` is deterministic by design; the bug is not randomness but the fixed slot contract.

## Target Behavior

- Public output still returns four directions by default.
- No visible slot is reserved for a fixed number of curated directions.
- `curated` and `open_scene` describe where a direction came from, not where it must appear.
- Multiple open-scene candidates are generated locally from the current scene/lane and reranked with curated candidates.
- First slot remains the strongest curated match when one exists, keeping `matched_direction_id` useful for existing callers.
- Later slots prefer uncovered scene facets, unused `diversity_key`, different `direction_type`, and different open-scene mechanisms.
- Metadata exposes the dynamic contract:
  - `selection_policy: "dynamic_scene_diversity_rerank"`
  - `open_direction_ids: list[str]`
  - `direction_type_counts: dict[str, int]`
  - Keep `open_direction_id` as a backwards-compatible alias for the first open-scene direction.
- Output still never exposes `docs/research`, source URLs, provenance, or internal candidate fields.

## Non-Goals

- Do not add live XHS/topic-radar scanning to ordinary `guide-post`.
- Do not let OpenClaw/Codex generate directions itself.
- Do not change `run-playbook` generation or publish behavior.
- Do not refactor unrelated playbook content.

## Task 1: Add Red Tests For Dynamic Breadth

**Files:**
- Modify: `tests/unit/domain/test_topic_guidance.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write domain tests**

Add tests that call `select_topic_directions(..., include_open_slot=True, dynamic_breadth=True)` and prove:

- It can return more than one `direction_type == "open_scene"` within four directions.
- It does not force exactly three curated directions.
- Returned open directions use distinct IDs and distinct names/mechanisms for the same scene.
- Internal fields still do not leak.

**Step 2: Write application tests**

Add or update tests for `run_guide_post`:

- Psychology guidance returns `selection_policy == "dynamic_scene_diversity_rerank"`.
- All supported topic packs return four directions, `open_direction_ids`, and `direction_type_counts`.
- For `sushi_poetry_daily_post`, three scene variants within the same resolved lane do not all expose the same first three curated IDs; the visible sets differ by more than an open-scene hash.

**Step 3: Write CLI tests**

Update JSON/Markdown assertions to expect:

- `dynamic_scene_diversity_rerank`
- `open_direction_ids`
- `direction_type_counts`
- `open_direction_id` still present for compatibility.

**Step 4: Run red tests**

Run:

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: FAIL because `dynamic_breadth`, `open_direction_ids`, and `dynamic_scene_diversity_rerank` do not exist yet, and current guidance still forces `3 curated + 1 open_scene`.

**verify:** The failures are assertion/API failures for the missing dynamic contract, not syntax/import failures.

**done_when:** Red tests demonstrate the fixed-slot regression and document the desired public contract.

## Task 2: Implement Multiple Open-Scene Candidates

**Files:**
- Modify: `src/ptsm/domain/topic_guidance.py`
- Test: `tests/unit/domain/test_topic_guidance.py`

**Step 1: Add an open-scene list builder**

Add `build_open_scene_topic_directions(scene, lane_name, count=3)` that:

- Extracts scene facets once.
- Ranks mechanisms deterministically from the current scene/lane.
- Returns distinct `TopicDirection` candidates for different mechanisms.
- Keeps `build_open_scene_topic_direction()` as a compatibility wrapper that returns the first candidate.

**Step 2: Split mechanism selection**

Replace single `_choose_open_scene_mechanism()` use with helpers:

- `_rank_open_scene_mechanisms(scene, lane_name) -> tuple[str, ...]`
- `_build_open_scene_topic_direction_for_mechanism(scene, lane_name, facets, mechanism)`

The ranked list should include the strongest mechanism first, then adjacent mechanisms so literary and relationship scenes can produce, for example, `copyable_line`, `comment_pattern`, and `save_card` instead of only one hash variant.

**Step 3: Verify domain red moves forward**

Run:

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

Expected: multiple-open generation tests pass or move to selector assertions; application tests may still fail until Task 3.

**verify:** Open-scene candidates are deterministic, distinct, public-safe, and still based only on local scene/lane facets.

**done_when:** The domain layer can generate multiple PTSM-owned open-scene candidates without changing default legacy selection.

## Task 3: Implement Dynamic Diversity Rerank

**Files:**
- Modify: `src/ptsm/domain/topic_guidance.py`
- Test: `tests/unit/domain/test_topic_guidance.py`

**Step 1: Extend selector API**

Add optional parameters:

```python
dynamic_breadth: bool = False
open_candidate_count: int = 3
```

Keep old behavior when `dynamic_breadth` is false.

**Step 2: Build combined candidate pool**

When `include_open_slot and dynamic_breadth`:

- Score authored curated candidates as today.
- Generate `max(open_candidate_count, limit - 1)` open candidates.
- Add open candidates to the scored list with scene-facet matches, lane matches, deterministic rotation, and a competitive but not dominant base score.

**Step 3: Select with novelty-aware scoring**

Implement a small deterministic reranker:

- Pick first slot from the best curated candidate when one exists; otherwise pick best candidate.
- For each next slot, compute an effective score from base relevance minus redundancy penalties:
  - repeated `diversity_key`
  - repeated `direction_type`
  - repeated scene facet set
  - repeated open-scene mechanism
- Add a novelty bonus for uncovered scene facets and source/type diversity.
- Tie-break with existing rotation and index.

**Step 4: Verify domain green**

Run:

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

Expected: PASS.

**verify:** Existing non-open selector behavior remains stable; dynamic mode no longer hard-codes `3 curated + 1 open_scene`.

**done_when:** The selector returns four deterministic, relevant, non-redundant directions with no fixed curated count.

## Task 4: Wire Dynamic Policy Into Guide-Post

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Update guidance builders**

Call:

```python
select_topic_directions(..., include_open_slot=True, dynamic_breadth=True)
```

for psychology and generic topic guidance.

**Step 2: Add metadata helpers**

Add internal helpers to compute:

- `open_direction_ids`
- `direction_type_counts`
- backwards-compatible `open_direction_id`
- `matched_direction_id` from first curated direction, or first direction if no curated exists.

**Step 3: Update Markdown output if needed**

Keep showing `type:` and `fit:` per direction. Do not expose internal rerank scores.

**Step 4: Verify application and CLI green**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: PASS.

**verify:** Sushi same-lane scene changes produce visibly different direction sets, not just changed open-scene IDs.

**done_when:** `guide-post` JSON and Markdown expose the new dynamic policy while preserving compatibility fields.

## Task 5: Update Wrapper Skills And Docs

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_openclaw_skill.py`
- Test: `tests/unit/docs/test_openclaw_topic_guide_skill.py`

**Step 1: Update wrapper wording**

Change wrapper wording from "the open_scene direction" to "any returned open_scene direction(s)" and clarify wrappers still must not invent, expand, or replace PTSM-returned directions.

**Step 2: Update source-of-truth docs**

Replace `3 curated + 1 open_scene` and `hybrid_curated_plus_open_scene` descriptions with the dynamic rerank contract.

**Step 3: Update installed Codex skill copies**

Mirror the wrapper updates into `$CODEX_HOME/skills` so current Codex sessions use the new contract.

**Step 4: Verify docs tests**

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

Expected: PASS.

**verify:** Docs no longer promise fixed curated slots, but still forbid source leakage and wrapper-invented directions.

**done_when:** Operator docs, wrapper skills, and installed Codex skills agree with the dynamic PTSM-owned guidance contract.

## Task 6: Full Verification And Integration

**Files:**
- Modify: `docs/plans/2026-05-24-topic-guidance-breadth.md`

**Step 1: Record evidence in this plan**

Append an implementation evidence section with red/green results and CLI smoke outputs.

**Step 2: Run targeted smoke commands**

Run two or more Sushi same-lane scenes:

```bash
uv run ptsm guide-post --playbook-id sushi_poetry_daily_post --account-id acct-sushi-local --scene "夜里读到怀民亦未寝，想写一种旧友关系" --non-interactive --json
uv run ptsm guide-post --playbook-id sushi_poetry_daily_post --account-id acct-sushi-local --scene "半夜一个人走在城市夜路上，突然想起怀民亦未寝" --non-interactive --json
```

Expected: Both return four directions, `dynamic_scene_diversity_rerank`, at least one `open_scene`, and different visible direction sets.

**Step 3: Run focused and full tests**

Run:

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
uv run pytest -q --ignore=tests/e2e
```

Expected: PASS.

**Step 4: Run harness-check**

Run inside the worktree with a base that isolates this branch from the current local main when possible:

```bash
harness-check --base-ref main
```

If the worktree cannot resolve local `main` as intended, run the equivalent changed-path or current-branch harness command and record the result.

**Step 5: Merge policy**

Do not push automatically while local `main` contains the pre-existing unpushed commit `fd7aa15`. If integration is complete, merge locally or leave the branch ready, then tell the user that pushing would also push that pre-existing commit unless they want it included.

**verify:** All relevant tests and harness pass; git status is understood; no unrelated main-worktree files are changed.

**done_when:** Dynamic topic guidance is implemented, documented, installed for Codex skills, and verified; final response explains push constraints clearly.

## Implementation Evidence

- Baseline before edits: `uv run pytest -q --ignore=tests/e2e` passed in the `fix/topic-guidance-breadth` worktree.
- Task 1 red: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q` failed as expected. The domain failure was `TypeError: select_topic_directions() got an unexpected keyword argument 'dynamic_breadth'`; application and CLI failures still returned `hybrid_curated_plus_open_scene`.
- Tasks 2-3 green: `uv run pytest tests/unit/domain/test_topic_guidance.py -q` passed after adding multiple open-scene candidates and dynamic breadth reranking while preserving legacy selector behavior.
- Task 4 green: `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q` passed after wiring `dynamic_scene_diversity_rerank`, `open_direction_ids`, compatible `open_direction_id`, and `direction_type_counts`.
- Focused topic-guidance green: `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q` passed.
- Task 5 green: `uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q` passed after updating OpenClaw wrapper docs and installed Codex skill copies.
- Sushi smoke: scene `夜里读到怀民亦未寝，想写一种旧友关系` returned `dynamic_scene_diversity_rerank`, `{'curated': 2, 'open_scene': 2}`, and visible ids `sushi_role_pair_huimin`, `open_scene_save_card_43cb0666`, `sushi_city_night_walk`, `open_scene_comment_pattern_c5e135ee`.
- Sushi smoke: scene `半夜一个人走在城市夜路上，突然想起怀民亦未寝` returned `dynamic_scene_diversity_rerank`, `{'curated': 1, 'open_scene': 3}`, and visible ids `sushi_city_night_walk`, `open_scene_save_card_102d570a`, `open_scene_comment_pattern_f74c88f8`, `open_scene_copyable_line_b77f2350`.
- Sushi smoke: scene `下班路上看到月亮，想写苏轼和一个没联系很久的人` returned `dynamic_scene_diversity_rerank`, `{'curated': 1, 'open_scene': 3}`, and visible ids `sushi_city_night_walk`, `open_scene_micro_task_c85f7468`, `open_scene_comment_pattern_ffbf538b`, `open_scene_save_card_fae95f53`.
- Full non-e2e verification: `uv run pytest -q --ignore=tests/e2e` passed.
- Whitespace check: `git diff --check` passed.
- Pre-commit harness: direct `harness-check --base-ref main` was not on PATH, so the project entrypoint `uv run python -m ptsm.bootstrap harness-check --base-ref main` was used and returned top-level `status: ok`; because the branch was still uncommitted, `docs_sync.changed_paths` was empty as documented in `docs/operations.md`.
- Post-commit harness: `uv run python -m ptsm.bootstrap harness-check --base-ref main` returned top-level `status: ok`; `docs_sync.status == ok`, `missing_updates == []`, `unmapped_changes == []`, and embedded pytest returned `status: ok`.
