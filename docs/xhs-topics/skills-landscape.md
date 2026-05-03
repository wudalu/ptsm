---
title: XHS Skills Landscape
status: active
owner: ptsm
last_verified: 2026-04-23
source_of_truth: false
related_paths:
  - docs/xhs-topics/index.md
  - docs/skills.md
  - docs/research/xhs-mcp-spike.md
  - src/ptsm/skills/builtin
  - src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md
  - src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py
  - src/ptsm/application/use_cases/xhs_browser.py
---

# XHS Skills Landscape

## Bottom Line

- 2026-04-22 用 `skill-installer` 的官方脚本复核 OpenAI curated skills 时，没有任何 XiaoHongShu-specific skill。
- 当前仓库内已经有 `xhs_trend_scan` 这个小红书 research builtin skill；`xhs_hashtagging` 和 `xhs_poetry_hashtagging` 仍然负责发帖后处理。
- 所以后续如果要继续做“小红书热点分析”，路线不是继续找一个现成官方 skill，而是在现有 `xhs_trend_scan` 之上补更细的研究能力。

## Generic Skills Worth Reusing

虽然没有小红书专项 skill，但官方 curated 列表里有几类可作为辅助：

- `playwright` / `playwright-interactive`: 适合需要真实浏览器采样、截图或回放时使用。
- `doc`: 适合把研究结果沉淀成结构化文档。
- `notion-research-documentation`: 如果后面要把热点报告同步到 Notion，可作为外围辅助。
- `screenshot`: 适合保留热点页或帖子样例图，不适合做主分析引擎。

这些 skill 只解决“通用研究/采样/记录”，不解决小红书语义结构本身。

## External XHS Ecosystems Worth Watching

### 1. `xpzouying/xiaohongshu-mcp`

链接：<https://github.com/xpzouying/xiaohongshu-mcp>

适合定位：底层数据面和操作面。

当前公开 README 已明确包含：

- 登录状态检查
- 搜索内容 `search_feeds`
- 首页推荐 `list_feeds`
- 帖子详情 `get_feed_detail`
- 发布图文/视频

这条链路和仓库现有结论是对得上的：[`docs/research/xhs-mcp-spike.md`](../research/xhs-mcp-spike.md) 已验证过 `search_feeds`、`get_feed_detail` 相关调用链和真实发布链路。

### 2. `autoclaw-cc/xiaohongshu-mcp-skills`

链接：<https://github.com/autoclaw-cc/xiaohongshu-mcp-skills>

适合定位：在“已经部署好 `xiaohongshu-mcp`”的前提下，把能力封装成可调用 skill。

这个仓库当前公开列出的 skill 包括：

- `xhs-content-ops`
- `xhs-search-analytics`
- `xhs-publish`

这类封装的价值在于：不用从零组织 MCP 请求和脚本，但它依赖外部 skill/runtime 约定，不会天然适配 PTSM 当前的 request-scoped `SkillSelector`。

### 3. `autoclaw-cc/xiaohongshu-skills`

链接：<https://github.com/autoclaw-cc/xiaohongshu-skills>

适合定位：偏真实浏览器工作流的一体化 skill 集。

当前公开列出的 skill 包括：

- `xhs-content-ops`
- `xhs-topic-radar`
- `xhs-comment-analysis`

如果后续要做“先采样热点，再拉评论做拆解”的一体化研究链，这个仓库的能力面最接近我们想要的方向。

### 4. `zhjiang22/openclaw-xhs`

链接：<https://github.com/zhjiang22/openclaw-xhs>

适合定位：做参考实现，而不是直接照抄。

它最有价值的点在于已经把“小红书热点跟踪”拆成了可执行动作：

- `search.sh <关键词>`
- `recommend.sh`
- `post-detail.sh`
- `track-topic.sh <话题> [选项]`

其中 `track-topic.sh` 会自动执行“搜索 -> 拉详情 -> 生成 Markdown 报告”，这正好说明 PTSM 后续也应该把热点分析视为一个独立 research surface，而不是塞进发帖 prompt 里。

## What PTSM Has Built And Should Build Next

基于当前 repo 结构，最值得补的不是“万能 skill”，而是 3 个边界明确的 builtin skills。

### `xhs_trend_scan` `landed`

职责：

- 输入一组关键词或一个垂类
- 调用 `list_feeds` / `search_feeds`
- 输出候选热点、关键词簇、样例帖子和推荐观察角度

当前状态：

- 已在 2026-04-23 落成 builtin skill
- 当前先以轻量“热点判断和切口选择”形式进入现有小红书 playbook
- 还不负责真实抓取执行和 artifact 持久化

### `xhs_note_teardown` `next`

职责：

- 输入 `feed_id + xsec_token`
- 拉帖子详情与高频评论
- 结构化输出标题钩子、内容结构、互动诱因、评论情绪

为什么适合现在做：

- 让热点研究从“看了很多帖”变成“可复用的帖子模式”
- 能直接服务 planner，而不仅是做外部报告

### `xhs_vertical_router` `next`

职责：

- 给一个候选主题或帖子草案
- 判断它更适合哪个垂类
- 返回对应的标签、语气、选题风险和建议 playbook lane

为什么适合现在做：

- 解决“选题发散，账号定位不稳定”的问题
- 能把下面的垂类索引真正接到运行时输入

## Install Or Reference?

当前建议很明确：

- 不要把外部 skill 直接安装进 PTSM 作为主路径。
- 可以把 `xiaohongshu-mcp` 和外部 OpenClaw skill 仓库当作参考实现或短期 operator tool。
- PTSM 主路径应当保留自己的 skill front matter、标签体系、artifact 命名和 planner 输入格式。

否则后面很难把热点研究和当前 harness、docs map、playbook 体系真正接起来。
