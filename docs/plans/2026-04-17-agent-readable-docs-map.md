# Agent-Readable Docs Map Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a standard, agent-readable docs map with core reference documents, shared-contracts indexing, and a lightweight docs freshness gate.

**Architecture:** Keep `AGENTS.md` and `README.md` concise, then move durable repo knowledge into a small set of core `docs/*.md` map files with uniform YAML front matter. Enforce the new contract with focused pytest checks that validate existence, metadata shape, cross-links, and recency for the core map only.

**Tech Stack:** Markdown, YAML front matter, Python 3.12, pytest, PyYAML

### Task 1: Add Docs Gate Tests

**Files:**
- Create: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing test**

Add tests that require:

- the following core docs to exist:
  - `docs/index.md`
  - `docs/architecture.md`
  - `docs/runtime.md`
  - `docs/playbooks.md`
- `docs/skills.md`
  - `docs/observability.md`
  - `docs/operations.md`
  - `docs/shared-contracts.md`
- each core doc to include YAML front matter with:
  - `status`
  - `owner`
  - `last_verified`
  - `source_of_truth`
  - `related_paths`
- `docs/index.md` to link to all core docs
- `docs/operations.md` to link existing runbooks under `docs/operations/`
- `docs/shared-contracts.md` to link `shared_contracts/README.md` plus one planning schema and one policy template
- active core docs to have `last_verified` within 90 days

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py -q`

Expected: FAIL because the core docs and metadata contract do not exist yet.

### Task 2: Add The Core Docs Map

**Files:**
- Create: `docs/index.md`
- Create: `docs/architecture.md`
- Create: `docs/runtime.md`
- Create: `docs/playbooks.md`
- Create: `docs/skills.md`
- Create: `docs/observability.md`
- Create: `docs/operations.md`
- Create: `docs/shared-contracts.md`

**Step 1: Write minimal implementation**

Create the eight docs above with:

- uniform YAML front matter
- short, high-signal summaries
- explicit source-of-truth notes
- links to code paths and existing docs

Content requirements:

- `docs/index.md` is the navigation entrypoint and links every core doc.
- `docs/architecture.md` explains repo slices and major package boundaries.
- `docs/runtime.md` explains `plan -> execute -> reflect`, artifact flow, and current memory/checkpoint limitations.
- `docs/playbooks.md` explains playbook definitions, registry/loading, and account-driven routing.
- `docs/skills.md` explains builtin skill metadata, selection, surface, and activation.
- `docs/observability.md` explains `RunStore`, artifacts, and operator log lookup.
- `docs/operations.md` indexes `docs/operations/local-runbook.md` and `docs/operations/task-completion-automation.md`.
- `docs/shared-contracts.md` indexes `shared_contracts/README.md`, planning schemas, and playbook policy templates.

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py -q`

Expected: PASS

### Task 3: Link The New Map From README And Regress

**Files:**
- Modify: `README.md`

**Step 1: Write a failing assertion**

Extend the docs metadata test so `README.md` must link to `docs/index.md`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py -q`

Expected: FAIL because `README.md` does not link the docs map yet.

**Step 3: Write minimal implementation**

Add a short “Docs Map” section to `README.md` that points readers and agents at `docs/index.md`.

**Step 4: Run targeted verification**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py -q`

Expected: PASS

**Step 5: Run the nearby regression set**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py tests/unit/test_bootstrap.py -q`

Expected: PASS
