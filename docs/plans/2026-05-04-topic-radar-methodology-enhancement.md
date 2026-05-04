# Topic Radar Methodology Enhancement — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 content-production-mcp 的四维方法论嵌入 topic-radar 的 LLM prompt，让选题分析有理论框架支撑。

**Architecture:** 从 `@jamesai/content-production-mcp` 的 methodology 中提取核心框架，静态嵌入 `llm_analyzer.py` 的 system prompt。不引入新的 MCP 运行时依赖。

**Tech Stack:** Python 3.12, existing LLM analyzer, vendorized methodology excerpt.

**Non-goals:** 不把 content-production-mcp 作为运行时 MCP server，不修改 CLI 接口，不改变 TopicScanResult schema，不影响 rule-based fallback。

---

### Task 1: Vendorize methodology as a prompt module

**Files:**
- Create: `src/topic_radar/analysis/methodology.py`

**What:**
- 从 content-production-mcp 方法论中提取最相关的框架：
  - 八大认知劫持机制
  - 12 荣格原型理论
  - 情绪触发 vs 讨论触发的区分
  - 各平台讨论特征
- 结构化为一组常量，供 LLM prompt 使用
- 总量控制在 ~800 tokens

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_methodology.py -q
```

**done_when:**
- `META_PROMPT` 常量可直接拼入 system prompt
- 内容包含 4D 框架核心概念
- 总 token 在 600-1000 范围

---

### Task 2: Integrate methodology into LLM prompt

**Files:**
- Modify: `src/topic_radar/analysis/llm_analyzer.py`

**What:**
- 将 `META_PROMPT` 拼接到 system prompt
- 在 LLM output schema 中新增可选字段: signal.mechanism, angle.hook_mechanism

**verify:**
```bash
uv run pytest tests/unit/topic_radar/test_llm_analyzer.py -q
```

**done_when:**
- System prompt 包含四维方法论
- Output schema 新增字段不影响兼容性

---

### Task 3: End-to-end quality validation

**Files:** No new files

**What:**
- 用增强 prompt 跑真实扫描，对比增强前后质量
- 保存对比结果到 tests/fixtures/

**verify:**
```bash
uv run pytest -q
topic-radar scan --platforms weibo,douyin
```

**done_when:**
- 增强后质量不低于增强前
- 全量测试通过

---

### Task 4: Docs update

**Files:**
- Modify: `docs/topic-radar.md`
- Modify: `docs/operations/topic-radar-runbook.md`

**verify:**
```bash
uv run pytest tests/unit/docs/test_docs_map.py -q
```

**done_when:**
- docs 反映 methodology 嵌入
