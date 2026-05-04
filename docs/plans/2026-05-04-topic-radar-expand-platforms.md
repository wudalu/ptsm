# Topic Radar Platform Expansion — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 mcp-trends-hub 中已有的知乎/B站/今日头条/豆瓣/少数派 5 个中文平台接入 topic-radar，丰富 LLM 分析的数据广度。

**Architecture:** 在现有 `weibo.py` 中新增平台类，复用 `TrendingItem`、`_parse_xml_items` 和 `McpClient`。每个平台一个 adapter class，模式完全一致。

**Tech Stack:** Python 3.12, mcp-trends-hub (stdio MCP), existing `McpClient`.

**Non-goals:** 不引入新的 MCP server，不修改 CLI 接口，不修改分析层。

---

### Task 1: Add 5 platform adapters

**Files:**
- Modify: `src/topic_radar/platforms/weibo.py`

**What:**
- Add classes: `ZhihuPlatform`, `BilibiliPlatform`, `ToutiaoPlatform`, `DoubanPlatform`, `SspaiPlatform`
- Each class: `platform_name`, `get_trending(limit)` → `list[TrendingItem]`
- Tool names: `get_zhihu_trending`, `get_bilibili_rank`, `get_toutiao_trending`, `get_douban_rank`, `get_sspai_rank`
- All reuse existing `_parse_xml_items` and `PlatformUnavailable`
- Each ~10 lines — no new logic

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_multi_platform.py -q
# Smoke: pick one new platform
topic-radar scan --platforms zhihu
```

**done_when:**
- 5 new platform adapters return `list[TrendingItem]`
- Each platform scannable via `--platforms zhihu,bilibili,...`

---

### Task 2: Wire new platforms into CLI

**Files:**
- Modify: `src/topic_radar/cli.py`

**What:**
- Add scan blocks for zhihu, bilibili, toutiao, douban, sspai in `_scan()`
- Each follows same pattern as weibo/douyin blocks
- Add platform name mappings: `"zhihu" → ZhihuPlatform`, etc.

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_cli.py -q
topic-radar scan --platforms zhihu,bilibili,toutiao,douban
```

**done_when:**
- All 5 platforms can be selected via `--platforms`
- Multi-platform scan with 7 sources works end-to-end

---

### Task 3: Update runbook and docs

**Files:**
- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`

**verify:**
```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

**done_when:**
- Platform list updated from 3 to 8
- Runbook reflects new platform options
