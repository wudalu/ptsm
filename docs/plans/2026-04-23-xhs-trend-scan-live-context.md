# XHS Trend Scan Live Context Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `xhs_trend_scan` enrich the planner prompt with live XiaoHongShu trend context gathered from the local `xiaohongshu-mcp` server.

**Architecture:** Keep the harness contract stable by attaching dynamic trend context during the planner step. The planner will still load builtin skill markdown as before, but it will append an extra generated context block when `xhs_trend_scan` is activated and live MCP search is available. When MCP is unavailable or not logged in, the workflow must degrade cleanly back to the static skill behavior.

**Tech Stack:** Python 3.12, existing planner/runtime graph, `langchain-mcp-adapters`, `xiaohongshu-mcp`, pytest.

### Task 1: Lock the behavior with failing tests

**Files:**
- Create: `tests/unit/skills/test_runtime_context.py`
- Create: `tests/unit/agent_runtime/test_planner_node.py`

**Step 1: Write the failing test**

Add tests that prove:
- the live trend scan provider can turn MCP `search_feeds` payloads into a compact trend context string
- the planner appends dynamic context when `xhs_trend_scan` is active
- unavailable MCP/login state does not crash the planner path

**Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/agent_runtime/test_planner_node.py -q
```

Expected: FAIL because the runtime context resolver and live trend provider do not exist yet.

### Task 2: Implement the live trend scan provider

**Files:**
- Create: `src/ptsm/skills/runtime_context.py`

**Step 1: Write minimal implementation**

Implement:
- a planner-facing runtime context resolver
- an MCP-backed `xhs_trend_scan` live context builder
- keyword derivation, feed parsing, simple ranking, and markdown rendering
- graceful fallback when MCP is unreachable, missing `search_feeds`, or not logged in

**Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py -q
```

Expected: PASS

### Task 3: Attach the provider to the planner/runtime

**Files:**
- Modify: `src/ptsm/agent_runtime/nodes/planner.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`

**Step 1: Wire the resolver**

Pass the resolver from runtime construction into the planner builder, and append generated live context blocks to `loaded_skill_contents` without changing executor inputs.

**Step 2: Run planner/runtime tests**

Run:

```bash
uv run pytest tests/unit/agent_runtime/test_planner_node.py tests/integration/test_fengkuang_workflow.py -q
```

Expected: planner unit tests pass; existing unrelated DeepSeek instability may still affect the integration file, so record exact failures if any remain.

### Task 4: Update docs and skill description

**Files:**
- Modify: `src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md`
- Modify: `docs/skills.md`
- Modify: `docs/xhs-topics/harness-integration.md`

**Step 1: Document the live context behavior**

Explain that `xhs_trend_scan` now prefers real-time MCP search, but falls back to static guidance when live scan is unavailable.

**Step 2: Run docs checks**

Run:

```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS

### Task 5: Final verification

**Files:**
- No additional file changes expected

**Step 1: Run the focused regression suite**

Run:

```bash
uv run pytest tests/unit/skills/test_runtime_context.py tests/unit/agent_runtime/test_planner_node.py tests/unit/skills/test_skill_loader.py tests/unit/skills/test_skill_registry.py tests/unit/skills/test_selector.py tests/unit/playbooks/test_playbook_registry.py tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
```

Expected: PASS

**Step 2: Run one real MCP smoke check**

Run:

```bash
uv run python -m ptsm.spikes.xhs_mcp_probe --server-url http://localhost:18060/mcp --keyword 怎么才周四
```

Expected: returns live XiaoHongShu search results through the running local MCP service.
