---
title: PTSM Skills
status: active
owner: ptsm
last_verified: 2026-08-27
source_of_truth: true
related_paths:
  - src/ptsm/skills/contracts.py
  - src/ptsm/skills/registry.py
  - src/ptsm/skills/loader.py
  - src/ptsm/skills/selector.py
  - src/ptsm/skills/surface.py
  - src/ptsm/skills/runtime_context.py
  - src/topic_radar/cli.py
  - src/topic_radar/analysis/evidence.py
  - src/ptsm/skills/builtin
  - integrations/openclaw/ptsm-xhs-psychology/SKILL.md
  - integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md
  - integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md
  - integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/psychology_learning_series.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
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

- `xhs_trend_scan` 服务当前所有 `xiaohongshu` playbook，负责把本地 XHS pattern library snapshot 的格式/内容机制带进 drafting；普通生成只消费 snapshot 或静态 guidance，不从该 skill 发起实时 MCP 搜索。显式 fresh research 的 live collection 统一交给 public Topic Radar scan，选定后不再由该 skill 触发第二次搜索。
- `xhs_image_strategy` 服务当前所有 `xiaohongshu` playbook，负责让 drafting backend 输出可选 `final_content.image_plan`：先声明图片 `role`、`text_density`、`max_text_units` 和 `cover_text_strategy`，再在微信聊天记录、iPhone 记事本或笔记卡这类文字原生首屏适合时选择 `local_social_screenshot`，在真实物件、空间、材料、手作过程和生活氛围图更重要时选择 `provider_image`。它还允许给本地截图补充 `golden_line`、结构化 `chat_messages`、`chat_times` 和 `status_time`，让图片有真实昵称、时间变化和可保存短句；provider 图则用 `prompt_focus` 描述真实物件/空间/过程。`modern_psychology_post` 是唯一自动多图例外：普通心理学默认把一个主题在同一次 drafting pass 写成**一组** 4–7 张 semantic pages，以 `role=text_carousel`、`carousel_style=psychology_text_card_v1` 和 ordered `slides` 交给本地 renderer；`max_text_units` 是每页密度，不是页数，超过 7/12 张必须由 wrapper 先澄清，不能让 skill 拆分、循环或复用。cover 保持低密度，inner text cards 必须具有不同的可见语义，不能只换封面/标题。skill 现在把每页 `role` 的精确枚举值和必填字段写进 prompt 约束：封面页 `cover_hook`、具体场景页 `concrete_scene`、轻机制页 `light_mechanism`、可保存工具页 `save_tool`、范围边界页 `scope_boundary`、专业边界页 `professional_boundary`、评论入口页 `comment_prompt`，禁止 `scene`/`mechanism`/`boundary` 这类自然语言值；轮播计划还必须填写 `cover_text_strategy`、`reason`、`prompt_focus` 三个必填字段。skill 只做策略/结构决策，不直接生成图片，也不对其他领域启用自动 carousel。
- `xhs_human_voice` 服务当前所有 `xiaohongshu` playbook，是共享 persona 与结构约束。默认 `xhs_compact_native_v1` 要求内容先像真人账号，再像内容账号：标题优先 12-18 字、最多 22 字，以领域适配的具体场景、物件、关系或一句原话进入，避免 `日常`、`实录`、`干货分享` 这类泛标题；不再把同一套冲突/张力关键词强压给英语、诗词、世界杯等不同领域。正文用 2–4 short beats 完成现场/真人锚点、一个领域可用细节和自然的保存或回复入口，保存与评论可以合成一句，不强制四个独立 section。正文仍要少总述、少解释多交付，像朋友安利刚发现或刚试出来的东西；避免公文、讲义、通稿、AI 总结和 `首先`/`其次`/`综上` 这类格式化标记，也不能把 `可复制疯话`、`可收藏小结`、`可保存单元`、`评论交接` 等内部功能标签直接露给读者。
- `fengkuang_style` / `positive_reframe` / `xhs_hashtagging` 只服务 `fengkuang_daily_post`。这些 skills 现在把“具体职场物件或社交对象 + 可复制疯话/模板 + 评论区接龙 + 非医疗化安全边界”作为生成要求，并可借 2026-05-23 研究里的高雅外壳/狼狈内核、丝瓜汤式沟通和物件发疯机制；`也算`、`至少`、`还能` 只作为轻量缓冲词库，不再是固定结尾。
- `classic_poetry_style` / `xhs_classic_poetry_hashtagging` 只服务 `classic_poetry_quote_post`，现在要求“生活瞬间 -> 一句经典古诗词金句 -> 可保存的这一句读法 -> 评论区共读”，并可借李白长风破浪、李清照清醒感、王维山水松弛、杜甫现实感、月亮乡愁、节气四季和明确苏轼定风波场景做当代入口。它要求默认包含 `#古诗词`，避免只回到苏轼/怀民，也避免讲义腔、百科腔和伪造作者篇名。
- `wuxia_commentary_style` / `xhs_wuxia_hashtagging` 只服务 `wuxia_character_post`，现在要求当代切口、人物出处、原文佐证、可截图判断和评论区人物讨论，并可把“老款人格”、主体性和边界感转成角色理解，而不是把人物压成热词标签
- `ai_tech_style` / `ai_tech_hashtagging` 只服务 `ai_tech_daily_post`，且只能在应用层已经绑定 `news_brief`、`hands_on` 或 `fact_translation` evidence contract 后参与 drafting。它们把正文压成短、小红书原生、像人写的结构，但不补造事实：`news_brief` 是 3–5 条有 label 的事实卡；`hands_on` 是产品/版本/日期/任务/输入/观察/局限齐全的单次复现记录；`fact_translation` 是事实加“谁该关注 / 谁可等待”。只有 `hands_on` 可写作者实测或观察；提示词场景也只能写成带 test evidence 的复盘，不能交付万能或通用可复制 prompt。所有模式都不展示来源 URL、作者、原始标题、feed ID 或 opaque reference，避免发布会通稿、泛感受和伪体验。
- `daily_english_style` / `daily_english_hashtagging` 只服务 `daily_english_post`，现在要求真实场景例句、音标/词性/翻译、可收藏句型、评论区造句，避免词典式和课堂作业腔
- `psychology_style` / `psychology_safety` / `xhs_psychology_hashtagging` 只服务 `modern_psychology_post`，其中 `psychology_style` 要求标题只写一个具体生活瞬间，不出现心理学术语、机制名或 `不是你...` 破梗；正文在 200-380 字内以紧凑场景推进、轻量一句机制、自然保存动作或可选小工具、角色/阵营/填空式评论入口和专业边界完成，不把它写成六段科普。机制名最多轻量出现一次，且要等场景铺开后再出现；工具卡不是每篇必塞，只有真能截图/复用时才给。选题仍轮换到职场复盘、亲密关系不确定感、关系边界、数字生活、孤独比较、情绪调节、睡眠恢复/轻养生/办公室恢复和热点心理化重构；睡眠恢复/轻养生只写身体收口、下班信号、睡前降噪和 5 分钟低成本动作，不写医疗养生建议、营养方案、治疗承诺或睡眠改善保证；亲密关系里“没回消息、想到分手、复合挽留、猫归谁、忽冷忽热要不要问清楚”先写事实 / 脑补 / 我需要什么，或事实 / 信号 / 我要不要问清楚，不写成客户/同事式回复模板。`psychology_style` 还固定三类可测试的增长假设方向：忽冷忽热站队给 A/B 阵营和三栏确认，社交电量取消局给取消局三句，下班消息身体警报给下班消息三步；这些方向必须保持专业边界，不能被 wrapper 描述为已证明提高浏览或点赞。可使用爱你老己、三明治拒绝法、丝瓜汤式沟通和 AI 陪伴边界，但必须落回具体关系/消息/睡前/边界场景。`psychology_safety` 约束不诊断、不治疗承诺、不提供药物建议，并在严重风险场景引导专业帮助。普通自动图现在是一题一组的 4–7 张 `psychology_text_card_v1`，语义顺序从 cover/scene 到 mechanism/tool/boundary/comment；不把 body 分段贴图，不在 slides 中放 hashtags、来源、诊断或治疗主张。operator 明确选择普通帖的 legacy local style 时才回到单张 `iphone_notes` / `note_card` / `wechat_chat`。
- `learning_series` 不新增一套泛心理学 skill。它只在 `modern_psychology_post` 已绑定 catalog contract 时收紧现有心理学 style。builtin `after_work_rumination` 与经 `plan-psychology-series` / exact confirmation 生成的 immutable `user_confirmed` catalog 都可使用；operator 想法必须先以 2–6 项安全 outline 提案，审核 proposal 的 `series.lessons`、top-level `publication_plan` 和 `proposal_fingerprint`，proposal 不返回 roadmap，再由 `confirm-psychology-series --confirm` 固定为 version，不能直接塞进 lesson run。固定 series badge、概念、批准解释、微练习、适用范围和专业边界必须原样可核验，且读者可见 JSON 必须逐字段等于 catalog-derived 的 controlled lesson template，不能补造课程、来源、疗效、学习结果或“更有网感”的额外心理学断言。历史 confirmed template v1 按原单卡 immutable 验证；historic builtin curriculum v1 与 historic custom template v2 保留旧版 carousel；current builtin curriculum v2 和新确认 revision 使用 controlled template v3 的 7 张温柔克制、杂志感、emoji-free catalog-derived pages。目录 selection policy 仍是 `catalog_learning_series`：无 lesson 的 custom guide 明确返回 `selection_required`、`series.roadmap`，并额外给 `series.publication_plan`、`series.recommended_next_lesson` 和 `series.production_progress`；后者的 `kind` 是 `operator_content_production`，建议不是自动选择。builtin roadmap 不含这些 custom schedule/progress 字段。选中任一 returned lesson 后才给出该课独立的 title/cover hook 和 catalog-owned image plan，custom selection 必须显式 pin frozen version。wrapper 只展示 PTSM 返回的 `page_count` / `ordered_roles` 结构，不得声称 guide 返回了 `slides` 或 page copy，也不能自己写卡片文案；普通 `open_scene` guidance、runtime research、历史正文 memory、manual image override 都不可替代它。Topic Radar 不能提供 lesson facts/evidence/outline/run input。
- `human_enrichment_style` / `xhs_enrichment_visuals` / `xhs_enrichment_hashtagging` 只服务 `human_enrichment_daily_post`。其中 `human_enrichment_style` 要求“具体角落/物件 -> 原本惯性 -> 一个低成本变量 -> 三步清单 -> 评论区例子”，并能借鉴本地 pattern library 的 `sudden_realization`、`you_should_enrich`、`before_after_contrast`、`saveable_list`、`process_or_tutorial` 结构，以及 2026-05-23 研究里的适我主义、新独居、手作心流和一平米节庆角落，但禁止复写样本标题；`xhs_enrichment_visuals` 编码 3:4 竖版封面、每页文字约束和轮播图形式，`xhs_enrichment_hashtagging` 要求 `#人类丰容计划` 等搜索友好标签。
- `world_cup_style` / `xhs_world_cup_visuals` / `xhs_world_cup_hashtagging` 只服务 `world_cup_daily_post`。其中 `world_cup_style` 要求“比赛语境 -> 普通球迷入口 -> 2 到 3 个看点 -> 看球清单 -> 赛事情绪 -> 评论区问题”，禁止赌球、盘口、下注、预测比分和内部/官方消息伪装；`xhs_world_cup_visuals` 约束 3:4 赛前看点卡、看球清单、赛后复盘和球迷氛围图；`xhs_world_cup_hashtagging` 要求 `#世界杯` 等搜索友好标签。
- `reddit_discussion_scan` / `reddit_curation_style` / `xhs_reddit_curation_hashtagging` 只服务 `reddit_curation_daily_post`。其中 `reddit_discussion_scan` 读取已获批 Reddit app-only OAuth 的公开 hot/top 英文讨论，或在 app 创建受阻时用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 走低频只读 public JSON fallback；它优先筛选 AI 工具焦虑、心理/生活压力和工作流切口。缺少 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET`、`REDDIT_USER_AGENT` 且没有可用 fallback 时会注入缺配置/缺权限上下文。`reddit_curation_style` 要求“外网热点素材 -> 中文读者能懂的现象 -> 共鸣解释 -> 自然可保存的小结 -> 评论区问题”，读者可见标题、封面、正文和标签不暴露 Reddit、subreddit、英文讨论、翻译过程、来源 URL 或“可收藏小结：”这类内部标签；`xhs_reddit_curation_hashtagging` 要求 `#热点观察` 等中文话题标签，并禁止 `#Reddit`。

## Learning-series Storage Boundary

`learning_series` 的 custom catalog 在 PTSM skill/wrapper 之外还有一个显式 trusted setup：首次
`plan-psychology-series` 前，操作员先在所有 writer 停止且独占存储父目录时运行
`provision-psychology-learning-storage`。它只建立/验证私有固定的 `proposals`、`confirmations`、
`catalogs`、`progress` 树；普通 plan/confirm/run 不会把缺失目录重建为可信状态。wrapper 只展示
PTSM 返回的 proposal、frozen catalog 和 guide payload，不能把该命令作为运行期修复动作。异常
artifact/progress fail closed，不在线 cleanup 或复用；progress rename 后失败按 at-least-once 处理，
同一课次可幂等 retry，文件残留只由 trusted offline maintenance 处理。

## Strategy Layer

- `xhs_trend_scan` 是当前第一个小红书 research builtin skill，用来在写作前补一层格式/热点参考。
- `xhs_image_strategy` 是共享的小红书图片策略 skill，用来把正文结构、图片角色和图片生成后端连接起来。它要求草稿可附带 `image_plan`，下游 `run_playbook` 再把该计划解析为本地 renderer 或外部 provider 的实际调用；低密度本地截图会按 `max_text_units` 只渲染少量短句，并优先使用 `golden_line` / `quote_line` 这类短金句。`wechat_chat` 计划如果提供 `theme`、`chat_title`、`chat_times` 或结构化聊天内容，这些字段会保留到本地 renderer payload 和 artifact 证据中；如果没有显式时间或昵称，renderer 会确定性生成变化时间和模拟昵称。心理学 carousel 使用精确 parent/slide contract 与 local-only `psychology_text_card_v1`，其 cover 仍遵守低密度规则，inner pages 也只能使用 bounded headline/body lines。跨领域图片形式参考见 [`docs/xhs-topics/image-forms-by-domain.md`](xhs-topics/image-forms-by-domain.md)。
- `xhs_human_voice` 是共享的小红书人设策略 skill，用来把 `xhs_compact_native_v1` 的温暖、具体、像真人、不格式化、短标题、2–4 short beats、一个可用细节和自然保存/回复动作放进 skill surface，而不是散落在各个 runtime 分支里。它和领域 style skill 叠加使用：前者规定“像人说话”和“怎样短而可用”，后者规定“这个账号说什么、怎么说”。
- 它现在优先消费本地 `outputs/artifacts/xhs-pattern-library/current.json`。这些结果不会覆盖静态 `SKILL.md` 文本，而是作为独立 `runtime_skill_contents` 参与标题、正文和封面语气生成。如果本地 snapshot 缺失，普通生成会静默跳过动态 context 并保留静态 guidance；显式 fresh research 仍由 public Topic Radar scan 负责 live evidence，而非从这个 builder 直接搜索。
- `xhs_trend_scan` 的 runtime context 不只列热门标题，还会从标题和互动结构推断 `comment_chain`、`save_tool`、`copyable_line`、`identity_conflict` 等内容机制，提示 drafting backend 借鉴“为什么互动”，而不是复写样本标题。
- Topic Radar 的显式 fresh scan 保留平台级 timeout、登录和缺工具诊断；MCP 工具发现卡住时也会在 bounded timeout 后退化为对应平台诊断。它失败或 evidence 不足时不会阻塞普通 dry-run，因为普通生成仍回退到本地 snapshot/static skill，而不是把空 live context 当成内容依据。AI 科技 evidence mode 是例外：它不在 `run-playbook --fresh-topic-research` 中消费 scan，而要求先走独立 `hotspot-discovery`，再由 operator 把合格的 opaque `trend_support` 与事实/测试记录分别放入 evidence 文件。
- `topic_research` 是第二个 research builtin skill。普通运行只提供本地 pattern context，既不触发 live scan，也不回读当天/其他运行留下的 Topic Radar artifact。显式 fresh research 则由 `run_playbook` 先调用 public `topic_radar.cli.run_scan()`，仅允许本次 receipt 明示且可读 artifact 中 evidence-backed 的选定角度进入 drafting，缺失 receipt 即不消费；raw source title、author、URL、feed id、token 留在 Topic Radar artifact。fresh selection 已存在时，`topic_research` 不会再启动或叠加第二个 live direction；本地 pattern snapshot 不可用时静默跳过。
- 这类内容策略索引仍以 [`docs/xhs-topics/index.md`](xhs-topics/index.md) 和 [`docs/topic-radar.md`](topic-radar.md) 为入口。
- 运行时动态资源当前主要表现为 `runtime_context` 记录，例如 `xhs_trend_scan` 的本地格式 pattern；显式 fresh 的 `topic_research` 只注入当前选择的安全角度和构造场景，不注入当日或旧的 Topic Radar artifact 摘要。
- Reddit 动态资源也以 `runtime_context` 记录：`reddit_discussion_scan` 会写出 `available`、`missing_credentials` 或 `unavailable` 状态，artifact 的 `runtime_skill_details` 会记录这次是否真的有 Reddit 来源上下文。
- 当运行在 deterministic provider 下时，`run_playbook` 只读取本地 XHS pattern snapshot，不触发 live XHS MCP / topic scan；真实 LLM/provider 路径仍按默认 resolver 尝试注入动态上下文。

## OpenClaw Wrapper

### Psychology carousel count and relay boundary

For an ordinary psychology request over 7 pages/images (for example 12), the
OpenClaw wrapper must use the explicit three-way router rather than the older
two-choice shorthand: `one_carousel` is the supported one-topic 4–7-page set;
`multiple_posts` is supported only when every post/topic is separately confirmed
and run with its own receipt; `independent_assets` is unsupported because 8–12
**independent image assets** that are not posts/carousels are outside this
psychology wrapper/PTSM path. The wrapper must report unsupported and hand the
last case to a separately authorized asset workflow, never silently turn it into
a carousel/multi-run batch or fabricate `carousel_delivery.status=ready`.

For an ordinary ready receipt, `carousel_delivery.status=ready` and
`external_relay_required=true` are local-handoff evidence only. An external
chat/IM relay owns ACK, outcome, and retry state in its own record keyed by the
immutable `set_id` / `manifest_sha256`; PTSM does not infer those states or
claim delivered. The detailed relay-owned acknowledgement contract is part of
the wrapper below, not a PTSM sender capability.

- `integrations/openclaw/ptsm-xhs-psychology/SKILL.md` 是外部 OpenClaw 的薄包装说明，不是 PTSM builtin skill，也不参与 `SkillRegistry`。它先作为发布模式引导器，让用户在 **单篇心理学帖**、**内置学习系列**、**自定义学习系列** 中明确选择；意图不清时等待选择，不能默认创建 custom catalog、生成或发布。“继续下一课”与“看系列进度”先重新查询 roadmap，“改目录”创建新 proposal 和 immutable version。

  对 >7 页/12 张请求，wrapper 必须使用三路 router：`one_carousel` 是支持的一题一组 4–7 页，`multiple_posts` 只有逐帖确认、各自 guide/run/immutable receipt 时才支持，`independent_assets`（8–12 张 **independent image assets**）是 unsupported，必须转交另行授权的素材流程。它不能把 `max_text_units` 当图片数、静默拆分/循环/重复，或把 `independent_assets` 伪装为前两路。

  选择完成后，wrapper 只展示 PTSM 返回的 `topic_guidance.directions`、`format_recommendation` 和 `topic_guidance.image_recommendation`；普通默认显示 `text_carousel` / `psychology_text_card_v1` 的 4–7 页 ordered roles，并仍只传 `--auto-generate-image`。它不自行写 `slides` 或学习卡 copy，不向任何图片可见字段补 emoji，也不把 PTSM-returned psychology sublane/growth direction 改为其他 playbook 或效果结论。拿到 ready receipt 后，wrapper/relay 必须严格按 `carousel_delivery.attachments[].order` 升序逐张发送，不能按 path 或 filename 排序。

  ordinary success 的 `carousel_delivery.status=ready` 是 receipt-verified、按 `page_sha256` / `file_sha256` 核验的本地 relay handoff，不是 delivered。外部 relay 自己拥有 ACK/outcome/retry；若它编排 separately confirmed `multiple_posts`，可选 batch metadata 是 `batch_id`、`target_count`、`slot_index`、`variation_brief` / `variation_fingerprint` 和 `retry_of`，即 **not PTSM response fields**。PTSM 不拥有 chat/IM sender。学习系列仍遵循 proposal/review/exact-confirmation/roadmap/explicit-lesson 的受控流程；增长复盘只走 `xhs-record-metrics` / `xhs-metrics-report` 的真实或 artifact-backed 指标。
- `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` 是非心理学 XHS playbook 的通用薄 wrapper。它先按用户意图自动映射到 `fengkuang_daily_post`、`human_enrichment_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post` 或 `reddit_curation_daily_post`；AI 科技是证据优先例外：先让 caller 选 `news_brief` / `hands_on` / `fact_translation`，说明所需 evidence file，再带该 mode 调 `guide-post`，只展示匹配的 directions。确认方向后必须用 `run-playbook --ai-content-mode <mode> --ai-evidence-file <path> --topic-direction-id <id> --publish-mode dry-run`；wrapper 不把热点 headline 当事实，也不发明实测。其他领域保持原有的 scene/lane 指引：如果意图模糊，只问一个短澄清问题；如果 caller 已经给出 `--playbook-id`，直接用显式 id。随后它调用 `guide-post`，只展示返回的 `topic_guidance.directions`、每条方向的 `direction_type`、`scene_fit` 和 `format_recommendation`，方向确认后展示该方向的 `format_recommendation` 与 `topic_guidance.image_recommendation`。
- `integrations/openclaw/ptsm-xhs-domain-opportunity/SKILL.md` 是小红书领域机会分析的薄 wrapper。它只负责把“哪些领域容易爆 / 是否新增领域 / 现有 playbook 缺口”这类请求转成 `xhs-domain-opportunity` bounded scan，读取生成的 Markdown/JSON brief，并把结果分流为 `existing_playbook_fit`、`sublane_first`、`new_domain_candidate`。它不生成帖子、不发布、不复制 scoring 和 mapping 逻辑，也不展示 raw feed id/token。
- `integrations/openclaw/ptsm-topic-radar-discovery/SKILL.md` 是泛热点入口：用户要求不限定方向、看今天热点或全平台热点时，wrapper 只运行 `hotspot-discovery` 并读取独立 artifact。它先展示全平台 Top-N 的 `existing_playbook_fit`、`ambiguous`、`unmapped` 和可能的 `new_domain_candidate`，再可读不改变排名且不重复的 `routed_hotspots` 补充候选；每条补充行至少引入一个未展示 playbook，`ambiguous` 保留完整候选。要求用户选择后才委派给 `ptsm-xhs-topic-guide` 或 `ptsm-xhs-psychology`。它不生成、不发布，也不把 `operator_headline` 或来源字段传入草稿。
- `ptsm-xhs-domain-opportunity` 只接受明确候选领域/关键词的 bounded XHS 比较。空白或仅分隔符关键词会被 CLI 拒绝；宽泛“找热点”请求必须转向 `ptsm-topic-radar-discovery`，不能由 wrapper 猜一串现有赛道词。
- 心理学和跨领域热点、爆点、选题方向仍由 PTSM 的 `guide-post` 输出，OpenClaw skill 不复制这些逻辑，也不得向用户展示内部研究路径、原始研究笔记、URL 或来源文档。`guide-post` 的普通路径按 scene/lane 从产品化本地选题库和 PTSM-returned `open_scene` 候选中做确定性动态重排；AI 科技不走该普通路径，必须显式 mode 并过滤到同 mode 的 authored directions。选题确认后的格式建议由方向内的 `format_recommendation` 输出，wrapper 只展示 `format_archetype`、`cover_role`、`body_shape`、`visual_evidence_need` 和 `avoid_format`，不能自行发明、扩写或替换；图片建议同样由 PTSM 的 `topic_guidance.image_recommendation` 输出，wrapper 只展示 `recommended_backend`、`local_style`、`provider`、`model`、`format_archetype`、`carousel_style`、`role`、`text_density`、`max_text_units`、`page_count`、`ordered_roles`、`reason`、`command_hint` 和 `fallback`，不能自行发明、扩写或替换。OpenClaw/Codex 不能自行发明、扩写或替换方向。不默认触发 live XHS / topic-radar 扫描；宽泛热点先交给 `hotspot-discovery`，AI evidence mode 再由 operator 提供独立文件。只有心理学 wrapper 需要 `--guidance-ack` runtime gate；AI wrapper 需要证据文件 gate，其他非心理学 wrapper 只在 wrapper 层强制先选题再 dry-run。

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
