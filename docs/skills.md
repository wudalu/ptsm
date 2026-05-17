---
title: PTSM Skills
status: active
owner: ptsm
last_verified: 2026-05-17
source_of_truth: true
related_paths:
  - src/ptsm/skills/contracts.py
  - src/ptsm/skills/registry.py
  - src/ptsm/skills/loader.py
  - src/ptsm/skills/selector.py
  - src/ptsm/skills/surface.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/skills/builtin
  - docs/xhs-topics/index.md
  - docs/research/2026-04-25-skill-routing-and-priority.md
---

# Skills

Skill 层负责让运行时按请求范围暴露合适的 builtin skills，而不是把所有技能一股脑塞进上下文。

## Current Model

- `SkillSpec` 描述技能元数据，包括 domain/platform/playbook tags。
- `SkillRegistry` 发现本地 builtin skills。
- `SkillSelector` 根据请求上下文筛选候选技能。
- `RequestSkillSurface` 负责在单次执行内列出和激活可用技能。
- `SkillLoader` 负责真正读取 skill 内容。
- planner 现在会把激活的静态 skill 额外记录为 `activated_skill_details`，并把动态 research / runtime context 记录为 `runtime_skill_details`，让 artifact 和 run summary 都能回答“这次到底用了哪些 skill 与动态资源”。

## Builtin Skills

当前 builtin skills 位于 [`src/ptsm/skills/builtin/`](../src/ptsm/skills/builtin/)。

常见用途：

- 风格约束
- 内容后处理
- 平台话题或格式化辅助

当前真实例子：

- `xhs_trend_scan` 服务当前所有 `xiaohongshu` playbook，负责热点扫描、选题切口判断和内容机制提取；普通生成优先消费本地 XHS pattern library snapshot，只有显式 fresh research 且本地 snapshot 不可用时才回退到实时 MCP 趋势上下文
- `fengkuang_style` / `positive_reframe` / `xhs_hashtagging` 只服务 `fengkuang_daily_post`。这些 skills 现在把“具体职场物件或社交对象 + 可复制疯话/模板 + 评论区接龙 + 非医疗化安全边界”作为生成要求；`也算`、`至少`、`还能` 只作为轻量缓冲词库，不再是固定结尾。
- `sushi_poetry_style` / `xhs_poetry_hashtagging` 只服务 `sushi_poetry_daily_post`，现在要求“生活瞬间 -> 苏轼词句 -> 可收藏小纸条 -> 评论区共读”，避免讲义腔和百科腔
- `wuxia_commentary_style` / `xhs_wuxia_hashtagging` 只服务 `wuxia_character_post`，现在要求当代切口、人物出处、原文佐证、可截图判断和评论区人物讨论
- `ai_tech_style` / `ai_tech_hashtagging` 只服务 `ai_tech_daily_post`，现在要求 3 秒核心信息、是什么/为什么重要/普通人影响、收藏清单、评论区使用反馈和非投资建议边界
- `daily_english_style` / `daily_english_hashtagging` 只服务 `daily_english_post`，现在要求真实场景例句、音标/词性/翻译、可收藏句型、评论区造句，避免词典式和课堂作业腔
- `psychology_style` / `psychology_safety` / `xhs_psychology_hashtagging` 只服务 `modern_psychology_post`，其中 `psychology_style` 要求“第一人称微场景 -> 心理机制 -> 非诊断化重构 -> 可保存小工具 -> 例子型评论 -> 专业边界”，`psychology_safety` 约束不诊断、不治疗承诺、不提供药物建议，并在严重风险场景引导专业帮助
- `human_enrichment_style` / `xhs_enrichment_visuals` / `xhs_enrichment_hashtagging` 只服务 `human_enrichment_daily_post`。其中 `human_enrichment_style` 要求“具体角落/物件 -> 原本惯性 -> 一个低成本变量 -> 三步清单 -> 评论区例子”，并能借鉴本地 pattern library 的 `sudden_realization`、`you_should_enrich`、`before_after_contrast`、`saveable_list`、`process_or_tutorial` 结构，但禁止复写样本标题；`xhs_enrichment_visuals` 编码 3:4 竖版封面、每页文字约束和轮播图形式，`xhs_enrichment_hashtagging` 要求 `#人类丰容计划` 等搜索友好标签。

## Strategy Layer

- `xhs_trend_scan` 是当前第一个小红书 research builtin skill，用来在写作前补一层格式/热点参考。
- 它现在优先消费本地 `outputs/artifacts/xhs-pattern-library/current.json`。这些结果不会覆盖静态 `SKILL.md` 文本，而是作为独立 `runtime_skill_contents` 参与标题、正文和封面语气生成。如果本地 snapshot 缺失，普通生成会静默跳过动态 context；显式 fresh research 才会尝试 live MCP scan。
- `xhs_trend_scan` 的 runtime context 不只列热门标题，还会从标题和互动结构推断 `comment_chain`、`save_tool`、`copyable_line`、`identity_conflict` 等内容机制，提示 drafting backend 借鉴“为什么互动”，而不是复写样本标题。
- `xhs_trend_scan` live MCP 调用现在有短超时保护；MCP 未响应、未登录或缺工具时会回退静态 skill，不阻塞 dry-run。
- `topic_research` 是第二个 research builtin skill，通过读取 topic-radar 产出的多平台选题报告，为 planner 提供跨平台的热门话题和选题角度。优先消费当日 artifact JSON 中的 LLM 分析结果，artifact 不可用时静默跳过。
- 这类内容策略索引仍以 [`docs/xhs-topics/index.md`](xhs-topics/index.md) 和 [`docs/topic-radar.md`](topic-radar.md) 为入口。
- 运行时动态资源当前主要表现为 `runtime_context` 记录，例如 `xhs_trend_scan` 的站内热点扫描结果，或 `topic_research` 对当日 topic-radar artifact 的摘要注入。
- 当运行在 deterministic provider 下时，`run_playbook` 会传入空的 runtime skill resolver，避免本地 harness 和离线 dry-run 因 live XHS MCP / topic scan 状态而阻塞；真实 LLM/provider 路径仍按默认 resolver 尝试注入动态上下文。

## Routing Design

- 关于 skill metadata、orchestrator 职责、单一职责、顺序关系和 eval 的结构化结论，见 [`docs/research/2026-04-25-skill-routing-and-priority.md`](research/2026-04-25-skill-routing-and-priority.md)。
- 当前和未来的 skill 扩展都应该优先遵守那份文档里的分层原则：`metadata` 做 discovery，`orchestrator` 做 candidate set 和 conflict resolution，运行时只在小 skill surface 上做 activation。

## What This Does Not Mean Yet

- 还没有用户自定义 skill 市场。
- 还没有跨会话持久化的 skill activation 历史。
- 还没有复杂 capability negotiation。
- 还没有 skill 级别的内容质量 judge；当前 harness 只先聚合 skill 使用率、完成率和 runtime context 命中情况。

## Related Files

- Registry: [`src/ptsm/skills/registry.py`](../src/ptsm/skills/registry.py)
- Selector: [`src/ptsm/skills/selector.py`](../src/ptsm/skills/selector.py)
- Surface: [`src/ptsm/skills/surface.py`](../src/ptsm/skills/surface.py)
