# Harness Engineering First Stage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add the first-stage harness-engineering improvements that make PTSM easier for agents to navigate, verify, and query directly from the repository.

**Architecture:** Start with the lowest-risk leverage points from the OpenAI harness-engineering article: repository knowledge as a map, not a monolith; agent-readable documentation with explicit freshness metadata; and observability that is directly queryable instead of only inspectable one run at a time. Keep the first stage narrow: docs + docs gate + run query surface. Defer heavier structural linting and persistent memory changes to later stages.

**Tech Stack:** Markdown, YAML front matter, Python 3.12, pytest, PyYAML, local JSON/JSONL persistence

### Task 1: Add The Harness Engineering Source Document And Docs Map

**Files:**
- Modify: `README.md`
- Create: `docs/harness-engineering.md`
- Create: `docs/index.md`
- Create: `docs/architecture.md`
- Create: `docs/runtime.md`
- Create: `docs/playbooks.md`
- Create: `docs/skills.md`
- Create: `docs/observability.md`
- Create: `docs/operations.md`
- Create: `docs/shared-contracts.md`
- Create: `tests/unit/docs/test_docs_map.py`

**Step 1: Write the failing test**

Add focused tests that require:

- `README.md` links to `docs/index.md`
- `docs/harness-engineering.md` exists and mentions:
  - repository knowledge as the system of record
  - agent readability
  - observability readable by agents
- `docs/index.md` exists and links:
  - `harness-engineering.md`
  - `architecture.md`
  - `runtime.md`
  - `playbooks.md`
  - `skills.md`
  - `observability.md`
  - `operations.md`
  - `shared-contracts.md`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_docs_map.py -q`

Expected: FAIL because the docs map and harness-engineering source document do not exist yet.

**Step 3: Write minimal implementation**

Add the new docs and keep them short and high-signal:

- `docs/harness-engineering.md`
  - what PTSM can borrow from the article
  - what already exists
  - what should be built next
  - what should not be copied directly
- `docs/index.md`
  - current source-of-truth links
  - core maps list
  - reading order
- supporting docs
  - architecture/runtime/playbooks/skills/observability/operations/shared-contracts summaries with links to code and existing runbooks
- `README.md`
  - add a short `Docs Map` section pointing to `docs/index.md`

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/docs/test_docs_map.py -q`

Expected: PASS

### Task 2: Add Docs Metadata And Freshness Gate

**Files:**
- Modify: `docs/harness-engineering.md`
- Modify: `docs/index.md`
- Modify: `docs/architecture.md`
- Modify: `docs/runtime.md`
- Modify: `docs/playbooks.md`
- Modify: `docs/skills.md`
- Modify: `docs/observability.md`
- Modify: `docs/operations.md`
- Modify: `docs/shared-contracts.md`
- Create: `tests/unit/docs/test_docs_metadata.py`

**Step 1: Write the failing test**

Add tests that require every core doc above to:

- start with YAML front matter
- include:
  - `status`
  - `owner`
  - `last_verified`
  - `source_of_truth`
  - `related_paths`
- use `status` from `active|historical|draft`
- have `last_verified` parse as ISO date
- have non-empty `related_paths`
- for `status: active`, have `last_verified` within 90 days

Also require:

- `docs/index.md` links every core doc
- `docs/operations.md` links:
  - `docs/operations/local-runbook.md`
  - `docs/operations/task-completion-automation.md`
- `docs/shared-contracts.md` links:
  - `shared_contracts/README.md`
  - `shared_contracts/planning/planning_brief.schema.yaml`
  - `shared_contracts/playbook_policies/content_drafting.policy.yaml`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/docs/test_docs_metadata.py -q`

Expected: FAIL because the docs lack uniform metadata and freshness rules.

**Step 3: Write minimal implementation**

Add uniform front matter to every core doc and adjust text only where needed to satisfy the link and freshness contract.

**Step 4: Run targeted verification**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q`

Expected: PASS

### Task 3: Add A Queryable Run Surface For Agent-Readable Observability

**Files:**
- Modify: `src/ptsm/infrastructure/observability/run_store.py`
- Create: `src/ptsm/application/use_cases/runs.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Create: `tests/unit/application/use_cases/test_runs.py`
- Modify: `tests/unit/infrastructure/observability/test_run_store.py`
- Modify: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

Add tests that require:

```python
def test_run_store_lists_recent_runs_with_filters(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)
    ...
    result = store.list_runs(account_id="acct-fk-local", status="completed", limit=2)
    assert [item["run_id"] for item in result] == [newest_run_id, older_run_id]

def test_run_runs_returns_filtered_summaries(tmp_path: Path) -> None:
    result = run_runs(
        base_dir=tmp_path,
        account_id="acct-fk-local",
        platform="xiaohongshu",
        status="completed",
        limit=5,
    )
    assert result["count"] == 1
    assert result["runs"][0]["account_id"] == "acct-fk-local"
```

Extend CLI tests so:

- parser accepts `runs`
- `main()` dispatches the new command

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_runs.py tests/unit/test_bootstrap.py -q`

Expected: FAIL because `list_runs`, `run_runs`, and the CLI command do not exist yet.

**Step 3: Write minimal implementation**

- `RunStore.list_runs(...)`
  - scan `.ptsm/runs/*/summary.json`
  - filter by `account_id`, `platform`, `playbook_id`, `status`
  - sort by `started_at` descending
  - apply `limit`
- `run_runs(...)`
  - wrap `RunStore.list_runs(...)`
  - return `count` plus `runs`
- CLI
  - add `runs` subcommand with:
    - `--account-id`
    - `--platform`
    - `--playbook-id`
    - `--status`
    - `--limit`

**Step 4: Run targeted verification**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_runs.py tests/unit/test_bootstrap.py -q`

Expected: PASS

### Task 4: Run The First-Stage Regression Set

**Files:**
- No code changes expected

**Step 1: Run the first-stage regression suite**

Run: `uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_logs.py tests/unit/application/use_cases/test_runs.py tests/unit/test_bootstrap.py -q`

Expected: PASS

**Step 2: Run full project verification**

Run: `uv run pytest -q`

Expected: PASS
