# Psychology Learning-Series Publish-Mode Guide Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Make the existing psychology OpenClaw wrapper guide a user through the correct publication mode—single scene post, builtin learning series, or custom learning series—without duplicating the existing CLI or runtime contracts.

**Architecture:** Keep `ptsm-xhs-psychology` as the only psychology wrapper. Add a small natural-language routing layer before its existing detailed flows. It resolves intent into the already implemented generic `guide-post` path or the existing `learning_series` plan → review → confirmation → roadmap → explicit lesson → dry-run path. No CLI, runtime, storage, artifact, or playbook state is added.

**Tech Stack:** Markdown OpenClaw Skill, PTSM CLI contracts, pytest docs-contract tests, docs-sync, harness-check.

## Scope and constraints

- Scope: `modern_psychology_post` only; no cross-domain router in this change.
- The wrapper must ask for a choice on ambiguous requests; it must not assume a custom series or generate/publish a post.
- Custom curricula remain immutable: changed topic, outline, lesson identity, or order requires a new proposal and exact confirmation.
- “Continue next lesson” and “view progress” re-query a roadmap first; `recommended_next_lesson` is not automatic selection, generation, or publishing.
- Use the existing trusted provisioning requirement and do not turn it into an online recovery/retry step.
- Keep dry-run before real publishing, PTSM-returned IDs only, and all existing psychology-safety boundaries.

## Documentation-surface review

- Update: `docs/skills.md`, `docs/operations.md`, and `docs/operations/local-runbook.md`; each gains the user-facing routing contract while retaining existing command/security detail.
- Update: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` and the installed `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md` mirror.
- Update: focused docs tests under `tests/unit/docs/`.
- Reviewed and unchanged: `docs/architecture.md`, `docs/runtime.md`, `docs/playbooks.md`, `docs/harness-engineering.md`, `docs/observability.md`, `docs/operations/content-experiment-runbook.md`, and `docs/operations/topic-radar-runbook.md`. This feature adds no domain/playbook, CLI, runtime, storage, artifact, metrics, harness, or Topic Radar behavior; their existing learning-series contracts remain the source of truth.

### Task 1: Lock the publication-mode contract with failing tests

**Files:**

- Modify: `tests/unit/docs/test_openclaw_skill.py`
- Modify: `tests/unit/docs/test_docs_map.py`

**Step 1: Write the failing docs-contract tests.**

Add a focused OpenClaw Skill test that requires the following user-visible statements before the detailed learning-series flow:

- the three modes: `单篇心理学帖`, `内置学习系列`, `自定义学习系列`;
- ambiguous intent requires a user choice and does not default to a custom series or post generation;
- builtin flow names `after_work_rumination` and preserves `selection_required` / explicit lesson selection;
- custom flow preserves `provision → plan → review → exact confirmation → roadmap` ordering;
- `继续下一课`, `看系列进度`, and `改目录` preserve re-query / new-version semantics and forbid automatic generation or publishing.

Add a docs-map assertion that the wrapper, the operator index, and the local runbook all describe `单篇心理学帖`, `内置学习系列`, and `自定义学习系列`.

**Step 2: Verify RED.**

Run:

```bash
uv run pytest -q tests/unit/docs/test_openclaw_skill.py -k publication_mode
```

Expected: failure because the existing wrapper has detailed commands but lacks the user-visible publication-mode router.

**verify:** The new test fails for the missing route language, not a test setup error.

**done_when:** The tests express the conversational entry and the non-bypass boundaries independently of implementation wording.

### Task 2: Add the minimal routing layer to the existing psychology wrapper

**Files:**

- Modify: `integrations/openclaw/ptsm-xhs-psychology/SKILL.md`
- Modify: `/Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md`

**Step 1: Add a concise “choose a publication mode” section before `Psychology Learning Series`.**

It must route clear requests as follows:

1. `单篇心理学帖` → existing generic scene/guidance flow.
2. `内置学习系列` → builtin `after_work_rumination` roadmap, then explicit user lesson selection.
3. `自定义学习系列` → user topic plus optional 2–6 item outline, existing trusted provision/plan/review/confirm flow, then roadmap and explicit lesson selection.

For an ambiguous psychology request, show these three choices and wait. Do not write content, call a series run, or make a custom catalog by default.

**Step 2: Add continuation semantics without adding commands.**

Specify that “继续下一课” and “看系列进度” require the known confirmed custom series identity and a roadmap query before displaying the recommendation/progress and waiting for an explicit lesson choice. Specify that “改目录” creates a new proposal and immutable version; it cannot mutate a confirmed catalog. If no outline is supplied, PTSM may create a review-only proposal; the wrapper must not invent course facts.

**Step 3: Sync the installed mirror exactly.**

Apply the same content to the installed Codex skill file. Do not use a second skill name or change its external trigger scope beyond the new series-related phrases.

**Step 4: Verify GREEN.**

Run:

```bash
uv run pytest -q tests/unit/docs/test_openclaw_skill.py -k publication_mode
cmp -s integrations/openclaw/ptsm-xhs-psychology/SKILL.md /Users/wudalu/.codex/skills/ptsm-xhs-psychology/SKILL.md
```

Expected: pytest passes and `cmp` exits zero.

**verify:** Existing generic and learning-series guardrails remain in the wrapper.

**done_when:** A user can enter through a clear mode choice and cannot accidentally bypass explicit lesson/version/confirmation boundaries.

### Task 3: Make the routing contract discoverable to operators

**Files:**

- Modify: `docs/skills.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `tests/unit/docs/test_docs_map.py`

**Step 1: Update the OpenClaw wrapper source-of-truth paragraph.**

State that the psychology wrapper is a publication-mode guide over existing single/builtin/custom paths, not a new builtin skill, domain, CLI mode, or runtime behavior. Record the explicit-selection and no-auto-publish principle.

**Step 2: Add concise operator entry maps.**

In `docs/operations.md`, add an index-level mapping from user intent to existing command flow. In `docs/operations/local-runbook.md`, add the same three modes before the detailed commands and cover “continue”, “progress”, and “change outline”. Reuse links/terms rather than duplicating the complete command examples.

**Step 3: Refresh `last_verified` only on docs whose claims were revalidated.**

**Step 4: Verify docs contracts.**

Run:

```bash
uv run pytest -q tests/unit/docs/test_openclaw_skill.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py
uv run python -m ptsm.bootstrap docs-sync --changed-path integrations/openclaw/ptsm-xhs-psychology/SKILL.md --changed-path docs/skills.md --changed-path docs/operations.md --changed-path docs/operations/local-runbook.md
```

**verify:** The route text appears consistently in wrapper and operator docs; docs metadata remains valid.

**done_when:** Operators can discover the safe user journey without inferring it from low-level flags.

### Task 4: Run the user-surface smoke and final repository gates

**Files:**

- Verify only; no planned source changes.

**Step 1: Run targeted and end-to-end learning-series tests.**

```bash
uv run pytest -q \
  tests/unit/docs/test_openclaw_skill.py \
  tests/unit/docs/test_docs_map.py \
  tests/unit/application/use_cases/test_guide_post.py \
  tests/unit/interfaces/cli/test_main.py \
  tests/e2e/test_modern_psychology_publish_dry_run.py
```

**Step 2: Run quality and full gates serially.**

```bash
uv run python -m compileall -q src tests
uv run pytest -q
uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main
uv run python -m ptsm.bootstrap harness-check --base-ref origin/main
git diff --check
```

**Step 3: Review, commit, and hand off.**

Request an independent read-only review, commit the plan/source/test/docs changes, push the feature branch, then merge and push `main` only after the gates succeed.

**verify:** All commands above exit zero; OpenClaw mirror comparison succeeds.

**done_when:** The new guide is usable, documented, validated, committed, and safely integrated according to the user’s merge/push direction.
