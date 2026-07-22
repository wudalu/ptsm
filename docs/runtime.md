---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-07-22
source_of_truth: true
related_paths:
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/agent_runtime/graph
  - src/ptsm/agent_runtime/nodes
  - src/ptsm/agent_runtime/nodes/planner.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/application/models.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/application/use_cases/runs.py
  - src/ptsm/evaluations/contracts_eval.py
  - src/ptsm/infrastructure/llm
  - src/ptsm/infrastructure/llm/factory.py
  - src/ptsm/infrastructure/reddit
  - src/ptsm/domain/xhs_patterns.py
  - src/ptsm/infrastructure/xhs_patterns
  - src/ptsm/infrastructure/images
  - src/ptsm/infrastructure/images/watermark_remover.py
  - src/ptsm/infrastructure/memory/checkpoint.py
  - src/ptsm/infrastructure/memory/store.py
  - src/topic_radar/cli.py
  - src/topic_radar/analysis/evidence.py
---

# Runtime

当前运行时围绕 `plan -> execute -> reflect -> finalize` 组织，并由应用层用例负责把账号、playbook 和发布链路拼起来。

## Main Flow

1. `run_playbook()` 接收 `PlaybookRequest`，解析账号和 playbook。
2. `build_playbook_workflow()` 按所选 playbook/domain 组装 LangGraph 图。
3. graph 依次运行 ingest、planner、memory、executor、reflector、finalize。
4. memory 节点读取当前账号最近同 playbook lessons，并把避免重复的 compact context 注入 `runtime_skill_contents`。
5. reflector 先跑 deterministic reflection rules；如果当前 playbook 的 `evaluation.yaml` 声明 required executor content-quality judge 且运行时配置了 LLM judge backend，还会把 executor draft 交给 content-quality judge。judge 失败或输出无效时会把 `rewrite_hint` 写入 `reflection_feedback` 并回到 executor 重写，直到通过或达到 `max_attempts`。
6. finalize 写入 artifact、执行 lessons memory，并生成 `content_review` 供人工确认。
7. 应用层根据结果决定是否生成发布图片、发布、查状态、开浏览器。

## Current Runtime Facts

- 当前通用运行时入口是 `build_playbook_workflow()`，`build_fengkuang_workflow()` 只是兼容 wrapper。
- 运行结果会落到 artifact，并写入本地 run store。
- `run_playbook()` 默认会在 `.ptsm/agent_runtime/` 下创建持久 execution memory 和 checkpoint。
- PTSM 有两个显式 live research application surface：`hotspot-discovery` 是 playbook 前的开放发现（不启动 workflow/run/publish），`--fresh-topic-research` 是已选 playbook 内的兼容路径。后者调用 public `topic_radar.cli.run_scan()`，不传 `platforms`，因此由 Topic Radar 统一控制当前八平台默认集合、canonical evidence、事件簇、history novelty 与 quality 状态；普通 `run-playbook`、deterministic provider、`guide-post` 和本地 topic pack 路径都不触发该 scan，也不会回读当天或其他运行遗留的 `topic-scan-*.json`。
- fresh scan 为 `insufficient_evidence` 时，`run_playbook()` 在 workflow/发布前返回 operator-safe receipt（quality、platform diagnostics、artifact/report path），不会继续拿静态建议冒充实时热点。`partial` 可以继续到交互选择，但 artifact 会保留失败平台/关键词/LLM 诊断，operator 不得把它解释为完整全平台覆盖。
- fresh 交互只允许选择已经绑定真实 cluster/evidence 的角度。drafting runtime context 只接收安全的 `vertical`、`angle`、`why_discussion_likely` 与构造场景；it never receives raw source titles, authors, URLs, feed IDs, or tokens。canonical evidence title guard 会拒绝等价 title 和较具体 title 的内嵌复写；像 `AI` 这样的短泛词可作为新角度语言。author/URL/feed/token 的规范化值仍无论长短一律阻断，避免异常 LLM/旧 artifact 穿透。builder 只接受本次 fresh `run_scan()` receipt 明示且存在的常规 artifact 文件，缺失或不可读 receipt 会 fail closed；`fresh_topic_research=False` 或 local-only builder 只保留本地 pattern context。`cluster_id`、`event_fingerprint`、`evidence_ids`、quality 和 artifact receipt 留在 `topic_selection` metadata 供审计；终端展示用的 `scan_summary` 和一切原始来源材料都不写入该 metadata。选择完成后 workflow payload 关闭 fresh builder，does not start a second live scan，也不会把竞争性的 `topic_research` context 叠加进同一草稿。
- `guide-post` 是应用层只读选题引导，不启动 workflow、不创建 run、不发布、不调用 live XHS / topic-radar。它用 `ptsm.domain.topic_guidance` 的确定性 selector、open-scene composer、`application/use_cases/topic_guidance_packs.py` 的非心理学本地 topic pack 和心理学专用 brief 数据，为当前九个 playbook 返回 4 个场景相关方向：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。公开方向采用 `selection_policy == "dynamic_scene_diversity_rerank"`：selector 先从 authored curated 候选和多个本地组合的 `direction_type == "open_scene"` 候选中建立候选池，再按场景相关性、未覆盖 facets、`diversity_key`、direction source type 和 open-scene mechanism 做确定性重排。第一条仍优先保留最强 curated 场景锚点，后续方向不再固定 curated 数量；公开元数据包含 `open_direction_ids`、兼容字段 `open_direction_id` 和 `direction_type_counts`。`open_scene` 由当前 scene/lane facets 和可复制句式、保存卡、评论区模式、小任务、看点清单、工具交接等内容机制本地组合。每个方向带 `direction_type`、`scene_fit`、趋势信号、病毒式 hook、适合场景、内容角度、保存工具、评论提示、避坑和 `format_recommendation`。`format_recommendation` 是生成前的图文形态约束，包含 `format_archetype`、`cover_role`、`body_shape`、`visual_evidence_need` 和 `avoid_format`；人类丰容/手作/Colorwalk 倾向 `provider_scene` 或 `carousel` 视觉证据，AI prompt、边界句和睡眠恢复倾向低密度 `note_card` / `iphone_notes` 保存卡。`ai_tech_daily_post` 现在把 prompt / 提示词 / AI 提问场景路由为 `提示词构建 / 好用 prompt` 子线，优先返回 `ai_prompt_context_card`，要求正文先给用户能直接复制的完整 prompt 成品，再用 `任务 / 背景 / 输出格式 / 反例` 拆解它为什么有效；这仍是本地 topic pack，不是 live XHS 采样结果。输出还包含 `topic_guidance.image_recommendation`，用于用户确认选题方向后决定封面方式：消息/回复场景推荐 `local_social_screenshot` + `wechat_chat`，但亲密关系等待消息、分手脑补或猫归谁这类不确定感场景会优先推荐 `iphone_notes` + `save_tool`，承接 `事实 / 脑补 / 我需要什么`；边界句、清单、练习、英语句型和 prompt 成品拆解卡推荐 `iphone_notes`，短判断/诗意重构推荐 `note_card`，空间、物件、材料、人物或场景证据推荐 `provider_image` + `bailian` / `qwen-image-2.0-pro`。输出不包含内部 research 文档路径、原始来源说明、URL 或 provenance。
- `classic_poetry_quote_post` 的 topic pack 把诗词、古诗词金句、经典诗句、李白、李清照、王维、杜甫、月亮乡愁、节气和明确苏轼场景路由到古诗词金句方向。默认标签是 `#古诗词`，苏轼只是可选子方向；泛诗词场景不再强制 `#苏轼`、怀民或苏轼赏析入口。古诗词金句方向的图片建议通常是低密度 `note_card` / `iphone_notes` 保存卡。
- 心理学 `guide-post` 还把睡眠恢复、轻养生、办公室恢复作为既有 `modern_psychology_post` 子线实验处理：相关场景会路由到 `睡眠恢复 / 轻养生` lane，优先返回 `sleep_recovery_shutdown_card` 等低成本保存工具方向，并推荐 `iphone_notes` / `save_tool` 低密度封面。该路径仍不 live-scan；2026-06-02 的 domain opportunity 尝试没有真实样本，只能作为子线假设背景。
- 心理学 `guide-post` 还包含三类本地 authored 增长假设方向：`relationship_mixed_signal_camp_vote` 命中忽冷忽热、暧昧和要不要问清楚场景，输出 `事实 / 信号 / 我要不要问清楚` 与 A/B 阵营评论；`social_battery_cancel_plan_boundary` 命中社交电量、约好的局临时不想去和扫兴愧疚场景，输出取消局三句；`after_hours_message_body_alarm` 命中 18:57 在吗、下班消息和身体被拉回工位场景，输出下班消息三步和 A/B/C 评论入口。这些方向只是 deterministic guidance payload 和后续 metrics loop 的分组维度，不代表已经有真实浏览/点赞 uplift。
- `run_playbook()` 现在支持 caller-aware preflight：当 `PlaybookRequest.caller == "openclaw"` 且目标 playbook 是 `modern_psychology_post` 时，如果没有 `guidance_ack`，会在启动 workflow、创建 run 或执行发布前返回 `topic_guidance_required`。这个硬 runtime gate 只覆盖心理学，因为心理学方向还带专业边界；OpenClaw 确认方向后再带 `--guidance-ack` 重新调用。非心理学 playbook 由 `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` 在 wrapper 层先调用 `guide-post`，但 `run-playbook --caller openclaw` 不会因为缺少非心理学 guide ack 而被 runtime 拦截。确认方向后的 `run-playbook --topic-direction-id` 会解析 guide-post 方向 id，把公开方向 payload 写入 workflow payload、response、run payload 和 artifact 的 `topic_selection.direction`，并在 planner 阶段追加 `# XHS Topic Direction Guidance` runtime context，让 drafting backend 按已确认方向的 hook、正文角度、保存工具、评论入口和 `format_recommendation` 生成。
- workflow 会在 drafting 前读取最近 3 条同账号、同 playbook 的 lessons，形成 `# Recent Account Memory` runtime context，提示 drafting backend 避免重复标题形状、开头、热词和收尾。对 `reddit_curation_daily_post`，memory 注入 prompt 前会隐藏旧帖里的 Reddit/source/翻译痕迹，避免历史样例把已废弃的来源披露写法带回新草稿。
- `run_playbook()` 现在也会在 `.ptsm/agent_runtime/side-effects.json` 下记录成功副作用结果，用于同一 `thread_id` 的安全重放。
- `run_playbook()` 现在可以在真实发布缺图或显式 `--auto-generate-image` 时生成封面图，默认写到 `outputs/generated_images/`；即梦配置优先于百炼配置。若 `final_content.image_plan.backend` 选择 `local_social_screenshot`，或 operator 传入 `--local-image-style`，即使 provider 已配置也会主动走本地 `local_note_card` PNG renderer。本地 renderer 支持默认笔记卡、iPhone Notes-like 和 WeChat chat-like 三类确定性 3:4 样式，且不会在画面上添加 PTSM branding/footer。PTSM 生成图会在源头请求不加 provider 水印：百炼请求发送 `watermark=false` 并合并水印/logo negative prompt，即梦请求发送 `logo_info.add_logo=false`，本地 renderer 记录 `provenance.source == "ptsm_local_renderer"` 和 `watermark_removal == "skip"`；这些都会归一化到 `image_generation.watermark_policy.requested == "no_provider_watermark"`。`final_content.image_plan` 还会携带 `role`、`text_density`、`max_text_units`、`cover_text_strategy`、`golden_line` 和本地截图参数，让运行时知道这张图是封面钩子、保存工具、评论触发还是证据/场景图；微信聊天截图参数如 `theme`、`chat_title`、`show_avatars`、`chat_times` 和结构化/多行聊天内容会原样进入本地图片 prompt，缺省时间会从 scene 明确时间或 payload hash 确定性生成，generic `other` 发言人会补成本地模拟昵称，避免 renderer 退回固定 `9:41` 或浅色单气泡图。
- deterministic / deepseek drafting backend 现在会读取 playbook prompt、playbook persona prompt、静态 scoped skills，以及 planner 注入的 runtime skill contexts，不再只面向发疯文学。runtime contexts 可能包含本地 format pattern、Reddit/research context、最近账号记忆，以及确认选题后的 `# XHS Topic Direction Guidance`。DeepSeek prompt assembly 会额外注入共享 `xhs_compact_native_v1` 标题/正文合同：标题最多 22 字、优先 12-18 字，以领域适配的具体场景、物件、关系或一句原话切入，避免泛标题；不再把一组跨领域 tension cue 当作统一硬门槛。正文用 2–4 个短节拍完成场景/真人锚点、一个领域可用细节和自然的保存或回复入口，而不是四个独立的文章段落。
- DeepSeek prompt assembly 还会注入正文人味硬约束：正文要先有现场锚点和真人视角，用时间、物件、关系、一句原话、材料、路线或动作开场，少用 `本文`、`本篇`、`建议大家`、`从本质上`、`核心逻辑是`、`总体来说` 这类总述/文章腔；正文还要像朋友安利一个刚发现或刚试出来的东西，少解释多交付，给出一个可抄作业式模板、prompt、清单、句式、判断框架或动作。保存和评论/回复可以自然合在同一句，不能露出内部写作标签或靠通用补字段落凑长度。
- `xhs_trend_scan` 的 runtime context 读取本地 `outputs/artifacts/xhs-pattern-library/current.json` 里的 approved/candidate format patterns；普通 `run-playbook` 不实时搜索小红书，snapshot 缺失时回退静态 skill guidance。显式 fresh research 的 live collection 统一由 `run_playbook` 的 public Topic Radar scan 完成，选定方向进入 workflow 后不会让 `xhs_trend_scan` 再回退到 live MCP。`topic_research` 在普通路径可追加同一份本地 pattern summary；fresh selection 已存在时不再追加竞争性 Topic Radar 方向。
- `reddit_discussion_scan` 的 runtime context 服务 `reddit_curation_daily_post`，优先通过已获批的 Reddit app-only OAuth 读取公开英文讨论的 hot/top 列表；当 OAuth app 创建受阻时，可用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 读取 Reddit public `.json` 列表页作为低频只读 fallback。两种路径都会按 AI 工具焦虑、心理/生活压力和工作流相关性筛选适合中文读者的内部素材。缺少可用 Reddit 环境变量时会注入 `missing_credentials` 上下文，提示配置 public JSON fallback 或按 Reddit Responsible Builder Policy 取得 explicit approval 后配置 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT`。读者可见内容不得暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL，来源追踪只保留在 runtime context / artifact。
- deterministic drafting backend 可以通过小型 contextual draft helper 为特定 playbook 提供离线 dry-run 草稿，供 harness 和 e2e 测试在没有真实 LLM 调用时验证领域硬约束；当前覆盖现代心理学、武侠人物评述、古诗词金句、AI 科技资讯、每日英语学习、人类丰容实验、世界杯主题和 Reddit英文讨论转译的基础结构。所有 deterministic XHS 标题都要落在 22 字以内，并满足该领域的具体入口/禁用词规则，而不是机械插入同一组张力 cue。现代心理学 deterministic 分支覆盖职场反刍、亲密关系不确定感、忽冷忽热、社交电量取消局、关系边界、消息压力、数字生活/信息过载、孤独/比较焦虑、三明治拒绝法、睡眠恢复/轻养生/办公室恢复等 lane，避免所有离线样例退化成同一标题形状；其中“他3小时没回消息，我已经想好分手后猫归谁了”这类 scene 会输出 `事实 / 脑补 / 我需要什么`，忽冷忽热 scene 会输出 `事实 / 信号 / 我要不要问清楚`，社交电量取消局 scene 会输出取消局三句，并禁止 `你这边多久能回`、`处理优先级` 等工作式回复口吻或教人失联；睡眠恢复/轻养生 scene 会输出 5 分钟下班信号和身体收口，不给医疗养生建议或睡眠改善承诺。它还会保持标题不暴露心理机制或 `不是你` 句式，把机制名放在场景铺开后轻量出现一次以内，正文控制在 200-380 字，并使用角色/阵营/填空式评论提示。人类丰容 deterministic 分支覆盖桌面/角落、路线/感官、手作/材料流、适我主义/新独居角落等场景；AI 科技 deterministic 分支除模型更新外还覆盖 prompt 构建场景，输出可直接复制的完整 prompt 成品、`任务 / 背景 / 输出格式 / 反例` 拆解、追问边界、读者互晒好用 prompt / 失败输出和改后版本的评论入口，以及隐私/机密提醒；发疯文学 deterministic fallback 也覆盖丝瓜汤式沟通和职场物件发疯样例；世界杯 deterministic 分支覆盖赛前看点、赛后复盘和看球局/球迷氛围三类场景，并禁止输出赌球、盘口、预测比分或伪装内部消息；Reddit英文讨论转译 deterministic 分支要求把外网素材改写成中文热点帖，保留自然可保存的小结和评论区问题，同时禁止读者可见内容泄漏 Reddit/source URL、subreddit、英文讨论、翻译过程或“可收藏小结：”这类内部标签。contextual draft 领域识别只使用明确 playbook/style skill 标记或 scene 语义，不能因为共享 `xhs_image_strategy` catalog 里提到其他领域而误路由。
- 显式注入依赖时，运行时仍兼容 `InMemoryExecutionMemory` 和 `InMemorySaver`。
- 持久 checkpoint 以 `thread_id` 为键保存；复用同一个 `thread_id` 才能跨进程读取同一条执行线程。
- 当前 side-effect ledger 只复用成功 publish 结果，不缓存失败 publish 或只读状态检查。
- planner 现在会把每个激活 skill 的元信息（`activated_skill_details`）和 runtime context 元信息（`runtime_skill_details`）注入 state，供 finalize 写入 artifact 和 harness evals 消费。
- LLM JSON 解析现在对模型把 hashtags 内嵌在 body 中的情况有容错：缺失 `hashtags` key 时从 body 尾部提取并剥离，避免因输出格式微小偏差导致整个 run 失败。
- finalize 现在会把 planner / executor / reflector 的 bounded step evidence 写入 artifact 的 `step_outputs`，包括 selected playbook、prompt refs、attempt count、draft content、reflection decision 和 feedback，供 online evaluation 抽取 phase targets。
- finalize 写入 lessons memory 时会记录 title、image_text、hashtags 和 final_body，供后续 memory 节点做跨帖去重参考。
- deterministic drafting fallback 会消费 recent account memory 做轻量去重；发疯文学和现代心理困境观察都会在近期标题/封面撞车时切换到备用表达，而不是只证明 memory 被读到。
- finalize 现在还会写入 `content_review`，包含生成逻辑、互动/收藏/安全信号、LLM 内容质量门状态和人工确认建议。这个 review 不等于自动发布批准；当前人工调整流程是 operator 基于该说明继续对话修改，而不是进入独立审核队列。
- 对 `human_enrichment_daily_post`，`content_review` 还会写入 `image_form`，记录 3:4 竖版封面、真实创作者封面风格和推荐轮播顺序（封面、原本状态、变量/材料平铺、清单、改变后细节、评论区提问）。当前发布链路仍只自动生成单张封面图，轮播顺序先作为人工 review 和未来图片扩展依据。
- 当本地 pattern library 命中时，`run-playbook` 会在 response 和 artifact 中写入 `format_patterns_used`，包含 pattern ids、hook archetypes、body structures、image sequences 和 snapshot 来源。人类丰容的 `content_review.image_form` 还会带上 `image_pattern_id`、`carousel_pattern_id`、`carousel_brief` 和封面/清单页文字约束。

## Practical Implications

- lessons memory 现在可以跨 CLI 调用保留，不再只活在单进程里。
- lessons memory 不只是写入；后续同账号同 playbook 运行会在 executor 前回读，并以 runtime context 进入 drafting backend。
- graph checkpoint 现在可跨进程保留，用于后续调试、回读和 thread 续跑。
- publish side effects 现在可按 `thread_id` 去重，避免 resume 或重复调用时再次执行成功 publish。
- planner 现在会把 playbook 的 persona prompt 一起送入 executor，让不同领域的账号口吻保留在版本化资产里，而不是硬编码在 runtime。
- `xhs_trend_scan` 这类动态 research skill 输出现在以独立 `runtime_skill_contents` 进入 drafting backend，不再和静态 `SKILL.md` 文本混在同一个字段里。
- 图片生成现在是发布前的一段显式步骤，会把 prompt、模型、生成路径、`watermark_policy`、`provenance` 和 generated image asset ledger 结果写回 artifact，便于后续验收和排障。每次自动生成的图片还会追加一条本地 JSONL 资产记录到 `outputs/artifacts/generated-image-assets/assets.jsonl`，记录图片路径、provider/style/model、playbook/account、artifact、image_plan、provenance source 和 prompt hash；该 ledger 只积累元数据，不复制或提交图片文件。
- 图片生成 prompt 现在也会读取 `runtime_skill_contents` 里的实时切口和场景张力，让封面图和正文共享同一层热点上下文。
- 图片生成 prompt 现在也会读取 artifact `content_review.image_form` 中的图片形式摘要；当人类丰容 playbook 提供轮播式建议时，单张封面生成会保留“原本状态、材料平铺、清单、改变后细节”等视觉提示，并明确 AI 生成图只是氛围参考，不应伪装成真实前后证据。
- 本地 note-card renderer 生成 3:4 竖版 PNG，使用 final content 的标题、封面语和经过筛选的可见短文字绘制，不调用外部图片 API。默认样式是小红书常见笔记卡片；`xhs_image_strategy` 会让 drafting backend 在 `final_content.image_plan` 中选择 `wechat_chat`、`iphone_notes`、`note_card` 或 `provider_image`，并用 `role`、`text_density`、`max_text_units` 控制封面可见文字量。对 `text_density=low` 或 `role=save_tool/cover_hook/comment_prompt/evidence_or_scene` 的本地截图，普通笔记卡和 iPhone Notes 样式只保留 1 到 3 条短句，优先使用 `golden_line` / `quote_line` 这类短金句，避免把整篇正文摘要画成密集小字；`wechat_chat` 会优先保留结构化消息或显式多行聊天记录，绘制为无头部、无底部、无头像但带发言人名的内容区对话截图，并可读取 `theme=dark`、`chat_title` / `conversation_title` 和 `chat_times` 等本地截图参数。缺省 `iphone_notes` 和 `wechat_chat` 时间不再固定为 `9:41`，而是按 scene 明确时间或 payload hash 确定性变化；缺省 generic 对话昵称会按职场/朋友/同事情境生成。现代心理学中三栏、5分钟练习和边界句会优先使用 `iphone_notes` / `save_tool`；只有真实对话、群聊或可复制回复是首屏资产时才走 `wechat_chat`。operator 也可以通过 `--local-image-style iphone_notes` 或 `--local-image-style wechat_chat` 主动覆盖为本地 iPhone 记事本风格或微信聊天记录风格封面。
- 真实发布的去水印现在按 image provenance 分流。PTSM 本地 renderer 生成的图片记录为 `ptsm_local_renderer`，不画水印，也不会进入 OpenCV inpainting；artifact 的 `watermark_removal` 会记录 `status=skipped`、`policy=skipped_for_local_renderer` 和原因。Provider/LLM 生成图与手动 `--publish-image-path` 图片在真实发布时仍会执行去水印后处理，处理结果写入 artifact 的 `watermark_removal` 字段，并且发布器收到的是清理后的图片路径。`WATERMARK_REMOVAL_ENABLED=true` 只控制 dry-run 图片实验是否也预览 provider/manual 图片清理。
- artifact evaluation 不在 LangGraph 节点内运行；`run_playbook()` 完成 artifact/image/publish/post-publish 后再调用 eval use case，因此 rule/contract evaluator 失败不会改变原始 runtime graph 的控制流。内容质量 LLM judge 是生成链路例外：它在 reflector 内作为重写门使用。playbook node contract 支持 `title_max_chars`、`title_must_include_any`、`title_must_not_include_any`、可选领域 title constraints、`body_min_chars` / `body_max_chars`、`body_must_include_scene_signal` / `body_scene_signal_any` / `body_human_anchor_any` 和 `combined_must_not_include_any`，可在离线 eval 阶段要求标题短、有具体入口并拦截泛标题，按领域控制更短正文，让正文带现场锚点和真人视角，并跨 title / image_text / body 拦截模板化、运营腔或 AI 元叙事表达。现代心理学用同一通用 contract 阻断标题里的机制词和 `不是你` 句式，把正文上限压到 380 字，并要求认领式评论触发。
- 当前仍没有远端 state backend；cross-thread lookup 只限本地 execution memory 中最近同账号同 playbook lessons 的轻量回读。

## Operator Entry Points

- 用例入口: [`src/ptsm/application/use_cases/run_playbook.py`](../src/ptsm/application/use_cases/run_playbook.py)
- 运行时入口: [`src/ptsm/agent_runtime/runtime.py`](../src/ptsm/agent_runtime/runtime.py)
- checkpoint 适配: [`src/ptsm/infrastructure/memory/checkpoint.py`](../src/ptsm/infrastructure/memory/checkpoint.py)
- 内存适配: [`src/ptsm/infrastructure/memory/store.py`](../src/ptsm/infrastructure/memory/store.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 发布后检查: [`src/ptsm/application/use_cases/xhs_publish_status.py`](../src/ptsm/application/use_cases/xhs_publish_status.py)

## Discovery Before Runtime

`hotspot-discovery` 不属于 LangGraph runtime，也不修改现有 `run-playbook --fresh-topic-research`
的既定 playbook 路径。它先进行开放扫描、验证 cluster/evidence 关系，再把候选映射为已有
playbook、多个候选或未映射；用户完成选择后才调用现有选题/生成入口。

route receipt 的 Top-N 主列表保持全平台 score 顺序；可选的 `routed_hotspots` 补充区只呈现同一次
scan 中每行至少引入一个未展示 playbook 的既有领域候选；`ambiguous` 保留完整候选集，不参与 scan 或 runtime 的 playbook 选择。

routing artifact 中的 `operator_headline` 只用于操作者阅读。它 does not enter drafting：
下游只可使用 profile-derived `generation_seed`、选定 playbook 和 opaque
`cluster_id` / `event_fingerprint` / `evidence_ids` traceability。原始来源字段和 headline
均不能被用作 scene、runtime context 或 draft text。
