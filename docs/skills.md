---
title: PTSM Skills
status: active
owner: ptsm
last_verified: 2026-05-29
source_of_truth: true
related_paths:
  - src/ptsm/skills/contracts.py
  - src/ptsm/skills/registry.py
  - src/ptsm/skills/loader.py
  - src/ptsm/skills/selector.py
  - src/ptsm/skills/surface.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/skills/builtin
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - docs/xhs-topics/index.md
  - docs/research/2026-04-25-skill-routing-and-priority.md
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
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
- `xhs_image_strategy` 服务当前所有 `xiaohongshu` playbook，负责让 drafting backend 输出可选 `final_content.image_plan`：先声明图片 `role`、`text_density`、`max_text_units` 和 `cover_text_strategy`，再在微信聊天记录、iPhone 记事本或笔记卡这类文字原生首屏适合时选择 `local_social_screenshot`，在真实物件、空间、材料、手作过程和生活氛围图更重要时选择 `provider_image`。它只做策略决策，不直接生成图片。
- `xhs_human_voice` 服务当前所有 `xiaohongshu` playbook，是共享 persona 与结构约束：内容要先像真人账号，再像内容账号；标题要由具体场景、物件、关系或一句原话叠加冲突、身份、工具感或反差，避免 `日常`、`实录`、`干货分享` 这类泛标题；正文按 `首屏钩子 -> 领域要素 -> 可保存单元 -> 评论交接` 组织，并按领域控制长度；避免公文、讲义、通稿、AI 总结和 `首先`/`其次`/`综上` 这类格式化标记，也不能把 `可复制疯话`、`可收藏小结`、`可保存单元`、`评论交接` 等内部功能标签直接露给读者。
- `fengkuang_style` / `positive_reframe` / `xhs_hashtagging` 只服务 `fengkuang_daily_post`。这些 skills 现在把“具体职场物件或社交对象 + 可复制疯话/模板 + 评论区接龙 + 非医疗化安全边界”作为生成要求，并可借 2026-05-23 研究里的高雅外壳/狼狈内核、丝瓜汤式沟通和物件发疯机制；`也算`、`至少`、`还能` 只作为轻量缓冲词库，不再是固定结尾。
- `sushi_poetry_style` / `xhs_poetry_hashtagging` 只服务 `sushi_poetry_daily_post`，现在要求“生活瞬间 -> 苏轼词句 -> 可收藏小纸条 -> 评论区共读”，并可借文化力、非遗、手作、节气和年味角落做当代入口，避免讲义腔和百科腔
- `wuxia_commentary_style` / `xhs_wuxia_hashtagging` 只服务 `wuxia_character_post`，现在要求当代切口、人物出处、原文佐证、可截图判断和评论区人物讨论，并可把“老款人格”、主体性和边界感转成角色理解，而不是把人物压成热词标签
- `ai_tech_style` / `ai_tech_hashtagging` 只服务 `ai_tech_daily_post`，现在要求 3 秒核心信息、是什么/为什么重要/普通人影响、收藏清单、评论区使用反馈和非投资建议边界；语气是普通人 AI 生活搭子和工作流实践者，不是发布会通稿
- `daily_english_style` / `daily_english_hashtagging` 只服务 `daily_english_post`，现在要求真实场景例句、音标/词性/翻译、可收藏句型、评论区造句，避免词典式和课堂作业腔
- `psychology_style` / `psychology_safety` / `xhs_psychology_hashtagging` 只服务 `modern_psychology_post`，其中 `psychology_style` 要求标题只写一个具体生活瞬间，不出现心理学术语、机制名或 `不是你...` 破梗；正文按“具体瞬间 -> 场景继续推进 -> 一句轻机制 -> 自然保存动作或可选小工具 -> 角色/阵营/填空式评论入口 -> 专业边界”组织，目标 350-550 字，硬上限 580 字。机制名最多轻量出现一次，且要等场景铺开后再出现；工具卡不是每篇必塞，只有真能截图/复用时才给。选题仍轮换到职场复盘、亲密关系不确定感、关系边界、数字生活、孤独比较、情绪调节和热点心理化重构；亲密关系里“没回消息、想到分手、复合挽留、猫归谁”先写事实 / 脑补 / 我需要什么，不写成客户/同事式回复模板。可使用爱你老己、三明治拒绝法、丝瓜汤式沟通和 AI 陪伴边界，但必须落回具体关系/消息/睡前/边界场景。`psychology_safety` 约束不诊断、不治疗承诺、不提供药物建议，并在严重风险场景引导专业帮助。该领域的图片策略默认低密度：工具型内容优先 `iphone_notes` / `save_tool`，单句重构用 `note_card`，真实聊天对话才用 `wechat_chat`。
- `human_enrichment_style` / `xhs_enrichment_visuals` / `xhs_enrichment_hashtagging` 只服务 `human_enrichment_daily_post`。其中 `human_enrichment_style` 要求“具体角落/物件 -> 原本惯性 -> 一个低成本变量 -> 三步清单 -> 评论区例子”，并能借鉴本地 pattern library 的 `sudden_realization`、`you_should_enrich`、`before_after_contrast`、`saveable_list`、`process_or_tutorial` 结构，以及 2026-05-23 研究里的适我主义、新独居、手作心流和一平米节庆角落，但禁止复写样本标题；`xhs_enrichment_visuals` 编码 3:4 竖版封面、每页文字约束和轮播图形式，`xhs_enrichment_hashtagging` 要求 `#人类丰容计划` 等搜索友好标签。
- `world_cup_style` / `xhs_world_cup_visuals` / `xhs_world_cup_hashtagging` 只服务 `world_cup_daily_post`。其中 `world_cup_style` 要求“比赛语境 -> 普通球迷入口 -> 2 到 3 个看点 -> 看球清单 -> 赛事情绪 -> 评论区问题”，禁止赌球、盘口、下注、预测比分和内部/官方消息伪装；`xhs_world_cup_visuals` 约束 3:4 赛前看点卡、看球清单、赛后复盘和球迷氛围图；`xhs_world_cup_hashtagging` 要求 `#世界杯` 等搜索友好标签。
- `reddit_discussion_scan` / `reddit_curation_style` / `xhs_reddit_curation_hashtagging` 只服务 `reddit_curation_daily_post`。其中 `reddit_discussion_scan` 读取已获批 Reddit app-only OAuth 的公开 hot/top 英文讨论，或在 app 创建受阻时用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 走低频只读 public JSON fallback；它优先筛选 AI 工具焦虑、心理/生活压力和工作流切口。缺少 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`REDDIT_USER_AGENT` 且没有可用 fallback 时会注入缺配置/缺权限上下文。`reddit_curation_style` 要求“外网热点素材 -> 中文读者能懂的现象 -> 共鸣解释 -> 自然可保存的小结 -> 评论区问题”，读者可见标题、封面、正文和标签不暴露 Reddit、subreddit、英文讨论、翻译过程、来源 URL 或“可收藏小结：”这类内部标签；`xhs_reddit_curation_hashtagging` 要求 `#热点观察` 等中文话题标签，并禁止 `#Reddit`。

## Strategy Layer

- `xhs_trend_scan` 是当前第一个小红书 research builtin skill，用来在写作前补一层格式/热点参考。
- `xhs_image_strategy` 是共享的小红书图片策略 skill，用来把正文结构、图片角色和图片生成后端连接起来。它要求草稿可附带 `image_plan`，下游 `run_playbook` 再把该计划解析为本地 renderer 或外部 provider 的实际调用；低密度本地截图会按 `max_text_units` 只渲染少量短句。`wechat_chat` 计划如果提供 `theme`、`chat_title`、`chat_times` 或结构化聊天内容，这些字段会保留到本地 renderer payload 和 artifact 证据中。跨领域图片形式参考见 [`docs/xhs-topics/image-forms-by-domain.md`](xhs-topics/image-forms-by-domain.md)。
- `xhs_human_voice` 是共享的小红书人设策略 skill，用来把温暖、具体、像真人、不格式化、标题有点击动机、正文有首屏钩子和保存/评论动作这类横向要求放进 skill surface，而不是散落在各个 runtime 分支里。它和领域 style skill 叠加使用：前者规定“像人说话”和“如何组织标题/正文”，后者规定“这个账号说什么、怎么说”。
- 它现在优先消费本地 `outputs/artifacts/xhs-pattern-library/current.json`。这些结果不会覆盖静态 `SKILL.md` 文本，而是作为独立 `runtime_skill_contents` 参与标题、正文和封面语气生成。如果本地 snapshot 缺失，普通生成会静默跳过动态 context；显式 fresh research 才会尝试 live MCP scan。
- `xhs_trend_scan` 的 runtime context 不只列热门标题，还会从标题和互动结构推断 `comment_chain`、`save_tool`、`copyable_line`、`identity_conflict` 等内容机制，提示 drafting backend 借鉴“为什么互动”，而不是复写样本标题。
- `xhs_trend_scan` live MCP 调用现在有短超时保护；MCP 未响应、未登录或缺工具时会回退静态 skill，不阻塞 dry-run。
- `topic_research` 是第二个 research builtin skill，通过读取 topic-radar 产出的多平台选题报告，为 planner 提供跨平台的热门话题和选题角度。优先消费当日 artifact JSON 中的 LLM 分析结果；如果本地 XHS pattern library 命中，它会把 format pattern summary 追加到 topic context。artifact 不可用但 pattern snapshot 可用时，`topic_research` 仍会返回 pattern context；两者都不可用时静默跳过。
- 这类内容策略索引仍以 [`docs/xhs-topics/index.md`](xhs-topics/index.md) 和 [`docs/topic-radar.md`](topic-radar.md) 为入口。
- 运行时动态资源当前主要表现为 `runtime_context` 记录，例如 `xhs_trend_scan` 的本地格式 pattern / 站内热点扫描结果，或 `topic_research` 对当日 topic-radar artifact 与本地 format pattern 的摘要注入。
- Reddit 动态资源也以 `runtime_context` 记录：`reddit_discussion_scan` 会写出 `available`、`missing_credentials` 或 `unavailable` 状态，artifact 的 `runtime_skill_details` 会记录这次是否真的有 Reddit 来源上下文。
- 当运行在 deterministic provider 下时，`run_playbook` 只读取本地 XHS pattern snapshot，不触发 live XHS MCP / topic scan；真实 LLM/provider 路径仍按默认 resolver 尝试注入动态上下文。

## OpenClaw Wrapper

- `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` 是外部 OpenClaw 的薄包装说明，不是 PTSM builtin skill，也不参与 `SkillRegistry`。它只负责让 OpenClaw 在心理学小红书内容中先调用 `guide-post`、展示返回的 4 个 `topic_guidance.directions`（名称、`direction_type`、`scene_fit`、趋势信号、病毒式 hook、适合场景、保存工具、评论提示和避坑），用户确认方向后再展示 `topic_guidance.image_recommendation`，最后带 `--caller openclaw --guidance-ack` 调 `run-playbook`。
- `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` 是非心理学 XHS playbook 的通用薄 wrapper。它先按用户意图自动映射到 `fengkuang_daily_post`、`human_enrichment_daily_post`、`sushi_poetry_daily_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post` 或 `reddit_curation_daily_post`；如果意图模糊，只问一个短澄清问题；如果 caller 已经给出 `--playbook-id`，直接用显式 id。随后它调用 `guide-post`，只展示返回的 `topic_guidance.directions` 和每条方向的 `direction_type`、`scene_fit`，方向确认后展示 `topic_guidance.image_recommendation`，再调用 `run-playbook --caller openclaw --publish-mode dry-run`。
- 心理学和跨领域热点、爆点、选题方向仍由 PTSM 的 `guide-post` 输出，OpenClaw skill 不复制这些逻辑，也不得向用户展示内部研究路径、原始研究笔记、URL 或来源文档。`guide-post` 普通路径按 scene/lane 从产品化本地选题库和 PTSM-returned `open_scene` 候选中做确定性动态重排，公开策略为 `dynamic_scene_diversity_rerank`，不再固定 curated 槽位；`open_scene` 由 PTSM 根据当前 scene/lane facets 本地组合，可能返回 1 个或多个。选题确认后的图片建议同样由 PTSM 的 `topic_guidance.image_recommendation` 输出，wrapper 只展示 `recommended_backend`、`local_style`、`provider`、`model`、`role`、`text_density`、`max_text_units`、`reason`、`command_hint` 和 `fallback`，不能自行发明、扩写或替换。OpenClaw/Codex 不能自行发明、扩写或替换方向。不默认触发 live XHS / topic-radar 扫描；如果用户更换场景，wrapper 必须重新调用 `guide-post`，不能复用上一轮方向。只有心理学 wrapper 需要 `--guidance-ack` runtime gate；非心理学 wrapper 只在 wrapper 层强制先选题再 dry-run。

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
