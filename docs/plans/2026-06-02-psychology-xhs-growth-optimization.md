# Psychology XHS Growth Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the `modern_psychology_post` path so psychology posts are more likely to earn Xiaohongshu views, saves, comments, and likes through stronger scene routing, saveable tools, and role-recognition prompts.

**Architecture:** Keep the change in the existing asset/application/evaluation layers: psychology `guide-post` lane/direction data, deterministic draft helpers, playbook/skill prompt assets, and source-of-truth docs. Do not add a runtime branch, new playbook, new account, or real publish flow. The live XHS opportunity scan on 2026-06-02 could not collect samples because the MCP server lacked `search_feeds`, so sleep recovery/light wellness is treated as a weak but actionable sublane hypothesis, not a proven trend ranking.

**Tech Stack:** Python 3.12, pytest, PTSM CLI via `uv run python -m ptsm.bootstrap`, Markdown source-of-truth docs.

## Current Docs Summary

- `docs/development-workflow.md` requires isolated worktree development, source-of-truth docs first, a plan under `docs/plans/`, task-level `verify:` / `done_when:`, docs updates with code changes, and final `harness-check`.
- `docs/playbooks.md` and `docs/skills.md` place modern psychology quality in playbook/skill assets: concrete first-person scene, one light mechanism, saveable action, role/camp/fill-in comment prompt, and professional-help safety boundary.
- `docs/runtime.md` says `guide-post` is deterministic and local-first; it should return 4 scene-relevant directions plus an image recommendation without starting workflow or live research.
- `docs/harness-engineering.md` already locks short XHS titles, psychology-native title bans, body length bands, comment prompts, save triggers, and the relationship-uncertainty regression path.
- `docs/operations.md` documents `guide-post`, dry-run, OpenClaw psychology guidance ack, and dry-run/eval commands as the operator surfaces to verify.

## Task 1: Add failing guide-post regression for growth sublane

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`

**Step 1: Write the failing test**

Add a test that calls:

```python
result = run_guide_post(
    GuidePostRequest(scene="睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复")
)
```

Assert:

- `brief["lane"] == "睡眠恢复 / 轻养生"`
- `topic_guidance["matched_direction_id"] == "sleep_recovery_shutdown_card"`
- first direction mentions `睡眠恢复` or `办公室恢复`
- first direction has a saveable tool containing `5 分钟` or `下班信号`
- first direction comment prompt uses `A.` / `B.` or `____`
- image recommendation is `local_social_screenshot`, `iphone_notes`, `save_tool`
- no internal source leakage

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_sleep_recovery_growth_sublane -q
```

Expected: FAIL because the lane and curated direction do not exist yet.

**Step 3: Implement minimal guide-post data**

Modify `src/ptsm/application/use_cases/guide_post.py`:

- Add `PsychologyLane(name="睡眠恢复 / 轻养生", ...)` with keywords for `睡眠恢复`, `轻养生`, `办公室恢复`, `下班信号`, `疲惫`, `睡前`, `下线`.
- Add `TopicDirection(id="sleep_recovery_shutdown_card", ...)` with a concrete save tool and role/camp comment prompt.
- Add this new lane affinity to the existing `sleep_scroll_closing_ritual` and `office_recovery_without_shopping` directions so the selector has breadth.
- Extend `_match_topic_direction_id()` only enough for sleep/light-wellness terms.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py::test_psychology_topic_guidance_routes_sleep_recovery_growth_sublane -q
```

Expected: PASS.

`done_when:` The new scene routes to the new sublane and exposes a save/comment/image package optimized for retention and engagement.

## Task 2: Add failing deterministic dry-run regression

**Files:**
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**Step 1: Write the failing test**

Add a deterministic CLI test for:

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --thread-id thread-modern-psychology-sleep-recovery
```

Assert title <= 22 chars, title has a dramatic cue, body length is 350-580, body contains a sleep/light-recovery signal, `5分钟` or `下班信号`, a role/camp/fill-in comment prompt, `专业帮助`, and no diagnosis/treatment/medicine claims.

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/e2e/test_modern_psychology_publish_dry_run.py::test_run_playbook_cli_outputs_sleep_recovery_growth_sublane -q
```

Expected: FAIL because the deterministic helper falls back to generic workplace rumination.

**Step 3: Implement minimal deterministic branch**

Modify `src/ptsm/infrastructure/llm/contextual_drafts.py`:

- Add a branch in `_build_modern_psychology_draft()` for `睡眠恢复`, `轻养生`, `办公室恢复`, `下班信号`, or `5分钟`.
- Output a short, concrete title with a tension cue.
- Keep mechanism after the scene, mention only one light mechanism, and keep the body in the 350-580 band.
- Include a saveable 5-minute shutdown or office recovery tool and a role/camp/fill-in comment prompt.
- Add sleep-recovery-specific recent-memory fallback candidates so repeated dry-runs rotate title, cover text, and body without falling back to unrelated workplace-rumination padding.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/e2e/test_modern_psychology_publish_dry_run.py::test_run_playbook_cli_outputs_sleep_recovery_growth_sublane -q
```

Expected: PASS.

`done_when:` The deterministic dry-run proves the new growth sublane can produce a publishable psychology draft that still passes safety and XHS quality constraints.

## Task 3: Update playbook and skill assets

**Files:**
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`
- Modify: `tests/unit/docs/test_openclaw_skill.py`

**Step 1: Write the failing skill docs test**

Add assertions in `tests/unit/docs/test_openclaw_skill.py` that the psychology
OpenClaw skill:

- mentions `睡眠恢复`
- mentions `轻养生`
- says these are PTSM-returned psychology sublane/direction payloads
- still says not to invent or expand returned directions

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py -q
```

Expected: FAIL because the skill has not been updated yet.

**Step 2: Update assets**

Add concise instructions that:

- Include `睡眠恢复 / 轻养生 / 办公室恢复` as a psychology sublane, not a new domain.
- Tie growth to first-screen specificity, saveable low-cost tools, and role/camp/fill-in comments.
- Keep the safety boundary and no-diagnosis/no-treatment limits.
- Update the OpenClaw/Codex psychology topic skill to describe sleep recovery/light wellness as a possible PTSM-returned psychology sublane without copying direction logic into the skill.
- Keep the personal Codex skill copy in `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md` in sync with the repo integration copy.

**Step 3: Run asset-related tests**

Run:

```bash
uv run pytest tests/unit/docs/test_openclaw_skill.py tests/unit/skills/test_skill_loader.py tests/unit/playbooks/test_playbook_registry.py -q
```

Expected: PASS.

`done_when:` Prompt assets, OpenClaw/Codex psychology topic skill, and tests agree on the new sublane without changing skill routing or duplicating PTSM topic logic.

## Task 4: Update source-of-truth docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`

**Step 1: Update docs**

Document that:

- The psychology playbook now treats sleep recovery/light wellness/office recovery as an existing-playbook sublane experiment.
- The optimization remains local-first and does not prove live ranking because the 2026-06-02 scan had no samples.
- `guide-post` should route these scenes to the sleep recovery sublane and recommend low-density `iphone_notes` save tools.
- Deterministic dry-run coverage now includes the sublane.

**Step 2: Run docs checks**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/infrastructure/llm/contextual_drafts.py --changed-path src/ptsm/skills/builtin/psychology_style/SKILL.md
```

Expected: PASS / status ok.

`done_when:` Active docs explain the optimization and docs-sync accepts the code/doc surface.

## Task 5: End-to-end verification

**Files:**
- No production edits expected.

**Step 1: Run targeted tests**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/unit/infrastructure/llm/test_factory.py tests/unit/evaluations/test_playbook_contracts.py -q
```

Expected: PASS.

**Step 2: Run guide-post smoke**

Run:

```bash
uv run python -m ptsm.bootstrap guide-post --scene "睡眠恢复和轻养生很火，想写办公室下班后的5分钟恢复" --non-interactive --format json
```

Expected: JSON status `completed`, first or matched direction `sleep_recovery_shutdown_card`, and image recommendation `iphone_notes`.

**Step 3: Run deterministic dry-run with eval**

Run:

```bash
uv run python -m ptsm.bootstrap run-playbook --scene "办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号" --account-id acct-psychology-local --playbook-id modern_psychology_post --eval --publish-mode dry-run
```

Expected: status `completed`, body within contract band, required evals not failed.

**Step 4: Run harness gate**

Run:

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: status ok. If the command only compares committed diff and the work is uncommitted, run targeted `--changed-path` checks and record that limitation.

`done_when:` Targeted tests, guide-post smoke, dry-run eval, and the available harness gate all pass or have a documented environmental limitation.
