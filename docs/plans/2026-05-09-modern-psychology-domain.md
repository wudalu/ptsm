# Modern Psychology Domain Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a 现代心理困境观察 domain that publishes Xiaohongshu psychology education posts about modern stress, relationships, loneliness, digital life, and emotional regulation without providing diagnosis or treatment.

**Status:** implemented in this branch/workspace.

**Architecture:** Start with product documentation and research, then implement as an additive vertical slice: one playbook, one account definition, and three builtin skills. Keep runtime graph behavior unchanged. The only shared-code changes should be generic harness support: reusable playbook contract constraints for text/hashtag safety and a deterministic contextual draft helper so dry-run tests do not depend on live LLM access.

**Tech Stack:** Markdown research and PRD docs, YAML playbook/account definitions, builtin `SKILL.md` files, existing PTSM playbook/skill/account registries, pytest, `run-playbook` dry-run.

## Current Docs Summary

- `docs/index.md` says current truth starts from source-of-truth docs, and new domains should follow `docs/development-workflow.md`.
- `docs/development-workflow.md` requires a plan with `verify:` and `done_when:` checks before implementing new domains or playbooks.
- `docs/playbooks.md` defines a playbook as the business orchestration unit with `playbook.yaml`, `planner.md`, `persona.md`, and `reflection.md`.
- `docs/skills.md` says builtin skills should be selected by request-scoped domain/platform/playbook tags.
- `docs/topic-radar.md` and `docs/xhs-topics/verticals.md` show PTSM already has adjacent lanes: `情绪疗愈`, `轻养生`, `打工人日常`, plus dynamic trend/topic research input.

## Scope

- Product research: `docs/research/2026-05-09-modern-psychology-domain.md`
- PRD update: `prd.md`
- Future implementation:
  - Playbook: `modern_psychology_post`
  - Account: `acct-psychology-local`
  - Skills: `psychology_style`, `psychology_safety`, `xhs_psychology_hashtagging`
  - Evaluation: `modern_psychology_post/evaluation.yaml` plus generic text/hashtag contract constraints
  - Test support: deterministic contextual draft helper for offline psychology dry-run evidence
  - Tests and dry-run verification

## Non-goals

- No diagnosis, treatment, medication, crisis counseling, or user mental-health assessment.
- No interactive self-test or score-based screening.
- No real Xiaohongshu publish without dry-run evidence and manual approval.
- No runtime rewrite for this domain.

---

### Task 1: Research and PRD design docs

**Files:**
- Create: `docs/research/2026-05-09-modern-psychology-domain.md`
- Modify: `prd.md`
- Create: `docs/plans/2026-05-09-modern-psychology-domain.md`

**verify:**
```bash
uv run pytest -q tests/unit/docs
rg -n "现代心理困境观察|psychology|心理" prd.md docs/research/2026-05-09-modern-psychology-domain.md docs/plans/2026-05-09-modern-psychology-domain.md
```

**done_when:**
- Research note includes external sources, PTSM fit, content pillars, safety boundaries, and first experiment plan.
- PRD lists the psychology domain as planned, not implemented.
- The plan includes `verify:` and `done_when:` checks for current docs and future implementation.

---

### Task 2: Add account and playbook definitions

**Files:**
- Create: `src/ptsm/accounts/definitions/acct-psychology-local.yaml`
- Create: `src/ptsm/playbooks/definitions/modern_psychology_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/modern_psychology_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/modern_psychology_post/persona.md`
- Create: `src/ptsm/playbooks/definitions/modern_psychology_post/reflection.md`

**verify:**
```bash
uv run pytest -q tests/unit/accounts/test_account_registry.py tests/unit/playbooks/test_playbook_registry.py
```

**done_when:**
- `AccountRegistry` loads `acct-psychology-local`.
- `PlaybookRegistry` loads `modern_psychology_post`.
- The playbook domain is `现代心理困境观察`.
- Required skills include `xhs_trend_scan`, `topic_research`, `psychology_style`, `psychology_safety`, and `xhs_psychology_hashtagging`.

---

### Task 3: Add psychology skills

**Files:**
- Create: `src/ptsm/skills/builtin/psychology_style/SKILL.md`
- Create: `src/ptsm/skills/builtin/psychology_safety/SKILL.md`
- Create: `src/ptsm/skills/builtin/xhs_psychology_hashtagging/SKILL.md`
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`

**verify:**
```bash
uv run pytest -q tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py
```

**done_when:**
- All three skills are discoverable.
- Each skill has `domain_tags: 现代心理困境观察` and `platform_tags: xiaohongshu`.
- Skill selector exposes these skills only for the psychology playbook/account context.

---

### Task 4: Add psychology safety evaluation checks

**Files:**
- Create or modify: `src/ptsm/playbooks/definitions/modern_psychology_post/evaluation.yaml`
- Modify: `src/ptsm/evaluations/contracts_eval.py`
- Modify: `tests/unit/evaluations/test_playbook_contracts.py`
- Modify: `tests/unit/evaluations/test_contract_evaluators.py`
- Modify: `tests/e2e/test_modern_psychology_publish_dry_run.py`

**verify:**
```bash
uv run pytest -q tests/unit/evaluations/test_playbook_contracts.py tests/unit/evaluations/test_contract_evaluators.py tests/e2e/test_modern_psychology_publish_dry_run.py
```

**done_when:**
- Dry-run output must include a concrete life scene, one psychology mechanism, one low-risk action, and appropriate hashtags.
- Dry-run output must not contain diagnosis promises, medication guidance, or treatment claims.
- If severe-risk phrases appear in the scene, output includes professional-help guidance.

---

### Task 5: End-to-end dry-run and docs sync

**Files:**
- Create: `src/ptsm/infrastructure/llm/contextual_drafts.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/architecture.md`
- Modify as needed: `docs/operations/local-runbook.md`

**verify:**
```bash
uv run pytest -q
uv run python -m ptsm.bootstrap run-playbook \
  --scene "下班后还在反复复盘白天一句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --strict
```

**done_when:**
- Full tests pass.
- Dry-run reaches `status == completed`.
- Generated content respects the psychology safety boundaries.
- Source-of-truth docs mention the new playbook and skills.
- Harness gate passes or reports only documented non-blocking issues.
