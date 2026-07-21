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

**趋势平台数据源** (`mcp-trends-hub`):

无需单独启动，topic-radar 通过 `npx -y mcp-trends-hub` 自动拉起 stdio MCP。它提供微博、抖音、知乎、B站、今日头条、豆瓣、少数派七个平台；需要 Node.js 20+ 和 npx 可用。

**LLM 分析** (DeepSeek):

默认优先使用 DeepSeek 做语义分析。无需额外配置——复用 PTSM 的 `DEEPSEEK_API_KEY`。API key 不可用、调用失败或返回不含可验证推荐时，会记录安全化诊断并自动回退到规则引擎；collector evidence 仍是每个推荐的前提。

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

表示两个数据源都可达。工具发现有 bounded timeout；`✗` 既可能表示不可达，也可能表示某一 server 卡住后被隔离降级。它覆盖的平台会在后续 scan 中被跳过，不阻塞其他平台。

注意：`--mcp-check` 只验证 MCP 工具可达，不代表小红书账号已登录。XHS 未登录时，`topic-radar scan --platforms xiaohongshu` 会写 diagnostic artifact 并返回 exit code `2`，错误里会提示 `login required; run ptsm xhs-login-qrcode`；不要把 0 条 `raw_trending` 当作有效采样。

### Step 2 — Basic Scan (XHS Only)

先只扫小红书，验证端到端链路：

```bash
topic-radar scan --platforms xiaohongshu
```

这会：
1. 用默认关键词（"打工人", "治愈"）调用 `search_feeds`
2. 解析返回的 FeedItem 列表
3. 聚类到候选垂类
4. 输出 `outputs/artifacts/topic-scan-{date}.json` 和 Markdown 报告；没有有效 evidence 时仍会输出 diagnostic artifact，但不会调用 LLM 或给出推荐

检查产物：

```bash
cat outputs/artifacts/topic-scan-2026-05-03.json | python -m json.tool | head -30
cat outputs/artifacts/topic-brief-2026-05-03.md
```

### Step 3 — Full Multi-Platform Scan

```bash
topic-radar scan
```

默认请求八个平台：`xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai`。

CLI 可接受 `xhs`/`小红书`、`微博`、`抖音`、`知乎`、`B站`、`头条`、`豆瓣`、`少数派`等别名，平台列表的 ASCII `,` 和中文 `，` 都会拆分（例如 `--platforms "小红书，微博"`）。未知平台不是 silent skip：会进入 `platform_errors`。小红书 HTTP MCP 与 mcp-trends-hub 会分 server 加载；任一服务未安装、未登录、不可达或工具发现超时时，它覆盖的各平台会被分别记录，小红书或 trends-hub 的其他成功来源仍可继续扫描，不会被空 tool cache 连带阻断。

先读 artifact 的 `scan_quality`，再读推荐：`completed` 表示所有请求平台都有有效 canonical evidence；`partial` 表示至少一个平台有有效 evidence、但另一些平台/关键词/LLM analysis 有诊断；`insufficient_evidence` 表示没有有效 evidence。exit code `1` 表示 `partial`，exit code `2` 表示 `insufficient_evidence`；两种情况都会有 diagnostic artifact。

### Step 4 — Targeted Keyword Scan

```bash
topic-radar scan --platforms xiaohongshu --keywords "情绪疗愈,修复系手作,AI效率"
```

用指定关键词替换默认关键词搜索，每个关键词都会搜索一次，结果合并。ASCII `,` 与中文 `，` 都可分隔关键词；只含分隔符/空白的 `--keywords` 会安全回退到默认关键词，不会令扫描崩溃。XHS 会优先按 `feed_id` 去重；完整标题+作者只桥接一条缺 ID 观察到其首个真实 ID，之后同标题/作者的不同真实 ID 仍会保留；若已经有多个真实 ID，后续缺 ID 观察保持 unresolved。相同来源的 `matched_queries` 和 `source_observation_count` 会合并。`raw_trending` 仍会保留 `feed_id`、`xsec_token`、作者和互动数，后续可以直接拿来跑 `topic-radar teardown`，但 PTSM drafting context 不会接收这些原始字段。

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
- 默认登录预检若返回 `login_required`，说明还未启动关键词搜索；读取 `_login` diagnostic，执行 `ptsm xhs-login-qrcode` 恢复会话后重跑。它没有 fit、排序推荐或 `new_domain_candidate`；`--skip-login-check` 只跳过预检，不会绕过实际搜索的登录要求。
- 跨关键词会优先按同一 XHS `feed_id` 去重；完整标题+作者只用于桥接缺 ID 的同一观察，首个真实 ID 会消费这条 bridge，后续不同真实 ID 不折叠；已有多个真实 ID 后的缺 ID 样本保持 unresolved。标题单独不折叠不同笔记。ASCII `,` 与中文 `，` 都可分隔关键词；只含分隔符/空白时使用 bounded 默认基线。若没有 successful unique samples，结果为 `insufficient_evidence`，不会输出 fit、排序推荐或 `new_domain_candidate`；不要把静态 keyword mapping 当作 live 发现。
- `new_domain_candidate` 表示有真实搜索样本、值得进入新领域计划，不表示可以跳过完整 playbook/skill/harness 文档面。
- 普通 `guide-post` 和 `run-playbook` 不会因为这个命令存在而默认 live-scan；发帖仍优先读取本地 topic pack 和 pattern snapshot。

### Step 5b — Fresh Topic Research Before a Post

只有要把当下热点作为发帖选题时，才使用 `--fresh-topic-research`：

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --fresh-topic-research \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post
```

它通过 public `topic_radar.cli.run_scan()` 走与 CLI 相同的八平台路径。`insufficient_evidence` 会在 workflow 前停止并返回 artifact/report 路径与 platform diagnostics；`partial` 会展示 evidence-backed 候选并保留诊断。交互选择只把选定角度、讨论诱因和构造场景送进 drafting；raw title、作者、URL、feed id、token 只留在 Topic Radar artifact，canonical-equivalent 或较具体 title 的内嵌复写、以及 raw author/URL/feed/token（包括短值）都不能作为 `vertical`、`angle` 或讨论诱因穿透该边界；短泛 title 可以作为新角度语言。普通/local-only builder 不回读旧 scan artifact；fresh builder 也只接受本次 receipt 明示且可读的 artifact，缺失 receipt 会 fail closed。`topic_selection` 只保留 opaque traceability，不包含终端 `scan_summary`；选定后不会再发起第二次 live scan。

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
| schema_version | int | 当前为 `2`；保留原字段的向后兼容扩展 |
| scan_quality | string | `completed`、`partial` 或 `insufficient_evidence` |
| evidence | list[EvidenceRecord] | canonical source evidence、查询聚合与平台内归一化热度 |
| topic_clusters | list[TopicCluster] | 保守事件簇，含 `cluster_id`、`event_fingerprint`、真实平台和 `evidence_ids` |
| discovered_verticals | list[DiscoveredVertical] | 发现的候选垂类 |
| cross_platform_signals | list[CrossPlatformSignal] | 仅有至少两个真实平台 evidence 的跨平台扩散信号；单次快照的 `velocity` 为 `unknown`，不推断传播速度 |
| high_engagement_patterns | list[dict] | 高互动模式摘要 |
| recommended_angles | list[dict] | evidence-backed 推荐角度，含 `cluster_id`、`event_fingerprint`、`evidence_ids`、`angle_signature`、`novelty_state` 和 `ranking_score` |
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
| `scan_quality: insufficient_evidence` | 无有效 canonical evidence | 读 `platform_errors`，恢复登录/MCP 或换关键词；不要从空 artifact 生成热点推荐 |
| `scan_quality: partial` | 一部分平台、关键词或 LLM 分析失败 | 可使用现有 evidence-backed 推荐，但不得声称失败平台已覆盖；先记录/修复 `platform_errors` |
| `status: login_required`（domain opportunity） | XHS 登录预检未通过，尚未搜索关键词 | 读 `_login`，运行 `ptsm xhs-login-qrcode` 后重跑；不要从静态 mapping 生成推荐 |
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
| 0 | `completed`：所有请求平台有有效 evidence，且无诊断 |
| 1 | `partial`：至少一个平台有 evidence，但有平台/关键词/LLM diagnostic；artifact 已产出 |
| 2 | `insufficient_evidence`：没有有效 evidence；diagnostic artifact 已产出，未调用 LLM/未生成推荐 |

## Tuning

通过环境变量调整行为（`.env`）:

```env
XHS_MCP_SERVER_URL=http://localhost:18060/mcp
TOPIC_RADAR_OUTPUT_DIR=outputs/artifacts
TOPIC_RADAR_PLATFORMS=xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai
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

同一输出目录中重跑同一天的 scan 时，JSON 和 Markdown 会使用相同 suffix 配对（如 `topic-scan-2026-07-22-2.json` 与 `topic-brief-2026-07-22-2.md`），不会覆盖上一份。`topic-radar-history.jsonl` 是 append-only 的 14 天 event+angle cooldown 索引；若需要重新测试同一角度，请换输出目录，而不是手改历史行。
