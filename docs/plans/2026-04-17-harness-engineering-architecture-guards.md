# Harness Engineering Architecture Guards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add second-stage harness-engineering support by turning PTSM's current package boundaries into mechanically enforced architecture guards.

**Architecture:** Keep this stage narrow and grounded in the code that already exists. Document the intended dependency direction in `docs/architecture.md`, then encode only the stable, already-true import rules as structural pytest checks. Prefer a lightweight AST-based test harness over introducing a new linter stack so the repo gets immediate mechanical enforcement without adding tool churn.

**Tech Stack:** Markdown, Python 3.12, pytest, `ast`, `pathlib`

### Task 1: Document Explicit Dependency Rules

**Files:**
- Modify: `docs/architecture.md`
- Create: `tests/unit/docs/test_architecture_doc.py`

**Step 1: Write the failing test**

Add a focused docs test that requires `docs/architecture.md` to include a section naming explicit import rules for:

- `interfaces`
- `application`
- `agent_runtime`
- `infrastructure`
- `playbooks`
- `skills`

The test should also require the doc to mention:

- `dependency direction`
- `mechanical enforcement`
- `tests/unit/architecture/`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_architecture_doc.py -q`

Expected: FAIL because the architecture doc describes packages, but does not yet state explicit dependency rules and enforcement location.

**Step 3: Write minimal implementation**

Update `docs/architecture.md` with:

- a short `Dependency Direction` section
- flat, explicit rules for which packages may import which others
- a note that structural checks live under `tests/unit/architecture/`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/docs/test_architecture_doc.py -q`

Expected: PASS

### Task 2: Add Structural Import Guards

**Files:**
- Create: `tests/unit/architecture/test_import_boundaries.py`

**Step 1: Write the failing test**

Add structural tests that parse `src/ptsm/**/*.py` and enforce these stable rules:

- `ptsm.interfaces` must not import `ptsm.infrastructure` or `ptsm.agent_runtime`
- `ptsm.infrastructure` must not import `ptsm.application`, `ptsm.interfaces`, or `ptsm.agent_runtime`
- `ptsm.agent_runtime` must not import `ptsm.interfaces` or `ptsm.application.use_cases`
- `ptsm.skills` must not import `ptsm.application`, `ptsm.interfaces`, or `ptsm.agent_runtime`
- `ptsm.playbooks` must not import `ptsm.application`, `ptsm.interfaces`, or `ptsm.agent_runtime`

Keep the test output agent-readable:

- report the offending file
- report the forbidden import
- report the rule that was violated

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/architecture/test_import_boundaries.py -q`

Expected: FAIL at first because the test file does not exist yet.

**Step 3: Write minimal implementation**

Implement the AST-based import guard test with:

- package discovery from relative paths
- support for both `import ptsm.foo` and `from ptsm.foo import ...`
- a small allow/block rule table
- clear assertion messages

Do not over-generalize into a framework yet.

**Step 4: Run targeted verification**

Run: `uv run pytest tests/unit/architecture/test_import_boundaries.py -q`

Expected: PASS

### Task 3: Regress Harness Layer And Full Suite

**Files:**
- No code changes expected

**Step 1: Run the harness-focused regression set**

Run: `uv run pytest tests/unit/docs/test_architecture_doc.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/architecture/test_import_boundaries.py -q`

Expected: PASS

**Step 2: Run the broader regression set**

Run: `uv run pytest -q`

Expected: PASS
