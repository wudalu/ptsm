---
title: XHS Topic Harness Integration
status: active
owner: ptsm
last_verified: 2026-05-03
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/harness-engineering.md
  - docs/observability.md
  - docs/research/xhs-mcp-spike.md
  - src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/agent_runtime/nodes/planner.py
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/infrastructure/artifacts/file_store.py
  - src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py
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

这样做的好处是后面既能被 planner 直接消费，也能被 `logs` / `runs` / `diagnose-*` 一类只读 surface 追溯。

## Skill And Playbook Hook Points

### 1. Trend Scan Skill

`xhs_trend_scan` 已经作为 builtin skill 落地，并且已经挂进 planner。

把热点扫描做成 `xhs_trend_scan` skill：

- 输入：垂类、关键词、采样上限
- 输出：候选主题 brief

当前挂载位置：

- 现有 XiaoHongShu playbook 的 `required_skills`
- planner 在激活 `xhs_trend_scan` 后，会优先尝试调用本地 `xiaohongshu-mcp` 的 `search_feeds`
- 成功时把实时站内趋势上下文写入独立的 `runtime_skill_contents`
- 失败或未登录时回退到静态 skill，不中断 drafting workflow

后续更适合扩展到：

- 或未来单独的 `ptsm xhs-topic-scan` 命令
- 或把 `get_feed_detail` / comment signals 再补进更完整的 research artifact

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

当前已经落地的是“轻量 runtime 版”：

1. 先用 scene 和 playbook 语境推导一组小红书搜索词。
2. 通过本地 `xiaohongshu-mcp` 采样 `search_feeds`，收敛高互动表达和推荐切口。
3. 把结果直接并入 planner 的 runtime skill context，而不是先引入新的 artifact 类型。
4. 等结构稳定后，再决定要不要加新的 CLI/use case 和更细的 research skill。

这样做的取舍是：先把“可用的实时趋势上下文”接进现有 harness，再决定是否值得把 topic scan 产品化成独立研究流。

## Mapping To Current Playbooks

- `fengkuang_daily_post`
  更适合优先接“修复系手作 / 情绪疗愈”“轻养生 / 睡眠恢复”“职场向 AI 解法”。
- `sushi_poetry_daily_post`
  更适合优先接“文博 / 非遗 / 地方文化体验”“手作修复”“季节性生活观察”。

这不是说 playbook 只能写这些，而是说明热点研究应先给现有语气找到可持续的垂类落点。
