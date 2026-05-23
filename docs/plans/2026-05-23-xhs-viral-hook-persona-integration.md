# XHS Viral Hook Persona Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Turn the 2026-05-23 XHS viral hook research into PTSM prompt, persona, style, and deterministic verification improvements for existing Xiaohongshu playbooks.

**Architecture:** Keep the change additive inside current playbook + skill + eval-contract surfaces. Do not add a new domain, account, publisher, or runtime branch. Use one shared XHS voice skill for project-wide warmth/persona, playbook-local prompt edits for domain-specific hooks, and contract evaluator constraints for deterministic harness coverage.

**Tech Stack:** Python 3.12, pytest, YAML playbook definitions, Markdown prompt assets, deterministic drafting backend, PTSM playbook-local `evaluation.yaml`, `docs-sync`, `harness-check`.

## Relevant Current Docs Summary

- `AGENTS.md` requires major development to use a feature branch and isolated worktree, read `docs/index.md` and `docs/development-workflow.md`, summarize current docs before planning/coding, create a dated plan with `verify:` / `done_when:`, implement and test inside the worktree, update source-of-truth docs, then run `harness-check`.
- `docs/development-workflow.md` says this scope is major work because it changes playbook prompts, skills, and harness rules. It requires TDD for behavior changes, task-level verification, end-to-end dry-run evidence, source-of-truth docs updates, and a final harness gate.
- `docs/harness-engineering.md` says PTSM already has deterministic pytest, docs-sync, playbook-local eval contracts, content quality gates, local XHS pattern library, and required content-quality judge metadata. New verification should extend playbook-local contracts rather than hard-code runtime branches.
- `docs/architecture.md` says playbook/persona/skill assets belong under `src/ptsm/playbooks/definitions` and `src/ptsm/skills/builtin`; eval contract behavior belongs in `src/ptsm/evaluations/contracts_eval.py`; ordinary XHS generation should consume local patterns and static scoped skills without live MCP by default.
- `docs/playbooks.md` says there are eight real XHS playbooks and all have `evaluation.yaml`. The most relevant playbooks for this research are `human_enrichment_daily_post`, `modern_psychology_post`, and `fengkuang_daily_post`, but the user also asked for whole-project persona improvements.
- `docs/skills.md` says scoped builtin skills are how style and platform mechanics enter the drafting prompt. A shared `xiaohongshu` skill is the correct place for project-wide voice rules.
- `docs/xhs-topics/verticals.md` and `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md` establish the content inputs: human enrichment, boundary/self-care, object-based workplace emotion, AI as life helper, culture/handcraft, old-style reliability, pet/culture lanes, and avoidance of pure trend stuffing.

## Scope

In scope:

- Add a shared `xhs_human_voice` builtin skill and require it in all existing XHS playbooks.
- Update prompt/persona/style assets so outputs are warmer, more tasteful, less formatted, and closer to a real creator.
- Apply viral hook research to existing playbooks without changing routing:
  - `fengkuang_daily_post`: object-based workplace emotion, abstract/high-elegance mechanism, silk-soup-style indirect conflict, copyable lines.
  - `modern_psychology_post`: `爱你老己`, boundary tools, sandwich refusal, silk-soup communication, AI companion boundary, non-diagnostic warmth.
  - `human_enrichment_daily_post`: `人你该丰容了`, `适我主义`, new solo living, handcraft/material flow, micro-scene variables.
  - `ai_tech_daily_post`: AI life helper / ordinary-person workflow framing.
  - `sushi_poetry_daily_post`: culture power, handmade/holiday micro-scenes, warm reader voice.
  - `wuxia_character_post`: old-style reliability, subjectivity, boundary/personality hooks.
  - `daily_english_post` and `world_cup_daily_post`: inherit shared human voice and avoid generic classroom/report tone.
- Extend deterministic contract evaluator coverage for title hook presence and cross-field template-language bans.
- Update source-of-truth docs for skills, playbooks, harness expectations, runtime/eval behavior, and operations command discoverability.

Out of scope:

- No real Xiaohongshu publishing.
- No new account, new playbook, or new external MCP workflow.
- No LLM-judge calibration work beyond existing metadata.
- No broad refactor of drafting, image generation, or topic-radar internals.

## Design Decisions

Recommended approach: shared voice skill + playbook-local hook prompts + deterministic eval constraints.

Tradeoffs considered:

- Only editing playbook prose would be fast, but would leave whole-project persona inconsistent and weakly tested.
- Adding a runtime persona layer would centralize voice, but it would be a larger architecture change and unnecessary because scoped skills already solve this.
- A shared skill plus playbook-local evals matches the current architecture and gives docs-sync/harness a concrete surface to verify.

## Task 1: Shared XHS Human Voice Skill

**Files:**

- Create: `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/*/playbook.yaml`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`
- Modify: `tests/unit/skills/test_skill_loader.py`

**Step 1: Write failing tests**

- Add a registry test asserting every current XHS playbook includes `xhs_human_voice` in `required_skills`.
- Add a skill loader test asserting `xhs_human_voice` contains core voice rules: `温暖`, `真人`, `不格式化`, `具体场景`.

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

Expected before implementation: failure because the skill and required-skill entries do not exist.

**Step 2: Implement**

- Create the shared skill with rules:
  - warm but not saccharine
  - specific scene before conclusion
  - one platform-native action per post
  - avoid `首先/其次/最后/综上/本文/作为AI/模板化总结`
  - avoid trend stuffing
  - keep a real creator voice with small imperfections and clear boundaries
- Add `xhs_human_voice` after `xhs_image_strategy` in all eight XHS playbooks.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

done_when:

- All current XHS playbooks require `xhs_human_voice`.
- The new skill loads through `SkillRegistry` / `SkillLoader`.
- Existing required-skill ordering remains deterministic.

## Task 2: Contract Evaluator Extensions

**Files:**

- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`

**Step 1: Write failing tests**

Add tests for two new deterministic constraints:

- `title_must_include_any`: fails when a title has none of the required hook/object terms.
- `combined_must_not_include_any`: fails when forbidden template wording appears in title, image text, or body.

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

Expected before implementation: failure because these constraints are ignored.

**Step 2: Implement**

- In `_constraint_failures`, evaluate `title_must_include_any` against `title`.
- Build a `combined_text` from title, image_text, and body; evaluate `combined_must_not_include_any`.
- Keep error evidence consistent with existing evaluator shape.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/unit/evaluations/test_contract_evaluators.py -q
```

done_when:

- New constraints fail and pass deterministically.
- Existing contract evaluator tests still pass.

## Task 3: Prompt, Persona, And Skill Updates

**Files:**

- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/modern_psychology_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/human_enrichment_daily_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/ai_tech_daily_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/wuxia_character_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/daily_english_post/{planner.md,persona.md,reflection.md}`
- Modify: `src/ptsm/playbooks/definitions/world_cup_daily_post/{planner.md,persona.md,reflection.md}`
- Modify: relevant `src/ptsm/skills/builtin/*/SKILL.md`

**Step 1: Write failing prompt-asset tests**

Use focused static tests in existing unit files where possible:

- `test_playbook_registry.py`: assert key playbook prompts include the new research terms and voice constraints.
- `test_skill_loader.py`: assert shared and domain skills expose core mechanics.

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

Expected before implementation: failure because prompt assets do not yet contain the new voice/hook language.

**Step 2: Implement prompt edits**

- Keep each playbook's existing domain contract.
- Add domain-specific research mechanics without copying sample titles.
- Add whole-project voice guidance: warmer, less formatted, more creator-like, fewer template transitions.
- Keep safety boundaries intact.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py -q
```

done_when:

- Prompt assets contain the planned hook/persona rules.
- No prompt asks the model to leak internal labels such as `comment_chain`, `save_tool`, `identity_conflict`, or `pattern_id` into final content.

## Task 4: Evaluation Contract Tightening

**Files:**

- Modify: `src/ptsm/playbooks/definitions/*/evaluation.yaml`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`

**Step 1: Write failing contract tests**

Add assertions that all XHS playbook contracts include:

- `combined_must_not_include_any` with core formulaic/meta markers.
- For key playbooks, `title_must_include_any` with domain-specific hook/object terms.
- Existing safety and leakage constraints remain present.

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py -q
```

Expected before implementation: failure because the new contract fields are missing.

**Step 2: Implement**

- Add `combined_must_not_include_any` to all eight XHS `evaluation.yaml` files.
- Add targeted `title_must_include_any` to the six most research-affected playbooks.
- Tighten body includes where needed for viral mechanisms while avoiding brittle exact phrasing.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/unit/evaluations/test_playbook_contracts.py tests/unit/evaluations/test_contract_evaluators.py -q
```

done_when:

- Contract tests prove the new fields exist.
- Contract evaluator tests prove the new fields are enforced.

## Task 5: Deterministic Draft And E2E Dry-Run Coverage

**Files:**

- Modify: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify as needed: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`
- Modify: `tests/e2e/test_human_enrichment_publish_dry_run.py`
- Modify targeted e2e tests for AI/Su Shi/Wuxia if prompt contracts require output changes.

**Step 1: Write failing e2e assertions**

Add dry-run assertions that deterministic outputs:

- avoid formulaic markers from `combined_must_not_include_any`;
- include a concrete scene/object/hook;
- include one save/comment mechanism;
- keep warmth and safety boundaries where relevant.

Run:

```bash
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

Expected before implementation: at least one failure due to missing new persona/hook signal.

**Step 2: Implement**

- Update deterministic helpers only where test coverage exposes a real gap.
- Prefer prompt/config changes over code changes unless deterministic fallback needs to satisfy a tightened contract.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

done_when:

- Dry-runs complete.
- Outputs satisfy new voice/hook constraints and existing safety checks.

## Task 6: Source-Of-Truth Docs

**Files:**

- Modify: `docs/skills.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/runtime.md`
- Modify: `docs/operations.md`
- Modify as needed: `docs/xhs-topics/index.md`, `docs/xhs-topics/verticals.md`, `docs/xhs-topics/image-forms-by-domain.md`

**Step 1: Update docs**

- Document `xhs_human_voice`.
- Document which playbooks now explicitly consume viral hook/persona mechanics.
- Document new deterministic eval constraints.
- Document that no new domain/playbook/operation was added.

**Step 2: Verify docs**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/skills/builtin/xhs_human_voice/SKILL.md --changed-path docs/skills.md
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/playbooks/definitions/fengkuang_daily_post/planner.md --changed-path docs/playbooks.md
uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/evaluations/contracts_eval.py --changed-path docs/harness-engineering.md
```

done_when:

- Docs metadata/map tests pass.
- docs-sync recognizes matching source-of-truth updates for skill, playbook, and eval code changes.

## Task 7: Final Harness Verification

**Files:** no intended edits.

**Step 1: Run targeted unit/e2e set**

```bash
uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_loader.py tests/unit/evaluations/test_contract_evaluators.py tests/unit/evaluations/test_playbook_contracts.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_modern_psychology_publish_dry_run.py tests/e2e/test_human_enrichment_publish_dry_run.py -q
```

**Step 2: Run full non-e2e suite**

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 3: Run final harness gate**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

done_when:

- Targeted tests pass.
- Full non-e2e tests pass.
- `harness-check` exits 0.
- Handoff lists all docs updated and any checks that could not run.
