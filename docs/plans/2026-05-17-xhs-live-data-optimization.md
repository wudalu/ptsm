# XHS Live Data Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a periodic Xiaohongshu format intelligence pipeline that
collects real XHS samples on a schedule, distills reusable post/image patterns,
and guides generation from a stable local pattern library instead of searching
live high-engagement posts during every content run.

**Architecture:** Keep generation offline-first. A periodic collector uses
`xiaohongshu-mcp` and `topic-radar` to gather bounded XHS samples, then a
separate analyzer converts raw posts into reusable `PostFormatPattern` and
`ImageCarouselPattern` records. `run-playbook` reads the latest approved pattern
snapshot from disk and injects that summary into runtime context; if no snapshot
exists, generation falls back to static skills. Live MCP is therefore a research
dependency, not a publish-time dependency.

**Tech Stack:** Python 3.12, uv, pytest, xiaohongshu-mcp over streamable HTTP,
topic-radar JSON/Markdown artifacts, YAML playbooks/evaluation contracts,
Markdown builtin skills, existing LangGraph runtime artifacts.

## Current Docs Summary

- `AGENTS.md` and `docs/development-workflow.md` require branch/worktree
  isolation, current-doc review, a plan with `verify:` and `done_when:`, source
  docs updates, and final `harness-check`.
- `docs/harness-engineering.md` requires deterministic local gates and no
  default dependency on live XHS login.
- `docs/topic-radar.md` and `docs/operations/topic-radar-runbook.md` describe
  the XHS MCP scan path and require not treating login-required or empty scans
  as valid evidence.
- `docs/runtime.md` and `docs/skills.md` already support runtime skill context;
  approved format patterns should enter through that layer instead of being
  hard-coded into static prompts or fetched live during generation.
- `docs/observability.md` treats artifacts and eval outputs as local evidence;
  live sample artifacts must be persisted and referenced.

## Live Evidence Summary

See `docs/research/2026-05-17-xhs-live-mcp-sample.md`.

Successful real MCP samples:

- `outputs/artifacts/xhs-live-theme-a-2026-05-17/topic-scan-2026-05-17.json`
- `outputs/artifacts/xhs-live-theme-b-2026-05-17/topic-scan-2026-05-17.json`

Key findings:

- `人类丰容` and `家的丰容计划` are real live XHS search surfaces, not only
  public-report assumptions.
- Strong hooks include `突然意识到...`, `人，你该...`, and explicit contrast
  such as `空无一物的家vs丰容后的家`.
- `低成本改造` posts get high save/share value when they include cost framing,
  before/after contrast, and experience-summary language.
- `观鸟` has high identity/discussion value but requires real observation
  evidence and should remain a later, more accuracy-sensitive playbook.
- `钩织` and `拼豆` show very strong visual/process virality; use them as
  sub-series inside human enrichment before creating a separate playbook.
- A direct MCP probe confirmed a 1080x1440 cover payload for a high-ranking
  `人类丰容` result, reinforcing 3:4 vertical cover guidance.

Reliability finding:

- The XHS MCP server is usable for bounded sequential scans, but broad or
  repeated search batches can return HTTP 500 and eventually lose login state.
  This is exactly why generation should not call live XHS every time. The MCP
  path belongs in a periodic collection job with retries, partial persistence,
  and human review, while content generation should consume a stable local
  pattern library.

## Target Behavior

Periodic research flow:

1. Run a bounded XHS collection job daily or weekly per topic lane.
2. Persist raw samples with title, engagement counts, keyword, feed ID,
   `xsec_token`, author, cover dimensions, and collection timestamp.
3. Analyze raw samples into pattern records:
   - title hook archetype
   - body structure
   - save trigger
   - comment trigger
   - carousel/image sequence
   - example titles
   - topic lane and freshness window
4. Optionally mark patterns as `approved`, `candidate`, or `rejected`.
5. Keep a small current snapshot, such as
   `outputs/artifacts/xhs-pattern-library/current.json`, for generation.

Generation flow:

1. `run-playbook` loads the latest approved pattern snapshot for the playbook's
   topic lane.
2. The generator produces title/body/image-brief variants using pattern
   archetypes, not copied sample titles.
3. The image brief describes a 3:4 cover plus a carousel sequence with
   per-slide purpose and text limits.
4. The artifact records which pattern IDs influenced generation.
5. If the pattern library is missing or stale, the run falls back to static
   skills and clearly marks `format_patterns.status: unavailable`.

Out of scope:

- Real publishing.
- Downloading or reusing XHS creator images.
- Automatic factual before/after generation.
- Real-time XHS search during ordinary `run-playbook` execution.
- A dashboard or always-on crawler. A manual command and optional scheduled job
  are enough for this phase.

## 2026-05-17 Implementation Slice

Current source-of-truth docs say the cross-domain content-quality contracts and
local note-card cover backend have already landed. This branch therefore treats
`docs/plans/2026-05-17-cross-domain-content-quality-and-note-images.md` as
completed context and implements the remaining live-data optimization path:

1. design: keep XHS MCP access in a bounded, manually runnable collection use
   case; never call live XHS from ordinary deterministic generation.
2. implement: add local `XhsSample`, pattern extraction, pattern snapshot store,
   CLI commands, generation-time pattern context injection, and richer
   human-enrichment image/form metadata.
3. test: write failing unit tests first for sample normalization, partial MCP
   collection, pattern analysis/store, pattern-context injection, run-playbook
   artifact metadata, and human-enrichment contract expectations.
4. verify: run targeted pytest after each task, then `docs-sync` and
   `harness-check --base-ref origin/main` before handoff.

Branch assumptions:

- The collector is a manual/cron-friendly command, not a daemon.
- Tests use fake clients and local JSON fixtures; they must not require a live
  MCP server or logged-in Xiaohongshu session.
- Pattern records may store title/body/image structure and cover dimensions, but
  must not store creator image URLs as reusable assets.
- Generated posts should borrow pattern archetypes, not copy sample titles.

Final branch gate:

```bash
uv run pytest -q --ignore=tests/e2e
DEFAULT_LLM_PROVIDER=deterministic uv run pytest tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Implementation status in this branch:

- Implemented periodic sample collection via `ptsm collect-xhs-patterns`.
- Implemented local sample normalization and deterministic pattern extraction.
- Implemented local snapshot persistence under `outputs/artifacts/xhs-pattern-library`.
- Implemented pattern-library runtime context injection for `xhs_trend_scan`.
- Implemented `run-playbook --format-pattern-path` and artifact
  `format_patterns_used` metadata.
- Expanded human-enrichment prompt assets, deterministic draft behavior,
  `content_review.image_form` carousel brief, and pattern leakage constraints.
- Updated source-of-truth docs for architecture, runtime, skills, playbooks,
  observability, operations and topic-radar.

Verification evidence collected while implementing:

```bash
uv run pytest tests/unit/topic_radar/test_mcp_client.py tests/unit/topic_radar/test_xiaohongshu_platform.py tests/unit/topic_radar/test_cli.py tests/unit/topic_radar/test_output.py tests/unit/domain/test_xhs_patterns.py tests/unit/application/use_cases/test_collect_xhs_patterns.py tests/unit/application/use_cases/test_analyze_xhs_patterns.py tests/unit/infrastructure/test_xhs_pattern_store.py tests/unit/skills/test_xhs_pattern_context.py tests/unit/skills/test_runtime_context.py tests/unit/skills/test_skill_registry.py tests/unit/application/use_cases/test_run_playbook.py tests/unit/interfaces/cli/test_main.py tests/unit/test_bootstrap.py tests/unit/agent_runtime/test_finalize_node.py tests/unit/infrastructure/llm/test_factory.py tests/unit/evaluations/test_playbook_contracts.py -q
uv run pytest -q --ignore=tests/e2e
DEFAULT_LLM_PROVIDER=deterministic uv run pytest tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run python -m ptsm.bootstrap collect-xhs-patterns --lane human_enrichment --keywords "人类丰容,家的丰容计划" --sample-limit-per-keyword 2 --output-dir /tmp/ptsm-xhs-pattern-smoke --dry-run --delay-seconds 0
uv run python -m ptsm.bootstrap analyze-xhs-patterns --sample-path /tmp/ptsm-xhs-pattern-smoke/samples-2026-05-17.json --lane human_enrichment --output-dir /tmp/ptsm-xhs-pattern-smoke/library
```

## 2026-05-17 Continuation Polish Slice

After merging the first implementation slice, a follow-up audit found two
remaining weak spots from the original plan:

1. `Task 4` says the local pattern summary should be available to both
   `xhs_trend_scan` and `topic_research`. Current generation records the
   pattern context through `xhs_trend_scan`, while `topic_research` still only
   returns topic-radar context.
2. `Task 5` asks deterministic human-enrichment drafts to vary across at least
   desk/home corner, walking/sensory route, and handcraft/material flow scenes.
   Current deterministic tests cover the desk/home-corner path, while route and
   material-flow variants are only represented in prompt assets.

### Polish Task 1: Pattern-Aware Topic Research Context

**Files:**

- Modify: `src/ptsm/skills/runtime_context.py`
- Modify: `tests/unit/skills/test_runtime_context.py`
- Modify: `tests/unit/skills/test_xhs_pattern_context.py`

**Steps:**

1. Write a failing unit test proving `topic_research` can receive local
   `# XHS Format Pattern Library Context` when a matching pattern snapshot
   exists and the topic-radar artifact is missing.
2. Write a paired test proving existing topic-radar context is preserved and the
   format-pattern block is appended when both sources exist.
3. Add a small `PatternAwareTopicResearchContextBuilder` that composes
   `TopicResearchContextBuilder` with `XhsPatternContextBuilder`.
4. Wire `build_skill_context_resolver()` so `topic_research` uses the composed
   builder while `xhs_trend_scan` keeps its current pattern-first/live-fallback
   behavior.

verify:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/skills/test_xhs_pattern_context.py -q
```

done_when:

- Human-enrichment runs with both `xhs_trend_scan` and `topic_research` can see
  the same local format pattern library without live XHS calls.
- Existing topic-radar selected-angle behavior is not removed.

### Polish Task 2: Deterministic Human-Enrichment Scene Variation

**Files:**

- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/reflection.md`

**Steps:**

1. Write failing tests for walking/sensory route and handcraft/material flow
   scenes.
2. Assert the three scene families produce distinct titles and bodies while
   retaining `变量`, `十分钟` or `低成本`, a three-step saveable structure, and a
   comment prompt.
3. Add route and material-flow branches before the generic human-enrichment
   fallback.
4. Keep safety and leakage constraints unchanged.

verify:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

done_when:

- Offline deterministic human-enrichment generation covers desk/home corner,
  walking/sensory route, and handcraft/material flow scenes.
- The e2e human-enrichment dry-run still passes with the existing desk scene.

### Polish Task 3: Docs And Harness Gate

**Files:**

- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/plans/2026-05-17-xhs-live-data-optimization.md`

verify:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/skills/test_xhs_pattern_context.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

done_when:

- Source-of-truth docs describe pattern-aware `topic_research` and the three
  deterministic human-enrichment scene families.
- Docs sync and strict harness both report `status=ok`.

Polish implementation status:

- Added `PatternAwareTopicResearchContextBuilder`, so `topic_research` preserves
  topic-radar context when present and appends local XHS format patterns when a
  matching snapshot exists.
- Wired the default runtime skill resolver so both `xhs_trend_scan` and
  `topic_research` can expose local pattern context without live XHS calls.
- Updated the deterministic / no-DeepSeek-key `run-playbook` resolver to expose
  the same local pattern context to `topic_research` while disabling fresh
  topic-radar scans.
- Added deterministic human-enrichment branches for route/sensory scenes and
  handcraft/material-flow scenes, alongside the existing desk/corner branch.
- Updated `docs/runtime.md`, `docs/playbooks.md`, and `docs/skills.md`.

Polish verification evidence:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/skills/test_xhs_pattern_context.py -q
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_uses_local_pattern_context_for_deterministic_provider tests/unit/application/use_cases/test_run_playbook.py::test_run_playbook_uses_local_pattern_context_when_deepseek_key_missing -q
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_deterministic_human_enrichment_varies_route_and_material_scenes -q
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/skills/test_xhs_pattern_context.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict
```

---

### Task 1: Add Periodic XHS Sample Collection

**Files:**

- Modify: `src/topic_radar/mcp_client.py`
- Modify: `src/topic_radar/platforms/xiaohongshu.py`
- Modify: `src/topic_radar/cli.py`
- Create: `src/ptsm/application/use_cases/collect_xhs_patterns.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `tests/unit/topic_radar/test_mcp_client.py`
- Modify: `tests/unit/topic_radar/test_xiaohongshu_platform.py`
- Modify: `tests/unit/topic_radar/test_cli.py`
- Create: `tests/unit/application/use_cases/test_collect_xhs_patterns.py`

**Steps:**

1. Add a CLI command such as `ptsm collect-xhs-patterns`.
2. Accept:
   - `--lane human_enrichment`
   - `--keywords 人类丰容,家的丰容计划,低成本改造,钩织,拼豆`
   - `--sample-limit-per-keyword 8`
   - `--output-dir outputs/artifacts/xhs-pattern-library`
   - `--dry-run`
3. Add a unit test where one keyword raises an MCP HTTP 500-like
   `ExceptionGroup`, while another keyword returns rows.
4. Assert the collector preserves successful rows and records the failed keyword
   under `keyword_errors`.
5. Improve `_clean_error()` so `ExceptionGroup` reports nested `HTTPStatusError:
   500` instead of only `unhandled errors in a TaskGroup`.
6. Collect XHS keywords sequentially with a per-keyword timeout and no
   concurrent MCP calls.
7. Persist partial results after each keyword so a later keyword cannot discard
   earlier evidence.
8. Add a small delay between keyword calls, configurable with a conservative
   default.

verify:

```bash
uv run pytest \
  tests/unit/topic_radar/test_mcp_client.py \
  tests/unit/topic_radar/test_xiaohongshu_platform.py \
  tests/unit/topic_radar/test_cli.py \
  tests/unit/application/use_cases/test_collect_xhs_patterns.py -q
```

done_when:

- A failed XHS keyword no longer discards successful samples from earlier
  keywords.
- HTTP 500 root cause is visible in CLI output.
- The collector can be run manually or from cron/launchd without changing
  ordinary generation behavior.
- Deterministic tests do not require a live MCP server.

---

### Task 2: Preserve Full Sample Evidence

**Files:**

- Modify: `src/topic_radar/platforms/xiaohongshu.py`
- Modify: `src/topic_radar/output/artifacts.py`
- Create: `src/ptsm/domain/xhs_patterns.py`
- Modify: `tests/unit/topic_radar/test_output.py`
- Modify: `tests/unit/topic_radar/test_cli.py`
- Create: `tests/unit/domain/test_xhs_patterns.py`

**Steps:**

1. Extend XHS `FeedItem.metadata` to include cover width, cover height, and a
   boolean `has_cover_url` without storing or downloading the actual image.
2. Replace `_flatten_trending()`'s hard `items[:30]` behavior with either:
   - `raw_trending_limit_per_platform`, default 100; or
   - per-keyword capped flattening, default 10 per keyword.
3. Add tests proving later keywords such as `普通人用AI` and `睡前仪式感` are not
   dropped from a multi-keyword artifact.
4. Add collection metadata:
   - `keyword_count`
   - `successful_keywords`
   - `failed_keywords`
   - `sample_limit_per_keyword`
   - `live_source: xiaohongshu-mcp`
   - `collected_at`
   - `lane`
5. Add a typed `XhsSample` model or dataclass with fields for title, keyword,
   engagement, cover dimensions, and identifiers.

verify:

```bash
uv run pytest \
  tests/unit/topic_radar/test_output.py \
  tests/unit/topic_radar/test_cli.py \
  tests/unit/domain/test_xhs_patterns.py -q
```

done_when:

- Artifacts retain all requested keyword groups within configured limits.
- Cover ratio evidence can be summarized from live data.
- Samples are normalized into a local schema before pattern analysis.

---

### Task 3: Analyze Samples Into A Pattern Library

**Files:**

- Create: `src/ptsm/application/use_cases/analyze_xhs_patterns.py`
- Create: `src/ptsm/infrastructure/xhs_patterns/store.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Create: `tests/unit/application/use_cases/test_analyze_xhs_patterns.py`
- Create: `tests/unit/infrastructure/test_xhs_pattern_store.py`

**Steps:**

1. Add `ptsm analyze-xhs-patterns --sample-path ... --lane ...`.
2. Define pattern records:
   - `pattern_id`
   - `lane`
   - `status`: `candidate`, `approved`, `rejected`
   - `title_hook`: e.g. `sudden_realization`, `you_should_enrich`,
     `before_after_contrast`, `low_cost_list`, `process_reveal`
   - `body_structure`: e.g. `problem -> variable -> checklist -> comment`
   - `image_sequence`: e.g. `cover -> before -> material -> checklist -> after`
   - `save_trigger`
   - `comment_trigger`
   - `example_titles`
   - `source_sample_ids`
   - `created_at`
3. Implement deterministic title/body/image pattern extraction rules from live
   samples:
   - `突然意识到...` -> `sudden_realization`
   - `人，你该...` -> `you_should_enrich`
   - `vs` or `前后` -> `before_after_contrast`
   - `低成本`, `建议收藏`, `清单`, `教程` -> `saveable_list`
   - `过程`, `完成`, `原来这么简单`, `新手必看` -> `process_or_tutorial`
4. Write `patterns-YYYY-MM-DD.json` and update `current.json` with approved or
   highest-scoring candidate patterns.
5. Do not store creator image URLs as reusable assets; only store dimensions and
   structural image observations.

verify:

```bash
uv run pytest \
  tests/unit/application/use_cases/test_analyze_xhs_patterns.py \
  tests/unit/infrastructure/test_xhs_pattern_store.py -q
```

done_when:

- Raw XHS samples are converted into reusable format patterns.
- Pattern snapshots can be reviewed, approved, and loaded by later generation.
- No generation run needs to call XHS MCP to get these patterns.

---

### Task 4: Load Pattern Library During Generation

**Files:**

- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/skills/runtime_context.py` or the existing runtime context
  builder location used by `xhs_trend_scan`
- Create: `tests/unit/skills/test_xhs_pattern_context.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Steps:**

1. Add a `FormatPatternContext` structure carrying:
   - lane
   - pattern IDs
   - hook archetypes
   - body structures
   - image sequences
   - freshness metadata
   - source artifact path
   - status: `available`, `stale`, or `unavailable`
2. Load `outputs/artifacts/xhs-pattern-library/current.json` by default.
3. Allow an explicit pattern path override for experiments.
4. Inject a short pattern summary into `runtime_skill_contents` for
   `xhs_trend_scan` and `topic_research`.
5. Mark artifacts with `format_patterns_used`.
6. In deterministic/offline mode, use the local snapshot if present; otherwise
   preserve the empty resolver fallback.

verify:

```bash
uv run pytest \
  tests/unit/skills/test_xhs_pattern_context.py \
  tests/unit/application/use_cases/test_run_playbook.py -q
```

done_when:

- Generation can use a stable local pattern snapshot.
- Missing or stale snapshots degrade cleanly without live MCP calls.
- Artifacts record which pattern IDs guided generation.

---

### Task 5: Optimize Copy Generation From Pattern Library

**Files:**

- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/reflection.md`
- Modify: `src/ptsm/skills/builtin/human_enrichment_style/SKILL.md`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Steps:**

1. Update prompts to prefer these pattern-library hook archetypes:
   - `突然意识到{ordinary thing}也需要丰容`
   - `人，你该给{corner/object}丰容了`
   - `{before state} vs {after enrichment state}`
   - `{cost/time}低成本变量清单`
   - `{process}原来这么简单`
2. Require each draft to include:
   - concrete object or corner
   - one variable
   - time or cost boundary
   - three-step saveable list
   - example-based comment prompt
3. Add deterministic draft variation keyed by scene so repeated runs do not
   always output the same title/body.
4. Add tests for at least three deterministic scene categories:
   - desk/home corner
   - walking/sensory route
   - handcraft/material flow

verify:

```bash
uv run pytest \
  tests/unit/infrastructure/llm/test_factory.py \
  tests/unit/application/use_cases/test_run_playbook.py -q
```

done_when:

- Generated human enrichment posts visibly match approved format patterns.
- Repeated scene families are not identical.

---

### Task 6: Optimize Image And Carousel Briefs

**Files:**

- Modify: `src/ptsm/agent_runtime/runtime.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/skills/builtin/xhs_enrichment_visuals/SKILL.md`
- Modify: `tests/unit/agent_runtime/test_finalize_node.py`
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`

**Steps:**

1. Expand `content_review.image_form` into a structured carousel brief selected
   from the pattern library:
   - slide 1: 3:4 cover, one short sentence
   - slide 2: original state or ordinary friction
   - slide 3: variable/material flat lay
   - slide 4: three-step checklist
   - slide 5: after/detail/sensory change
   - slide 6: comment invitation
2. Add text-length constraints:
   - cover text <= 14 Chinese characters when possible
   - checklist page <= 3 bullets
   - no hashtags or watermarks on image text
3. Use live cover metadata to set `primary_ratio: 3:4` when the sampled covers
   in the pattern snapshot support it; otherwise keep the current static
   fallback.
4. Make `_build_image_generation_prompt()` mention that generated images are
   mood/reference only unless the user supplies real source images.
5. Store `image_pattern_id` and `carousel_pattern_id` in `content_review` when
   available.

verify:

```bash
uv run pytest \
  tests/unit/agent_runtime/test_finalize_node.py \
  tests/unit/application/use_cases/test_run_playbook.py -q
```

done_when:

- Artifacts carry per-slide image guidance.
- Image prompts encode cover ratio, text limits, and non-factual AI image use.

---

### Task 7: Add Pattern-Based Evaluation Rules

**Files:**

- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`
- Modify: `tests/e2e/test_human_enrichment_publish_dry_run.py`

**Steps:**

1. Add required evaluators for:
   - one approved hook pattern or equivalent concrete hook
   - one cost/time/action boundary
   - one saveable list
   - one example-based comment prompt
2. Add warning evaluators for:
   - title too generic
   - body reads as shopping list only
   - image brief missing carousel sequence
3. Ensure existing safety forbids remain:
   - `治好`
   - `治愈焦虑`
   - `治愈抑郁`
   - `诊断`
   - `用药`
   - prompt/meta leakage

verify:

```bash
uv run pytest \
  tests/unit/evaluations/test_playbook_contracts.py \
  tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

done_when:

- A generic emotional post fails or warns.
- A pattern-guided post passes deterministic eval.

---

### Task 8: Update Source-Of-Truth Docs And Run Gates

**Files:**

- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`
- Modify: `docs/runtime.md`
- Modify: `docs/skills.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/observability.md`
- Modify: `docs/xhs-topics/verticals.md`

**Steps:**

1. Document the periodic collection and pattern-library pipeline.
2. Document MCP reliability behavior:
   - no concurrent XHS scans
   - bounded keyword batches
   - persist partial results
   - if HTTP 500 appears, stop broad scans and recover login/session
3. Document that ordinary generation reads local pattern snapshots and does not
   call live XHS by default.
4. Link `docs/research/2026-05-17-xhs-live-mcp-sample.md`.
5. Run docs-sync with explicit changed paths before commit.
6. Run full non-e2e pytest and harness-check.

verify:

```bash
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main \
  --changed-path docs/research/2026-05-17-xhs-live-mcp-sample.md \
  --changed-path docs/plans/2026-05-17-xhs-live-data-optimization.md

uv run pytest -q --ignore=tests/e2e

uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when:

- Source-of-truth docs describe the behavior.
- `docs-sync` reports `status=ok`.
- Non-e2e pytest exits 0.
- `harness-check` reports `status=ok`.

## Completion Criteria

- Periodic XHS samples are persisted with enough metadata to explain pattern
  decisions.
- Raw samples are distilled into approved local pattern snapshots.
- `human_enrichment_daily_post` uses approved XHS-derived hook and carousel
  mechanics without requiring live XHS during ordinary generation or
  deterministic harness runs.
- Image artifacts carry carousel-ready guidance and pattern IDs.
- MCP failures are isolated to the collection job and produce actionable
  diagnostics plus partial artifacts instead of blocking content generation.
