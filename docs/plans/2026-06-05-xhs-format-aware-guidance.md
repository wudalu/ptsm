# XHS Format-Aware Guidance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Put the XHS/Douyin hot-post insight into PTSM's topic guidance and drafting flow so `guide-post` returns post-shape guidance and `run-playbook --topic-direction-id` injects the confirmed direction into generation context.

**Architecture:** Keep wrappers thin. PTSM owns format-aware guidance in `ptsm.domain.topic_guidance` and `application/use_cases/guide_post.py`; generation receives selected direction details through application-layer runtime context, not by duplicating strategy in OpenClaw skills. No new playbook/domain is added in this change.

**Tech Stack:** Python 3.12, dataclasses, pytest, PTSM `guide-post`, deterministic `run-playbook`, docs-sync, harness-check.

## Current Docs Summary

- `docs/development-workflow.md` requires this major runtime/skill behavior work to use an isolated worktree, a dated plan, task-level `verify:` / `done_when:`, source-of-truth docs updates, and final `harness-check`.
- `docs/architecture.md` says `guide-post` stays application-layer and read-only; wrappers must not copy topic/image strategy. It also says `PlaybookRequest.topic_direction_id` currently writes handoff metadata and does not change routing or selection logic.
- `docs/runtime.md` says `guide-post` returns directions and `image_recommendation`, while `run-playbook` generation reads scene, playbook/persona prompts, static skills, and runtime skill contexts.
- `docs/playbooks.md` and `docs/skills.md` already encode XHS short-title, scene-first, saveable-unit, comment-handoff, and low-density image strategy requirements. This change should strengthen the handoff rather than add duplicate per-wrapper prompt text.
- `docs/operations.md` already exposes `guide-post`, `run-playbook --topic-direction-id`, metrics grouping by `topic_direction_id`, and XHS experiment commands.
- `docs/harness-engineering.md` says tests already cover topic guidance, image recommendations, topic-direction persistence, docs wrapper contracts, deterministic dry-runs, and metrics grouping. New behavior should extend that harness surface.

## Scope

- Add structured `format_recommendation` to public topic directions.
- Make `guide-post` Markdown/JSON and OpenClaw wrapper docs expose the returned format fields without inventing strategy.
- Resolve selected `topic_direction_id` inside `run_playbook()` and inject direction summary into runtime context before drafting.
- Persist selected direction details in `topic_selection` for artifacts and metrics review.
- Update current source-of-truth docs.

## Non-Goals

- No tenth playbook.
- No live XHS/Douyin scan in normal generation.
- No real publish.
- No wrapper-side copy of scoring, trend ranking, or post-shape strategy.
- No broad refactor of the topic pack dataset beyond targeted format metadata.

### Task 1: Add Format Recommendation To Topic Direction Payload

**Files:**
- Modify: `src/ptsm/domain/topic_guidance.py`
- Test: `tests/unit/domain/test_topic_guidance.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write failing tests**

Add assertions that every public `TopicDirection` includes:

```python
format_recommendation = direction["format_recommendation"]
assert format_recommendation["format_archetype"] in {
    "note_card",
    "carousel",
    "chat_screenshot",
    "provider_scene",
}
assert format_recommendation["cover_role"]
assert format_recommendation["body_shape"]
assert format_recommendation["visual_evidence_need"] in {"none", "low", "high"}
assert "dense_text_poster" in format_recommendation["avoid_format"]
```

Also assert:

- a human-enrichment material/handcraft scene returns `provider_scene` or `carousel` with `visual_evidence_need == "high"`;
- a psychology sleep recovery scene returns `note_card` with `cover_role == "save_tool"`;
- CLI JSON includes this nested field.

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest -q tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -k "format_recommendation or guide_post or topic_guidance"
```

Expected: FAIL because `format_recommendation` is missing.

**Step 3: Implement minimal behavior**

Add a frozen dataclass such as:

```python
@dataclass(frozen=True)
class FormatRecommendation:
    format_archetype: str = "note_card"
    cover_role: str = "cover_hook"
    body_shape: str = "scene -> saveable_tool -> comment_prompt"
    visual_evidence_need: str = "low"
    avoid_format: str = "dense_text_poster"
```

Add `format_recommendation: FormatRecommendation = field(default_factory=FormatRecommendation)` to `TopicDirection`.

Update `public_topic_direction()` to serialize it as a nested dict.

Add heuristic format defaults for open-scene directions so generated directions also include the field:

- message/reply/comment-chain mechanisms -> `chat_screenshot`
- save-card/checklist/prompt/steps -> `note_card`
- material/space/route/process/object facets -> `provider_scene` or `carousel`
- world-cup/checklist -> `carousel`

Set targeted curated directions where needed:

- `enrichment_handmade_material_flow` -> `carousel`, `visual_evidence_need=high`, `cover_role=evidence_or_scene`
- `enrichment_route_colorwalk` -> `provider_scene`, `visual_evidence_need=high`
- `sleep_recovery_shutdown_card` -> `note_card`, `cover_role=save_tool`
- `ai_prompt_context_card` -> `note_card`, `cover_role=save_tool`
- Sushi/culture route directions that emphasize place/object -> `provider_scene` or `carousel`

**Step 4: Run tests to verify GREEN**

Run the same targeted command.

**verify:** targeted pytest command exits 0.

**done_when:** all public topic directions, including open-scene directions, include stable `format_recommendation`; application and CLI guide-post JSON expose it.

### Task 2: Inject Confirmed Direction Details Into Drafting Context

**Files:**
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Possibly modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write failing tests**

Add a test for non-psychology direction context:

```python
result = run_playbook(
    PlaybookRequest(
        scene="把手作材料摊开，先做十分钟就停",
        account_id="acct-enrichment-local",
        playbook_id="human_enrichment_daily_post",
        topic_direction_id="enrichment_handmade_material_flow",
        publish_mode="dry-run",
    )
)
assert result["topic_selection"]["topic_direction_id"] == "enrichment_handmade_material_flow"
assert result["topic_selection"]["direction"]["saveable_tool"] == "材料 / 十分钟动作 / 停止点"
assert result["topic_selection"]["direction"]["format_recommendation"]["format_archetype"] == "carousel"
```

Assert the artifact step/runtime evidence contains a runtime skill context or topic-selection context string with:

- the direction id;
- `content_angle`;
- `saveable_tool`;
- `comment_prompt`;
- `format_recommendation`.

Add a psychology case for `sleep_recovery_shutdown_card` so both pack-backed and psychology-authored directions resolve.

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest -q tests/unit/application/use_cases/test_run_playbook.py -k "topic_direction"
```

Expected: FAIL because only `topic_direction_id` is persisted and no direction details/runtime context exist.

**Step 3: Implement minimal behavior**

Add application-layer helpers:

- `resolve_topic_direction_for_playbook(playbook_id, scene, topic_direction_id)` or equivalent;
- resolve against `TOPIC_GUIDANCE_PACKS[playbook_id].directions` for non-psychology;
- resolve against `PSYCHOLOGY_TOPIC_DIRECTIONS` for `modern_psychology_post`;
- when no exact id exists, return id-only metadata and do not fail generation.

Build a public-safe direction context string:

```text
# Confirmed Topic Direction
direction_id: ...
name: ...
direction_type: ...
content_angle: ...
saveable_tool: ...
comment_prompt: ...
avoid: ...
format_archetype: ...
cover_role: ...
body_shape: ...
visual_evidence_need: ...
avoid_format: ...
```

Inject it into the `runtime_skill_contents` or equivalent drafting context path before calling the workflow. Persist the public-safe selected direction in `topic_selection.direction`.

**Step 4: Run tests to verify GREEN**

Run the same targeted command.

**verify:** `uv run pytest -q tests/unit/application/use_cases/test_run_playbook.py -k "topic_direction"` exits 0.

**done_when:** selected direction details are artifact-backed and generation context contains format-aware guidance for exact direction ids without breaking id-only fallback.

### Task 3: Strengthen Topic Packs With The New Insight

**Files:**
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py` only if psychology directions need explicit format metadata
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write failing tests**

Add/extend tests for the insight-driven lanes:

- human enrichment `拼豆 / 手作材料 / 钩织` scene returns a direction with `format_archetype in {"carousel", "provider_scene"}` and `visual_evidence_need == "high"`;
- Sushi/poetry `古诗词里的中国 / 地方文化 / 旅行` scene returns a culture/place direction and visual evidence format;
- AI prompt scene returns `format_archetype == "note_card"` and `body_shape` mentions prompt handoff;
- psychology light-wellness/sleep recovery returns low-density save-tool format.

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest -q tests/unit/application/use_cases/test_guide_post.py -k "enrichment or sushi or prompt or sleep_recovery"
```

Expected: FAIL until topic pack/direction metadata covers these cases.

**Step 3: Implement minimal pack updates**

Add only targeted lanes/directions:

- Human enrichment: `拼豆/钩织/手作过程` as a sublane/direction if current handcraft direction is too generic.
- Sushi: culture/place/route framing as sublane/direction, still under `sushi_poetry_daily_post`.
- AI: keep prompt cards under `ai_tech_daily_post`; update format metadata, not playbook routing.
- Psychology: keep sleep/light wellness as sublane; format metadata only.

**Step 4: Run tests to verify GREEN**

Run the same targeted command.

**verify:** targeted guide-post tests pass.

**done_when:** `guide-post` turns the user-facing insight into concrete direction choices and post-form guidance without adding a playbook or exposing raw research.

### Task 4: Update Wrapper Skills And Source-Of-Truth Docs

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/harness-engineering.md`
- Test: `tests/unit/docs/test_openclaw_topic_guide_skill.py`
- Test: `tests/unit/docs/test_openclaw_skill.py`
- Test: docs metadata/map tests

**Step 1: Write failing docs tests**

Update wrapper docs tests to require display of `topic_guidance.directions[].format_recommendation` and explicit no-invention guard:

```python
assert "format_recommendation" in text
assert "Do not invent" in text
```

**Step 2: Run tests to verify RED**

Run:

```bash
uv run pytest -q tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/docs/test_openclaw_skill.py
```

Expected: FAIL until wrapper docs mention the new field.

**Step 3: Update docs**

Document:

- `guide-post` now returns format recommendation per direction.
- `run-playbook --topic-direction-id` resolves and injects selected direction details into drafting context.
- `format_recommendation` is operator-visible, but wrappers must not invent or alter it.
- This is a sublane/format enhancement, not a new domain.

**Step 4: Run docs tests and docs-sync**

Run:

```bash
uv run pytest -q tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/domain/topic_guidance.py --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py --changed-path src/ptsm/application/use_cases/run_playbook.py --changed-path integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/operations.md --changed-path docs/harness-engineering.md
```

**verify:** docs tests and docs-sync exit 0.

**done_when:** all active docs describe the new contract and no wrapper owns strategy.

### Task 5: End-To-End Smoke And Harness Gate

**Files:**
- No new files expected beyond implementation/docs.

**Step 1: Run guide-post JSON smoke**

Run:

```bash
uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "拼豆上也可以作画了，想写一条十分钟手作过程小红书" --non-interactive --format json
```

Expected: JSON includes `topic_guidance.directions[0].format_recommendation` and image recommendation.

**Step 2: Run deterministic dry-run with confirmed direction**

Run:

```bash
DEFAULT_LLM_PROVIDER=deterministic uv run python -m ptsm.bootstrap run-playbook --caller openclaw --scene "拼豆上也可以作画了，想写一条十分钟手作过程小红书" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --topic-direction-id enrichment_handmade_material_flow --publish-mode dry-run
```

Expected: `status == completed`, `topic_selection.direction.format_recommendation` present, and artifact preserves direction metadata.

**Step 3: Run targeted tests**

Run:

```bash
uv run pytest -q tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/docs/test_openclaw_skill.py
```

**Step 4: Run full local tests**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 5: Run final harness-check**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**verify:** all commands exit 0.

**done_when:** guide-post, dry-run, targeted tests, full tests, docs-sync, and harness-check prove format-aware guidance reaches both selection and generation surfaces.

## Implementation Notes

- Added `FormatRecommendation` to public topic directions and serialized it for curated and open-scene directions.
- Added explicit format metadata for human enrichment visual-first directions, AI prompt cards, psychology boundary cards, and sleep recovery shutdown cards.
- Updated `guide-post` JSON/Markdown and OpenClaw wrapper contracts to expose `format_recommendation` without wrapper-side invention.
- Changed `run_playbook --topic-direction-id` from id-only metadata to a generation handoff: it resolves the public direction payload, writes `topic_selection.direction`, preserves it in response/run/artifact metadata, and planner injects `# XHS Topic Direction Guidance` into runtime contexts before drafting.
- Updated active local Codex skill copies at `/Users/wudalu/.codex/skills/ptsm-xhs-topic-guide/SKILL.md` and `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md` to match the repo wrapper contract.

## Verification Results

```bash
uv run pytest -q tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -k "format_recommendation or guide_post or topic_guidance"
uv run pytest -q tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_injects_selected_topic_direction_into_workflow_and_artifact tests/unit/agent_runtime/test_ingest_node.py tests/unit/agent_runtime/test_planner_node.py::test_planner_adds_topic_direction_guidance_runtime_context
uv run pytest -q tests/unit/application/use_cases/test_guide_post.py::test_format_guide_post_markdown_includes_scene_fit tests/unit/docs/test_openclaw_topic_guide_skill.py::test_openclaw_topic_guide_skill_shows_only_returned_direction_fields tests/unit/docs/test_openclaw_skill.py::test_openclaw_psychology_skill_documents_two_step_guidance_flow
uv run pytest -q tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/agent_runtime/test_ingest_node.py tests/unit/agent_runtime/test_planner_node.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/domain/topic_guidance.py --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/application/use_cases/run_playbook.py --changed-path src/ptsm/agent_runtime/state.py --changed-path src/ptsm/agent_runtime/nodes/ingest.py --changed-path src/ptsm/agent_runtime/nodes/planner.py --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md --changed-path integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md --changed-path docs/harness-engineering.md --changed-path tests/unit/domain/test_topic_guidance.py --changed-path tests/unit/application/use_cases/test_guide_post.py --changed-path tests/unit/application/use_cases/test_run_playbook.py --changed-path tests/unit/agent_runtime/test_ingest_node.py --changed-path tests/unit/agent_runtime/test_planner_node.py --changed-path tests/unit/interfaces/cli/test_main.py --changed-path tests/unit/docs/test_openclaw_skill.py --changed-path tests/unit/docs/test_openclaw_topic_guide_skill.py
uv run python -m ptsm.bootstrap guide-post --playbook-id human_enrichment_daily_post --account-id acct-enrichment-local --scene "想把书桌角落改成十分钟适我主义手作位" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --scene "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出" --non-interactive --format json
uv run python -m ptsm.bootstrap run-playbook --scene "把书桌改成十分钟手作角" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --topic-direction-id enrichment_desk_corner_variable --publish-mode dry-run
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check
```

All verification commands exited 0.
