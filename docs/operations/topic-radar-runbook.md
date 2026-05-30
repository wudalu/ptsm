# Topic Radar Runbook

See also:

- `docs/topic-radar.md`
- `docs/plans/2026-05-03-topic-radar-research-agent.md`
- `docs/plans/2026-05-17-xhs-live-data-optimization.md`

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

### Step 5 — Domain Opportunity Scan

当问题是“现有领域里哪些更容易出爆款、是否要加新领域”时，不要直接把一批
关键词塞进 `guide-post`。先运行 PTSM 的领域机会对比命令：

```bash
uv run python -m ptsm.bootstrap xhs-domain-opportunity \
  --keywords "睡眠恢复,轻养生,人类丰容,苏轼,世界杯" \
  --sample-limit-per-keyword 5 \
  --output-dir outputs/artifacts/xhs-domain-opportunity
```

如果本地 `xiaohongshu-mcp` 登录预检很慢但确认账号可用，可以显式跳过登录预检并
延长 tool timeout：

```bash
uv run python -m ptsm.bootstrap xhs-domain-opportunity \
  --keywords "睡眠恢复,轻养生,人类丰容,苏轼,世界杯" \
  --sample-limit-per-keyword 3 \
  --skip-login-check \
  --tool-timeout-seconds 70
```

输出：

- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.json`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.md`

解读规则：

- 这是搜索级证据，不是全站热榜，也不是详情/评论拆解。
- 分数使用 `likes + comments * 4 + collects * 2 + shares * 6`，用于同批关键词之间的方向性比较。
- `new_domain_candidate` 表示值得进入新领域计划，不表示可以跳过完整 playbook/skill/harness 文档面。
- 普通 `guide-post` 和 `run-playbook` 不会因为这个命令存在而默认 live-scan；发帖仍优先读取本地 topic pack 和 pattern snapshot。

### Step 6 — Post Teardown

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
| raw_trending | list[dict] | 原始热榜数据 (默认 ≤100/平台) |
| platform_errors | dict | 平台错误详情 |
| analysis_method | string | `"llm"` 或 `"rules"` |
| scan_summary | string | LLM 模式下的整体摘要 |
| noise_topics | list[str] | LLM 模式下的噪声话题 |

## Error Recovery

| 症状 | 原因 | 解决 |
|------|------|------|
| `xiaohongshu: unavailable (connection refused)` | xhs-mcp 未启动 | 启动 `xiaohongshu-mcp-darwin-amd64` |
| `xiaohongshu: unavailable (login required)` | 未登录 | `ptsm xhs-login-qrcode` 扫码登录 |
| `xiaohongshu: no search results returned for requested keywords` | 已登录但关键词搜索无结果，不能形成有效样本 | 更换关键词或确认 xhs-mcp 搜索接口状态 |
| `weibo: unavailable (mcp-trends-hub not installed)` | npx 不可用 | 安装 Node.js 20+ 和 npm |
| `douyin: unavailable (...)` | 同上 | 同上 |
| scan 产出 0 条数据 | 无平台可用 | 检查 `--mcp-check` 输出 |
| teardown 返回 None | feed_id 无效或帖子已下架 | 换一个有效的 feed_id |

XHS `raw_trending` rows should include `feed_id`, `xsec_token`, `author`, `likes`, `comments`, `collects`, `shares`, and the source `keyword` when returned by `search_feeds`. If those fields are missing, do not start detail teardown; first rerun scan after login recovery.

## Periodic Pattern Library Workflow

普通发帖不要每次临时检索最新小红书热帖。需要定期采样时，用 PTSM 的本地 pattern library 命令：

```bash
uv run python -m ptsm.bootstrap collect-xhs-patterns \
  --lane human_enrichment \
  --keywords "人类丰容,家的丰容计划,低成本改造,钩织,拼豆" \
  --sample-limit-per-keyword 8 \
  --output-dir outputs/artifacts/xhs-pattern-library

uv run python -m ptsm.bootstrap analyze-xhs-patterns \
  --sample-path outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json \
  --lane human_enrichment \
  --output-dir outputs/artifacts/xhs-pattern-library
```

运行规则：

- 关键词必须顺序采集，不并发调用 XHS MCP。
- 每个关键词采完后立即落盘，后续关键词失败不能丢掉前序证据。
- 遇到 HTTP 500 或 login/session 波动时，保留 partial artifact，并把失败关键词写入 `keyword_errors`。
- 样本只保留标题、互动、feed identifiers、作者、封面尺寸和是否有封面 URL；不要下载或复用创作者图片。
- 分析产物写入 `outputs/artifacts/xhs-pattern-library/current.json`，由普通 `run-playbook` 读取。

如果 broad scan 连续出现 HTTP 500，停止扩大批量，先重启 MCP 服务并恢复登录态。不要把空样本或失败 keyword 当成有效趋势证据。

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
