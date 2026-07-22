---
title: XHS Topic Harness Integration
status: active
owner: ptsm
last_verified: 2026-07-23
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/harness-engineering.md
  - docs/observability.md
  - docs/topic-radar.md
  - docs/operations/topic-radar-runbook.md
  - docs/research/xhs-mcp-spike.md
  - src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/agent_runtime/nodes/planner.py
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/infrastructure/artifacts/file_store.py
  - src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/domain/ai_tech_content.py
---

# XHS Topic Harness Integration

## Why This Belongs In The Harness

如果热点判断只停留在人工刷帖，它无法复盘，也无法复用。

PTSM 已经有：

- `xiaohongshu-mcp` 接入和验证过的搜索/发布链路
- 本地 artifacts
- run summaries / events / evidence
- request-scoped skill surface

所以更合理的方向是把“小红书热点研究”做成一个轻量、可重复、可追溯的 harness 子流程。

## Minimal Research Loop

建议固定成 4 步：

1. `list_feeds`
   用来抓平台首页正在浮出的内容，不预设关键词，适合看突然冒头的话题。
2. `search_feeds`
   针对垂类关键词做定向采样，例如“手作修复”“睡前仪式感”“普通人用AI”。
3. `get_feed_detail`
   对高互动样本拉完整正文、图文结构、评论和互动线索。
4. 结构化沉淀
   输出主题摘要、样例帖、评论关键词、建议角度，而不是只保留一堆原始帖子。

## Recommended Artifact Shape

当前不需要立刻改代码，但后续如果做自动化，建议沿用现有 artifact 思路，生成两类产物：

- `outputs/artifacts/xhs-topic-scan-<date>-<vertical>.json`
- `outputs/artifacts/xhs-topic-brief-<date>-<vertical>.json`

建议字段：

- `platform`
- `scan_date`
- `vertical`
- `queries`
- `sampled_feeds`
- `top_patterns`
- `comment_signals`
- `recommended_angles`
- `rejected_angles`
- `source_urls`

这样做的好处是研究 artifact 可被 `logs` / `runs` / `diagnose-*` 一类只读 surface 追溯。若
未来把它交给 PTSM drafting，必须先转成 provenance-safe contract：raw `source_urls`、作者、
feed identity、原始标题与 token 只留在 research artifact，不能直接给 planner、checkpoint、
reader-visible content 或最终 post artifact。

## Skill And Playbook Hook Points

### 1. Trend Scan Skill

`xhs_trend_scan` 已经作为 builtin skill 落地，并且已经挂进 planner。

`xhs_trend_scan` 仍作为现有 XiaoHongShu playbook 的 `required_skills`，但它的职责已经收窄为把本地 XHS pattern library snapshot（或静态 guidance）写进独立的 `runtime_skill_contents`。普通 drafting 不从该 skill 调用 `xiaohongshu-mcp`，也不会因缺少 snapshot 而启动实时搜索。

泛热点先由 `hotspot-discovery` 调用 public Topic Radar API，再让 operator 选择 post-scan route；显式 `--fresh-topic-research` 则仍由大多数已选 playbook 的 `run_playbook` 调用同一 API。默认八个平台只扫描一次，产物保留证据、质量状态和候选事件簇；进入 drafting 的只有本次 receipt 已选方向/角度等安全元数据，不包含原始标题、作者、URL、feed ID 或 token。普通/local-only runtime 不会回读旧 Topic Radar artifact。`partial` 会保留诊断，`insufficient_evidence` 在启动 workflow 前停止。AI 科技 evidence mode 不走这条 run 内 fresh 路径：`--fresh-topic-research` 返回单独 discovery 提示，热点最多作为 opaque `trend_support`，而可发表 facts 或 test record 必须来自 AI evidence file。

若运营问题只需要小红书领域机会，使用 `xhs-domain-opportunity`：它是 bounded `search_feeds` 证据报告，不是全站或跨平台热榜；没有成功的唯一样本时只返回 `insufficient_evidence` 与恢复建议，不产出排名、匹配或新领域候选。

### 2. Note Teardown Skill

把单帖拆解做成 `xhs_note_teardown` skill：

- 输入：`feed_id + xsec_token`
- 输出：标题钩子、结构模式、互动动因、评论洞察

最适合挂载位置：

- planner 的 reference examples
- reflection 阶段的“为什么这条可能会/不会起量”

### 3. Vertical Router

把垂类判断做成 `xhs_vertical_router`：

- 输入：一个选题草案或场景
- 输出：建议垂类、语气、标签、风险

最适合挂载位置：

- playbook 选择前
- 或 planner 内部作为 topic guardrail

## Suggested Near-Term Integration

当前已经落地的是分层 research 边界：

1. 普通小红书生成只消费本地 pattern snapshot 或静态 skill guidance。
2. 需要最新且不限定方向的跨平台热点时，先运行 `hotspot-discovery`；只有已选 playbook 的发帖前 research 才显式运行一次 public Topic Radar fresh scan，并从其 artifact/诊断复盘。
3. 需要小红书领域比较时，运行 bounded `xhs-domain-opportunity`，只把成功的唯一样本作为证据。
4. `get_feed_detail` / 评论信号等更重的单帖拆解仍应作为未来独立 research artifact，而不是塞回普通 drafting prompt。
5. AI 科技内容在 route 选定后还需要 evidence gate：`news_brief` 收集 3–5 条事实，`hands_on` 收集完整复现记录，`fact_translation` 收集至少两条事实和人群判断。任何 raw research material 均不得替代该 evidence file。

这样保持普通生成可预测，也让实时研究的来源、失败和新颖度都能被独立追溯。

## Current Discovery-First Route Receipt

当前泛热点流程不再把垂类作为 scan 输入：`hotspot-discovery` 先请求 Topic Radar 默认集合，验证
cluster/evidence 关系，再写独立 receipt。receipt 可展示 `operator_headline`、cluster/evidence
traceability、平台范围和 `existing_playbook_fit` / `ambiguous` / `unmapped`；它不保存原始 URL、
author、feed id 或 token 到下游 drafting handoff。跨平台充分证据的未映射 cluster 可标为
`new_domain_candidate` 进入人工复盘，不能自动接入 playbook。

默认 Top-N 是全平台 score 排名；若其中没有适合现有领域的候选，receipt 可额外给出不重复的
`routed_hotspots`，但该补充不会改变 scan、排名或自动进入 drafting。

当 route 选中 `ai_tech_daily_post` 时，receipt 不是内容输入。operator 先选三种 evidence mode
之一并核验事实/测试；最终 AI artifact 仅保留 mode、opaque evidence manifest 与通过的 draft-gate
receipt。离线 evaluator 可审计该 receipt，但不读取或复制 Topic Radar 的 raw provenance。

## Mapping To Current Playbooks

- `fengkuang_daily_post`
  更适合优先接“修复系手作 / 情绪疗愈”“轻养生 / 睡眠恢复”“职场向 AI 解法”。
- `classic_poetry_quote_post`
  更适合优先接“文博 / 非遗 / 地方文化体验”“手作修复”“季节性生活观察”。

这不是说 playbook 只能写这些，而是说明热点研究应先给现有语气找到可持续的垂类落点。
