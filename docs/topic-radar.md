---
title: Topic Radar
status: active
owner: ptsm
last_verified: 2026-07-23
source_of_truth: true
related_paths:
  - src/topic_radar
  - src/topic_radar/analysis/evidence.py
  - src/topic_radar/cli.py
  - src/topic_radar/platforms/xiaohongshu.py
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/xhs_domain_opportunity.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/domain/xhs_patterns.py
  - src/ptsm/infrastructure/xhs_patterns
  - docs/index.md
  - docs/xhs-topics/index.md
  - docs/operations/topic-radar-runbook.md
  - docs/plans/2026-05-03-topic-radar-research-agent.md
---

# Topic Radar

独立的多平台选题研究引擎，发现各平台容易引发讨论的话题，产出结构化的选题建议。

与 PTSM 解耦，不依赖 PTSM 内部模块。PTSM 可通过 skill 或 planner 消费其产出的 artifact。

## 使用方式

```bash
# 多平台扫描
topic-radar scan                          # 默认请求全部 8 个已支持平台
topic-radar scan --platforms xhs,weibo    # 限定平台（xhs 是 xiaohongshu 别名）
topic-radar scan --mcp-check              # 仅检查 MCP 健康

# 单帖拆解
topic-radar teardown <feed_id> --xsec-token <token>

# PTSM 领域机会对比，只读搜索级采样
uv run python -m ptsm.bootstrap xhs-domain-opportunity \
  --keywords "睡眠恢复,轻养生,人类丰容,苏轼,世界杯" \
  --sample-limit-per-keyword 5 \
  --output-dir outputs/artifacts/xhs-domain-opportunity

# PTSM 泛热点：不预设赛道，先发现后路由（默认展示前 12 个）
uv run python -m ptsm.bootstrap hotspot-discovery --max-hotspots 12
```

## 架构

```
src/topic_radar/
├── cli.py                 # CLI: scan, teardown
├── config.py              # pydantic-settings 配置
├── mcp_client.py          # MCP client (HTTP + stdio)
├── platforms/
│   ├── xiaohongshu.py     # list_feeds, search_feeds, get_feed_detail
│   └── weibo.py           # Weibo/Douyin via mcp-trends-hub
├── analysis/
│   ├── evidence.py        # canonical evidence、质量状态、事件簇、历史去重
│   ├── schemas.py         # Pydantic schemas for LLM output
│   ├── llm_analyzer.py    # LLM-driven analysis (primary)
│   ├── methodology.py     # 4D methodology framework for prompt injection
│   ├── note_teardown.py   # 帖子拆解 (fallback)
│   ├── cross_platform.py  # 跨平台话题/垂类聚类 (fallback)
│   └── comment_signals.py # (included in note_teardown)
└── output/
    ├── artifacts.py       # TopicScanResult → JSON
    └── report.py          # Markdown 报告
```

### 分析路径

**默认路径：canonical evidence → 保守事件聚类 → LLM 或 rules → 多样性/新颖度筛选**

1. 八个平台的 collector 先产生原始观察；小红书 HTTP MCP 与 trends-hub stdio MCP 分 server 加载和缓存，工具发现也有 bounded timeout。未传关键词时小红书使用 `list_feeds` 的 `open_feed_listing`，明确关键词才使用 `search_feeds`；任一服务不可用或卡住只记录它覆盖的平台诊断，不能阻断另一服务的健康采集。空结果、未登录、不可用平台和不支持的平台都记为显式诊断，绝不把空列表当作成功采样。
2. canonical evidence 在分析前去重。小红书优先按 `feed_id`；完整标题+作者只可桥接一条缺 ID 观察到其第一个真实 ID，随后同标题/作者的不同真实 ID 仍是独立来源。若同一可见身份已有多个真实 ID，后来的缺 ID 观察保持 unresolved，不会任意并到其中一篇。URL 或保守 fallback 只在 ID 不可用时参与识别；多关键词命中会合并 `matched_queries` 并累计 `source_observation_count`。热度只在各自平台内归一化，不把不同平台的绝对热度直接相加比较。
3. 相近标题以保守 complete-link 规则聚成 event cluster；天气现象、AI 内容形态等互斥核心词不能被模糊匹配合并。AI 视觉同义词（如绘图、绘画、作图、图像、图片）属于同一槽位，和写作、编程等不同槽位仍互斥。只有一个簇确实有至少两个实际平台的 evidence 时，才会生成跨平台扩散信号；单次快照只说明共现，不会声称 `accelerating` 等时序速度。
4. LLM 只能引用 prompt 中给出的 `evidence_id` / `cluster_id`，输出会在落盘前验证；八平台 prompt 有明确上限（每平台 12 条热搜、48 条 evidence、24 个事件簇），并以 round-robin 保留各平台可见证据。事件簇只可引用本次 prompt 内可见的 evidence，避免 raw rows/evidence/clusters 三重展开失控。任何与 canonical source title 等价的 `vertical`、`angle` 或 `why` 都会被拒绝，较具体 title 的内嵌复写也会被拒绝。像 `AI` 这样的短泛词可以作为新角度里的普通语言；raw author/URL/feed/token 仍无论长短一律阻断，不能作为 drafting-facing 二次创作角度。未展开的 `{placeholder}` 会在 LLM 结果验证阶段拒绝，因此不会把 rules fallback 错误地压成空结果；rules 产出的角度同样必须绑定真实 event evidence，且不得包含未展开的 `{placeholder}`。
5. 最终 selector 每个 event 最多保留一个角度，并在默认 14 天窗口内压制同一事件+同一角度（包括语义等价的标题别名）；同一事件的新角度仍可进入报告。

artifact 中 `analysis_method` 字段标记实际使用的路径（`"llm"` 或 `"rules"`）。

## Evidence Quality, Clusters, and Novelty

每次 scan 都有一个显式 `scan_quality`：

- `completed`：每个请求平台都有有效 canonical evidence，且没有 collector/analysis 诊断。
- `partial`：至少有一个平台有有效 evidence，但另一些平台、关键词或 LLM analysis 有可追溯问题；报告仍可使用，但不得把缺失平台当成已覆盖。
- `insufficient_evidence`：没有任何有效 evidence。不会调用 LLM，也不会生成推荐；仍写出 diagnostic artifact 供排障。

JSON schema 已升级为 `schema_version: 2`。除兼容保留的 `raw_trending` 外，关键字段是：

- `evidence`：每条 canonical source 的 `evidence_id`、平台、规范化标题、平台内 `normalized_heat`、匹配查询数和观测次数。
- `topic_clusters`：`cluster_id`、`event_fingerprint`、代表标题、`evidence_ids`、实际平台集合和 score。
- `recommended_angles`：证据绑定的 `cluster_id`、`event_fingerprint`、`evidence_ids`、`angle_signature`、`novelty_state` 与 `ranking_score`。这些字段解释“为什么这个角度在本次有资格出现”，不是新的跨平台热度承诺。
- `platform_errors`：collector 或安全化 LLM fallback 诊断。`partial` 和 `insufficient_evidence` 都必须先读它再解读推荐。

选中的 event/angle 对会 append 到输出目录的 `topic-radar-history.jsonl`。它是小型本地历史索引，不回写或覆盖旧的 scan artifact；同一天多次扫描会成对产生 `topic-scan-<date>.json` / `topic-brief-<date>.md`，必要时追加 `-2`、`-3` 等后缀。

## 数据来源

- **小红书**: 本地 xiaohongshu-mcp (HTTP MCP on localhost:18060)
- **微博、抖音、知乎、B站、今日头条、豆瓣、少数派**: mcp-trends-hub (stdio MCP via npx)

当前已支持且默认请求的平台集合是
`xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai`。CLI 同时接受
`xhs`、`小红书`、`微博`、`抖音`、`知乎`、`B站`、`头条`、`豆瓣`、`少数派`等常用别名；未知平台会保留为 diagnostic，而不会被悄悄忽略。
平台列表与小红书关键词都接受 ASCII `,` 和中文 `，`，例如
`--platforms "小红书，微博"` 会请求两个平台。未传关键词（或只传分隔符/空白）时 XHS
采集 `open_feed_listing`，不会偷偷注入 `打工人,治愈`；这只是 open feed listing sample，
not an exhaustive whole-site ranking，登录/MCP 问题会如实成为 `partial` diagnostic。

## XHS Periodic Pattern Collection

PTSM 现在把“实时小红书检索”和“普通发帖生成”拆开：

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

`collect-xhs-patterns` 顺序采集关键词，不并发打 XHS MCP；单个关键词遇到
HTTP 500、timeout 或登录波动时，会把已成功关键词的样本先落盘，并把失败关键词写入
`keyword_errors`。样本保留标题、关键词、互动数、`feed_id`、`xsec_token`、
作者、封面宽高和是否有封面 URL，但不会下载或复用创作者图片。

`analyze-xhs-patterns` 把原始样本归一化为本地 `XhsSample`，再沉淀为
`PostFormatPattern` snapshot。当前确定性规则会识别：

- `sudden_realization`
- `you_should_enrich`
- `before_after_contrast`
- `saveable_list`
- `process_or_tutorial`

最新可用 snapshot 写入 `outputs/artifacts/xhs-pattern-library/current.json`。
普通 `run-playbook` 只读取这个本地 snapshot，不会默认实时搜索小红书。

## XHS Domain Opportunity Scan

`xhs-domain-opportunity` 是 PTSM 的只读领域机会对比 surface，用来回答
“哪些候选领域更值得开新线或加子线”。它和普通 `guide-post` 不同：

- `xhs-domain-opportunity` 面向 operator，按一组关键词做 bounded `search_feeds`，
  计算 `likes + comments * 4 + collects * 2 + shares * 6`，再映射到现有
  playbook、候选 sublane 或新领域建议。跨关键词优先按 `feed_id` 去重；完整标题+作者只用于桥接缺失 ID 的同一观察，首个真实 ID 会消费该 bridge，后续同标题/作者的不同真实 ID 仍保留；若已知多个真实 ID，后来的缺 ID 样本保持 unresolved。标题单独不能折叠不同笔记。ASCII `,` 与中文 `，` 都能分隔关键词；只传分隔符或空白时会被拒绝，必须由 operator 给出明确候选，而不会回退到默认赛道。出现
  no successful unique samples 时，不会产出 playbook fit、排序推荐或 `new_domain_candidate`。
- `guide-post` 面向发帖前选题确认，默认只读本地 topic pack，不触发 live XHS
  搜索，不展示原始来源或 provenance。
- 普通 `run-playbook` 仍不默认 live-scan；要么消费本地 pattern snapshot，要么由
  operator 显式运行 fresh research / domain opportunity scan 后再选择方向。
- `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md` 是 Codex/OpenClaw 的薄 wrapper，只调用这个 CLI 并读取生成 brief，不复制评分或映射逻辑。

输出产物：

- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.json`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-<date>.md`

JSON 会保留搜索级样本的标题、互动指标和 feed identifiers，便于追溯；Markdown
brief 只展示 top domain、playbook fit、新领域候选和 workflow notes，不默认暴露
feed id 或 token。搜索完成后的结果状态为 `completed`、`partial` 或
`insufficient_evidence`；后者表示没有有效样本，不是“低热度的新领域”结论。若未使用
`--skip-login-check` 且 XHS 登录预检先失败，状态会是 `login_required`：尚未搜索、没有
fit/排序/新领域候选，先按 `_login` diagnostic 恢复登录再重跑。该 scan 是 bounded
Xiaohongshu keyword-search evidence，not a whole-site or cross-platform trend ranking。

## 分析能力

1. **帖子拆解**: 标题钩子分类（悬念/反常识/情绪共鸣/利益驱动/身份认同）、正文结构、互动诱因检测
2. **跨平台话题发现**: 只从至少两个真实平台支持的 event cluster 生成扩散信号；单次快照不推断传播速度
3. **垂类聚类**: 自动将话题分配到候选垂类，附带置信度和讨论密度；LLM 结论必须可回溯到 canonical evidence
4. **重复控制**: source 去重、同扫描一事件一角度、近期同事件+同角度 cooldown
5. **评论区信号**: 提问密度、情感极性、真讨论 vs 打卡

## 产物

- `outputs/artifacts/topic-scan-{date}.json` — 结构化 JSON；同日重跑会使用 `-2`、`-3` 后缀而不覆盖
- `outputs/artifacts/topic-brief-{date}.md` — 与 JSON stem 配对的可读 Markdown 报告
- `outputs/artifacts/topic-radar-history.jsonl` — append-only 的近期 event/angle cooldown 索引

## Programmatic API

`topic_radar.cli.run_scan()`（包级 `topic_radar.run_scan()` 同样可用）提供异步
programmatic API，返回 `TopicScanResult`：

```python
from topic_radar.cli import ScanOptions, run_scan

result = await run_scan(options=ScanOptions(max_recommendations=6, history_days=14))
# no platforms / keywords: configured default platforms, no hidden XHS query seed
# result.discovered_verticals  — 发现的垂类
# result.recommended_angles    — 推荐角度
# result.scan_quality          — completed | partial | insufficient_evidence
# result.evidence / result.topic_clusters — 可追溯 canonical evidence
```

## 与 PTSM 协作

PTSM 有两个不同的 Topic Radar surface：`hotspot-discovery` 是先开放发现、后路由，
`--fresh-topic-research` 则保留为大多数已选 playbook 内的 fresh 选题。AI 科技 evidence
mode 是明确例外：它必须先 discovery、再由 operator 独立整理事实或测试 evidence file，不能
让 scan 直接进入 AI drafting。

```bash
# 默认泛热点入口：先读 route receipt，再由 operator 选择已有 playbook 或处理 unmapped
uv run python -m ptsm.bootstrap hotspot-discovery --max-hotspots 12
```

`hotspot-discovery` 不传 account、playbook、domain、platform 或 keyword filter。它只消费与
canonical evidence 一致的 `topic_clusters`，按 score 输出 `existing_playbook_fit`、`ambiguous`、
`unmapped` 和可能的 `new_domain_candidate`。默认展示前 12 个；`--max-hotspots` 只控制已验证
cluster 的返回数量，不能用来指定赛道或关键词。receipt 会同时写入 `eligible_hotspot_count`、
`returned_hotspot_count` 与 `hotspot_limit`，避免把截断列表伪装成完整热榜。`operator_headline`
仅供报告阅读，不能进入 drafting；`partial` 不得称为完整全平台结果，`insufficient_evidence`
不产生静态推荐。

为避免 Top-N 恰好全是未映射新闻而掩盖扫描中真实存在的内容机会，receipt 还会给出不与主列表
重复的 `routed_hotspots` 补充视图（最多 6 个）。它只从同一次、已经完成的无方向扫描结果中挑出
`existing_playbook_fit` / `ambiguous`，不改变全平台排名；`route_status_counts` 和
`eligible_supplemental_routed_hotspot_count` / `returned_supplemental_routed_hotspot_count` 会明确范围。
为避免重复推荐，每条补充候选至少引入一个未展示的 playbook；若它是 `ambiguous`，仍保留完整候选集，
不能因其中一个 playbook 已展示就吞掉另一个可选项。主列表仍保留完整的热点路由事实。

`--fresh-topic-research` 将 topic-radar 集成到已经选择的发帖流程：

```bash
# 选题驱动发帖（topic-radar 扫描 → 交互选题 → 自动生成内容）
ptsm run-fengkuang --fresh-topic-research --account-id acct-fk-local
ptsm run-playbook --fresh-topic-research --account-id acct-psychology-local --playbook-id modern_psychology_post

# 结合图片生成和发布
ptsm run-fengkuang --fresh-topic-research --account-id acct-fk-local --auto-generate-image --publish-mode mcp-real --publish-visibility "仅自己可见"
```

流程：
1. `run-playbook --fresh-topic-research` 在已解析 account/playbook 后调用 public `topic_radar.cli.run_scan()`；它不传入平台参数，因此使用 Topic Radar 配置的八平台默认集合。它不是泛发现或自动换 playbook 的入口。
2. 如果结果为 `insufficient_evidence`，PTSM 在启动 workflow 前返回可操作诊断，不会用静态映射伪造一个“热点方向”。`partial` 会保留平台错误和 artifact/report 路径，供 operator 判断是否继续。
3. 终端交互只展示 evidence-backed 的推荐角度。选定的垂类、角度和讨论诱因构成 enriched scene；`cluster_id`、`event_fingerprint`、`evidence_ids` 和 scan receipt 仅保留在 response/run/artifact 的 traceability metadata。
4. drafting context never receives raw source titles, authors, URLs, feed IDs, or tokens。选定后 runtime 也不会再启动第二次 live scan 或叠加竞争性的 `topic_research` 方向。
5. workflow 继续按普通 playbook 的安全、标签、来源和文案合同生成内容。

### AI Tech Evidence Modes

`ai_tech_daily_post` 不接受 Topic Radar 的 headline、angle 或 cluster 作为 publishable fact。
当 operator 选择 AI 科技路由时，先完成 `hotspot-discovery`，再核验并写入
`--ai-evidence-file`：`news_brief` 需要 3–5 条独立 facts，`hands_on` 需要一条完整、可复现
的测试记录，`fact_translation` 需要至少两条 facts 和人群判断。scan 的可用输出最多作为
opaque `trend_support`（`cluster_id` / `evidence_ids`），仍不能代替 `source_refs` 或
`test_evidence_refs`。

因此不要这样运行 AI playbook：

```bash
# 返回 ai_tech_fresh_research_separate，不会把 scan 注入 AI 草稿
ptsm run-playbook --fresh-topic-research --account-id acct-ai-tech-local \
  --playbook-id ai_tech_daily_post --ai-content-mode news_brief \
  --ai-evidence-file /path/to/ai-evidence.json
```

正确流程是 discovery → operator evidence collection → evidence-gated dry-run。原始 source
title、author、URL、feed ID、token 和完整 Topic Radar artifact 都留在研究边界；AI artifact
只保存 opaque evidence manifest 与通过的 gate receipt。

topic_radar 不依赖 PTSM。PTSM 还可以：
- 通过 CLI 命令独立运行，人工参考结果
- 通过 programmatic API 在其他场景中消费分析结果
