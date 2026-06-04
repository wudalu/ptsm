# XHS Body Human Voice Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve current Xiaohongshu post bodies so generated posts feel more like a real person with a lived scene, while turning available hot-post evidence into reusable, testable strategy.

**Architecture:** Keep the change in the existing asset and evaluation layers: shared `xhs_human_voice`, playbook-local `evaluation.yaml`, generic contract evaluation, deterministic dry-runs, DeepSeek hard requirements, and source-of-truth docs. Do not add a runtime branch for "human voice"; the runtime should keep loading playbook/skill assets and contracts as it already does.

**Tech Stack:** Python 3.12, pytest, YAML playbook contracts, Markdown prompt assets, deterministic drafting backend, DeepSeek prompt assembly, docs-sync, harness-check.

## Relevant Current Docs Summary

- `docs/index.md` says content and strategy work should start from `docs/playbooks.md`, `docs/skills.md`, and `docs/xhs-topics/index.md`, while code and current source-of-truth docs beat historical plans.
- `docs/development-workflow.md` classifies this as major development because it changes runtime-visible content generation behavior and evaluation contracts. It requires an isolated worktree, a dated plan, task-level `verify:` / `done_when:`, source-of-truth docs updates, and final `harness-check`.
- `docs/architecture.md` and `docs/runtime.md` already place title/body quality in assets, contracts, deterministic drafts, and DeepSeek hard requirements, not in new runtime orchestration branches.
- `docs/playbooks.md` says all nine current XHS playbooks share `xhs_human_voice`, body length bands, save/comment triggers, anti-generic title checks, and required content-quality judge gates.
- `docs/skills.md` says `xhs_human_voice` owns cross-domain human tone: warm, concrete, non-formulaic, short-title, first-screen hook, save action, and comment handoff.
- `docs/harness-engineering.md` says generic node-contract constraints should be extended before adding runtime branches.
- `docs/operations.md` says ordinary `run-playbook` should not live-scan XHS; bounded `collect-xhs-patterns` / `analyze-xhs-patterns` are the research path.

## Evidence Summary

### Live Grab Attempt On 2026-06-04

I attempted a fresh bounded XHS grab in the isolated worktree:

```bash
COOKIES_PATH=/Users/wudalu/llm-app/ptsm/cookies/fk-local.json \
  /Users/wudalu/llm-app/ptsm/.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane body_human_voice \
  --keywords "活人感,小红书文案,发疯文学,情绪管理,人类丰容" \
  --sample-limit-per-keyword 3 \
  --delay-seconds 0.5 \
  --skip-login-check \
  --tool-timeout-seconds 20 \
  --output-dir outputs/artifacts/xhs-body-human-voice
```

Observed output:

- `outputs/artifacts/xhs-body-human-voice/samples-2026-06-04.json`
- `sample_count: 0`
- `keyword_errors`: `活人感` and `小红书文案` both failed with `MCP connection failed — check if server is healthy`
- MCP logs showed `search_feeds` for `活人感` and `小红书文案` each returning HTTP 500 after about 20 seconds; `发疯文学` reached the tool before the process was stopped, but no usable sample rows were persisted.

This means the current fresh-grab attempt is reliability evidence, not hot-post evidence. Do not claim that 2026-06-04 live XHS samples were collected.

### Usable Local XHS Evidence

- `docs/research/2026-05-15-xhs-content-quality-sample-set.md` and `/Users/wudalu/llm-app/ptsm/outputs/artifacts/xhs-content-quality-search-2026-05-15.json` contain 117 real search-level XHS candidates across `发疯文学`, `打工人发疯`, `职场发疯`, `心理学`, `情绪管理`, `职场焦虑`, and `反刍思维`.
- High-score examples support the strategy:
  - `跳过情绪，看见事实。` had high collect/share weight, showing that short, screenshot-worthy cognition reframes work.
  - `看一次笑一次` had high comment/share weight, showing that repeatable social jokes beat generic venting.
  - `强女思维 | 工作越来越顺的一些Tips：` combines identity and saveable tips.
  - Low controls like `当代打工人抽象发疯实录 3.0（玩梗）` and `平静地发疯` show that broad mood labels underperform when they lack object, scene, or participation.
- `docs/research/2026-05-17-xhs-live-mcp-sample.md` records successful live search-level samples for human-enrichment adjacent lanes. It found strong hooks around `突然意识到...`, `人，你该...`, before/after contrast, low-cost methods, materials/process, and concrete comment prompts.

### Public 2026 Trend Refresh

Public sources still align with the local sample direction:

- 千瓜's 2026 XHS hotword report summary lists `抽象力`, `主体性`, `活人感`, `边界感`, `反精致`, `AI人格`, `代入感`, and `文化力`, plus signals such as `丝瓜汤` and `爱你老己`: https://www.qian-gua.com/information/detail/3318
- A recent summary of the same report describes `活人感` as a preference for real life texture over perfect filtered persona, and connects `丝瓜汤` / `三明治拒绝法` to boundary and self-positioning content: https://wwwsrc.wsdsocial.com/zh-cn/article/Top%2010%20Hot%20Words%20on%20Xiaohongshu
- A public operations-style note says 2026 XHS popular notes should trigger screenshot/save, long comments, and high-contribution interaction, not just likes: https://www.php.cn/faq/1956111.html

Use these as weak public trend context only; implementation should rely on repository-local sample artifacts and deterministic tests.

## Product Strategy

Turn "增加人味" into five testable body rules:

1. **现场锚点:** The body must include an exact moment, object, relationship, line, material, route, text, match scene, tool, or user action. Avoid opening with broad claims.
2. **真人视角:** Prefer first-person or direct reader perspective: `我`, `你`, `我们`, `今天`, `刚刚`, `下班`, `今晚`, `路上`, `桌上`, etc. This is not mandatory for every single sentence, but each body should sound situated.
3. **少总述:** Ban or discourage abstract essay framing such as `本文`, `建议大家`, `我们应该`, `本篇`, `从本质上`, `核心逻辑是`, `总体来说`.
4. **自然保存:** Keep save/comment mechanics, but remove visible internal labels. Write `我会把这三句存一下`, not `可保存单元：`.
5. **可接话结尾:** End with concrete participation: ask for a line, corner, route, role, example, sentence, tool boundary, watch moment, or character.

## Scope

In scope:

- `xhs_human_voice`
- generic contract evaluator support for body scene/person signals
- all nine XHS playbook `evaluation.yaml` contracts
- targeted prompt tests and playbook contract tests
- DeepSeek hard requirements
- representative deterministic dry-run body checks
- source-of-truth docs and research note

Out of scope:

- no new playbook/domain/account
- no real publishing
- no default live XHS lookup during ordinary generation
- no LLM judge rubric recalibration beyond existing gate
- no claim that 2026-06-04 live XHS hot posts were successfully sampled

## Task 1: Research Note And Plan

**Files:**
- Create: `docs/research/2026-06-04-xhs-body-human-voice-strategy.md`
- Create: `docs/plans/2026-06-04-xhs-body-human-voice.md`

**Step 1: Record the evidence**

Write a research note that includes:

- the exact 2026-06-04 `collect-xhs-patterns` command and the zero-sample failure;
- the local artifact path `outputs/artifacts/xhs-body-human-voice/samples-2026-06-04.json`;
- the 2026-05-15 and 2026-05-17 usable sample findings;
- the five body strategy rules above;
- public trend links as weak supporting context.

**Step 2: Save this implementation plan**

Keep all implementation work gated behind this plan and task-level verification.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**done_when:**

- Research note exists.
- Plan exists.
- The plan explicitly says the 2026-06-04 live grab produced zero usable samples.
- Docs metadata/map tests pass.

## Task 2: Generic Body Human-Voice Contract

**Files:**
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`

**Step 1: Write failing evaluator tests**

Add tests for two generic constraints:

```python
def test_fails_when_body_lacks_required_scene_signal(self):
    contract = PlaybookEvalContract(
        suite_id="human_voice.default",
        node_contracts={
            "executor": {
                "required_fields": ["title", "body", "hashtags"],
                "constraints": {
                    "body_must_include_scene_signal": True,
                    "body_scene_signal_any": ["领导", "工牌", "下班"],
                },
            }
        },
    )
    target = _target(
        phase="executor",
        target_type="artifact_slice",
        output_ref={
            "final_content": {
                "title": "下班那一秒",
                "body": "职场压力需要被合理释放。评论区接一句。",
                "hashtags": ["#发疯文学"],
            }
        },
    )
    result = contract_playbook_node_contract(target, contract)
    assert result.status == "failed"
    assert "body_must_include_scene_signal" in result.reason
```

```python
def test_passes_when_body_contains_scene_signal_and_human_anchor(self):
    contract = PlaybookEvalContract(
        suite_id="human_voice.default",
        node_contracts={
            "executor": {
                "required_fields": ["title", "body", "hashtags"],
                "constraints": {
                    "body_must_include_scene_signal": True,
                    "body_scene_signal_any": ["领导", "工牌", "下班"],
                    "body_human_anchor_any": ["我", "今天", "那一秒"],
                },
            }
        },
    )
    target = _target(
        phase="executor",
        target_type="artifact_slice",
        output_ref={
            "final_content": {
                "title": "下班那一秒",
                "body": "领导18:57发在吗那一秒，我的工牌已经想先下班。评论区接一句。",
                "hashtags": ["#发疯文学"],
            }
        },
    )
    result = contract_playbook_node_contract(target, contract)
    assert result.status == "passed"
```

**Step 2: Run tests to verify red**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py::TestPlaybookNodeContract::test_fails_when_body_lacks_required_scene_signal tests/unit/evaluations/test_contract_evaluators.py::TestPlaybookNodeContract::test_passes_when_body_contains_scene_signal_and_human_anchor -q
```

Expected before implementation: FAIL because `body_must_include_scene_signal` is currently ignored.

**Step 3: Implement evaluator support**

In `_constraint_failures` body block:

- when `body_must_include_scene_signal` is `true`, require at least one substring from `body_scene_signal_any`;
- if `body_human_anchor_any` is present, require at least one anchor too;
- reason text must include `body_must_include_scene_signal` or `body_human_anchor_any`.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

**done_when:**

- Missing scene signal fails.
- Body with concrete scene and human anchor passes.
- Existing contract evaluator tests still pass.

## Task 3: Configure All XHS Playbooks For Body Human Voice

**Files:**
- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Add failing playbook-contract test**

Add `BODY_SCENE_SIGNAL_MARKERS` per playbook and assert every XHS contract defines:

- `body_must_include_scene_signal: true`
- non-empty `body_scene_signal_any`
- non-empty `body_human_anchor_any`

Use domain-specific scene signals:

- `fengkuang_daily_post`: `领导`, `工牌`, `群聊`, `周报`, `早会`, `下班`, `工位`, `地铁`
- `modern_psychology_post`: `下班`, `会议`, `消息`, `睡前`, `关系`, `脑子`, `身体`, `今晚`, `那句话`
- `human_enrichment_daily_post`: `角落`, `书桌`, `床头`, `路线`, `材料`, `今天`, `十分钟`, `手边`
- `sushi_poetry_daily_post`: `苏轼`, `夜里`, `这一句`, `风雨`, `月亮`, `旧友`, `今天`
- `daily_english_post`: `今天`, `开会`, `私聊`, `这句`, `例句`, `评论区`, `你会怎么说`
- `ai_tech_daily_post`: `AI`, `工具`, `普通人`, `今天`, `工作流`, `试`, `边界`
- `world_cup_daily_post`: `赛前`, `看球`, `普通球迷`, `今晚`, `这场`, `评论区`
- `reddit_curation_daily_post`: `AI`, `工具`, `压力`, `消息`, `普通人`, `今天`, `你现在`
- `wuxia_character_post`: `令狐冲`, `黄蓉`, `郭靖`, `这一段`, `原文`, `今天`, `职场`

Shared human anchors can include `我`, `你`, `我们`, `今天`, `刚刚`, `那一秒`, `今晚`, `路上`, `手边`, `这句`, `这个`.

**Step 2: Run test to verify red**

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py::TestPlaybookEvalContract::test_all_xhs_contracts_require_body_scene_and_human_anchors -q
```

Expected before implementation: FAIL for most playbooks because only `fengkuang_daily_post` has an unused boolean flag and no signal lists.

**Step 3: Update playbook `evaluation.yaml` files**

Add the fields to each executor constraints block without removing existing safety, save, comment, title, and length constraints.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py tests/unit/evaluations/test_contract_evaluators.py -q
```

**done_when:**

- Every XHS playbook has body scene/person anchor constraints.
- All existing title/body/hashtag/safety constraints remain.

## Task 4: Prompt Assets And DeepSeek Human-Voice Requirements

**Files:**
- Modify: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: selected domain style prompt assets only if tests reveal a gap
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/unit/skills/test_skill_loader.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`

**Step 1: Add/update failing tests**

In `test_skill_loader_reads_shared_xhs_human_voice_skill`, assert the shared skill contains:

- `现场锚点`
- `真人视角`
- `少总述`
- `自然保存`
- `可接话结尾`

In `test_factory_deepseek_prompt_includes_title_body_appeal_requirements`, assert the DeepSeek hard requirements include:

- `现场锚点`
- `真人视角`
- `不要先总述`
- `自然保存`

**Step 2: Run tests to verify red**

```bash
uv run pytest tests/unit/skills/test_skill_loader.py::test_skill_loader_reads_shared_xhs_human_voice_skill tests/unit/infrastructure/llm/test_factory.py::test_factory_deepseek_prompt_includes_title_body_appeal_requirements -q
```

Expected before implementation: FAIL because those exact rules are not present.

**Step 3: Update assets and prompt assembly**

Update `xhs_human_voice` with the five body strategy rules and concrete examples. Update `_build_deepseek_hard_requirements()` to carry the same body rule in one concise sentence.

**verify:**

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py -q
```

**done_when:**

- Shared skill carries the five body strategy rules.
- DeepSeek prompt receives the same rules.
- Tests pass.

## Task 5: Deterministic Dry-Run Body Quality Checks

**Files:**
- Modify: `tests/e2e/test_xhs_title_body_quality_contracts.py`
- Modify: deterministic drafts in `src/ptsm/infrastructure/llm/contextual_drafts.py` only if tests reveal a real miss
- Modify: fallback deterministic draft path in `src/ptsm/infrastructure/llm/factory.py` only if `fengkuang_daily_post` or generic fallback misses the new contract

**Step 1: Add dry-run assertions**

In `test_xhs_playbook_dry_runs_fit_title_body_quality_contract`, add per-playbook expectations for:

- at least one domain scene signal in the body;
- at least one shared human anchor in the body;
- no abstract body markers: `本文`, `本篇`, `从本质上`, `总体来说`, `核心逻辑是`, `建议大家`.

**Step 2: Run e2e test to verify current behavior**

```bash
uv run pytest tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

Expected: may fail for one or more deterministic drafts that are valid but too generic.

**Step 3: Update deterministic drafts only where needed**

Keep body length and domain safety constraints intact. Add small scene anchors rather than broad rewrites.

**verify:**

```bash
uv run pytest tests/e2e/test_xhs_title_body_quality_contracts.py -q
```

**done_when:**

- All nine deterministic XHS dry-runs pass title/body length, no functional labels, scene signal, human anchor, and no abstract body markers.

## Task 6: Source-Of-Truth Docs

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Review: `docs/xhs-topics/index.md`

**Step 1: Update docs**

Document:

- body human voice stays in asset/contract layer;
- contract evaluator supports body scene signal and human anchor checks;
- all XHS playbooks now require body scene/person anchors;
- live XHS sampling on 2026-06-04 failed with MCP 500/connection failures, so ordinary generation still relies on local samples/snapshots;
- operators should use bounded `collect-xhs-patterns` for future hot-post refreshes.

If `docs/xhs-topics/index.md` remains unchanged, record the reason in the handoff: no new topic taxonomy or domain coverage changed.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/evaluations/contracts_eval.py --changed-path src/ptsm/infrastructure/llm/factory.py --changed-path src/ptsm/skills/builtin/xhs_human_voice/SKILL.md --changed-path src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml --changed-path docs/architecture.md --changed-path docs/runtime.md --changed-path docs/playbooks.md --changed-path docs/skills.md --changed-path docs/harness-engineering.md --changed-path docs/operations.md
```

**done_when:**

- Docs tests pass.
- Docs-sync passes with changed paths.
- Source-of-truth docs mention the new body human voice contract.

## Task 7: Final Verification

**Files:**
- No new source files expected.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py tests/e2e/test_xhs_title_body_quality_contracts.py -q
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:**

- Targeted tests pass.
- Non-e2e baseline passes.
- Harness-check passes, or any failure is captured with exact evidence and is unrelated/pre-existing.
- `git diff` only contains this body human-voice change set.
