# XHS Title Body Appeal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve title click appeal and cross-domain body organization/length for all current Xiaohongshu playbooks without adding new domains or live-XHS dependencies.

**Architecture:** Keep the change inside existing playbook, skill, deterministic draft, and evaluation-contract surfaces. Add one generic contract constraint for substring title bans, tighten playbook-local body bands, update shared/domain prompt assets, and make the deterministic/DeepSeek drafting paths consume the same title/body rules.

**Tech Stack:** Python 3.12, pytest, YAML playbook contracts, Markdown prompt assets, PTSM deterministic drafting backend, `docs-sync`, and `harness-check`.

## Relevant Current Docs Summary

- `docs/index.md` says content and strategy work should start from `playbooks.md`, `skills.md`, and XHS topic docs, while historical plans are not current truth when they conflict with code.
- `docs/development-workflow.md` classifies this as major development because it changes playbook prompts, skills, runtime-visible generation behavior, and harness contracts. It requires an isolated worktree, a dated plan, task-level `verify:` and `done_when:`, source-of-truth docs updates, and final `harness-check`.
- `docs/architecture.md` places playbook/persona/skill behavior in `src/ptsm/playbooks/definitions` and `src/ptsm/skills/builtin`, deterministic eval behavior in `src/ptsm/evaluations/contracts_eval.py`, and LLM provider prompt assembly in `src/ptsm/infrastructure/llm`.
- `docs/runtime.md` says deterministic and DeepSeek drafting read playbook persona, planner prompt, static scoped skills, and runtime context. Ordinary generation should not depend on live XHS MCP.
- `docs/playbooks.md` says all nine current XHS playbooks use `xhs_human_voice`, have playbook-local `evaluation.yaml`, and should express persona/hook behavior through assets rather than runtime branches.
- `docs/skills.md` says `xhs_human_voice` is the shared place for warm, concrete, platform-native human voice, while domain style skills define what each account says and how.
- `docs/harness-engineering.md` says XHS content quality should use generic playbook node-contract constraints and deterministic tests before optional LLM judge calibration.
- `docs/operations.md` records `collect-xhs-patterns` / `analyze-xhs-patterns` as periodic research paths. The 2026-05-24 attempt confirmed MCP/browser access can be unstable, so this change must not add live XHS to the ordinary generation path.

## Research Summary

See `docs/research/2026-05-24-xhs-title-body-appeal-synthesis.md`.

Key conclusions:

- Good XHS titles are not broad category labels. They need a concrete scene/object/role plus tension, utility, or identity.
- Good bodies have four moves: first-screen hook, domain substance, saveable unit, concrete comment handoff.
- Body length should be domain-specific. Wuxia can stay long, but most domains should fit 120-700 chars.
- Fresh live sampling on 2026-05-24 was attempted but failed due MCP 500/timeouts and browser IP-risk login, so implementation should use local snapshots, public trend summaries, and deterministic verification.

## Scope

In scope:

- all nine current XHS playbooks;
- `xhs_human_voice` and affected domain style/planner/reflection assets;
- playbook-local `evaluation.yaml` body length bands and title generic bans;
- contract evaluator support for `title_must_not_include_any`;
- deterministic draft updates where current outputs exceed or underuse the new title/body rules;
- DeepSeek hard requirements for title/body organization;
- source-of-truth docs and targeted tests.

Out of scope:

- no new account, playbook, skill, or domain;
- no real publishing;
- no live XHS lookup during ordinary `run-playbook`;
- no LLM judge rubric calibration beyond existing content-quality gate.

## Task 1: Research And Plan Artifacts

**Files:**

- Create: `docs/research/2026-05-24-xhs-title-body-appeal-synthesis.md`
- Create: `docs/plans/2026-05-24-xhs-title-body-appeal.md`

**Step 1: Verify docs metadata before edits**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS on current baseline.

**Step 2: Record the research synthesis**

Document:

- local sample evidence from 2026-05-15 and 2026-05-17;
- 2026-05-24 fresh-check commands and failures;
- public source links used for current trend read;
- title/body/length rules.

**Step 3: Write this implementation plan**

Include exact files, verification commands, and done criteria.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**done_when:**

- Research note exists and is linked from this plan.
- Plan states the body length bands and implementation sequence.
- Docs metadata and map tests pass.

## Task 2: Contract Evaluator Title Generic Ban

**Files:**

- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`

**Step 1: Write the failing test**

Add a test showing `title_must_not_include_any` fails on substring-level generic markers:

```python
def test_fails_when_title_contains_forbidden_generic_marker(self):
    contract = PlaybookEvalContract(
        suite_id="title.default",
        node_contracts={
            "executor": {
                "required_fields": ["title", "body", "hashtags"],
                "constraints": {"title_must_not_include_any": ["实录", "小红书爆款"]},
            }
        },
    )
    target = _target(
        phase="executor",
        target_type="artifact_slice",
        output_ref={
            "final_content": {
                "title": "打工人地铁生存实录",
                "body": "评论区接一句。",
                "hashtags": ["#发疯文学"],
            }
        },
    )

    result = contract_playbook_node_contract(target, contract)

    assert result.status == "failed"
    assert "title_must_not_include_any" in result.reason
```

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py::TestPlaybookNodeContract::test_fails_when_title_contains_forbidden_generic_marker -q
```

Expected before implementation: FAIL because the evaluator ignores the new constraint.

**Step 2: Implement evaluator support**

In `_constraint_failures`, when `title` is a string:

- read `_string_list(constraints.get("title_must_not_include_any"))`;
- append a failure when any term is a substring of `title`;
- evidence path should be `final_content.title` for executor targets.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

**done_when:**

- New test fails before implementation and passes after implementation.
- Existing title equality and title required-term tests still pass.

## Task 3: Playbook Contract Length Bands And Title Bans

**Files:**

- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Write failing contract tests**

Add tests that assert:

- every XHS playbook has `body_min_chars` and `body_max_chars`;
- each `body_max_chars` matches the planned upper bound:
  - `fengkuang_daily_post`: 380
  - `modern_psychology_post`: 620
  - `human_enrichment_daily_post`: 520
  - `sushi_poetry_daily_post`: 520
  - `daily_english_post`: 520
  - `ai_tech_daily_post`: 650
  - `world_cup_daily_post`: 620
  - `reddit_curation_daily_post`: 700
  - `wuxia_character_post`: 1100
- every XHS playbook has `title_must_not_include_any` with generic markers relevant to its domain.

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py::TestPlaybookEvalContract::test_all_xhs_contracts_define_domain_specific_body_length_bands tests/unit/evaluations/test_playbook_contracts.py::TestPlaybookEvalContract::test_all_xhs_contracts_block_generic_title_substrings -q
```

Expected before implementation: FAIL because several playbooks have no body length band and no substring title ban.

**Step 2: Update `evaluation.yaml` files**

Apply length bands:

- `fengkuang_daily_post`: `body_min_chars: 120`, `body_max_chars: 380`
- `modern_psychology_post`: `body_min_chars: 260`, `body_max_chars: 620`
- `human_enrichment_daily_post`: `body_min_chars: 180`, `body_max_chars: 520`
- `sushi_poetry_daily_post`: keep min at 180, lower max to 520
- `daily_english_post`: keep min at 180, lower max to 520
- `ai_tech_daily_post`: keep min at 220, lower max to 650
- `world_cup_daily_post`: lower max to 620
- `reddit_curation_daily_post`: lower max to 700
- `wuxia_character_post`: lower band to 700-1100

Add `title_must_not_include_any` to all XHS playbooks with generic category/title markers, while preserving existing `title_must_include_any`, `combined_must_not_include_any`, save/comment triggers, and safety constraints.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py tests/unit/evaluations/test_contract_evaluators.py -q
```

**done_when:**

- All XHS playbooks have explicit body min/max.
- Generic title substring bans are present and enforceable.
- Existing required tags, body terms, save/comment triggers, and safety terms remain present.

## Task 4: Prompt Assets For Title And Body Organization

**Files:**

- Modify: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: selected domain style skills under `src/ptsm/skills/builtin/*_style/SKILL.md`
- Modify: selected `src/ptsm/playbooks/definitions/*/{planner.md,reflection.md,persona.md}`
- Modify: `tests/unit/skills/test_skill_loader.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`

**Step 1: Write failing prompt-asset tests**

Add tests asserting:

- `xhs_human_voice` contains the four body moves: `首屏钩子`, `领域要素`, `可保存单元`, `评论交接`;
- `xhs_human_voice` contains title guidance around `具体场景`, `冲突`, `身份`, `工具`, and forbids `泛标题`;
- key playbook prompt bundles include `正文长度`, `首屏钩子`, and `可保存单元`.

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/playbooks/test_playbook_registry.py -q
```

Expected before implementation: FAIL because these exact rules are not present.

**Step 2: Update shared and domain prompt assets**

Update:

- `xhs_human_voice`: shared title formula, four body moves, domain-length discipline, no generic title labels.
- `fengkuang_style` / planner / reflection: short joke-social-object structure, 120-380 chars, object + copyable line + comment game.
- `psychology_style` / planner / reflection: 260-620 chars, micro-scene then mechanism, save tool, professional boundary, example comment.
- `human_enrichment_style` / planner / reflection: 180-520 chars, corner/material/route variable, low-cost action, three-step save unit.
- AI / English / Su Shi / Wuxia / World Cup / Reddit assets only where needed to make length and first-screen hook expectations explicit.

**verify:**

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/playbooks/test_playbook_registry.py -q
```

**done_when:**

- Shared skill and prompt assets explicitly encode the title/body organization rules.
- Tests prove the prompt surface contains the rules operators expect.
- No prompt asks the model to reveal internal labels such as `comment_chain`, `save_tool`, `identity_conflict`, `pattern_id`, or `hook_archetypes` in final content.

## Task 5: Drafting Backend Guidance And Deterministic Outputs

**Files:**

- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: targeted e2e tests under `tests/e2e/`
- Optionally modify: `tests/unit/infrastructure/llm/` if a suitable unit-test file exists or should be added.

**Step 1: Write failing tests**

Add targeted assertions that representative dry-runs stay inside body bands and keep concrete hook titles:

- `fengkuang_daily_post`: body <= 380 and title does not contain `实录` / `日常`.
- `modern_psychology_post`: body between 260 and 620 and title contains a concrete reframe such as `不是你` or `边界`.
- `human_enrichment_daily_post`: body <= 520 and title contains `丰容`, `变量`, `角落`, `书桌`, `路线`, or `材料`.
- `wuxia_character_post`: body <= 1100.
- `ai_tech_daily_post`, `daily_english_post`, `world_cup_daily_post`, and `reddit_curation_daily_post`: body <= configured max.

Run a narrow subset first:

```bash
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

Expected before implementation: at least one failure once the tests assert the new bands and title bans.

**Step 2: Add DeepSeek hard requirement guidance**

Update `_build_deepseek_hard_requirements()` to infer playbook/domain context and append:

- title must be a concrete click hook, not a category label;
- body must use first-screen hook, domain substance, saveable unit, concrete comment handoff;
- body should follow the domain-specific target range.

**Step 3: Update deterministic drafts**

Keep drafts natural while satisfying the new bands:

- shorten AI, World Cup, Reddit, and Wuxia drafts where needed;
- keep Psychology and Human Enrichment complete but compact;
- ensure Fengkuang titles and bodies stay short and strongly participatory.

**verify:**

```bash
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run pytest tests/e2e/test_ai_tech_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py tests/e2e/test_sushi_poetry_publish_dry_run.py tests/e2e/test_world_cup_publish_dry_run.py tests/e2e/test_wuxia_publish_dry_run.py tests/e2e/test_reddit_curation_publish_dry_run.py -q
```

**done_when:**

- Deterministic dry-runs pass the new title/body contracts.
- The DeepSeek path receives explicit title/body requirements through existing prompt assembly.
- Outputs remain structurally complete and do not merely become shorter.

## Task 6: Source-Of-Truth Docs

**Files:**

- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Review and modify if needed: `docs/operations/content-experiment-runbook.md`
- Review and modify if needed: `docs/operations/topic-radar-runbook.md`

**Step 1: Update docs in the same change as behavior**

Document:

- title generic substring bans are now part of playbook contract evaluation;
- all XHS playbooks have domain-specific body length bands;
- `xhs_human_voice` owns the shared title/body organization rules;
- DeepSeek and deterministic drafting both receive these rules;
- live XHS sampling remains periodic/operator-driven, not a normal generation dependency.

**Step 2: Review operations runbooks**

If no operational command changes are needed, record that in final handoff. If the content-experiment or topic-radar runbooks mention old length or live-sampling assumptions, update them.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/evaluations/contracts_eval.py --changed-path src/ptsm/playbooks/definitions/fengkuang_daily_post/evaluation.yaml --changed-path src/ptsm/skills/builtin/xhs_human_voice/SKILL.md --changed-path src/ptsm/infrastructure/llm/factory.py
```

**done_when:**

- Source-of-truth docs match the implemented runtime/eval/prompt behavior.
- Docs-sync accepts representative changed code paths.
- Any intentionally unchanged runbook is named in the handoff.

## Task 7: Final Verification And Merge

**Files:**

- Verify only.

**Step 1: Run targeted suites**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py -q
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/playbooks/test_playbook_registry.py -q
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

**Step 2: Run broad local verification**

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**Step 3: Review worktree**

```bash
git status --short
git diff --stat
```

**done_when:**

- Targeted tests pass.
- Full pytest and harness-check pass, or failures are documented with exact output and next action.
- Worktree is ready to merge back to `main`.
