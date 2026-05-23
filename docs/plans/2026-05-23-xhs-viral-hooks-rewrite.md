# XHS Viral Hooks Research Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rework `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md` into a clearer research artifact with a sharper title, stronger product-hook framing, and the new role-claim/comment-section insight from the Zhang Huaimin case.

**Architecture:** This is a docs-only research rewrite. No runtime, playbook, skill, account, publish, or harness behavior changes are intended. The research note remains advisory context, while `docs/xhs-topics/index.md` gets a one-line summary sync so the topic index reflects the stronger hook model.

**Tech Stack:** Markdown docs, existing docs metadata conventions, docs metadata/map tests, `ptsm.bootstrap docs-sync`, and `ptsm.bootstrap harness-check`.

## Current Docs Context

- `docs/development-workflow.md` requires major work to happen in an isolated worktree with a written plan and verification path before implementation.
- `docs/xhs-topics/index.md` positions the viral-hooks research note as the entry point for recent XHS hook mechanisms and playbook mapping.
- `docs/playbooks.md` and `docs/skills.md` already describe the current runtime surface that consumed the earlier research. This rewrite does not alter those current runtime claims.
- The Zhang Huaimin post adds a missing mechanism: a strong comment section is not only a chain, tool, or example bucket; it can be a role-pair arena where users identify as one side, correct the interpretation, remember a relationship, or recruit someone into the scene.

## Non-Goals

- Do not change `src/ptsm/**`, playbook prompts, builtin skills, evaluation contracts, or account routing.
- Do not add a new XHS domain, playbook, or runtime research skill.
- Do not claim the Zhang Huaimin sample is platform-wide evidence; treat it as a focused case study layered onto the broader evidence base.

### Task 1: Reframe The Research Note

**Files:**
- Modify: `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md`

**Steps:**

1. Replace the current broad title with a sharper title around "爆品梗到产品化内容 Hook".
2. Reorganize the top of the document into `Scope`, `Executive Read`, `Mechanism Stack`, and `Evidence Base`.
3. Add the Zhang Huaimin case as a compact evidence row and a dedicated hook archetype.
4. Preserve the useful existing trend evidence and playbook mapping, but reduce repeated prose.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_metadata.py -q
```

**done_when:**

- The research note explains why role-pair prompts create better comments than generic "share your story" prompts.
- The note keeps evidence limitations explicit.
- The note still maps recommendations to existing playbooks.

### Task 2: Improve Format Patterns And Experiments

**Files:**
- Modify: `docs/research/2026-05-23-xhs-viral-meme-product-hooks.md`

**Steps:**

1. Replace the flat format table with a more actionable hook-pattern table.
2. Add `role-pair prompt`, `relationship test`, and `comment-correction bait` as reusable patterns with safety notes.
3. Rewrite sample topic seeds so titles and body organization show the new approach rather than just listing hot words.
4. Keep "What Not To Do" focused on operational risks: heat-word stuffing, fake evidence, medical claims, AI-image misrepresentation, and manipulative comment bait.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

**done_when:**

- The sample topics show concrete title/body/comment-prompt structure.
- The document gives writers a reusable decision model, not only a list of trends.

### Task 3: Sync Topic Index Summary

**Files:**
- Modify: `docs/xhs-topics/index.md`

**Steps:**

1. Update the existing bullet that summarizes the viral-hooks research note.
2. Mention role-pair prompts and relationship-entry comments as an added mechanism.
3. Do not update `docs/playbooks.md` or `docs/skills.md` because no current runtime contract changes.

**verify:**

```bash
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/xhs-topics/index.md
```

**done_when:**

- The topic index points readers to the revised research note accurately.
- Source-of-truth runtime docs remain untouched because their claims are still current.

### Task 4: Final Docs Gate

**Files:**
- Verify only

**Steps:**

1. Run docs metadata/map tests.
2. Run docs-sync for both changed docs.
3. Run harness-check against `origin/main`.
4. Review `git diff --stat` and `git status`.

**verify:**

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/xhs-topics/index.md
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
```

**done_when:**

- All planned checks pass, or any exception is documented with exact failure output.
- The branch is ready to merge back into `main`.
