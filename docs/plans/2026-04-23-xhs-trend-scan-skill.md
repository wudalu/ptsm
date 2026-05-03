# XHS Trend Scan Skill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real builtin `xhs_trend_scan` skill that fits the current PTSM skill registry, can be activated in XiaoHongShu playbook runs, and is documented in the docs/harness map.

**Architecture:** Keep the implementation aligned with the existing builtin skill model: a `SKILL.md` file under `src/ptsm/skills/builtin/` plus playbook wiring via `required_skills`. Do not introduce a new runtime surface or optional-skill planner refactor in this step; instead, make `xhs_trend_scan` a platform-scoped research skill that both existing XiaoHongShu playbooks can load safely.

**Tech Stack:** Markdown skill assets, Python skill registry/selector tests, existing playbook YAML definitions, pytest, existing docs map under `docs/`.

### Task 1: Lock the desired behavior with failing tests

**Files:**
- Modify: `tests/unit/skills/test_skill_registry.py`
- Modify: `tests/unit/skills/test_selector.py`
- Modify: `tests/unit/playbooks/test_playbook_registry.py`

**Step 1: Write the failing registry assertions**

Add assertions that:

- `xhs_trend_scan` is discovered by `SkillRegistry`
- it is platform-scoped to `xiaohongshu`
- it does not require a domain or playbook-specific tag

**Step 2: Run the focused tests to verify RED**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py -q
```

Expected: FAIL because `xhs_trend_scan` does not exist yet and current playbooks do not require it.

**Step 3: Commit**

```bash
git add tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py
git commit -m "test: cover xhs trend scan skill wiring"
```

### Task 2: Add the builtin skill and wire it into playbooks

**Files:**
- Create: `src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md`
- Modify: `src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml`
- Modify: `src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml`

**Step 1: Write the minimal skill content**

Create the skill with front matter matching repo conventions:

- `skill_name`
- `display_name`
- `description`
- `display_order`
- `platform_tags`
- `token_budget_hint`
- `assets_present`

Body requirements:

- define the lightweight trend-scan workflow
- instruct the model to choose one relevant vertical before drafting
- keep the skill generic enough for both existing XiaoHongShu playbooks
- avoid forcing domain-specific output like `#苏轼` or `#发疯文学`

**Step 2: Wire the skill into the two existing XiaoHongShu playbooks**

Add `xhs_trend_scan` to each playbook’s `required_skills` list.

Expected: planner can now discover and activate it via the existing `required_skills` path.

**Step 3: Run the focused tests to verify GREEN**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py -q
```

Expected: PASS

**Step 4: Commit**

```bash
git add src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md src/ptsm/playbooks/definitions/fengkuang_daily_post/playbook.yaml src/ptsm/playbooks/definitions/sushi_poetry_daily_post/playbook.yaml
git commit -m "feat: add xhs trend scan builtin skill"
```

### Task 3: Update docs to reflect the new truth

**Files:**
- Modify: `docs/skills.md`
- Modify: `docs/xhs-topics/skills-landscape.md`
- Modify: `docs/xhs-topics/harness-integration.md`

**Step 1: Update the skill map**

Document that:

- `xhs_trend_scan` now exists as a builtin skill
- it is a platform-scoped research skill
- it complements rather than replaces style / hashtag skills

**Step 2: Update the XHS topic docs**

Change the docs from “future candidate” to “first builtin research skill landed”, while still keeping `xhs_note_teardown` and `xhs_vertical_router` as next-step candidates.

**Step 3: Run docs-focused verification**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS

**Step 4: Commit**

```bash
git add docs/skills.md docs/xhs-topics/skills-landscape.md docs/xhs-topics/harness-integration.md
git commit -m "docs: record xhs trend scan builtin skill"
```

### Task 4: Verify end-to-end surfaces

**Files:**
- Test: `tests/unit/skills/test_skill_loader.py`
- Test: `tests/unit/skills/test_selector.py`
- Test: `tests/unit/playbooks/test_playbook_registry.py`

**Step 1: Run a broader focused suite**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS

**Step 2: Run full repo verification if the focused suite is green**

Run:

```bash
uv run pytest -q
```

Expected: PASS or an explicitly documented unrelated existing failure.

**Step 3: Final commit**

```bash
git add docs/plans/2026-04-23-xhs-trend-scan-skill.md
git commit -m "docs: add xhs trend scan implementation plan"
```
