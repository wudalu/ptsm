# XHS Image Role Strategy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `xhs_image_strategy` control not just image backend/style, but also the image's job and text density so local generated XHS covers stay simple and acceptable across domains.

**Architecture:** Extend `final_content.image_plan` with `role`, `text_density`, `max_text_units`, and `cover_text_strategy`. The LLM/deterministic draft layer preserves and emits those fields, `run_playbook` carries them into image generation metadata and local renderer payloads, and the Pillow local renderer clamps visible copy for low-density local screenshots.

**Tech Stack:** Python 3, pytest, Pillow local image renderer, PTSM playbook runtime, built-in skill Markdown docs.

### Task 1: Plan And Baseline

**Files:**
- Create: `docs/plans/2026-05-17-xhs-image-role-strategy.md`

**Step 1: Confirm relevant source-of-truth docs**

Read:
- `docs/index.md`
- `docs/development-workflow.md`
- `docs/runtime.md`
- `docs/skills.md`
- `docs/observability.md`
- `docs/research/2026-05-16-xhs-new-theme-research.md`

Expected: summarize that this is runtime behavior work, must use an isolated worktree, plan before code, TDD, update source docs, run `harness-check`, then merge back to `main`.

**Step 2: Run baseline targeted tests**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/infrastructure/llm/test_factory.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/docs/test_docs_map.py -q
```

Expected: PASS before behavior changes.

### Task 2: Preserve And Emit Image Role Fields

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`

**Step 1: Write failing parser test**

Add a test that parses JSON with:

```json
{
  "image_plan": {
    "backend": "local_social_screenshot",
    "style": "iphone_notes",
    "role": "save_tool",
    "text_density": "low",
    "max_text_units": 3,
    "cover_text_strategy": "封面只放一个问题和三条短句",
    "prompt_focus": "会议复盘急救卡"
  }
}
```

Assert all new fields survive normalization, with `max_text_units` normalized consistently.

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_parse_json_payload_preserves_image_role_and_density -q
```

Expected: FAIL because unknown image plan fields are dropped.

**Step 3: Implement minimal parser allowlist**

Update `_normalize_image_plan_payload()` to preserve:
- `role`
- `text_density`
- `max_text_units`
- `cover_text_strategy`

Do not add unrelated schema machinery.

**Step 4: Verify GREEN**

Run the same test. Expected: PASS.

**Step 5: Add deterministic backend test**

Add a failing test for psychology / note-oriented context that expects deterministic drafts with `iphone_notes` to include:
- `role == "save_tool"`
- `text_density == "low"`
- `max_text_units == "3"` or equivalent normalized string
- a non-empty `cover_text_strategy`

**Step 6: Verify RED**

Run the new deterministic test. Expected: FAIL because the deterministic plan currently only emits backend/style/reason/prompt_focus.

**Step 7: Implement deterministic defaults**

Update `_build_deterministic_image_plan()`:
- chat-like scenes: `role=comment_prompt` or `cover_hook`, `text_density=low`, `max_text_units=2`
- note/checklist/tool scenes: `role=save_tool`, `text_density=low`, `max_text_units=3`
- real visual scenes: `role=evidence_or_scene`, `text_density=low`, `max_text_units=1`
- default note card: `role=cover_hook`, `text_density=low`, `max_text_units=2`

Also update the hard requirements prompt so LLM-backed drafts know these fields are required when `xhs_image_strategy` is active.

**Step 8: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py -q
```

Expected: PASS.

### Task 3: Carry Role Fields Through Runtime And Clamp Local Payload Copy

**Files:**
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`

**Step 1: Write failing metadata test**

Add a test for `_resolve_image_generation_decision()` or the existing local-image-plan path asserting `image_generation.image_plan` includes `role`, `text_density`, `max_text_units`, and `cover_text_strategy`.

**Step 2: Verify RED**

Run the specific test. Expected: FAIL because decision metadata omits the new fields.

**Step 3: Implement metadata propagation**

Update:
- `_resolve_image_generation_decision()`
- `_image_generation_decision_metadata()`
- `_summarize_image_plan()`

Expected behavior: new fields are copied for both local and provider routes, including manual override when supplied through normalized decision objects.

**Step 4: Verify GREEN**

Run the specific metadata test. Expected: PASS.

**Step 5: Write failing low-density payload test**

Add a test for `_build_note_card_image_payload()` using a long psychology body and an image plan:

```python
{
    "source": "llm_image_plan",
    "requested_backend": "local_social_screenshot",
    "selected_backend": "local_note_card",
    "requested_style": "iphone_notes",
    "role": "save_tool",
    "text_density": "low",
    "max_text_units": "3",
    "cover_text_strategy": "封面只放一个问题和三条急救句",
    "prompt_focus": "心理复盘急救卡",
}
```

Assert payload `body` is concise, does not contain the long narrative paragraph, and the plan metadata remains present.

**Step 6: Verify RED**

Run the specific payload test. Expected: FAIL because `_build_note_card_image_payload()` passes the long body summary through.

**Step 7: Implement payload copy selection**

Add small helpers in `run_playbook.py`:
- normalize plan fields
- decide whether copy should be low density
- derive compact local image body from `prompt_focus`, `image_text`, and short body lines

For low-density roles, cap body to `max_text_units` short lines and avoid long paragraphs.

**Step 8: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q
```

Expected: PASS.

### Task 4: Enforce Low-Density Rendering In Local Note Backend

**Files:**
- Modify: `tests/unit/infrastructure/images/test_note_card_backend.py`
- Modify: `src/ptsm/infrastructure/images/note_card_backend.py`

**Step 1: Write failing helper test**

Add a test around a small renderer helper using a payload with:
- `style=iphone_notes_v1`
- long psychology `body`
- `image_plan.role=save_tool`
- `image_plan.text_density=low`
- `image_plan.max_text_units=3`

Assert the selected display body has no more than three non-empty lines and excludes the long paragraph.

**Step 2: Verify RED**

Run the helper test. Expected: FAIL because the helper does not exist or returns the full body.

**Step 3: Implement display-body helper**

Add a private helper such as `_select_display_body(payload)` and use it in `_render_note_card()` and `_render_iphone_notes()`. Keep renderer output dimensions and style names unchanged.

Rules:
- low-density roles only render short lines
- `save_tool` prefers compact tool lines
- fallback behavior for older payloads remains unchanged enough to avoid breaking existing tests

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py -q
```

Expected: PASS.

### Task 5: Update Skill And Source-Of-Truth Docs

**Files:**
- Modify: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`
- Modify: `docs/runtime.md`
- Modify: `docs/skills.md`
- Modify: `docs/observability.md`
- Modify: `docs/xhs-topics/index.md`
- Create: `docs/xhs-topics/image-forms-by-domain.md`
- Modify: `tests/unit/docs/test_docs_map.py`

**Step 1: Write failing docs test**

Update docs map tests to assert:
- `xhs_image_strategy` documents `role`, `text_density`, and `max_text_units`
- runtime docs explain low-density local renderer behavior
- observability docs mention these fields in artifacts
- XHS topics index links `image-forms-by-domain.md`

**Step 2: Verify RED**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

Expected: FAIL because docs do not yet mention the new role/density contract.

**Step 3: Update docs and skill**

Update the skill so the drafting agent must treat image strategy as:
1. image role
2. text density
3. backend/style

Document simple domain guidance:
- psychology: one question, one felt scene, or a 3-line tool card
- English: phrase card or chat-like contrast
- AI/tech/news: annotated evidence or one key contrast, provider image when real interface/device matters
- food/craft/sushi: real process/detail photos, not text posters unless no visual proof exists
- wuxia/fiction: atmosphere/character visual through provider image

Add `docs/xhs-topics/image-forms-by-domain.md` as a concise cross-domain guide.

**Step 4: Verify GREEN**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

Expected: PASS.

### Task 6: End-To-End Verification, Merge, Push

**Files:**
- No new code expected.

**Step 1: Run targeted suite**

Run:

```bash
uv run pytest tests/unit/infrastructure/images/test_note_card_backend.py tests/unit/infrastructure/llm/test_factory.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS.

**Step 2: Dry run psychology cover**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook --scene "下班路上反复复盘会议上说错的那句话" --account-id acct-psychology-local --playbook-id modern_psychology_post --auto-generate-image
```

Expected:
- artifact contains `content_review.image_plan` and `image_generation.image_plan`
- plan includes `role`, `text_density`, `max_text_units`
- generated local image is 3:4 PNG and uses concise visible copy

**Step 3: Run harness-check**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: PASS. If `origin/main` is unavailable, rerun with the project-supported fallback and document the exact command.

**Step 4: Merge back to main**

Check main worktree status first:

```bash
git -C /Users/wudalu/llm-app/ptsm status --short
```

If main has unrelated dirty files, do not overwrite them. Merge only when safe:

```bash
git -C /Users/wudalu/llm-app/ptsm switch main
git -C /Users/wudalu/llm-app/ptsm merge --no-ff feature/xhs-image-role-strategy
```

Expected: merge completes without losing unrelated user changes.

**Step 5: Push**

Run:

```bash
git -C /Users/wudalu/llm-app/ptsm push
```

Expected: branch `main` pushes successfully.

**Step 6: Final report**

Report:
- changed behavior
- dry-run artifact/image path
- verification commands and results
- merge/push result
