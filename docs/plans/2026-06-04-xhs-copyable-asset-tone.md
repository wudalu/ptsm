# XHS Copyable Asset Tone Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make XHS drafts copy the observed "friend found a useful thing and gives the homework directly" tone, so正文更像可抄作业而不是总结型文章。

**Architecture:** Keep the change in the existing shared XHS voice layer and DeepSeek prompt assembly. `xhs_human_voice` describes the reusable writing rule; `_build_deepseek_hard_requirements()` turns it into hard generation instructions; existing unit tests verify both surfaces. No new playbook, runtime gate, publish flow, or external scan is needed.

**Tech Stack:** Python 3.12, pytest, PTSM builtin skill markdown, DeepSeek prompt assembly in `src/ptsm/infrastructure/llm/factory.py`.

## Current Docs Summary

- `docs/index.md` says content/strategy changes should start with `playbooks.md` and `skills.md`.
- `docs/development-workflow.md` requires an isolated worktree, a plan with `verify:` and `done_when:`, task-level tests, source-of-truth docs updates, and a final `harness-check` for larger runtime-visible changes.
- `docs/skills.md` defines `xhs_human_voice` as the shared XHS persona/structure layer for all XHS playbooks.
- `docs/runtime.md` says DeepSeek prompt assembly injects shared title/body hard constraints and already carries正文人味 rules into generation.
- `docs/playbooks.md` says all nine XHS playbooks share the title/body organization contract and the shared `xhs_human_voice` skill.

## Scope

- Add a "copyable homework" body rule to `xhs_human_voice`.
- Add matching hard prompt language to DeepSeek requirements.
- Extend existing tests so the rule is not silently removed.
- Update active source-of-truth docs that describe the shared skill and runtime prompt behavior.

## Non-Goals

- Do not claim current live XHS scraping succeeded.
- Do not copy protected wording from the referenced post.
- Do not add new evaluation YAML constraints unless we need deterministic contract enforcement beyond prompt/skill text.
- Do not change publishing, image generation, or guide-post routing.

### Task 1: Lock The New Skill Rule With A Failing Test

**Files:**
- Modify: `tests/unit/skills/test_skill_loader.py`

**Step 1: Write the failing test**

Add assertions in `test_skill_loader_reads_shared_xhs_human_voice_skill()` requiring:

```python
for body_rule in ("可抄作业", "原模板直接放这", "朋友安利", "少解释多交付"):
    assert body_rule in loaded.content
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py::test_skill_loader_reads_shared_xhs_human_voice_skill -q
```

Expected: FAIL because current `xhs_human_voice` does not contain the new copyable-asset phrases.

**Step 3: Implement minimal skill update**

Modify `src/ptsm/skills/builtin/xhs_human_voice/SKILL.md`:

- Add one body organization sentence that the middle of the body should deliver a copyable asset.
- Add one `正文人味策略` bullet named `可抄作业`.
- Add one self-check line about whether the reader can immediately copy a template, checklist, prompt, sentence, or step.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py::test_skill_loader_reads_shared_xhs_human_voice_skill -q
```

Expected: PASS.

**verify:** targeted skill loader test passes after red/green.

**done_when:** `xhs_human_voice` contains the new rule without exposing internal labels as reader-visible copy.

### Task 2: Lock The DeepSeek Hard Prompt With A Failing Test

**Files:**
- Modify: `tests/unit/infrastructure/llm/test_factory.py`
- Modify: `src/ptsm/infrastructure/llm/factory.py`

**Step 1: Write the failing test**

In `test_factory_deepseek_prompt_includes_title_body_appeal_requirements()`, add:

```python
for copyable_rule in ("朋友安利", "可抄作业", "原模板直接放这", "少解释多交付"):
    assert copyable_rule in user_prompt
```

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_factory_deepseek_prompt_includes_title_body_appeal_requirements -q
```

Expected: FAIL because current hard prompt does not include these phrases.

**Step 3: Implement minimal prompt update**

Modify `_build_deepseek_hard_requirements()` to require:

- Body starts like a friend recommending something just found or tested.
- Middle gives a directly copyable asset: template, prompt, checklist, sentence, framework, or steps.
- Avoid over-explaining before giving the asset.

**Step 4: Run test to verify it passes**

Run:

```bash
uv run pytest tests/unit/infrastructure/llm/test_factory.py::test_factory_deepseek_prompt_includes_title_body_appeal_requirements -q
```

Expected: PASS.

**verify:** targeted factory prompt test passes after red/green.

**done_when:** DeepSeek prompt includes the copyable-asset tone in the hard requirements.

### Task 3: Docs And Regression Verification

**Files:**
- Modify: `docs/skills.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`

**Step 1: Update source-of-truth docs**

Update active docs to say `xhs_human_voice` and DeepSeek body hard constraints now include a copyable-homework rule: friend-style discovery, fast asset delivery, and less explanation before the reusable unit.

**Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py -q
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS.

**Step 3: Run docs-sync for changed paths**

Run:

```bash
uv run python -m ptsm.bootstrap docs-sync \
  --changed-path src/ptsm/skills/builtin/xhs_human_voice/SKILL.md \
  --changed-path src/ptsm/infrastructure/llm/factory.py \
  --changed-path docs/skills.md \
  --changed-path docs/runtime.md \
  --changed-path docs/playbooks.md \
  --changed-path docs/plans/2026-06-04-xhs-copyable-asset-tone.md
```

Expected: status ok, no missing docs updates.

**verify:** tests and docs-sync pass.

**done_when:** docs match the runtime-visible behavior.

### Task 4: Final Harness And Merge

**Files:**
- No new source files.

**Step 1: Run final validation in worktree**

Run:

```bash
uv run pytest -q --ignore=tests/e2e
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

Expected: pytest ok; harness-check status ok or only known non-blocking stale run warnings.

**Step 2: Commit and merge**

Run:

```bash
git status --short
git add docs/plans/2026-06-04-xhs-copyable-asset-tone.md docs/skills.md docs/runtime.md docs/playbooks.md src/ptsm/skills/builtin/xhs_human_voice/SKILL.md src/ptsm/infrastructure/llm/factory.py tests/unit/skills/test_skill_loader.py tests/unit/infrastructure/llm/test_factory.py
git commit -m "feat: add xhs copyable asset tone"
cd /Users/wudalu/llm-app/ptsm
git merge --ff-only feat/xhs-copyable-asset-tone
```

**verify:** final tests run in merged `main` if merge succeeds.

**done_when:** change is committed, merged to `main`, worktree removed, and verification evidence is available.
