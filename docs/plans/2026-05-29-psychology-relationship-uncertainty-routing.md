# Psychology Relationship Uncertainty Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make intimate relationship waiting-message scenes route to relationship uncertainty / catastrophizing content instead of workplace-like message-boundary replies.

**Architecture:** Keep the change inside the existing modern psychology guidance and deterministic draft surfaces. Add one curated topic direction and one lane cue for romantic uncertainty, adjust the image recommendation guard so these scenes use a saveable notes card, and add a deterministic draft branch that writes the breakup/cat-custody scene as relationship uncertainty rather than collaboration pressure.

**Tech Stack:** Python 3.12, pytest, PTSM CLI, existing deterministic draft backend and `guide-post` topic selector.

## Current Docs Summary

- `docs/index.md` says content strategy work starts from `playbooks.md`, `skills.md`, and related topic docs, with runtime and operations docs used for command behavior.
- `docs/development-workflow.md` requires an isolated worktree, baseline tests, a plan under `docs/plans/`, task-level verification, docs updates, and final harness verification for runtime/playbook behavior changes.
- `docs/playbooks.md` and `docs/skills.md` define `modern_psychology_post` as a life-account style psychology playbook: concrete title moments, one light mechanism, optional saveable tool, role/camp/fill-in comment prompt, no diagnosis or treatment promises, and 260-580 char body.
- `docs/runtime.md` says `guide-post` is a deterministic pre-generation topic surface with dynamic scene reranking and image recommendation; deterministic modern psychology drafts must vary by lane and avoid mechanism-first titles.
- `docs/operations.md` already exposes `guide-post` and `run-playbook --caller openclaw --guidance-ack` commands for the exact scene: `他3小时没回消息，我已经想好分手后猫归谁了`.

## Task 1: Lock The Guide-Post Routing Regression

**Files:**
- Modify test: `tests/unit/application/use_cases/test_guide_post.py`

**Steps:**
1. Add a failing unit test for `他3小时没回消息，我已经想好分手后猫归谁了`.
2. Assert the brief lane/mechanism/save tool are `亲密关系 / 不确定感`, `关系不确定感`, and `事实 / 脑补 / 我需要什么`.
3. Assert `matched_direction_id == "relationship_uncertainty_waiting_message"` and the first direction is not `message_boundary_reply_draft`.
4. Assert the image recommendation is `local_social_screenshot` + `iphone_notes` + `save_tool`.
5. Assert the recommended scene does not include work-style reply wording such as `我现在不方便` or `处理`.

verify:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_romantic_waiting_to_uncertainty -q
```

done_when: the test fails before implementation for the current misrouting.

## Task 2: Implement Minimal Guide-Post Routing

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`

**Steps:**
1. Add a `PsychologyLane` before generic `关系边界 / 消息压力` for `亲密关系 / 不确定感`.
2. Add a curated `TopicDirection` before `message_boundary_reply_draft` with id `relationship_uncertainty_waiting_message`.
3. Add romantic uncertainty keywords: `分手`, `猫归谁`, `没回消息`, `不回消息`, `3小时`, `挽留`, `复合`, `冷淡`, `伴侣`.
4. Adjust `_build_image_recommendation()` so this lane/tool returns `iphone_notes` before the generic chat keyword branch.
5. Preserve `wechat_chat` for true reply assets like `朋友半夜发来一大段消息，我想写一版不被掏空的回复`.

verify:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_romantic_waiting_to_uncertainty -q
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_recommends_wechat_for_message_reply_assets -q
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_does_not_collapse_relationship_scenes -q
```

done_when: romantic waiting routes to the new direction and notes tool while existing message-reply assets still use `wechat_chat`.

## Task 3: Lock The Deterministic Draft Tone Regression

**Files:**
- Modify test: `tests/unit/infrastructure/llm/test_factory.py`

**Steps:**
1. Add a failing deterministic draft test for `他3小时没回消息，我已经想好分手后猫归谁了`.
2. Assert the title keeps a concrete romantic moment and avoids mechanism terms.
3. Assert the body contains the exact scene and `事实`, `脑补`, `我需要`.
4. Assert `关系不确定感` or `不确定感` appears at most once and after the scene is underway.
5. Assert the combined title/image/body excludes work-like reply wording: `你这边`, `多久能回`, `我现在不方便`, `处理`, `优先级`, `工位`, `客户`, `领导`.
6. Assert body length stays within 350-580 chars, includes professional help boundary, and uses an A/B comment prompt.

verify:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_keeps_romantic_waiting_scene_out_of_work_reply_mode -q
```

done_when: the test fails before implementation.

## Task 4: Implement Minimal Deterministic Draft Branch

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`

**Steps:**
1. Add the relationship uncertainty branch before generic boundary/message branches.
2. Write body shape: quiet phone, mind jumps to breakup logistics, one light `关系不确定感` mention, `事实 / 脑补 / 我需要什么` tool, safety boundary, and A/B comment prompt.
3. Add prompt-asset rules saying intimate waiting/breakup/reconciliation/cat-custody scenes must not become workplace collaboration replies, processing-time negotiation, or generic boundary sentences.

verify:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_keeps_romantic_waiting_scene_out_of_work_reply_mode -q
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_varies_by_scene_mechanic -q
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_has_mini_tool_and_example_prompt -q
```

done_when: romantic scene no longer contains workplace reply wording and existing deterministic lanes still pass.

## Task 5: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`

**Steps:**
1. Document that `modern_psychology_post` distinguishes intimate relationship uncertainty from generic message-boundary replies.
2. Mention the representative guide/dry-run scene now routes to `事实 / 脑补 / 我需要什么`.
3. Keep non-changing architecture/operations surfaces explicit in the handoff.

verify:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

done_when: docs metadata and map tests pass.

## Task 6: End-To-End Verification

**Files:**
- No new production files unless verification exposes a bug.

**Steps:**
1. Run targeted unit tests for guide and deterministic draft behavior.
2. Run `guide-post` smoke for the exact scene.
3. Run deterministic `run-playbook --caller openclaw --guidance-ack` dry-run for the exact scene.
4. Run full pytest and local docs/harness gates.

verify:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/infrastructure/llm/test_factory.py -q
uv run python -m ptsm.bootstrap guide-post --scene "他3小时没回消息，我已经想好分手后猫归谁了" --non-interactive --format json
DEFAULT_LLM_PROVIDER=deterministic uv run python -m ptsm.bootstrap run-playbook --caller openclaw --guidance-ack --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/infrastructure/llm/contextual_drafts.py --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/planner.md --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/persona.md --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/runtime.md --changed-path docs/operations.md --changed-path docs/harness-engineering.md
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when: tests and gates pass, or any external-environment warning is reported precisely.
