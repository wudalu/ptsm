# Cross-Domain Topic Guidance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the psychology-only `guide-post` topic guidance into a reusable cross-domain Xiaohongshu pre-post guidance surface that can suggest scene-aware, viral-hook-aware topics for multiple playbooks before generation.

**Architecture:** Extract the current psychology topic direction selection into a deterministic candidate-ranking engine with playbook-specific topic packs. Keep live research separate: default guidance uses productized local packs and current playbook knowledge; explicit `--fresh-topic-research` and periodic XHS pattern collection remain the paths for live or periodically refreshed data. Keep OpenClaw wrappers thin: they call PTSM, display returned guidance, and do not own topic logic.

**Tech Stack:** Python 3.12 dataclasses, argparse CLI, pytest, existing PTSM playbook/account registries, Markdown source-of-truth docs, OpenClaw `SKILL.md` wrapper instructions.

## Current Docs Summary

- `docs/index.md` says current source-of-truth docs are the starting point; historical plans and research notes are context only.
- `docs/development-workflow.md` classifies this as major runtime/operator work because it changes a caller-facing guidance contract. Work must happen in an isolated worktree, with a plan, task-level verification, docs updates, and a final harness gate.
- `docs/architecture.md` keeps CLI in `interfaces`, orchestration in `application`, reusable business facts in `domain` / playbook assets, and external wrapper instructions outside builtin skill discovery. A cross-domain guide should not add domain branches to `agent_runtime`.
- `docs/runtime.md` says `run-playbook` is the generation path, while the existing OpenClaw psychology preflight returns read-only guidance before any workflow, run creation, publish, or image side effect. Ordinary generation does not run live XHS / topic-radar scans by default.
- `docs/playbooks.md` lists nine playbooks and documents that all XHS playbooks already share `xhs_image_strategy` and `xhs_human_voice`; domain-specific style and eval contracts stay in playbook/skill assets.
- `docs/skills.md` says `xhs_trend_scan` and `topic_research` provide dynamic context to generation, while `guide-post` currently owns productized psychology directions. The generic guide must reuse this local-first boundary instead of duplicating live MCP logic.
- `docs/xhs-topics/index.md` and `docs/topic-radar.md` separate periodic/live research from ordinary generation. Topic guidance may use productized hook knowledge, but live scans stay opt-in.
- `docs/operations.md` documents `guide-post` as the operator pre-post guide, and `run-playbook` as the actual generation/publish entry point.
- `docs/harness-engineering.md` requires deterministic pytest coverage, docs-sync coverage, and `harness-check` before merge.

## User Need

The current psychology guidance proved useful because it lets an agent or operator choose a topic direction before drafting. The same pattern should work for other domains, especially domains where topic quality depends on hook mechanics, comment participation, and saveability rather than only a raw scene.

## Scope

- Generalize `guide-post` from psychology-only to a playbook-aware topic guidance command.
- Preserve the existing psychology output contract where practical, so current OpenClaw psychology flows continue to work.
- Add first-class topic packs for:
  - `fengkuang_daily_post`
  - `human_enrichment_daily_post`
  - `sushi_poetry_daily_post`
  - existing `modern_psychology_post`
- Add a generic OpenClaw wrapper that works across supported XHS playbooks.
- Keep `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` available as a specialized safety-first wrapper for psychology.
- Update source-of-truth docs and operations examples.

## Review Decisions

- First implementation supports four playbooks: existing `modern_psychology_post`, plus `fengkuang_daily_post`, `human_enrichment_daily_post`, and `sushi_poetry_daily_post`. Later phases can roll the same topic-pack pattern across all XHS playbooks.
- The generic OpenClaw wrapper auto-maps user intent to a supported playbook id when the caller has not already supplied one. If intent is ambiguous, it should ask a short clarification instead of guessing silently.
- A hard runtime preflight gate means `run-playbook --caller openclaw` itself refuses to run unless a prior `guide-post` acknowledgement/token is present. Psychology already needs this stricter gate because it carries extra safety boundaries. Non-psychology playbooks should not get this runtime block in phase one; their generic wrapper should enforce the recommended order by calling `guide-post` first, then dry-run generation.

## Non-Goals

- Do not add new playbooks, accounts, or domains.
- Do not run live XHS MCP, web search, Reddit, or topic-radar scans by default in `guide-post`.
- Do not move generation into the guide. `guide-post` remains read-only and returns a dry-run command.
- Do not broaden hard `run-playbook --caller openclaw` preflight gates beyond psychology in this first implementation. The generic OpenClaw skill enforces call order at the wrapper level; runtime hard-gating other domains can be a later opt-in after usage proves stable.
- Do not expose internal research paths, raw notes, source URLs, or provenance in user-facing guidance.
- Do not make candidate selection random. It must be deterministic for tests and repeatability.

## Proposed Design

Use a source / score / select shape, kept small and deterministic:

1. **Source:** playbook-specific topic packs provide lanes and directions.
2. **Hydrate:** each direction already carries public fields such as `trend_signal`, `viral_hook`, `best_scenes`, `content_angle`, `saveable_tool`, `comment_prompt`, and `avoid`.
3. **Filter:** unsupported playbooks return a clear error with supported ids.
4. **Score:** scene keywords, explicit lane, playbook affinity, evergreen priority, and deterministic hash tie-break.
5. **Select:** return top 4 directions and set `matched_direction_id` to the first selected direction.
6. **Side effects:** none. The command only prints JSON/Markdown and a dry-run `run-playbook` command.

This keeps the system explainable and testable without needing ML ranking or live platform calls.

### Output Contract

`guide-post --non-interactive --format json` should return:

```json
{
  "status": "completed",
  "playbook_id": "human_enrichment_daily_post",
  "account_id": "acct-enrichment-local",
  "brief": {
    "lane": "一平米角落 / 低成本变量",
    "scene": "想写一个书桌角落改造",
    "content_angle": "把生活从惯性里挪出一个小缝",
    "save_tool": "三步变量清单",
    "image_style": "note_card",
    "comment_prompt": "你先想丰容哪个角落？"
  },
  "topic_guidance": {
    "status": "available",
    "matched_direction_id": "enrichment_desk_corner_variable",
    "directions": [
      {
        "id": "enrichment_desk_corner_variable",
        "name": "一平米角落：书桌下班信号",
        "trend_signal": "适我主义 / 新独居",
        "viral_hook": "低成本 before/after",
        "why_it_may_work": "具体角落 + 三步清单容易收藏，也容易让评论区交作业。",
        "best_scenes": ["书桌太像工位", "床头只有充电线", "玄关一进门就很乱"],
        "content_angle": "不是改造整个家，只是给一个角落加一个下班信号。",
        "saveable_tool": "原本惯性 / 一个变量 / 今天能试的一步",
        "comment_prompt": "你先想丰容哪个角落？",
        "avoid": "不要写成购物清单，不要用 AI 图伪装真实改造。"
      }
    ]
  },
  "recommended_scene": "...",
  "run_playbook_command": ["uv", "run", "python", "-m", "ptsm.bootstrap", "run-playbook", "..."],
  "run_playbook_command_text": "uv run python -m ptsm.bootstrap run-playbook ..."
}
```

## Initial Topic Pack Seeds

### `fengkuang_daily_post`

- `fk_work_object_vent`: 职场物件替人发疯；trend `物件发疯 / 抽象力`; hook `评论区补一句`
- `fk_loofah_soup_reply`: 丝瓜汤式复盘；trend `丝瓜汤 / 高雅外壳`; hook `可复制疯话`
- `fk_group_chat_unsent_line`: 群聊没发出去的话；trend `打工人关系角色`; hook `接龙`
- `fk_polite_shell_wild_core`: 体面外壳狼狈内核；trend `高雅外壳 / 活人感`; hook `身份认领`

### `human_enrichment_daily_post`

- `enrichment_desk_corner_variable`: 书桌/工位角落变量；trend `适我主义 / 新独居`; hook `低成本 before/after`
- `enrichment_bedside_shutdown_signal`: 床头下线信号；trend `睡前十分钟`; hook `三步清单`
- `enrichment_route_colorwalk`: 通勤路线微变量；trend `Colorwalk / 低成本行动`; hook `交作业`
- `enrichment_handmade_material_flow`: 手作材料平铺；trend `手作心流`; hook `过程轮播`

### `sushi_poetry_daily_post`

- `sushi_role_pair_huimin`: 苏轼/怀民关系角色；trend `文化力 / 角色认领`; hook `你是 A 还是 B`
- `sushi_old_friend_note`: 旧友旧物里的精神充电；trend `旧物 / 活人感`; hook `评论交一个人`
- `sushi_season_micro_ritual`: 节气里的小动作；trend `节气 / 非遗`; hook `可保存小纸条`
- `sushi_bad_day_reframe`: 把狼狈写进一句词；trend `柔软力`; hook `轻量重读`

Psychology keeps its current expanded pack.

## Task 1: Extract Generic Topic Guidance Models And Selector

**Files:**
- Create: `src/ptsm/domain/topic_guidance.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/domain/test_topic_guidance.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write failing domain tests**

Add tests for pure deterministic selection:

```python
from ptsm.domain.topic_guidance import TopicDirection, select_topic_directions

def test_select_topic_directions_scores_scene_keywords_before_priority() -> None:
    directions = (
        TopicDirection(
            id="general",
            name="General",
            trend_signal="evergreen",
            viral_hook="save",
            why_it_may_work="general",
            best_scenes=("general",),
            content_angle="general",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            base_priority=9,
        ),
        TopicDirection(
            id="desk",
            name="Desk",
            trend_signal="desk",
            viral_hook="before_after",
            why_it_may_work="desk",
            best_scenes=("书桌",),
            content_angle="desk",
            saveable_tool="tool",
            comment_prompt="prompt",
            avoid="avoid",
            scene_keywords=("书桌",),
            base_priority=1,
        ),
    )

    result = select_topic_directions(
        directions=directions,
        scene="想写书桌角落改造",
        lane_name="一平米角落",
    )

    assert [item["id"] for item in result] == ["desk", "general"]
```

Also test:

- internal fields (`lane_affinity`, `scene_keywords`, `base_priority`) do not appear in public dicts
- tie-breaks are stable across repeated calls
- `limit=4` returns no more than 4

**Step 2: Run red tests**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

Expected: FAIL because `ptsm.domain.topic_guidance` does not exist.

**Step 3: Implement minimal generic model**

Create `TopicDirection`, `TopicLane`, `TopicPack`, `select_topic_directions()`, `resolve_topic_lane()`, and `public_topic_direction()`.

Implementation rules:

- Use dataclasses.
- Keep scoring deterministic.
- Score scene keyword hits higher than base priority.
- Add lane affinity score when affinity appears in the resolved lane name.
- Use SHA-256 hash of `scene|lane_name|direction_id` as tie-breaker.
- Return only public fields.

**Step 4: Run green tests**

```bash
uv run pytest tests/unit/domain/test_topic_guidance.py -q
```

**verify:** domain tests pass.

**done_when:** Generic topic guidance ranking exists without playbook-specific code in the selector.

## Task 2: Move Psychology Pack Onto Generic Engine Without Changing Behavior

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write/adjust failing compatibility tests**

Add or keep assertions that:

- psychology `guide-post` still returns `brief.mechanism`, `brief.reframe`, `safety_boundary`, `quality_checklist`, and `safety_notes`
- `topic_guidance.directions` still includes scene-aware psychology directions with `trend_signal` and `viral_hook`
- `run-playbook --caller openclaw` still returns `topic_guidance_required` for psychology without `--guidance-ack`

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_requires_topic_guidance_for_openclaw_psychology -q
```

Expected: PASS before refactor; if a test is newly added around internals, it may fail until refactor.

**Step 2: Refactor psychology code**

In `guide_post.py`, replace `PsychologyTopicDirection`, `_select_topic_directions`, `_keyword_hits`, `_stable_topic_rotation`, and `_public_topic_direction` with imports from `ptsm.domain.topic_guidance`.

Keep:

- `GuidePostRequest`
- `run_guide_post()`
- psychology-specific brief building
- `build_psychology_topic_guidance()` as a compatibility wrapper

**Step 3: Run compatibility tests**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py -q
```

**verify:** Existing psychology and CLI behavior remains stable.

**done_when:** The existing psychology flow is backed by generic selector code, with no user-visible regression.

## Task 3: Add Cross-Domain Topic Packs

**Files:**
- Create: `src/ptsm/application/use_cases/topic_guidance_packs.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write failing tests for first three domains**

Add tests:

```python
def test_guide_post_supports_fengkuang_topic_guidance() -> None:
    result = run_guide_post(
        GuidePostRequest(
            playbook_id="fengkuang_daily_post",
            account_id="acct-fk-local",
            scene="领导18:57发来一句在吗，工牌想替我发疯",
        )
    )

    assert result["status"] == "completed"
    assert result["playbook_id"] == "fengkuang_daily_post"
    assert result["brief"]["lane"]
    assert result["topic_guidance"]["matched_direction_id"].startswith("fk_")
    assert len(result["topic_guidance"]["directions"]) == 4
    assert "run-playbook --scene" in result["run_playbook_command_text"]
```

Repeat for:

- `human_enrichment_daily_post`, scene `想把书桌角落改成十分钟适我主义手作位`
- `sushi_poetry_daily_post`, scene `夜里读到怀民亦未寝，想写一种旧友关系`

Also assert serialized output omits:

- `docs/research`
- `2026-05-23-xhs-viral-meme-product-hooks.md`
- `"source"`
- `http://`
- `https://`

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_guide_post_supports_fengkuang_topic_guidance tests/unit/application/use_cases/test_guide_post.py::test_guide_post_supports_human_enrichment_topic_guidance tests/unit/application/use_cases/test_guide_post.py::test_guide_post_supports_sushi_poetry_topic_guidance -q
```

Expected: FAIL because `guide-post` currently only supports `modern_psychology_post`.

**Step 2: Add topic packs**

Create `topic_guidance_packs.py` with:

- `TOPIC_GUIDANCE_PACKS: dict[str, TopicPack]`
- `DEFAULT_ACCOUNT_BY_PLAYBOOK`
- packs for `modern_psychology_post`, `fengkuang_daily_post`, `human_enrichment_daily_post`, `sushi_poetry_daily_post`

Each `TopicPack` should define:

- playbook id
- default account id
- default image style
- lane list
- direction list
- safety notes or avoid notes where domain-specific

**Step 3: Update `run_guide_post()`**

Change validation from a single `SUPPORTED_PLAYBOOK_ID` to pack lookup:

- if playbook unsupported: raise `ValueError("guide-post supports ...")`
- resolve account default from pack when not supplied
- resolve lane using generic `resolve_topic_lane`
- build a generic brief for non-psychology packs
- keep psychology's extended brief fields
- build `recommended_scene` generically for non-psychology packs
- build `run-playbook` command with selected playbook/account

**Step 4: Run tests**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py -q
```

**verify:** `guide-post` supports all four packs and still rejects unsupported playbooks clearly.

**done_when:** Cross-domain topic guidance returns deterministic, scene-aware topic directions for psychology, fengkuang, human enrichment, and sushi poetry.

## Task 4: CLI Behavior And Markdown Output

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Test: `tests/unit/interfaces/cli/test_main.py`

**Step 1: Write failing CLI tests**

Add tests:

```python
def test_guide_post_cli_outputs_non_interactive_human_enrichment_brief(capsys):
    exit_code = main([
        "guide-post",
        "--playbook-id",
        "human_enrichment_daily_post",
        "--account-id",
        "acct-enrichment-local",
        "--scene",
        "想把书桌角落改成十分钟适我主义手作位",
        "--non-interactive",
        "--format",
        "json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["playbook_id"] == "human_enrichment_daily_post"
    assert payload["topic_guidance"]["directions"]
```

Add Markdown test:

- output heading should be generic, e.g. `# Topic Guidance Brief`, not `# Psychology Guidance Brief`, for non-psychology playbooks
- direction lines should include trend signal and viral hook

Run:

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py::test_guide_post_cli_outputs_non_interactive_human_enrichment_brief tests/unit/interfaces/cli/test_main.py::test_guide_post_cli_outputs_generic_markdown_for_non_psychology -q
```

Expected: FAIL until CLI/output supports generic playbooks.

**Step 2: Update interactive flow conservatively**

Recommended first implementation:

- Keep the rich six-question interactive wizard for psychology.
- For non-psychology interactive use, ask only:
  - scene
  - optional lane selection
  - optional comment prompt override
- Do not ask psychology-specific mechanism questions for other domains.

**Step 3: Update Markdown output**

Change `format_guide_post_markdown()`:

- Use generic heading for non-psychology.
- Show playbook id and account id.
- Show common brief fields.
- Preserve psychology-specific lines when present.

**Step 4: Run CLI tests**

```bash
uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py -q
```

**verify:** CLI parser and output support cross-domain guidance without breaking current psychology prompts.

**done_when:** Operators can use `guide-post` for first-batch domains from the CLI.

## Task 5: Generic OpenClaw Topic Guide Wrapper

**Files:**
- Create: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Create or modify: `tests/unit/docs/test_openclaw_topic_guide_skill.py`
- Modify: `tests/unit/docs/test_openclaw_skill.py`

**Step 1: Write failing docs tests**

Add tests asserting the generic wrapper:

- exists
- calls `guide-post` before `run-playbook`
- auto-maps user intent to a supported playbook id when the request clearly implies one
- asks a short clarification when the intended playbook is ambiguous
- still accepts an explicit `--playbook-id` when the caller has already resolved one
- shows only returned `topic_guidance.directions`
- includes direction name, trend signal, viral hook, best scenes, content angle, saveable tool, comment prompt, and avoid note
- says not to expose internal research paths, raw notes, URLs, or provenance
- does not duplicate specific topic pack logic

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/docs/test_openclaw_skill.py -q
```

Expected: FAIL because generic wrapper does not exist yet.

**Step 2: Create wrapper**

`integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` should say:

- Resolve the playbook automatically from user intent when clear. Example mappings:
  - 发疯文学 / 打工人 / 抽象吐槽 -> `fengkuang_daily_post`
  - 生活丰容 / 居家变量 / 低成本改造 -> `human_enrichment_daily_post`
  - 苏轼 / 诗词 / 古典文化治愈 -> `sushi_poetry_daily_post`
  - 心理学 / 情绪 / 关系边界 / 内耗 -> use the specialized `ptsm-xhs-psychology` wrapper
- If multiple playbooks fit, ask one short clarification question before calling PTSM.
- Once resolved, call:

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id "<resolved playbook id>" \
  --account-id "<resolved account id>" \
  --scene "<user request or concrete scene>" \
  --non-interactive \
  --format json
```

Then show returned directions and ask user to choose/confirm before dry-run generation:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --caller openclaw \
  --scene "<confirmed direction and concrete scene>" \
  --account-id "<account id>" \
  --playbook-id "<playbook id>" \
  --publish-mode dry-run
```

For psychology, keep recommending the specialized wrapper because it also knows the `--guidance-ack` hard gate and safety boundaries.

**Step 3: Update psychology wrapper**

Add one sentence:

- For non-psychology XHS playbooks, use `ptsm-xhs-topic-guide`; this file remains the psychology-specific wrapper.

**Step 4: Run docs tests**

```bash
uv run pytest tests/unit/docs/test_openclaw_topic_guide_skill.py tests/unit/docs/test_openclaw_skill.py -q
```

**verify:** OpenClaw has a generic thin wrapper, while psychology keeps its stricter specialized wrapper.

**done_when:** Agents can discover a cross-domain topic guidance skill without copying PTSM topic logic into the wrapper.

## Task 6: Source-Of-Truth Docs And Operations

**Files:**
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/xhs-topics/index.md`
- Modify: `docs/harness-engineering.md` if new harness facts are added
- Modify: `docs/plans/2026-05-24-cross-domain-topic-guidance.md`

**Step 1: Update docs**

Document:

- `guide-post` is now a cross-domain read-only topic guidance surface for supported XHS playbooks.
- Default guidance is local-first and deterministic; live scans still require existing fresh research / pattern collection flows.
- Initial supported playbooks are psychology, fengkuang, human enrichment, and sushi poetry.
- OpenClaw has a generic wrapper plus a psychology-specific wrapper.
- Non-psychology guidance does not introduce a hard runtime preflight gate in this first phase.

**Step 2: Run docs tests**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

**Step 3: Run docs-sync changed-path check**

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/domain/topic_guidance.py \
  --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py \
  --changed-path src/ptsm/application/use_cases/guide_post.py \
  --changed-path src/ptsm/interfaces/cli/main.py \
  --changed-path integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md \
  --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md \
  --changed-path docs/runtime.md \
  --changed-path docs/playbooks.md \
  --changed-path docs/skills.md \
  --changed-path docs/operations.md \
  --changed-path docs/xhs-topics/index.md
```

Expected: `status == "ok"`.

**verify:** Docs map, docs metadata, and docs-sync all pass.

**done_when:** Source-of-truth docs match the new operator/caller contract.

## Task 7: End-To-End Verification

**Files:**
- No code changes.

**Step 1: Run targeted unit suite**

```bash
uv run pytest \
  tests/unit/domain/test_topic_guidance.py \
  tests/unit/application/use_cases/test_guide_post.py \
  tests/unit/interfaces/cli/test_main.py \
  tests/unit/test_bootstrap.py \
  tests/unit/docs/test_openclaw_skill.py \
  tests/unit/docs/test_openclaw_topic_guide_skill.py \
  -q
```

**Step 2: Run CLI smoke checks**

```bash
uv run python -m ptsm.bootstrap guide-post \
  --playbook-id fengkuang_daily_post \
  --account-id acct-fk-local \
  --scene "领导18:57发来一句在吗，工牌想替我发疯" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id human_enrichment_daily_post \
  --account-id acct-enrichment-local \
  --scene "想把书桌角落改成十分钟适我主义手作位" \
  --non-interactive \
  --format json

uv run python -m ptsm.bootstrap guide-post \
  --playbook-id sushi_poetry_daily_post \
  --account-id acct-sushi-local \
  --scene "夜里读到怀民亦未寝，想写一种旧友关系" \
  --non-interactive \
  --format json
```

Expected:

- each payload has `status == "completed"`
- each payload has 4 `topic_guidance.directions`
- each payload has `trend_signal` and `viral_hook`
- selected direction ids differ by playbook and scene
- no internal research paths, URLs, or source fields appear

**Step 3: Run dry-run generation from one returned command**

Pick the `run_playbook_command_text` from one guidance result and run it with `--publish-mode dry-run`.

Expected:

- generation reaches `status == "completed"`
- no real publish side effects occur
- artifact contains the selected playbook id and final content

**Step 4: Run broad deterministic tests**

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 5: Run harness gate**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**verify:** Targeted tests, CLI smoke checks, dry-run generation, pytest, docs-sync, and harness-check pass.

**done_when:** Cross-domain guidance is proven through tests and real CLI surfaces without live MCP or real publishing.

## Implementation Notes

- Implemented `ptsm.domain.topic_guidance` with deterministic dataclass models, public-field serialization, scene/lane scoring, and SHA-256 tie-breaking.
- Kept psychology compatibility while moving topic direction ranking onto the generic selector.
- Added first-batch non-psychology topic packs for `fengkuang_daily_post`, `human_enrichment_daily_post`, and `sushi_poetry_daily_post`.
- Extended `guide-post` CLI JSON and Markdown output for generic playbooks. Psychology keeps its six-question wizard; generic interactive flow only asks scene, optional lane, and optional comment prompt override.
- Added `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` as the generic wrapper. `ptsm-xhs-psychology` remains the psychology-specific wrapper with `--guidance-ack`.
- Updated source-of-truth docs and the affected local operations runbook.

Verification completed in the implementation worktree:

- `uv run pytest tests/unit/domain/test_topic_guidance.py tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`
- `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q`
- `uv run python -m ptsm.bootstrap docs-sync --changed-path ...` with changed implementation, wrapper, and source-of-truth docs paths
- Three CLI smoke checks for `fengkuang_daily_post`, `human_enrichment_daily_post`, and `sushi_poetry_daily_post`
- One `human_enrichment_daily_post` dry-run generation from the returned `run_playbook_command_text`
- `uv run pytest -q --ignore=tests/e2e`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`

## Review Resolution

Confirmed decisions before implementation:

1. First batch is `fengkuang_daily_post`, `human_enrichment_daily_post`, `sushi_poetry_daily_post`, plus existing `modern_psychology_post`; later phases can expand the same pattern to all XHS playbooks.
2. Hard runtime preflight gate means `run-playbook --caller openclaw` refuses execution unless prior `guide-post` acknowledgement exists. Keep that only for psychology in phase one; generic non-psychology OpenClaw guidance enforces order at the wrapper level.
3. The generic wrapper auto-maps user intent to supported playbook id when clear, and asks one short clarification when ambiguous.
