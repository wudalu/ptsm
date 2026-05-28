# Modern Psychology Native XHS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `modern_psychology_post` read like native Xiaohongshu life/relationship notes while preserving psychology safety boundaries.

**Architecture:** Keep the change in playbook assets, builtin skill text, deterministic draft helpers, topic guidance copy, and playbook-local eval contracts. Do not add runtime branches; runtime already loads playbook assets, skills, topic guidance, and `evaluation.yaml` contracts.

**Tech Stack:** Python 3.12, pytest, PyYAML-backed playbook contracts, PTSM CLI dry-runs, Markdown source-of-truth docs.

## Current Docs Summary

- `docs/development-workflow.md` requires this work to happen in an isolated worktree, with a plan, task-level `verify:` / `done_when:`, source-of-truth docs updates, and `harness-check` before merge.
- `docs/architecture.md` says playbook and human-voice behavior belongs in asset/contract layers; new quality constraints should extend `src/ptsm/evaluations/contracts_eval.py` only when generic contract support is missing.
- `docs/runtime.md` says deterministic drafting reads playbook prompts, skills, runtime context, and playbook-local eval contracts; `guide-post` is a read-only selection surface and should not start workflows or live research.
- `docs/playbooks.md` currently describes psychology as first-person micro-scene plus mechanism, tool, comment prompt, and professional boundary. This is the main source-of-truth text that must change.
- `docs/skills.md` currently encodes `psychology_style` as a fixed teaching sequence. It must change to scene-first, mechanism-light, comment-role-first writing.
- `docs/harness-engineering.md` says XHS human-voice quality is enforced through generic node constraints and deterministic dry-run tests. This change should strengthen those contracts instead of relying only on LLM judge text.
- `docs/operations.md` already has representative psychology commands. It should update the operator expectation for psychology dry-runs, not add a new command surface.

## Scope

- Tighten psychology titles: concrete moment only; no psychology terms; no `不是你...` style reveal.
- Make body copy shorter and less instructional: target 350-550 chars, hard max 580 chars.
- Keep safety: no diagnosis, no treatment promises, no medication advice, keep concise professional-help boundary.
- Make save tools conditional in style, but keep deterministic contract satisfied through natural saveable cues when eval runs.
- Replace generic comment prompts with role / camp / fill-in prompts.
- Update deterministic psychology drafts so offline tests and harness reflect the new contract.

## Non-Goals

- No real XHS publishing.
- No new playbook or account.
- No live XHS research integration.
- No UI changes.
- No change to psychology `--caller openclaw --guidance-ack` runtime gate.

## Task 1: Red Tests For Psychology Native Constraints

**Files:**
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`

**Step 1: Write failing contract tests**

Assert `modern_psychology_post`:

- `body_max_chars == 580`
- `title_must_not_include_any` contains `不是你`, `反刍思维`, `低控制感`, `边界压力`, `情绪调节`, `灾难化思维`
- title no longer has a positive `title_must_include_any` gate that forces mechanism words
- `body_must_include_comment_prompt_any` includes camp/role prompts such as `哪派`, `A.`, `B.`, `____`
- `body_must_include_save_trigger_any` still has natural save cues, not only hard tool labels

**Step 2: Write failing deterministic draft tests**

Assert modern psychology deterministic drafts:

- titles do not contain psychology terms or `不是你`
- body length is `350 <= len(body) <= 580`
- mechanism names appear at most once and not in the first 120 chars
- body does not contain `这不是` / `不是你`
- comment prompt uses role, camp, option, or fill-in wording
- safety boundary contains `专业帮助` or `专业的人`

**Step 3: Verify RED**

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py tests/unit/infrastructure/llm/test_factory.py::test_deterministic_modern_psychology_draft_has_mini_tool_and_example_prompt tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

Expected: FAIL because existing contracts require old title/body shape and deterministic drafts still expose mechanism-heavy teaching copy.

**done_when:** Failing tests point at old psychology contract/draft behavior, not syntax or fixture errors.

## Task 2: Update Psychology Assets And Contracts

**Files:**
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml`
- Modify: `src/ptsm/skills/builtin/psychology_style/SKILL.md`

**Implementation notes:**

- Rewrite style from fixed teaching sequence to `具体瞬间 -> 场景继续推进 -> 一句轻机制 -> 可选保存动作 -> 角色/阵营评论 -> 简短专业边界`.
- Forbid title-level mechanism reveal and `不是你...` shape.
- Reduce `body_max_chars` from 620 to 580.
- Remove the forced `title_must_include_any` psychology/mechanism gate.
- Keep `body_must_include_all: ["专业帮助"]`.
- Keep forbidden diagnosis/treatment/medication terms.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py -q
```

**done_when:** Contract tests pass and no other playbook contract expectations are loosened.

## Task 3: Update Topic Guidance Psychology Prompts

**Files:**
- Modify: `src/ptsm/application/use_cases/guide_post.py`
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`

**Implementation notes:**

- Make `content_angle` fields less like `不是你...` and more like scene/relationship tension.
- Change comment prompts to role / camp / fill-in prompts where practical.
- Keep `avoid` safety language intact.
- Keep public field shape unchanged.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py -q
```

**done_when:** `guide-post` still returns 4 directions and image recommendations, but psychology directions no longer push title/body toward old teaching copy.

## Task 4: Update Deterministic Psychology Drafts

**Files:**
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`

**Implementation notes:**

- Rewrite `_build_modern_psychology_draft()` branches to use concrete title moments.
- Place the mechanism term late and at most once.
- Use a natural save cue instead of visible course/tool labels when possible.
- End with role/camp/fill-in comment prompts.
- Keep deterministic image plans valid for existing `xhs_image_strategy`.

**verify:**

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

**done_when:** Offline dry-runs produce native psychology copy within the new length band and still satisfy safety/hashtag checks.

## Task 5: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`

**Implementation notes:**

- `architecture.md`: no change expected; this stays in asset/contract layers already described there.
- `docs/operations/` runbooks: no command surface change expected; `docs/operations.md` operator expectations are enough.
- Update `last_verified` on touched active docs if the assertions are reverified.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/runtime.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md
```

**done_when:** Docs describe the new psychology behavior and docs metadata tests pass.

## Task 6: End-To-End Verification

**Files:**
- No new source files expected.

**verify:**

```bash
uv run python -m ptsm.bootstrap run-playbook --scene "他3小时没回消息，我已经想好分手后猫归谁了" --account-id acct-psychology-local --playbook-id modern_psychology_post --publish-mode dry-run
uv run python -m ptsm.bootstrap guide-post --scene "他3小时没回消息，我已经想好分手后猫归谁了" --non-interactive --format json
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --changed-path src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml --changed-path src/ptsm/skills/builtin/psychology_style/SKILL.md --changed-path src/ptsm/application/use_cases/guide_post.py --changed-path src/ptsm/infrastructure/llm/contextual_drafts.py --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/runtime.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md
```

**done_when:** The dry-run reaches `status == completed`, generated title/body match the new native XHS constraints, all tests pass, and harness-check exits 0.
