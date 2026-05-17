# Image Strategy Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make image generation strategy a first-class Xiaohongshu skill so the drafting LLM can actively choose local social screenshot covers or provider-generated images per theme, instead of treating local rendering as only a provider fallback.

**Architecture:** Keep image rendering adapters in `src/ptsm/infrastructure/images`, keep publish-time backend selection in `src/ptsm/application/use_cases/run_playbook.py`, and keep the new strategy guidance as a builtin skill under `src/ptsm/skills/builtin/xhs_image_strategy/`. The executor may output an optional structured `final_content.image_plan`; finalize and image generation should normalize and persist that plan for review and artifact evidence.

**Tech Stack:** Python 3.11, pytest, LangChain JSON parsing helpers, Pillow local renderer, PTSM builtin skill registry, YAML playbook definitions, `uv run python -m ptsm.bootstrap harness-check`.

## Current Docs Summary

- `docs/development-workflow.md` requires larger runtime/skill work to happen in an isolated worktree, with a dated plan, task-level `verify:` / `done_when:`, source-of-truth doc updates, an end-to-end smoke path, and `harness-check` before merge.
- `docs/harness-engineering.md` treats repository docs, deterministic pytest, docs-sync, runtime evidence, and local-first XHS pattern library artifacts as the harness backbone.
- `docs/architecture.md` currently says provider-backed image generation is orchestrated by `application/use_cases/run_playbook.py` and rendered by infrastructure adapters. It also currently describes `PlaybookRequest.local_image_style` as fallback-only, which this change must update.
- `docs/runtime.md` currently says auto image generation prefers provider backends and only falls back to local note-card PNGs when providers are missing. It must be updated so `final_content.image_plan` and manual `--local-image-style` can deliberately select local rendering even when a provider is configured.
- `docs/skills.md` says builtin skills are request-scoped prompt assets loaded through playbook `required_skills`. The new `xhs_image_strategy` should be a static strategy skill, not a side-effecting renderer.
- `docs/observability.md` already documents `image_generation` evidence and local styles. It must add backend-decision metadata so future runs can answer why local or provider images were chosen.
- `docs/operations/local-runbook.md` currently documents local styles as provider-missing fallback. It must document `--local-image-style` as an explicit local override and explain the automatic strategy path.

## Task 1: Preserve And Surface Structured Image Plan

**Files:**
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Test: `tests/unit/infrastructure/llm/test_factory.py`
- Test: `tests/unit/agent_runtime/test_finalize_node.py`

**Step 1: Write failing parser test**

Add a test showing `_parse_json_payload()` preserves an optional `image_plan` object:

```python
def test_parse_json_payload_preserves_optional_image_plan() -> None:
    payload = _parse_json_payload(
        '{"title":"t","image_text":"i","body":"b","hashtags":["#x"],'
        '"image_plan":{"backend":"local_social_screenshot","style":"wechat_chat","reason":"聊天截图更像真实发帖"}}'
    )
    assert payload["image_plan"]["backend"] == "local_social_screenshot"
    assert payload["image_plan"]["style"] == "wechat_chat"
```

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_parse_json_payload_preserves_optional_image_plan -q`

Expected: FAIL because `_parse_json_payload()` drops optional fields.

**Step 2: Write failing deterministic image plan test**

Add a test showing `DeterministicDraftBackend` emits `image_plan` when the static context contains `XHS Image Strategy` and the scene is chat/screenshot-shaped:

```python
def test_deterministic_backend_emits_local_chat_image_plan_when_strategy_skill_loaded() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="领导18:57发在吗让我补材料",
        skill_contents=["# XHS Image Strategy\n输出 image_plan。"],
    )
    assert draft["image_plan"]["backend"] == "local_social_screenshot"
    assert draft["image_plan"]["style"] == "wechat_chat"
```

Run: `uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_backend_emits_local_chat_image_plan_when_strategy_skill_loaded -q`

Expected: FAIL because deterministic drafts do not emit `image_plan`.

**Step 3: Write failing finalize review test**

Add a test showing `content_review.image_plan` mirrors normalized final content strategy:

```python
assert result["content_review"]["image_plan"]["backend"] == "local_social_screenshot"
assert result["content_review"]["image_plan"]["style"] == "wechat_chat"
```

Run: `uv run pytest tests/unit/agent_runtime/test_finalize_node.py::test_finalize_adds_image_plan_review_when_final_content_contains_plan -q`

Expected: FAIL because finalize ignores `final_content.image_plan`.

**Step 4: Implement minimal parser and deterministic support**

- Update `XHS_DRAFT_SYSTEM_PROMPT` and `_build_deepseek_hard_requirements()` to allow an optional `image_plan`.
- Preserve `payload["image_plan"]` only when it is a dict.
- Add a small deterministic helper that emits:
  - `backend: local_social_screenshot`, `style: wechat_chat` for after-hours leader/chat scenes.
  - `backend: local_social_screenshot`, `style: iphone_notes` for note/checklist/tool scenes.
  - `backend: provider_image` for real object/process visual scenes where local screenshot is not the right fit.
- Only add deterministic `image_plan` when the image strategy skill appears in static context.
- Add `content_review.image_plan` in finalize when `final_content.image_plan` is present.

verify: `uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/agent_runtime/test_finalize_node.py -q`

done_when: parser preserves optional image plans, deterministic dry-runs can prove local chat selection, and artifacts expose reviewable strategy metadata.

## Task 2: Route Image Generation By Image Plan

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing local-over-provider test**

Add a test where settings include an external image backend, `auto_generate_images=True`, and `final_content.image_plan` requests local WeChat screenshot. Assert local renderer is used:

```python
assert result["image_generation"]["provider"] == "local_note_card"
assert result["image_generation"]["style"] == "wechat_chat_v1"
assert result["image_generation"]["image_plan"]["selected_backend"] == "local_note_card"
```

Run the single test.

Expected: FAIL because current code uses provider whenever one is configured.

**Step 2: Write failing provider-plan test**

Add a test where `image_plan.backend == "provider_image"` and an external backend exists. Assert the provider backend is used and the provider prompt mentions the image plan summary.

Expected: FAIL if routing metadata or prompt plan summary is absent.

**Step 3: Write failing manual override test**

Add or update a test showing `PlaybookRequest(local_image_style="iphone_notes")` forces local rendering even with provider settings configured.

Expected: FAIL because local style currently only affects local fallback.

**Step 4: Implement backend decision helper**

Add a small private helper in `run_playbook.py`:

- manual `request.local_image_style` wins and selects `local_note_card`.
- `final_content.image_plan.backend` values `local_social_screenshot`, `local_note_card`, or `local` select `NoteCardImageBackend`.
- `final_content.image_plan.backend` values `provider_image`, `provider`, or `external` select the configured external backend when present.
- missing plan preserves current behavior: provider if configured, otherwise local note-card.
- provider requested but unavailable falls back to local note-card with `fallback_reason`.

Persist `image_generation["image_plan"]` with `source`, `requested_backend`, `selected_backend`, `requested_style`, `reason`, and optional `fallback_reason`.

verify: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q`

done_when: local rendering can be selected deliberately by request or LLM plan, provider paths remain compatible, and image generation artifacts explain the decision.

## Task 3: Add XHS Image Strategy Skill And Wire Playbooks

**Files:**
- Create: `src/ptsm/skills/builtin/xhs_image_strategy/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/playbook.yaml`
- Test: `tests/unit/skills/test_skill_registry.py`
- Test: `tests/unit/skills/test_selector.py`
- Test: `tests/unit/playbooks/test_playbook_registry.py`
- Test: `tests/unit/agent_runtime/test_planner_node.py`

**Step 1: Write failing registry test**

Assert `xhs_image_strategy` is discovered with `platform_tags == ["xiaohongshu"]`.

Expected: FAIL because the skill does not exist.

**Step 2: Write/update failing playbook and selector expectations**

Update exact `required_skills` expectations to include `xhs_image_strategy` for every Xiaohongshu playbook.

Expected: FAIL until YAML definitions include the skill.

**Step 3: Add the skill document**

The skill should:

- Be static, side-effect free, and platform-scoped to `xiaohongshu`.
- Tell the drafting backend to output optional `image_plan`.
- Define backend choices `local_social_screenshot` and `provider_image`.
- Define local styles `wechat_chat`, `iphone_notes`, and `note_card`.
- Choose local screenshots for chat records, note memos, checklist/tool cards, copyable templates, and strong text-native posts.
- Choose provider images for real objects, spaces, process visuals, materials, and mood references where a generated photo-style image is useful.
- Forbid hashtags, watermarks, dense small text, and fake factual evidence on images.

**Step 4: Wire every XHS playbook**

Add `xhs_image_strategy` to each playbook's `required_skills`.

verify: `uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py tests/unit/agent_runtime/test_planner_node.py -q`

done_when: the planner loads the image strategy skill for every current XHS playbook, and deterministic drafting receives the strategy context.

## Task 4: Update Source-Of-Truth Docs And Smoke Evidence

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/skills.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_docs_map.py`

**Step 1: Update docs**

Document:

- local renderer is first-class and can be LLM-selected.
- `--local-image-style` is an explicit local override.
- `xhs_image_strategy` is the shared XHS skill for image backend/style decisions.
- artifacts persist `content_review.image_plan` and `image_generation.image_plan`.
- provider-generated images remain the right choice for real object/process visuals.

verify: `uv run pytest tests/unit/docs/test_docs_map.py -q`

done_when: active docs match code behavior and docs map tests pass.

## Task 5: End-To-End Verification And Merge

**Files:**
- No planned source edits unless verification exposes a bug.

**Step 1: Run targeted suite**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py tests/unit/agent_runtime/test_planner_node.py tests/unit/docs/test_docs_map.py -q
```

done_when: all targeted tests pass.

**Step 2: Run dry-run smoke for 发疯文学**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --playbook-id fengkuang_daily_post \
  --account-id acct-fk-local \
  --scene "领导18:57发在吗让我补材料" \
  --publish-mode dry-run \
  --auto-generate-image
```

Expected: JSON `status == "completed"`, `image_generation.provider == "local_note_card"`, `style == "wechat_chat_v1"`, and `image_generation.image_plan.source` is `llm_image_plan` or deterministic equivalent.

done_when: dry-run proves the new active local routing path without real publish side effects.

**Step 3: Run repo and harness gates**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap docs-sync --base-ref main
uv run python -m ptsm.bootstrap harness-check --base-ref main
```

done_when: repo tests and harness pass inside the feature worktree.

**Step 4: Merge and push**

From main workspace after verification:

```bash
git checkout main
git merge feat/image-strategy-skill
git push
```

done_when: `main` contains the feature and is pushed to origin.
