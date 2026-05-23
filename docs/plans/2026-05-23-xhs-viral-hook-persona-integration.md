# XHS Viral Hook Persona Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate the 2026-05-23 Xiaohongshu viral meme/product-hook research into existing PTSM prompts, persona, style skills, and deterministic evaluation so generated XHS content feels warm, tuned, human, and non-template-like.

**Architecture:** Keep the change inside existing playbook, skill, LLM fake-backend, and evaluation extension points. Add one shared builtin skill for XHS human voice, enrich domain-local prompt/style assets, and extend generic contract evaluators instead of adding runtime branches or a new domain.

**Tech Stack:** Python, Pytest, YAML playbook definitions, Markdown prompt/skill assets, `uv`, `ptsm.bootstrap` CLI.

## Current Docs Summary

- `docs/index.md` is the active docs entrypoint and points agents to `architecture.md`, `runtime.md`, `playbooks.md`, `skills.md`, `xhs-topics/index.md`, `operations.md`, and `harness-engineering.md` before implementation.
- `docs/development-workflow.md` requires major development to use an isolated worktree, read active docs, write a plan under `docs/plans/`, define verification before implementation, update source-of-truth docs, then run `harness-check`.
- `docs/harness-engineering.md` treats `docs-sync` as a minimum gate and requires new or broad playbook/skill/eval changes to update the wider documentation surface, including `runtime.md`, `playbooks.md`, `skills.md`, `harness-engineering.md`, and `docs/operations.md`.
- Existing XHS playbooks already share `xhs_image_strategy`; this change adds a second cross-domain content quality skill focused on human voice, warmth, platform-native interaction, and anti-template phrasing.

## Scope

- Affected playbooks: `fengkuang_daily_post`, `modern_psychology_post`, `human_enrichment_daily_post`, `ai_tech_daily_post`, `sushi_poetry_daily_post`, `wuxia_character_post`, `daily_english_post`, `world_cup_daily_post`.
- Affected skill families: new `xhs_human_voice`; selected domain style skills where the research maps to concrete topic mechanics.
- Affected validation: generic contract evaluator support for title hook terms and cross-field forbidden template markers.
- Non-goals: no new domain, no new account, no real XHS publish flow, no live MCP dependency, no LLM judge policy change.

### Task 1: Shared XHS Human Voice Skill

**Files:**
- Create: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/*/playbook.yaml`
- Test: `tests/unit/playbooks/test_playbook_registry.py`
- Test: `tests/unit/skills/test_skill_loader.py`

**Steps:**
1. Write failing tests that all XHS playbooks include `xhs_human_voice` and the skill loader can read the new skill.
2. Run targeted tests and confirm they fail because the skill and required-skill entries are absent.
3. Add the shared skill with voice rules: warm, specific, platform-native, one living scene, no obvious outline markers.
4. Add `xhs_human_voice` to each affected playbook's `required_skills`.
5. Run targeted tests again.

**verify:**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

**done_when:** All affected playbooks load with the shared human voice skill and the skill text contains the anti-template persona guidance.

### Task 2: Prompt, Persona, Reflection, And Style Integration

**Files:**
- Modify: `src/ptsm/playbooks/definitions/*/{planner,persona,reflection}.md`
- Modify: `src/ptsm/skills/builtin/*_style/SKILL.md`
- Test: `tests/unit/playbooks/test_playbook_registry.py`
- Test: `tests/unit/skills/test_skill_loader.py`

**Steps:**
1. Add tests that key prompt/style assets contain the research mechanics they are expected to use.
2. Run targeted tests and confirm the missing terms fail.
3. Add domain-specific hooks conservatively:
   - Fengkuang: high-style shell plus embarrassing workplace core, `丝瓜汤式沟通`, object meltdown.
   - Psychology: `爱你老己`, `三明治拒绝法`, AI companionship boundary, warmer boundary scripts.
   - Human enrichment: `适我主义`, new solo living, handcraft micro-flow.
   - AI tech: AI life companion and ordinary-person workflow.
   - Sushi poetry: culture power, non-heritage/handcraft/seasonal context.
   - Wuxia: old-school personality, boundary, subjectivity.
   - Daily English and World Cup: warm companion voice and no classroom/media-report posture.
4. Run targeted tests again.

**verify:**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

**done_when:** Prompt, persona, reflection, and style assets encode research-informed mechanics without converting every post into trend stuffing.

### Task 3: Generic Evaluation Contract Extensions

**Files:**
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Test: `tests/unit/evaluations/test_contract_evaluators.py`
- Test: `tests/unit/evaluations/test_playbook_contracts.py`

**Steps:**
1. Add failing evaluator tests for `title_must_include_any` and `combined_must_not_include_any`.
2. Run the evaluator tests and confirm the fields are ignored before implementation.
3. Implement the two contract checks inside the generic contract evaluator.
4. Add cross-field anti-template markers to all XHS playbooks.
5. Add title hook term requirements to the research-affected playbooks where deterministic coverage is stable.
6. Run evaluator and playbook-contract tests.

**verify:**

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py -q
```

**done_when:** Contracts can block formulaic template language across title, cover text, and body, and key playbooks require concrete title hooks.

### Task 4: Deterministic Dry-Run Coverage

**Files:**
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`
- Modify: `tests/e2e/test_human_enrichment_publish_dry_run.py`

**Steps:**
1. Add dry-run tests for representative research hooks: `丝瓜汤`, `三明治拒绝法`, and `适我主义`/new solo living.
2. Run the focused e2e tests and confirm the deterministic drafts do not yet expose those mechanics.
3. Add narrow fake-backend/contextual draft branches for the tested hooks.
4. Keep image-generation assertions compatible with either configured provider output or local note-card fallback.
5. Run focused e2e tests.

**verify:**

```bash
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

**done_when:** Representative dry-runs complete and generated content includes the intended human, concrete, platform-native hooks without forbidden template markers.

### Task 5: Source-Of-Truth Docs And Docs Gates

**Files:**
- Create: `docs/plans/2026-05-23-xhs-viral-hook-persona-integration.md`
- Create: `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/runtime.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations.md`
- Modify: `docs/xhs-topics/index.md`

**Steps:**
1. Add this implementation plan and keep the research note linked from active XHS topic docs.
2. Update `skills.md` with `xhs_human_voice` and the style-skill research mechanics.
3. Update `playbooks.md` with the shared skill, prompt/persona shift, and eval contract additions.
4. Update `runtime.md` for deterministic dry-run and generic eval contract behavior.
5. Update `harness-engineering.md` for the new cross-field anti-template and title-hook gates.
6. Update `operations.md` only where operator-discoverable dry-run/eval guidance changes.
7. Run docs metadata/map tests and docs-sync changed-path checks.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/skills/builtin/xhs_human_voice/SKILL.md --changed-path docs/skills.md
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/playbooks/definitions/fengkuang_daily_post/planner.md --changed-path docs/playbooks.md
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/evaluations/contracts_eval.py --changed-path docs/harness-engineering.md
```

**done_when:** Active source-of-truth docs describe the changed content surfaces and docs-sync accepts the representative code-to-doc mappings.

### Task 6: Final Verification And Handoff

**Files:**
- No new files.

**Steps:**
1. Run the combined targeted suite for all changed units and representative e2e tests.
2. Run the full non-e2e suite.
3. Run the repository harness gate from the isolated worktree.
4. Summarize verification evidence and any remaining manual publish steps.

**verify:**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:** Targeted tests, non-e2e suite, and harness gate pass inside `.worktrees/xhs-viral-hook-integration`; no real publish action is required.
