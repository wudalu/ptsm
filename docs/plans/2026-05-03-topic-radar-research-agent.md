# Topic Radar Research Agent Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone `topic_radar` package that researches discussion-worthy topics across Xiaohongshu, Weibo, and Douyin, producing structured research artifacts. Runs independently from PTSM but can optionally feed into it.

**Architecture:** New package `src/topic_radar/` at the same level as `src/ptsm/`. Uses `langchain-mcp-adapters` to talk to `xiaohongshu-mcp` (HTTP transport) and `mcp-trends-hub` (stdio via npx). No imports from `ptsm` internals. Writes artifacts to the shared `outputs/artifacts/` directory.

**Tech Stack:** Python 3.12, langchain-mcp-adapters, xiaohongshu-mcp (HTTP MCP), mcp-trends-hub (npx stdio MCP), pytest.

**Non-goals:**
- No changes to PTSM runtime, playbooks, or skills
- No real publishing capability
- No browser automation or scraping
- No persistent database

---

## Task 1: Package skeleton and MCP client

**Files:**
- Create: `src/topic_radar/__init__.py`
- Create: `src/topic_radar/__main__.py`
- Create: `src/topic_radar/config.py`
- Create: `src/topic_radar/mcp_client.py`
- Create: `tests/unit/topic_radar/test_mcp_client.py`

**What:**
- `config.py`: reads `XHS_MCP_SERVER_URL` (default `http://localhost:18060/mcp`) from env; mcp-trends-hub uses stdio transport with `npx -y mcp-trends-hub`
- `mcp_client.py`: thin wrapper around `MultiServerMCPClient` supporting both HTTP (xiaohongshu-mcp) and stdio (mcp-trends-hub) transports. Provides `list_tools()`, `invoke_tool(server, tool_name, payload)`, `server_health()` for each server
- `__main__.py`: stub that prints "topic-radar" and exits cleanly

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_mcp_client.py -q
uv run python -m topic_radar
```

**done_when:**
- `MultiServerMCPClient` can connect to xiaohongshu-mcp and list its tools
- `MultiServerMCPClient` can connect to mcp-trends-hub and list its tools
- Missing/unreachable servers return health status rather than crashing

---

## Task 2: Xiaohongshu platform adapter

**Files:**
- Create: `src/topic_radar/platforms/__init__.py`
- Create: `src/topic_radar/platforms/xiaohongshu.py`
- Create: `tests/unit/topic_radar/test_xiaohongshu_platform.py`

**What:**
- `search_feeds(keyword)` → parsed feed list
- `get_feed_detail(feed_id, xsec_token)` → title, body, tags, interaction stats, comments
- `list_feeds()` → homepage recommended feeds
- Each method handles MCP errors gracefully, returns structured dataclasses

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_xiaohongshu_platform.py -q
```

**done_when:**
- Platform adapter returns typed dataclasses, not raw MCP dicts
- Unreachable MCP returns `PlatformUnavailable` instead of raising

---

## Task 3: Multi-platform hot topic adapter (mcp-trends-hub)

**Files:**
- Create: `src/topic_radar/platforms/weibo.py`
- Create: `src/topic_radar/platforms/douyin.py`
- Create: `tests/unit/topic_radar/test_multi_platform.py`

**What:**
- `weibo.py`: calls `get-weibo-trending` tool, normalizes ranking/hot score/topics
- `douyin.py`: calls `get-douyin-trending` tool, normalizes output
- Both return `TrendingItem` dataclass: `{rank, title, hot_score, label, url, platform}`
- Mark platform as `unavailable` when mcp-trends-hub is not installed

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_multi_platform.py -q
```

**done_when:**
- Both platform adapters return `list[TrendingItem]` with uniform schema
- Single-platform scan works when only one MCP is available

---

## Task 4: Note teardown and comment signal analysis

**Files:**
- Create: `src/topic_radar/analysis/__init__.py`
- Create: `src/topic_radar/analysis/note_teardown.py`
- Create: `src/topic_radar/analysis/comment_signals.py`
- Create: `tests/unit/topic_radar/test_note_teardown.py`
- Create: `tests/unit/topic_radar/test_comment_signals.py`

**What:**
- `note_teardown.py`: takes parsed feed detail, classifies:
  - Hook type: 悬念 / 反常识 / 情绪共鸣 / 利益驱动 / 身份认同
  - Body structure: 问题导入 → 展开 → 邀评 / 教程式 / 故事式
  - Engagement triggers: 投票式提问 / 留白 / 争议点 / 经验交换邀请
- `comment_signals.py`: takes comments list, extracts:
  - High-frequency terms
  - Question density (ratio of questions in comments)
  - Sentiment clusters
  - Real discussion vs low-effort engagement ratio

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_note_teardown.py tests/unit/topic_radar/test_comment_signals.py -q
```

**done_when:**
- At least 3 hook types correctly classified from sample data
- Comment question density score computed correctly

---

## Task 5: Cross-platform topic discovery and vertical clustering

**Files:**
- Create: `src/topic_radar/analysis/cross_platform.py`
- Create: `src/topic_radar/analysis/vertical_discovery.py`
- Create: `tests/unit/topic_radar/test_cross_platform.py`

**What:**
- `cross_platform.py`: compares trending items across platforms using keyword overlap + simple text similarity, identifies topics spreading across platforms vs platform-specific noise
- `vertical_discovery.py`: clusters all sampled topics into candidate verticals with:
  - Cluster name + keywords
  - Heat signals per platform
  - Discussion density
  - Suggested content angles
  - Rejected noise clusters

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_cross_platform.py -q
```

**done_when:**
- Same topic appearing on XHS + Weibo is flagged as cross-platform signal
- Topic clusters with low discussion density are classified as noise

---

## Task 6: Output layer — structured artifacts

**Files:**
- Create: `src/topic_radar/output/__init__.py`
- Create: `src/topic_radar/output/artifacts.py`
- Create: `src/topic_radar/output/report.py`
- Create: `tests/unit/topic_radar/test_output.py`

**What:**
- `artifacts.py`: writes `outputs/artifacts/topic-scan-{date}.json` with unified schema
- `report.py`: generates `outputs/artifacts/topic-brief-{date}.md` human-readable summary
- Both use `outputs/artifacts/` directory (shared with PTSM)

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_output.py -q
```

**done_when:**
- JSON artifact contains all required fields
- Markdown report is readable standalone
- Directory auto-created if missing

---

## Task 7: CLI and end-to-end wiring

**Files:**
- Create: `src/topic_radar/cli.py`
- Modify: `src/topic_radar/__main__.py`
- Create: `tests/unit/topic_radar/test_cli.py`

**What:**
- `topic-radar scan` — full scan across platforms, produces artifact + report
- `topic-radar teardown <url>` — single post deconstruction
- CLI options: `--platforms xhs,weibo`, `--output-dir`, `--mcp-check`
- Wires all previous tasks together

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_cli.py -q
uv run python -m topic_radar scan --platforms xhs
```

**done_when:**
- `topic-radar scan` runs end-to-end with at least one platform returning data
- Graceful degradation when platforms are unavailable
- Exit codes: 0 success, 1 partial (some platforms down), 2 all platforms down

---

## Task 8: Docs and verification

**Files:**
- Modify: `docs/index.md` — add topic_radar entry
- Modify: `docs/xhs-topics/index.md` — link to topic_radar
- Create: `docs/topic-radar.md` — topic_radar usage and architecture doc
- Modify: `CLAUDE.md` — add topic-radar commands

**verify:**
```bash
uv run pytest tests/unit/docs/test_docs_map.py tests/unit/docs/test_docs_metadata.py -q
uv run python -m ptsm.bootstrap docs-sync
```

**done_when:**
- `docs/index.md` maps to new topic-radar doc
- `docs-sync` passes

---

## Final verification

```bash
uv run pytest -q
uv run python -m topic_radar scan --platforms xhs
```
