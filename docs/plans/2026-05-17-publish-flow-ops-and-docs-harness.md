# Publish Flow Ops And Docs Harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Bring the operator publish docs in sync with the current selectable XHS MCP/image flow, make real publishes with images always pass through watermark removal, and add docs-only cleanup guidance plus harness coverage for this class of drift.

**Architecture:** Keep the current CLI surface and make the policy explicit instead of adding duplicate switches. XHS MCP remains selected by real-publish and research commands (`--publish-mode mcp-real`, `--fresh-topic-research`, `collect-xhs-patterns`), image generation remains selected by `--auto-generate-image` / `--no-auto-generate-image` / `--publish-image-path` / `--local-image-style` plus `final_content.image_plan`, and watermark removal becomes required only for real publishing when images exist while staying opt-in for dry-run image experiments.

**Tech Stack:** Python 3.12, pytest, Markdown source-of-truth docs, existing PTSM CLI and harness-check.

## Current Docs Summary

- `docs/index.md` says active docs and code are the current source of truth; historical plans are reference only.
- `docs/development-workflow.md` requires branch/worktree, plan, task-level `verify:` / `done_when:`, source-of-truth doc updates, and `harness-check` for new publish, verification, observability, or harness surfaces. It explicitly says docs-only cleanup should use a smaller workflow later, but that smaller workflow is not yet defined.
- `docs/harness-engineering.md` says `docs-sync` maps code changes to source-of-truth docs and `harness-check` runs `docs-sync`, harness drift checks, and deterministic pytest.
- Current `docs-sync` code only gates `src/ptsm/**` and `shared_contracts/**`; it intentionally ignores docs-only changes. Existing docs tests check metadata and selected keywords, so stale operational claims can pass when no test asserts the semantic contract.
- Current operations docs are stale in three places: dry-run is described as content-only/no image, local image rendering is described as fallback rather than active selection, and watermark removal is documented as optional even for real publish.

## Task 1: Real Publish Watermark Policy

**Files:**
- Modify: `tests/unit/application/use_cases/test_run_playbook.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `docs/runtime.md`
- Modify: `docs/observability.md`

**Step 1: Write the failing test**

Add a test proving that `publish_mode="mcp-real"` with `publish_image_paths` calls `WatermarkRemover` and publishes the cleaned path even when `Settings.watermark_removal_enabled=False`.

**Step 2: Verify red**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py::test_run_fengkuang_real_publish_always_removes_watermark_for_images -q
```

Expected: fail because the current implementation skips watermark removal when the env flag is false.

**Step 3: Implement minimal policy**

Add a helper near `_should_generate_images()`:

```python
def _should_remove_watermark(
    *,
    publish_mode: str,
    watermark_removal_enabled: bool,
    image_paths: Sequence[str],
) -> bool:
    if not image_paths:
        return False
    if publish_mode == "mcp-real":
        return True
    return watermark_removal_enabled
```

Use it in the existing watermark block and record a policy reason in `watermark_removal`.

**Step 4: Verify green**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py::test_run_fengkuang_real_publish_always_removes_watermark_for_images -q
uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q
```

**done_when:** Real publish with any image path uses cleaned `*-nowm` paths for publishing, dry-run image generation remains governed by `WATERMARK_REMOVAL_ENABLED`, and runtime/observability docs describe the required real-publish policy.

## Task 2: Docs-Only Cleanup Harness Coverage

**Files:**
- Modify: `tests/unit/docs/test_docs_map.py`
- Modify: `docs/development-workflow.md`
- Modify: `docs/harness-engineering.md`
- Modify: `docs/operations/task-completion-automation.md`

**Step 1: Write the failing docs tests**

Add focused docs tests that fail until the concise publish manual exists and the local runbook no longer contains stale claims:

- quickstart mentions `--publish-mode mcp-real`, `--auto-generate-image`, `--no-auto-generate-image`, `--publish-image-path`, `--local-image-style`, `final_content.image_plan`, and mandatory real-publish `watermark_removal`.
- local runbook does not claim dry-run is content-only/no image.
- local runbook does not describe local image styles as fallback-only.
- local runbook does not describe real-publish watermark removal as optional.

**Step 2: Verify red**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

Expected: fail because `docs/operations/publish-quickstart.md` does not exist and stale wording is still present.

**Step 3: Document the harness root cause**

Update the source docs with the investigation result:

- `docs/development-workflow.md`: define the smaller docs-only cleanup workflow.
- `docs/harness-engineering.md`: explain that docs-sync catches code-to-doc omissions, not semantic docs-only drift, and that targeted docs tests are the gate.
- `docs/operations/task-completion-automation.md`: add docs-only cleanup verification commands.

**Step 4: Verify green**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/application/use_cases/test_docs_sync.py tests/unit/application/use_cases/test_harness_check.py -q
```

**done_when:** The repo has a documented docs-only cleanup flow and a regression test that would have caught the stale publishing runbook claims.

## Task 3: Operator Publish Manuals

**Files:**
- Create: `docs/operations/publish-quickstart.md`
- Modify: `docs/operations.md`
- Modify: `docs/operations/local-runbook.md`
- Modify: `docs/operations/cloud-bootstrap.md`
- Modify: `docs/operations/content-experiment-runbook.md`

**Step 1: Create the concise manual**

Write `docs/operations/publish-quickstart.md` as the short operator guide. It must cover:

- whether to use XHS MCP
- whether to use LLM/provider image generation
- manual image path and local social screenshot options
- mandatory watermark removal for real publish with images
- safe dry-run, private publish, and public publish commands
- artifact fields to inspect

**Step 2: Update source-of-truth operation docs**

Update the full local runbook and operations index to point to the concise manual and correct stale text. Update cloud bootstrap and content experiment docs only where they describe publish/image behavior.

**Step 3: Verify**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync --changed-path docs/operations/publish-quickstart.md --changed-path docs/operations/local-runbook.md --changed-path docs/operations.md
```

**done_when:** The short manual and full runbook agree on the selectable publish/image flow, and docs-sync reports docs-only cleanup as ok while docs tests enforce the publish contract.

## Task 4: Final Verification And Integration

**Files:**
- Inspect: all changed files

**Step 1: Run targeted tests**

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/application/use_cases/test_docs_sync.py tests/unit/application/use_cases/test_harness_check.py -q
```

**Step 2: Run full deterministic tests**

```bash
uv run pytest -q --ignore=tests/e2e
```

**Step 3: Run harness-check**

```bash
uv run python -m ptsm.bootstrap harness-check --base-ref main
```

**Step 4: Commit, merge, and push**

```bash
git status --short
git add ...
git commit -m "docs: tighten publish flow operations"
cd /Users/wudalu/llm-app/ptsm
git merge feat/publish-flow-ops-docs
git push origin main
```

**done_when:** Worktree tests and harness-check pass, the branch is merged to `main`, and `main` is pushed to `origin`.
