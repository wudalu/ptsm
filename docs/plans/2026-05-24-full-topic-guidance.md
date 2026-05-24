# Full XHS Topic Guidance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend `guide-post` from psychology plus the first three non-psychology topic packs to every existing XHS playbook, so OpenClaw and operators can get scene-aware topic directions before drafting across all current domains.

**Architecture:** Keep the current deterministic local topic-pack architecture. `ptsm.domain.topic_guidance` owns generic lane/direction scoring, `application/use_cases/topic_guidance_packs.py` owns productized playbook packs, and `guide_post.py` remains a read-only application use case that emits a dry-run command. No workflow, memory, image generation, publish side effect, live XHS scan, Reddit scan, or topic-radar scan runs by default.

**Tech Stack:** Python 3.12 dataclasses, argparse CLI, pytest, existing PTSM account/playbook ids, Markdown source-of-truth docs, OpenClaw `SKILL.md` wrapper instructions.

## Current Docs Summary

- `docs/index.md` says active source-of-truth docs must be read before implementation; historical plans are context only.
- `docs/development-workflow.md` classifies this as major operator/runtime-visible work and requires a worktree, a plan, task-level verification, source-of-truth docs updates, `harness-check`, and merge back to `main`.
- `docs/architecture.md` places topic guidance in domain/application layers and says it must stay out of `agent_runtime`; the current text only names the first non-psychology packs.
- `docs/runtime.md` says `guide-post` is read-only and currently returns four directions only for `modern_psychology_post`, `fengkuang_daily_post`, `human_enrichment_daily_post`, and `sushi_poetry_daily_post`.
- `docs/playbooks.md` lists nine existing XHS playbooks and says the first `guide-post` batch covers only four playbooks.
- `docs/skills.md` says the generic OpenClaw topic wrapper currently auto-maps only发疯文学、人类丰容、苏轼诗词; psychology remains a specialized wrapper with a runtime `--guidance-ack` gate.
- `docs/xhs-topics/index.md` separates productized local hook packs from live or periodic research; this change should keep that boundary.
- `docs/operations.md` and `docs/operations/local-runbook.md` document guide and dry-run commands; they need examples for the remaining supported domains.
- `docs/harness-engineering.md` requires deterministic tests, docs tests, and harness coverage for cross-domain `guide-post`.

## Scope

- Add local deterministic topic packs for:
  - `wuxia_character_post`
  - `ai_tech_daily_post`
  - `daily_english_post`
  - `world_cup_daily_post`
  - `reddit_curation_daily_post`
- Preserve existing behavior for:
  - `modern_psychology_post`
  - `fengkuang_daily_post`
  - `human_enrichment_daily_post`
  - `sushi_poetry_daily_post`
- Update the generic OpenClaw wrapper to auto-map all supported non-psychology playbooks.
- Update source-of-truth docs and operator examples.
- Run targeted unit tests, docs tests, CLI smoke checks, one newly added domain dry-run, full non-e2e pytest, and `harness-check`.

## Non-Goals

- Do not add new playbooks, accounts, accounts registry entries, or publish flows.
- Do not add live scan behavior to `guide-post` by default.
- Do not add a hard runtime `guidance_ack` gate for non-psychology playbooks.
- Do not expose raw source URLs, research paths, provenance, Reddit thread ids, or internal notes in user-facing guidance.
- Do not make selection random; topic choice must remain deterministic and testable.

## Topic Pack Seeds

- `wuxia_character_post`: 老款人格/角色认领、当代职场镜像、主体性/边界选择、江湖人情债。
- `ai_tech_daily_post`: 模型更新人话拆解、普通人工作流、工具选择避坑、普通人影响判断。
- `daily_english_post`: 职场表达、情绪词场景记忆、每日一个高频词、评论区造句练习。
- `world_cup_daily_post`: 看球清单、球迷情绪、普通球迷赛前看点、赛后复盘顺序；禁止赌球、盘口、预测比分和内部消息。
- `reddit_curation_daily_post`: AI 工具焦虑、效率工作流经验、心理/生活压力观察、中文读者角度；禁止读者可见内容泄漏 Reddit、subreddit、英文讨论、翻译过程、URL 或来源。

## Task 1: Red Tests For Remaining Domains

**Files:**
- Modify: `tests/unit/application/use_cases/test_guide_post.py`
- Modify: `tests/unit/interfaces/cli/test_main.py`
- Modify: `tests/unit/docs/test_openclaw_topic_guide_skill.py`

**Steps:**
1. Add parametrized application tests for the five remaining playbooks.
2. Change the unsupported playbook test to use a truly unknown id.
3. Add CLI coverage for at least one newly supported playbook, preferably parametrized across all five.
4. Extend OpenClaw wrapper docs tests to require all new playbook ids and intent keywords.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py::test_guide_post_cli_outputs_non_interactive_new_domain_briefs tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

**done_when:** Tests fail because the remaining five playbooks are still unsupported or unmapped.

## Task 2: Add Topic Packs

**Files:**
- Modify: `src/ptsm/application/use_cases/topic_guidance_packs.py`

**Steps:**
1. Add five `TopicPack` constants with four lanes and four public directions each.
2. Register them in `TOPIC_GUIDANCE_PACKS`.
3. Keep all public direction fields complete and avoid internal source/provenance language.

**verify:**

```bash
uv run pytest tests/unit/application/use_cases/test_guide_post.py tests/unit/interfaces/cli/test_main.py::test_guide_post_cli_outputs_non_interactive_new_domain_briefs -q
```

**done_when:** All newly added playbooks return `status=completed`, four directions, a matching id prefix, default account, and no forbidden internal-source fields.

## Task 3: Update OpenClaw Wrapper Mapping

**Files:**
- Modify: `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md`
- Modify: `tests/unit/docs/test_openclaw_topic_guide_skill.py`

**Steps:**
1. Add intent mapping bullets for武侠、AI科技、每日英语、世界杯、Reddit英文讨论转译.
2. Keep the wrapper thin: call `guide-post`, show returned directions only, then dry-run through `run-playbook`.
3. Keep psychology routed to `ptsm-xhs-psychology`.

**verify:**

```bash
uv run pytest tests/unit/docs/test_openclaw_topic_guide_skill.py -q
```

**done_when:** Docs test locks all supported non-psychology ids and the wrapper still does not copy direction ids or internal topic logic.

## Task 4: Update Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/xhs-topics/index.md`

**Steps:**
1. Replace first-batch wording with all-nine/current-playbook wording.
2. Add the five new guide examples to operations docs.
3. Explicitly state that non-psychology still has no runtime hard gate.
4. Keep Reddit curation visibility guardrails clear.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/docs/test_openclaw_topic_guide_skill.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/application/use_cases/topic_guidance_packs.py
uv run python -m ptsm.bootstrap docs-sync --changed-path integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
```

**done_when:** Active docs reflect all supported `guide-post` playbooks and docs checks pass.

## Task 5: End-To-End Validation And Merge

**Steps:**
1. Smoke `guide-post` for each newly added playbook with `--non-interactive --format json`.
2. Run one real dry-run for a newly added domain through `run-playbook --publish-mode dry-run`.
3. Run full non-e2e pytest.
4. Run final harness gate in the worktree.
5. Merge the branch back to local `main` and clean up the worktree after verification passes.

**verify:**

```bash
uv run python -m ptsm.bootstrap guide-post --playbook-id wuxia_character_post --account-id acct-wuxia-local --scene "想用令狐冲写一种当代职场里的自由人格" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id ai_tech_daily_post --account-id acct-ai-tech-local --scene "Google 发布 Gemini 3，想写普通人能懂的 AI 工具变化" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id daily_english_post --account-id acct-daily-english-local --scene "学一个表示坚持的高级词汇，想配真实职场例句" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id world_cup_daily_post --account-id acct-world-cup-local --scene "阿根廷和法国决赛前，想写普通球迷看球清单" --non-interactive --format json
uv run python -m ptsm.bootstrap guide-post --playbook-id reddit_curation_daily_post --account-id acct-reddit-curation-local --scene "从外网 AI 工具焦虑讨论里选一个适合中文读者的角度" --non-interactive --format json
uv run python -m ptsm.bootstrap run-playbook --scene "学一个表示坚持的高级词汇，想配真实职场例句" --account-id acct-daily-english-local --playbook-id daily_english_post --publish-mode dry-run
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Worktree verification passes, branch is merged back to local `main`, and final handoff includes commands run plus any remaining warnings.
