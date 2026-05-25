# Topic Guidance Image Advice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PTSM-owned image generation recommendations to `guide-post` so OpenClaw/Codex can recommend local screenshot vs LLM/provider image, the preferred LLM image model, and the preferred local style after the user chooses a topic direction.

**Architecture:** Keep OpenClaw/Codex wrapper skills thin. `guide-post` will return structured `image_recommendation` metadata derived from the resolved playbook, lane, scene, and current brief image form; wrappers display this returned recommendation after direction confirmation and do not invent image strategy. `run-playbook` image generation remains unchanged and continues to consume `--local-image-style` and downstream `final_content.image_plan`.

**Tech Stack:** Python 3.12, dataclasses/dicts, deterministic heuristics, pytest, Markdown wrapper skills, PTSM CLI `guide-post`, `harness-check`.

## Current Docs Summary

- `docs/development-workflow.md` classifies new skill/runtime-visible behavior as major work: use an isolated worktree, write a plan, add verification before implementation, update source-of-truth docs, and run `harness-check`.
- `docs/runtime.md` and `docs/operations.md` already describe the existing image generation pipeline: `run-playbook` can generate provider images or local social screenshots, local styles are `note_card`, `iphone_notes`, and `wechat_chat`, and generated images request no provider watermark.
- `docs/skills.md` says `xhs_image_strategy` owns drafting-time image planning, while OpenClaw wrapper skills must not copy PTSM topic logic.
- `docs/xhs-topics/image-forms-by-domain.md` is the best source for per-domain image form decisions: `wechat_chat` for messages/replies, `iphone_notes` for save tools, `note_card` for short lines, and provider images for spaces, objects, materials, atmosphere, devices, and evidence/scene visuals.
- Current `guide-post` already returns `brief.image_style` and `brief.image_form`, but it does not give the user a post-selection recommendation that says local vs LLM/provider, model, local style, reason, and command impact.

## Requirements

- Add a structured `topic_guidance.image_recommendation` payload.
- The payload must answer:
  - whether to use local screenshot generation or LLM/provider image generation first
  - which LLM image model/provider to use when provider image is recommended
  - which local style to use when local screenshot is recommended: `wechat_chat`, `note_card`, or `iphone_notes`
  - why this route fits the selected topic/scene
  - which `run-playbook` command flag to use, especially `--local-image-style <style>` for local screenshots
- OpenClaw/Codex skills should show this recommendation after the user chooses or confirms one topic direction.
- Wrappers must not invent or override the recommendation. If the user changes topic direction or scene, rerun `guide-post`.
- No live image generation, no provider call, and no publishing change in this feature.

## Proposed Payload

```json
"image_recommendation": {
  "status": "available",
  "decision_stage": "after_topic_direction_confirmation",
  "recommended_backend": "local_social_screenshot",
  "local_style": "wechat_chat",
  "provider": "",
  "model": "",
  "role": "comment_prompt",
  "text_density": "low",
  "max_text_units": 2,
  "reason": "当前方向核心是消息/回复/评论接龙，微信对话截图比 LLM 氛围图更像可保存首屏。",
  "command_hint": "--local-image-style wechat_chat",
  "fallback": "如果没有明确消息/对话文本，改用 note_card 或 iphone_notes。"
}
```

For provider image recommendations, use:

```json
{
  "recommended_backend": "provider_image",
  "provider": "bailian",
  "model": "qwen-image-2.0-pro",
  "local_style": "",
  "command_hint": "--auto-generate-image"
}
```

## Task 1: Add Red Tests For Image Recommendation

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Add application tests**

Add tests that assert:

- Psychology message/boundary scenes return `image_recommendation.recommended_backend == "local_social_screenshot"` and `local_style == "wechat_chat"` or `iphone_notes` depending on the lane and scene.
- Human enrichment material/space scenes return `recommended_backend == "provider_image"`, `provider == "bailian"`, and `model == "qwen-image-2.0-pro"`.
- Sushi/poetry relationship scenes can stay local `note_card`/`iphone_notes`, while material/process domains use provider image.
- The payload has `decision_stage == "after_topic_direction_confirmation"` and `command_hint`.

**Step 2: Add CLI JSON test**

Update `guide-post` CLI JSON assertions to require `topic_guidance.image_recommendation`.

**Step 3: Run red tests**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: FAIL because `image_recommendation` is not returned yet.

**verify:** Failures are missing-field/assertion failures, not syntax/import errors.

**done_when:** Tests describe the post-direction image recommendation contract.

## Task 2: Implement PTSM-Owned Image Recommendation

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Add a helper**

Add `_build_image_recommendation(playbook_id, lane_name, scene, brief)` returning a public-safe dict.

**Step 2: Implement deterministic routing**

Use these priority rules:

- Message/reply/chat/comment-chain scenes -> local `wechat_chat`, `role=comment_prompt`, `max_text_units=2`.
- Save-tool/checklist/boundary/exercise/English sentence scenes -> local `iphone_notes`, `role=save_tool`, `max_text_units=3`.
- Short poetic line or strong judgment -> local `note_card`, `role=cover_hook`, `max_text_units=1-2`.
- Space/object/material/process/product/device/atmosphere domains -> provider image with `provider=bailian`, `model=qwen-image-2.0-pro`, `role=evidence_or_scene`, `max_text_units=0-1`.
- Respect explicit `brief.image_form` where it already chooses a local style, unless the domain clearly needs provider visuals.

**Step 3: Attach to `topic_guidance`**

Both `build_psychology_topic_guidance` and `build_topic_guidance` should include the recommendation. Prefer passing `playbook_id`, `scene`, `lane_name`, and `brief` from the two `run_guide_post` paths.

**Step 4: Verify green**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: PASS.

**verify:** Payload contains no internal docs paths, source URLs, or provenance.

**done_when:** `guide-post` JSON gives an actionable local/provider image recommendation after topic choice.

## Task 3: Update Markdown And Wrapper Skills

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md`
- Test: `tests/unit/docs/test_openclaw_skill.py`
- Test: `tests/unit/docs/test_openclaw_topic_guide_skill.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Markdown output**

Add an "Image Recommendation" section to Markdown output showing backend, model/style, reason, and command hint.

**Step 2: Wrapper wording**

Update both OpenClaw skills:

- After the user chooses/confirmation a topic direction, show only returned `topic_guidance.image_recommendation`.
- Mention LLM/provider route and model only from PTSM output.
- Mention local style only from PTSM output.
- Do not invent or override image recommendations.

**Step 3: Installed Codex skills**

Mirror wrapper updates to `$CODEX_HOME/skills`.

**Step 4: Verify docs tests**

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/interfaces/cli/test_main.py -q
```

Expected: PASS.

**done_when:** CLI Markdown and wrappers teach the post-direction image recommendation flow.

## Task 4: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Runtime/docs**

Document that `guide-post` now returns `image_recommendation` for post-direction confirmation and that it is advisory/read-only.

**Step 2: Operations/runbook**

Document how operators use `command_hint`, especially `--local-image-style`.

**Step 3: Harness docs**

Document targeted tests for the image recommendation payload and wrapper contract.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**done_when:** Active docs match the new behavior and do not imply that wrappers choose image strategy themselves.

## Task 5: Final Verification And Integration

**Files:**
- Modify: `docs/plans/2026-05-25-topic-guidance-image-advice.md`

**Step 1: CLI smoke**

Run representative `guide-post` JSON commands:

```bash
uv run python -m ptsm.bootstrap guide-post --scene "朋友半夜发来一大段情绪，我想写边界感" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "想把书桌角落改成十分钟手作位" --non-interactive --format json
```

Expected: psychology returns a local screenshot recommendation; human enrichment returns a provider image recommendation.

**Step 2: Full tests**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 3: Harness**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref main
```

**Step 4: Record evidence**

Append red/green/smoke/harness evidence to this plan.

**done_when:** Tests and harness pass, the feature is committed, merged to `main`, and pushed if requested by the user.

## Implementation Evidence

- Red test run:
  - `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`
  - Result: failed as expected with missing `topic_guidance.image_recommendation` and missing wrapper wording.
- Target green run:
  - `uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`
  - Result: passed.
- Docs verification:
  - `uv run pytest tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_architecture_doc.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`
  - Result: passed.
- CLI smoke:
  - Psychology message scene returned `recommended_backend=local_social_screenshot`, `local_style=wechat_chat`, `command_hint=--local-image-style wechat_chat`, and the generated `run_playbook_command_text` used `--local-image-style wechat_chat`.
  - Human enrichment desk-corner scene returned `recommended_backend=provider_image`, `provider=bailian`, `model=qwen-image-2.0-pro`, `command_hint=--auto-generate-image`, and the generated `run_playbook_command_text` did not force a local image style.
- Full non-e2e test run:
  - `uv run pytest -q --ignore=tests/e2e`
  - Result: passed.
- Harness:
  - `uv run python -m ptsm.bootstrap harness-check --base-ref main`
  - Result: `status=ok`; `docs_sync.status=ok`; embedded pytest passed.
