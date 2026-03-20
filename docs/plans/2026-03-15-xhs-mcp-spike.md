# XHS MCP Spike Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 验证 `xiaohongshu-mcp` 是否可以作为本项目的小红书发布 backend，并用 `langchain-mcp-adapters` 跑通最小 `status/search/publish` 链路。

**Architecture:** 本轮不改主业务 workflow，只做一个独立 spike。先把第三方 `xiaohongshu-mcp` 当成外部 HTTP MCP 服务跑起来，再在本仓库中增加一个最小 Python 客户端，通过 `langchain-mcp-adapters` 调它的工具并记录结果。只有 spike 成功后，才进入正式 publisher 集成。

**Tech Stack:** `uv`, Python 3.12, `langchain-mcp-adapters`, `langchain`, HTTP MCP, `xiaohongshu-mcp` 预编译二进制

### Task 1: 环境探测与服务器启动

**Files:**
- Create: `docs/research/xhs-mcp-spike.md`

**Step 1: 记录本机前置条件**

- 记录架构、OS 版本、是否具备 `go/docker/chrome`。

**Step 2: 下载预编译二进制**

- 选择 `xiaohongshu-mcp-darwin-amd64.tar.gz`。
- 解压到临时目录，不写入主仓库。

**Step 3: 启动服务并验证 HTTP MCP 入口**

- 启动 `xiaohongshu-mcp`。
- 用 `curl` 调 `http://localhost:18060/mcp` 初始化。
- 记录是否能成功响应。

### Task 2: Python MCP 客户端最小验证

**Files:**
- Modify: `pyproject.toml`
- Create: `src/ptsm/spikes/__init__.py`
- Create: `src/ptsm/spikes/xhs_mcp_probe.py`
- Test: `tests/e2e/test_xhs_mcp_probe.py`

**Step 1: 先写失败测试**

- 写一个针对探测脚本纯函数的测试，验证服务器配置能正确组装为 `MultiServerMCPClient` 所需字典。

**Step 2: 跑红**

- 运行目标测试，确认因为模块不存在而失败。

**Step 3: 最小实现**

- 增加 `langchain-mcp-adapters` 依赖。
- 实现一个最小 probe 模块：
  - 连接 HTTP MCP
  - 列出工具
  - 调 `check_login_status`
  - 在提供参数时调 `search_feeds`
  - 在提供参数时调 `publish_content`

**Step 4: 跑绿**

- 运行目标测试确认通过。

### Task 3: Spike 执行与结果沉淀

**Files:**
- Create: `docs/research/xhs-mcp-spike.md`

**Step 1: 实际执行 probe**

- 在服务启动后，用 `uv run python -m ptsm.spikes.xhs_mcp_probe` 调工具。

**Step 2: 记录 status/search/publish 结果**

- 明确每一项是：
  - 已跑通
  - 因未登录受阻
  - 因缺图片/账号状态受阻

**Step 3: 输出集成建议**

- 记录下一步是否值得正式接入主项目。
- 记录推荐 transport、配置字段和风险点。
