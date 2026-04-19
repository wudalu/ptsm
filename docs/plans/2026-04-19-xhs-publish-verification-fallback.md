# XHS Publish Verification Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve XiaoHongShu post-publish verification by adding a safe public-search fallback and by making private-post verification limits explicit in code, docs, and diagnostics.

**Architecture:** Keep the main publish path unchanged. Extend `check_xhs_publish_status(...)` with a narrow fallback that uses existing MCP read-only tools (`search_feeds`, optionally `get_feed_detail`) only when the artifact has no `post_id/post_url` and the requested visibility is not private. For private posts without identifiers, return an explicit blocker reason instead of implying that automatic verification is still available.

**Tech Stack:** Python 3.11+, existing `langchain-mcp-adapters` MCP publisher integration, pytest, JSON artifact files.

### Task 1: Lock the missing-identifier behaviors with failing tests

**Files:**
- Modify: `tests/unit/application/use_cases/test_xhs_publish_status.py`
- Modify: `tests/unit/application/use_cases/test_diagnose_publish.py`

**Step 1: Write the failing tests**

Add tests covering:
- public post with missing identifiers uses a publisher fallback and returns a verified status when an exact title match is found
- private post with missing identifiers returns `manual_check_required` with a precise blocker reason
- diagnostics classify the private-post case with a clearer likely cause / next action wording

**Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_diagnose_publish.py -q
```

Expected:
- new tests fail because the fallback path and clearer blocker reason do not exist yet

### Task 2: Implement the MCP search fallback and explicit private blocker

**Files:**
- Modify: `src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py`
- Modify: `src/ptsm/application/use_cases/xhs_publish_status.py`
- Modify: `src/ptsm/application/use_cases/diagnose_publish.py`

**Step 1: Write the failing publisher test**

Add publisher-level tests for a new helper that:
- calls `search_feeds` with the post title
- extracts an exact-title match from MCP search results
- returns `post_id`, `post_url`, and `xsec_token` when a safe match exists
- refuses to claim a match when titles are only fuzzy-similar

**Step 2: Run the publisher test to verify it fails**

Run:

```bash
uv run pytest tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py -q
```

Expected:
- failure because the fallback resolver does not exist yet

**Step 3: Implement the minimal publisher support**

Add a read-only helper on `XiaohongshuMcpPublisher` that:
- checks tool availability
- calls `search_feeds`
- parses returned JSON safely
- exact-matches `noteCard.displayTitle` against the published title
- returns a deterministic verification result only for exact matches

**Step 4: Wire the use case**

Update `check_xhs_publish_status(...)` so that:
- the existing `post_id/post_url` path still runs first
- if identifiers are missing and `visibility != "仅自己可见"`, it tries the publisher search fallback
- if identifiers are missing and `visibility == "仅自己可见"`, it returns `manual_check_required` with an explicit reason that private posts cannot be auto-verified under the current upstream/tooling contract

**Step 5: Update diagnostics**

Adjust `diagnose_publish` classification / next actions so the private-post blocker is surfaced clearly and is distinct from generic missing identifiers.

### Task 3: Update docs and verify the narrowed contract

**Files:**
- Modify: `docs/observability.md`
- Modify: `docs/operations/local-runbook.md`

**Step 1: Update the docs**

Document:
- public-post fallback verification via MCP search
- private-post limitation when upstream does not return identifiers
- the exact meaning of `manual_check_required` in the private-post case

**Step 2: Run focused verification**

Run:

```bash
uv run pytest tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_diagnose_publish.py tests/unit/docs/test_docs_metadata.py -q
```

Expected:
- all targeted tests pass

**Step 3: Run broader regression verification**

Run:

```bash
uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/infrastructure/llm/test_factory.py -q
uv run pytest -q
```

Expected:
- no regressions in the existing publish flow and harness surface
