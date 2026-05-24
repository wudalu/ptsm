# Psychology Topic Guidance Variation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `guide-post` and the OpenClaw psychology guidance gate return scene-aware, varied, domain-safe topic directions instead of the same fixed four options for every request.

**Architecture:** Keep PTSM as the source of truth for psychology topic guidance and keep OpenClaw as a thin wrapper. Expand the internal psychology direction bank with user-facing trend signals and viral hook mechanics, then rank a small set of directions by scene, resolved psychology lane, and deterministic rotation. Do not add live XHS research to every guidance call; live or periodic topic research remains in `topic-radar` and XHS pattern collection.

**Tech Stack:** Python 3.12 dataclasses, argparse CLI, pytest, Markdown source-of-truth docs, OpenClaw `SKILL.md` wrapper instructions.

## Current Docs Summary

- `docs/index.md` is the entry point and says current source-of-truth docs beat historical plans or research notes.
- `docs/development-workflow.md` treats this as major runtime/operator work because it changes a caller-facing guidance contract. Work must happen in an isolated worktree, with a plan, task-level verification, source-of-truth docs updates, and a final harness gate.
- `docs/architecture.md` keeps caller protocols in `application/use_cases` and external wrapper instructions outside the builtin skill registry. This change should not add runtime domain branches outside the existing `guide_post` / `run_playbook` boundary.
- `docs/runtime.md` says OpenClaw psychology calls are gated by a read-only `topic_guidance_required` preflight before workflow start or side effects. This behavior should remain read-only.
- `docs/playbooks.md` and `docs/skills.md` say `modern_psychology_post` has absorbed current XHS hook research into domain-safe ideas such as boundary tools, AI companion boundaries, role recognition, saveable tools, and non-diagnostic reframes.
- `docs/topic-radar.md` and `docs/xhs-topics/index.md` separate periodic/live trend collection from ordinary post generation. Ordinary guidance may use productized hook knowledge but should not run live XHS scans by default.
- `docs/operations.md` documents `guide-post` as the modern psychology pre-post guide and requires it to hide research paths, raw notes, URLs, and source provenance from user-facing output.

## Scope

- Expand psychology topic directions beyond the current fixed four items.
- Add user-facing `trend_signal` and `viral_hook` fields to each returned direction.
- Select a bounded list of directions dynamically from scene and lane instead of returning the full static list.
- Keep `matched_direction_id` aligned with the top selected direction.
- Update OpenClaw wrapper instructions to display the new fields when present.
- Update source-of-truth docs for the dynamic guidance contract.

## Non-Goals

- Do not add a new psychology playbook, account, or domain.
- Do not run live XHS MCP, web search, or topic-radar scans on every `guide-post` call.
- Do not expose research file paths, raw notes, URLs, or provenance in JSON, Markdown, or OpenClaw-facing output.
- Do not change real publishing behavior.
- Do not make topic selection random in a way that makes tests flaky.

### Task 1: Characterize Current Static Guidance

**Files:**
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write the failing tests**

Add tests that call `run_guide_post()` for clearly different scenes:

- `同事临时加需求，想练一版边界句`
- `晚上只想让 AI 帮我分析关系，结果越聊越空`
- `看到别人周末都在聚会，突然觉得自己很失败`

Assert:

- each result returns exactly four `topic_guidance.directions`
- direction id sets are not identical across all scenes
- the first/matched direction fits the scene (`boundary_sandwich_refusal`, an AI boundary direction, and a self-compassion/comparison direction respectively)
- each public direction includes `trend_signal` and `viral_hook`
- serialized output still omits `docs/research`, the viral hook research filename, URLs, and `"source"`

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_run_guide_post_varies_topic_directions_by_scene -q
```

Expected: FAIL because current guidance always returns the same four direction ids and does not include `trend_signal` or `viral_hook`.

**done_when:** The test captures the user-reported issue before implementation.

### Task 2: Implement Scene-Aware Direction Selection

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Extend the direction model**

Add public fields:

- `trend_signal`
- `viral_hook`

Add internal fields:

- `lane_affinity`
- `scene_keywords`
- `base_priority`

Keep internal fields out of returned public direction dictionaries.

**Step 2: Expand the direction bank**

Add domain-safe productized topics from the existing hook research:

- message boundary reply drafts
- comparison pause card
- AI over-analysis stop rule
- sleep information closing ritual
- Sunday night work anxiety
- 90-second grounding practice
- hot-search noise three questions
- real support system role-pair prompt
- office recovery without shopping

Keep existing four ids stable for compatibility.

**Step 3: Rank and select directions**

Implement `_select_topic_directions(scene, lane_name, limit=4)`:

- score scene keyword matches highest
- add score for lane affinity
- use `base_priority` for evergreen hook strength
- use a deterministic hash of `scene`, `lane_name`, and direction id as a tie-breaker so generic scenes do not always pick the same first four constants
- return the top four public direction dicts
- set `matched_direction_id` to the first selected direction id

**Step 4: Run targeted tests**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_requires_topic_guidance_for_openclaw_psychology -q
```

**done_when:** Different scenes receive different four-item direction sets, OpenClaw preflight reuses the same dynamic selector, and no internal research details leak.

### Task 3: Update Wrapper And Source-Of-Truth Docs

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Test: `tests/unit/docs/test_openclaw_skill.py`

**Step 1: Update OpenClaw wrapper**

Tell OpenClaw to show each returned direction's:

- name
- trend signal
- viral hook
- why it may work
- best scenes
- content angle
- saveable tool
- comment prompt
- avoid note

Keep the wrapper thin and keep PTSM as the owner of topic logic.

**Step 2: Update active docs**

Document that guidance now returns a scene-aware subset from a larger productized direction bank. State that live trend scans are not run by default and that research paths/provenance remain hidden.

**Step 3: Run docs tests**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py -q
```

**done_when:** Docs and wrapper describe the new guidance contract without copying internal research notes into user-facing instructions.

### Task 4: End-To-End Verification

**Files:**
- No code changes.

**Step 1: Run targeted unit suite**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py tests/unit/docs/test_openclaw_skill.py -q
```

**Step 2: Run CLI smoke checks**

```bash
uv run python -m ptsm.bootstrap guide-post --scene "同事临时加需求，想练一版边界句" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --scene "晚上只想让 AI 帮我分析关系，结果越聊越空" --non-interactive --format json
uv run python -m ptsm.bootstrap run-playbook --caller openclaw --scene "晚上只想让 AI 帮我分析关系，结果越聊越空" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run
```

Expected:

- first two `guide-post` payloads have different direction id sets
- returned directions include `trend_signal` and `viral_hook`
- OpenClaw preflight returns `status == "topic_guidance_required"` before workflow or publish side effects

**Step 3: Run docs-sync changed-path check**

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/application/use_cases/guide_post.py \
  --changed-path src/ptsm/application/use_cases/run_playbook.py \
  --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md \
  --changed-path docs/runtime.md \
  --changed-path docs/playbooks.md \
  --changed-path docs/skills.md \
  --changed-path docs/operations.md
```

**Step 4: Run final harness**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Targeted tests, smoke checks, docs-sync, and harness-check pass, or any skipped check is explained with a concrete reason.
