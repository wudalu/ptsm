# Psychology Domain Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve `modern_psychology_post` so Xiaohongshu psychology content uses low-density, saveable visual forms and rotates topic angles beyond repeated workplace rumination.

**Architecture:** Keep the existing playbook/skill architecture. Encode the format guidance in psychology-specific prompts and shared image strategy text, then adjust the deterministic draft fallback so local dry-runs can prove the behavior without live LLM or Xiaohongshu access. Do not add runtime branches or real-publish side effects.

**Tech Stack:** Python 3.12, pytest, YAML/Markdown playbook definitions, builtin skill Markdown, deterministic drafting backend, existing local image-plan contract.

## Current Docs Summary

- `docs/index.md` says content/strategy changes should start from `docs/playbooks.md`, `docs/skills.md`, and `docs/xhs-topics/index.md`.
- `docs/development-workflow.md` says playbook/domain behavior work should use a worktree, a plan, explicit `verify:` and `done_when:` checks, source-of-truth docs updates, and a final harness gate.
- `docs/playbooks.md` defines `modern_psychology_post` as a Xiaohongshu playbook that uses a first-person micro-scene, one psychology mechanism, one saveable tool, an example-style comment prompt, and professional-help boundaries.
- `docs/skills.md` says `psychology_style`, `psychology_safety`, `xhs_psychology_hashtagging`, `xhs_trend_scan`, `topic_research`, and `xhs_image_strategy` are the current psychology skill surface.
- `docs/xhs-topics/image-forms-by-domain.md` already says psychology covers should prefer `save_tool` or `cover_hook`, low text density, and no long mechanism explanation inside the image.

## Evidence Inputs

- Local XHS sample artifact `outputs/artifacts/xhs-content-quality-search-2026-05-15.json` includes high-engagement psychology-adjacent titles under `心理学`, `情绪管理`, `职场焦虑`, and `反刍思维`; the strongest patterns are concrete pain, short imperative/reframe, and saveable tips.
- Public Xiaohongshu operations sources also emphasize that topic selection determines ceiling, cover/title determine click, body determines completion, and comments drive conversion; they warn against dense text blocks and overfilled covers.
- Public emotion-cover guidance says psychology/consulting-style content often works with simple, restrained covers, but the cover should carry mood and core topic rather than every detail.
- Recent psychology artifacts show the system can generate `iphone_notes` low-density save tools, but repeated deterministic runs still overproduce the same rumination theme and can misclassify psychology posts as `wechat_chat` when body text mentions messages.

## Scope

- Tighten psychology visual guidance toward low-density `iphone_notes` / `note_card` covers, with `wechat_chat` only for actual message-boundary topics.
- Expand psychology topic lanes into a repeatable topic lattice: workplace rumination, relationship boundary, digital-life overload, loneliness/social comparison, emotional regulation, and timely social-event reframes.
- Preserve safety boundaries: no diagnosis, no treatment promise, no medication guidance, no crisis handling substitute.
- Keep `xhs_image_strategy` generic but make the psychology default clearer.

## Non-Goals

- No new playbook, account, scheduler, or runtime branch.
- No real Xiaohongshu publishing.
- No new image renderer.
- No medical or clinical advice system.

### Task 1: Add Failing Tests For Psychology Topic And Visual Strategy

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Add deterministic topic-lattice test**

Add a test that generates drafts for digital-life overload and loneliness/social-comparison scenes. Assert:
- titles differ from the existing workplace-rumination titles
- body includes relevant mechanisms such as `信息过载`, `比较焦虑`, `孤独`, `情绪回避`, or `低控制感`
- body still includes `专业帮助`
- hashtags include `#心理学` plus scene-specific tags

**Step 2: Add image-plan preference test**

Add a test for a psychology scene mentioning `消息` but centered on a saveable boundary tool. Assert deterministic `image_plan` remains:
- `backend == "local_social_screenshot"`
- `style == "iphone_notes"`
- `role == "save_tool"`
- `text_density == "low"`
- `max_text_units == "3"`

**Step 3: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_covers_digital_and_loneliness_lanes tests/unit/infrastructure/llm/test_factory.py::test_deterministic_psychology_message_boundary_prefers_save_tool_notes -q
```

Expected: FAIL because the new lanes or image-plan precedence are not yet implemented.

**done_when:** The failing output proves the tests are checking missing behavior, not typos.

### Task 2: Implement Deterministic Psychology Lanes And Image Precedence

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`

**Step 1: Add minimal lane branches**

In `_build_modern_psychology_draft()`, add branches for:
- digital-life overload: short video, sleep-time scrolling, information overload, comparison anxiety
- loneliness/social comparison: loneliness, social exhaustion, seeing others' lives and feeling worse

Each branch must keep the same safety shape: micro-scene -> mechanism -> non-diagnostic reframe -> one saveable tool -> professional-help boundary -> example comment prompt.

**Step 2: Adjust image-plan precedence**

In `_build_deterministic_image_plan()`, when the context is modern psychology and the draft contains a saveable tool cue, prefer the note-style save-tool plan before chat screenshot detection. Keep actual message-draft / leader-chat scenes eligible for `wechat_chat`.

**Step 3: Verify GREEN**

Run the RED command again. Expected: PASS.

**done_when:** Deterministic psychology dry-runs can represent at least five distinct lanes and message-boundary posts with saveable tools use note-style covers.

### Task 3: Tighten Psychology Skill And Playbook Prompts

**Files:**
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `src/ptsm/skills/builtin/xhs_psychology_hashtagging/SKILL.md`
- Modify: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`

**Step 1: Add topic lattice to planner/style**

State that each post should choose one lane from:
- 职场复盘/低控制感
- 关系边界/消息压力
- 数字生活/信息过载/睡前短视频
- 孤独/比较焦虑/社交耗竭
- 情绪调节/恢复练习
- 热点心理化重构

**Step 2: Add visual rules**

State that psychology covers should default to:
- `iphone_notes` save-tool card for checklist, three-column tools, boundary sentences, or five-minute exercises
- `note_card` for a single strong reframe
- `wechat_chat` only when the actual first-screen asset is a message draft or chat exchange
- no dense mechanism explanations in the image

**Step 3: Verify prompt tests**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py -q
```

Expected: PASS.

**done_when:** Skill metadata still loads, and prompt text now contains the topic lattice and visual constraints.

### Task 4: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/xhs-topics/image-forms-by-domain.md`
- Modify: `docs/research/2026-05-09-modern-psychology-domain.md`

**Step 1: Document current optimization**

Update active docs to reflect:
- psychology topic rotation
- low-density image defaults
- local evidence from the 2026-05-15 and 2026-05-17 research artifacts
- reason for not making every psychology post a text-heavy screenshot

**Step 2: Verify docs**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/playbooks.md
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/skills.md
```

Expected: PASS / `status=ok`.

**done_when:** Docs match the behavior and docs metadata/map tests stay green.

### Task 5: End-To-End Verification

**Files:**
- No new files expected beyond prior tasks.

**Step 1: Run targeted tests**

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_modern_psychology_publish_dry_run.py -q
```

**Step 2: Run psychology dry-run smoke**

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "睡前刷短视频停不下来，越刷越空但又不想停" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --publish-mode dry-run \
  --auto-generate-image
```

Expected: JSON output has `status == "completed"`, psychology safety boundaries, a non-repeated digital-life topic, and low-density image-plan metadata.

**Step 3: Final harness**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

Expected: `status=ok`, or any issue is specific, explained, and not a proxy for unverified behavior.

**done_when:** Targeted tests pass, dry-run completes, artifact contains the expected topic and image-plan signals, and harness gate passes or has a documented external blocker.
