# Topic Radar Runbook

See also:

- `docs/topic-radar.md`
- `docs/plans/2026-05-03-topic-radar-research-agent.md`

## Canonical Research Workflow (Agent-Ready)

### Step 0 — Activate Environment

topic-radar 运行时需要 DeepSeek API key。在 PTSM 主仓库的 `.env` 中已配置，worktree 会自动发现。

```bash
# 进入 worktree 并激活 venv
cd /Users/wudalu/llm-app/ptsm/.worktrees/feat-topic-radar
source .venv/bin/activate
```

之后所有 `topic-radar` 命令直接在终端执行，无需 `uv run` 或 `DEEPSEEK_API_KEY=` 前缀。

### Step 1 — Prerequisites

topic-radar 需要两个外部服务：

**小红书数据源** (`xiaohongshu-mcp`):

```bash
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

监听 `:18060`，匹配 `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`。

**微博/抖音数据源** (`mcp-trends-hub`):

无需单独启动，topic-radar 通过 `npx -y mcp-trends-hub` 自动拉起 stdio MCP。需要 Node.js 20+ 和 npx 可用。

**LLM 分析** (DeepSeek):

默认使用 DeepSeek 做语义分析。无需额外配置——复用 PTSM 的 `DEEPSEEK_API_KEY`。如果 API key 不可用，自动回退到规则引擎。

```env
DEEPSEEK_API_KEY=sk-...
DEEPSEEK_MODEL=deepseek-chat        # 可选，默认 deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1  # 可选
TOPIC_RADAR_LLM_MODEL=deepseek-chat # 可选，覆盖 DEEPSEEK_MODEL
```

验证环境:

```bash
which npx && npx --version
node --version  # >= 20
```

### Step 1 — MCP Health Check

```bash
topic-radar scan --mcp-check
```

输出示例:
```
✓ xiaohongshu: 13 tools
✓ trends_hub: 18 tools
```

表示两个数据源都可达。`✗` 标记的平台会在后续 scan 中被跳过，不阻塞其他平台。

注意：`--mcp-check` 只验证 MCP 工具可达，不代表小红书账号已登录。XHS 未登录时，`topic-radar scan --platforms xiaohongshu` 应直接失败并返回退出码 `2`，错误里会提示 `login required; run ptsm xhs-login-qrcode`，不要把 0 条 `raw_trending` 当作有效采样。

### Step 2 — Basic Scan (XHS Only)

先只扫小红书，验证端到端链路：

```bash
topic-radar scan --platforms xiaohongshu
```

这会：
1. 用默认关键词（"打工人", "治愈"）调用 `search_feeds`
2. 解析返回的 FeedItem 列表
3. 聚类到候选垂类
4. 输出 `outputs/artifacts/topic-scan-{date}.json` 和 Markdown 报告

检查产物：

```bash
cat outputs/artifacts/topic-scan-2026-05-03.json | python -m json.tool | head -30
cat outputs/artifacts/topic-brief-2026-05-03.md
```

### Step 3 — Full Multi-Platform Scan

```bash
topic-radar scan
```

默认三平台（xiaohongshu, weibo, douyin）。

可选平台：`xiaohongshu, weibo, douyin, zhihu, bilibili, toutiao, douban, sspai`（共 8 个）。

如果 mcp-trends-hub 未安装或不可达，微博和抖音会被标记为 `unavailable`，小红书继续正常扫描。退出码 `1` 表示部分平台不可用，`2` 表示全平台无数据。

### Step 4 — Targeted Keyword Scan

```bash
topic-radar scan --platforms xiaohongshu --keywords "情绪疗愈,修复系手作,AI效率"
```

用指定关键词替换默认关键词搜索，每个关键词都会搜索一次，结果合并。XHS `raw_trending` 会保留 `feed_id`、`xsec_token`、作者和互动数，后续可以直接拿来跑 `topic-radar teardown`。

### Step 5 — Post Teardown

对单篇高互动帖子做结构拆解：

```bash
# 从 scan 产物的 raw_trending 中找 feed_id
topic-radar teardown <feed_id> --xsec-token <token> --timeout-seconds 20
```

输出：
```
Title: 你绝对不知道的低成本治愈方法
Hook: 悬念 (confidence: 0.95)
Body structure: 问题导入式
Engagement triggers: 投票式提问, 留白邀请
Trigger confidence: 0.5
Comments: 80 (real discussion: True)
Question density: 0.35
Sentiment ratio: 0.82
Top terms: [('治愈', 24), ('教程', 18), ('求教程', 12), ('试试', 10), ('好看', 8)]
```

### XHS Detail Behavior

2026-05-15 登录后复测时，`search_feeds` 可以稳定返回候选笔记和互动指标。当前实现需要注意：

- LLM scan 路径会继续保留 `raw_trending`，不要只看 LLM 分析摘要来判断采样是否成功。
- `get_feed_detail` 兼容顶层 `note`、顶层详情对象和嵌套 `data.note` 结构；评论也会读取嵌套 `data.comments.list`。
- 部分笔记仍可能因为不可访问、timeout 或 MCP 500 失败；`topic-radar teardown` 会对单篇详情请求使用 `--timeout-seconds`，失败时输出紧凑错误，不应阻塞整批采样。

遇到详情失败时，先保留 `search_feeds` 的 `feed_id`、`xsec_token`、标题和互动指标，形成搜索级样本集；详情级评论拆解可以稍后重试，不要让单篇失败中断整体研究。

## Platform Availability Matrix

| 平台 | 数据源 | 传输方式 | 需要登录 | 工具名 |
|------|--------|----------|----------|--------|
| 小红书 | xiaohongshu-mcp | HTTP MCP | 是 | search_feeds, get_feed_detail, list_feeds |
| 微博 | mcp-trends-hub | stdio MCP (npx) | 否 | get_weibo_trending |
| 抖音 | mcp-trends-hub | stdio MCP (npx) | 否 | get_douyin_trending |
| 知乎 | mcp-trends-hub | stdio MCP (npx) | 否 | get_zhihu_trending |
| B站 | mcp-trends-hub | stdio MCP (npx) | 否 | get_bilibili_rank |
| 今日头条 | mcp-trends-hub | stdio MCP (npx) | 否 | get_toutiao_trending |
| 豆瓣 | mcp-trends-hub | stdio MCP (npx) | 否 | get_douban_rank |
| 少数派 | mcp-trends-hub | stdio MCP (npx) | 否 | get_sspai_rank |

小红书需要扫码登录（通过 `ptsm xhs-login-qrcode`）。微博和抖音通过 mcp-trends-hub 聚合，无需登录。

## Artifact Schema

`outputs/artifacts/topic-scan-{date}.json`:

| 字段 | 类型 | 说明 |
|------|------|------|
| scan_date | string | 扫描日期 |
| platforms | list[str] | 实际扫描的平台 |
| discovered_verticals | list[DiscoveredVertical] | 发现的候选垂类 |
| cross_platform_signals | list[CrossPlatformSignal] | 跨平台扩散信号 |
| high_engagement_patterns | list[dict] | 高互动模式摘要 |
| recommended_angles | list[dict] | 推荐选题角度 |
| raw_trending | list[dict] | 原始热榜数据 (≤30/平台) |
| platform_errors | dict | 平台错误详情 |
| analysis_method | string | `"llm"` 或 `"rules"` |
| scan_summary | string | LLM 模式下的整体摘要 |
| noise_topics | list[str] | LLM 模式下的噪声话题 |

## Error Recovery

| 症状 | 原因 | 解决 |
|------|------|------|
| `xiaohongshu: unavailable (connection refused)` | xhs-mcp 未启动 | 启动 `xiaohongshu-mcp-darwin-amd64` |
| `xiaohongshu: unavailable (login required)` | 未登录 | `ptsm xhs-login-qrcode` 扫码登录 |
| `weibo: unavailable (mcp-trends-hub not installed)` | npx 不可用 | 安装 Node.js 20+ 和 npm |
| `douyin: unavailable (...)` | 同上 | 同上 |
| scan 产出 0 条数据 | 无平台可用 | 检查 `--mcp-check` 输出 |
| teardown 返回 None | feed_id 无效或帖子已下架 | 换一个有效的 feed_id |

XHS `raw_trending` rows should include `feed_id`, `xsec_token`, `author`, `likes`, `comments`, `collects`, `shares`, and the source `keyword` when returned by `search_feeds`. If those fields are missing, do not start detail teardown; first rerun scan after login recovery.

## Exit Codes

| 码 | 含义 |
|----|------|
| 0 | 所有平台扫描成功 |
| 1 | 部分平台不可用，但至少一个平台有数据 |
| 2 | 全平台无数据，无产物产出 |

## Tuning

通过环境变量调整行为（`.env`）:

```env
XHS_MCP_SERVER_URL=http://localhost:18060/mcp
TOPIC_RADAR_OUTPUT_DIR=outputs/artifacts
TOPIC_RADAR_PLATFORMS=xiaohongshu,weibo,douyin
TOPIC_RADAR_SAMPLE_LIMIT=20
```

## CLI Reference

```bash
topic-radar scan                          # 全平台扫描
topic-radar scan --platforms xhs          # 单平台
topic-radar scan --platforms xhs,weibo    # 指定平台
topic-radar scan --keywords "关键词1,关键词2"  # 指定搜索词
topic-radar scan --mcp-check              # 仅检查 MCP 健康
topic-radar scan --output-dir /tmp/test   # 指定输出目录
topic-radar teardown <feed_id>            # 单帖拆解
topic-radar teardown <feed_id> --xsec-token <token>
```
