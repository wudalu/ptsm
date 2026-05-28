---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-05-29
source_of_truth: true
related_paths:
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/agent_runtime/graph
  - src/ptsm/agent_runtime/nodes
  - src/ptsm/agent_runtime/nodes/planner.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/application/models.py
  - src/ptsm/domain/topic_guidance.py
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
- `guide-post` 是应用层只读选题引导，不启动 workflow、不创建 run、不发布、不调用 live XHS / topic-radar。它用 `ptsm.domain.topic_guidance` 的确定性 selector、open-scene composer、`application/use_cases/topic_guidance_packs.py` 的非心理学本地 topic pack 和心理学专用 brief 数据，为当前九个 playbook 返回 4 个场景相关方向：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`sushi_poetry_daily_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。公开方向采用 `selection_policy == "dynamic_scene_diversity_rerank"`：selector 先从 authored curated 候选和多个本地组合的 `direction_type == "open_scene"` 候选中建立候选池，再按场景相关性、未覆盖 facets、`diversity_key`、direction source type 和 open-scene mechanism 做确定性重排。第一条仍优先保留最强 curated 场景锚点，后续方向不再固定 curated 数量；公开元数据包含 `open_direction_ids`、兼容字段 `open_direction_id` 和 `direction_type_counts`。`open_scene` 由当前 scene/lane facets 和可复制句式、保存卡、评论区模式、小任务、看点清单、工具交接等内容机制本地组合。每个方向带 `direction_type`、`scene_fit`、趋势信号、病毒式 hook、适合场景、内容角度、保存工具、评论提示和避坑。输出还包含 `topic_guidance.image_recommendation`，用于用户确认选题方向后决定封面方式：消息/回复场景推荐 `local_social_screenshot` + `wechat_chat`，但亲密关系等待消息、分手脑补或猫归谁这类不确定感场景会优先推荐 `iphone_notes` + `save_tool`，承接 `事实 / 脑补 / 我需要什么`；边界句、清单、练习和英语句型推荐 `iphone_notes`，短判断/诗意重构推荐 `note_card`，空间、物件、材料、人物或场景证据推荐 `provider_image` + `bailian` / `qwen-image-2.0-pro`。输出不包含内部 research 文档路径、原始来源说明、URL 或 provenance。
- `run_playbook()` 现在支持 caller-aware preflight：当 `PlaybookRequest.caller == "openclaw"` 且目标 playbook 是 `modern_psychology_post` 时，如果没有 `guidance_ack`，会在启动 workflow、创建 run 或执行发布前返回 `topic_guidance_required`。这个硬 runtime gate 只覆盖心理学，因为心理学方向还带专业边界；OpenClaw 确认方向后再带 `--guidance-ack` 重新调用。非心理学 playbook 由 `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` 在 wrapper 层先调用 `guide-post`，但 `run-playbook --caller openclaw` 不会因为缺少非心理学 guide ack 而被 runtime 拦截。
- workflow 会在 drafting 前读取最近 3 条同账号、同 playbook 的 lessons，形成 `# Recent Account Memory` runtime context，提示 drafting backend 避免重复标题形状、开头、热词和收尾。对 `reddit_curation_daily_post`，memory 注入 prompt 前会隐藏旧帖里的 Reddit/source/翻译痕迹，避免历史样例把已废弃的来源披露写法带回新草稿。
- `run_playbook()` 现在也会在 `.ptsm/agent_runtime/side-effects.json` 下记录成功副作用结果，用于同一 `thread_id` 的安全重放。
- `run_playbook()` 现在可以在真实发布缺图或显式 `--auto-generate-image` 时生成封面图，默认写到 `outputs/generated_images/`；即梦配置优先于百炼配置。若 `final_content.image_plan.backend` 选择 `local_social_screenshot`，或 operator 传入 `--local-image-style`，即使 provider 已配置也会主动走本地 `local_note_card` PNG renderer。本地 renderer 支持默认笔记卡、iPhone Notes-like 和 WeChat chat-like 三类确定性 3:4 样式，且不会在画面上添加 PTSM branding/footer。PTSM 生成图会在源头请求不加 provider 水印：百炼请求发送 `watermark=false` 并合并水印/logo negative prompt，即梦请求发送 `logo_info.add_logo=false`，本地 renderer 记录为本地生成；这些都会归一化到 `image_generation.watermark_policy.requested == "no_provider_watermark"`。`final_content.image_plan` 还会携带 `role`、`text_density`、`max_text_units`、`cover_text_strategy` 和本地截图参数，让运行时知道这张图是封面钩子、保存工具、评论触发还是证据/场景图；微信聊天截图参数如 `theme`、`chat_title`、`show_avatars`、`chat_times` 和结构化/多行聊天内容会原样进入本地图片 prompt，避免 renderer 退回默认浅色单气泡图。
- deterministic / deepseek drafting backend 现在会读取 playbook prompt、playbook persona prompt、静态 scoped skills，以及 planner 注入的 runtime skill contexts，不再只面向发疯文学。DeepSeek prompt assembly 会额外注入共享 XHS 标题/正文硬约束：标题要有具体点击钩子且避免泛标题，正文按 `首屏钩子 -> 领域要素 -> 可保存单元 -> 评论交接` 组织，并按激活的领域 skill 推断正文长度带。
- `xhs_trend_scan` 的 runtime context 现在优先读取本地 `outputs/artifacts/xhs-pattern-library/current.json` 里的 approved/candidate format patterns；普通 `run-playbook` 不默认实时搜索小红书。只有在显式 fresh research 路径且本地 pattern snapshot 不可用时，才会回退到 live MCP trend scan。`topic_research` 也会在保留 topic-radar 选题上下文的同时追加同一份本地 pattern summary；当 topic-radar artifact 缺失时，它仍可只返回 pattern context。
- `reddit_discussion_scan` 的 runtime context 服务 `reddit_curation_daily_post`，优先通过已获批的 Reddit app-only OAuth 读取公开英文讨论的 hot/top 列表；当 OAuth app 创建受阻时，可用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 读取 Reddit public `.json` 列表页作为低频只读 fallback。两种路径都会按 AI 工具焦虑、心理/生活压力和工作流相关性筛选适合中文读者的内部素材。缺少可用 Reddit 环境变量时会注入 `missing_credentials` 上下文，提示配置 public JSON fallback 或按 Reddit Responsible Builder Policy 取得 explicit approval 后配置 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT`。读者可见内容不得暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL，来源追踪只保留在 runtime context / artifact。
- deterministic drafting backend 可以通过小型 contextual draft helper 为特定 playbook 提供离线 dry-run 草稿，供 harness 和 e2e 测试在没有真实 LLM 调用时验证领域硬约束；当前覆盖现代心理学、武侠人物评述、苏轼诗词赏析、AI 科技资讯、每日英语学习、人类丰容实验、世界杯主题和 Reddit英文讨论转译的基础结构。现代心理学 deterministic 分支覆盖职场反刍、亲密关系不确定感、关系边界、消息压力、数字生活/信息过载、孤独/比较焦虑、三明治拒绝法等 lane，避免所有离线样例退化成同一标题形状；其中“他3小时没回消息，我已经想好分手后猫归谁了”这类 scene 会输出 `事实 / 脑补 / 我需要什么`，并禁止 `你这边多久能回`、`处理优先级` 等工作式回复口吻。它还会保持标题不暴露心理机制或 `不是你` 句式，把机制名放在场景铺开后轻量出现一次以内，正文控制在 350-580 字，并使用角色/阵营/填空式评论提示。人类丰容 deterministic 分支覆盖桌面/角落、路线/感官、手作/材料流、适我主义/新独居角落等场景；发疯文学 deterministic fallback 也覆盖丝瓜汤式沟通和职场物件发疯样例；世界杯 deterministic 分支覆盖赛前看点、赛后复盘和看球局/球迷氛围三类场景，并禁止输出赌球、盘口、预测比分或伪装内部消息；Reddit英文讨论转译 deterministic 分支要求把外网素材改写成中文热点帖，保留自然可保存的小结和评论区问题，同时禁止读者可见内容泄漏 Reddit/source URL、subreddit、英文讨论、翻译过程或“可收藏小结：”这类内部标签。contextual draft 领域识别只使用明确 playbook/style skill 标记或 scene 语义，不能因为共享 `xhs_image_strategy` catalog 里提到其他领域而误路由。
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
- 图片生成现在是发布前的一段显式步骤，会把 prompt、模型、生成路径和 `watermark_policy` 写回 artifact，便于后续验收和排障。
- 图片生成 prompt 现在也会读取 `runtime_skill_contents` 里的实时切口和场景张力，让封面图和正文共享同一层热点上下文。
- 图片生成 prompt 现在也会读取 artifact `content_review.image_form` 中的图片形式摘要；当人类丰容 playbook 提供轮播式建议时，单张封面生成会保留“原本状态、材料平铺、清单、改变后细节”等视觉提示，并明确 AI 生成图只是氛围参考，不应伪装成真实前后证据。
- 本地 note-card renderer 生成 3:4 竖版 PNG，使用 final content 的标题、封面语和经过筛选的可见短文字绘制，不调用外部图片 API。默认样式是小红书常见笔记卡片；`xhs_image_strategy` 会让 drafting backend 在 `final_content.image_plan` 中选择 `wechat_chat`、`iphone_notes`、`note_card` 或 `provider_image`，并用 `role`、`text_density`、`max_text_units` 控制封面可见文字量。对 `text_density=low` 或 `role=save_tool/cover_hook/comment_prompt/evidence_or_scene` 的本地截图，普通笔记卡和 iPhone Notes 样式只保留 1 到 3 条短句，避免把整篇正文摘要画成密集小字；`wechat_chat` 会优先保留结构化消息或显式多行聊天记录，绘制为无头部、无底部、无头像但带发言人名的内容区对话截图，并可读取 `theme=dark`、`chat_title` / `conversation_title` 和 `chat_times` 等本地截图参数。现代心理学中三栏、5分钟练习和边界句会优先使用 `iphone_notes` / `save_tool`；只有真实对话、群聊或可复制回复是首屏资产时才走 `wechat_chat`。operator 也可以通过 `--local-image-style iphone_notes` 或 `--local-image-style wechat_chat` 主动覆盖为本地 iPhone 记事本风格或微信聊天记录风格封面。
- 真实发布只要最终有图片路径，仍会强制执行去水印后处理，使用 OpenCV inpainting 检测并移除底角残留水印，处理结果写入 artifact 的 `watermark_removal` 字段。`image_generation.watermark_policy` 证明 PTSM 生成图已请求源头不加 provider 水印；`watermark_removal` 是发布前对所有最终图片的防御性清理。`WATERMARK_REMOVAL_ENABLED=true` 只控制 dry-run 图片实验是否也预览这一步。
- artifact evaluation 不在 LangGraph 节点内运行；`run_playbook()` 完成 artifact/image/publish/post-publish 后再调用 eval use case，因此 rule/contract evaluator 失败不会改变原始 runtime graph 的控制流。内容质量 LLM judge 是生成链路例外：它在 reflector 内作为重写门使用。playbook node contract 现在支持 `title_must_include_any`、`title_must_not_include_any`、`body_min_chars` / `body_max_chars` 和 `combined_must_not_include_any`，可在离线 eval 阶段要求标题带具体钩子、拦截泛标题、按领域控制正文长度，并跨 title / image_text / body 拦截模板化、运营腔或 AI 元叙事表达。现代心理学用同一通用 contract 阻断标题里的机制词和 `不是你` 句式，把正文上限压到 580 字，并要求认领式评论触发。
- 当前仍没有远端 state backend；cross-thread lookup 只限本地 execution memory 中最近同账号同 playbook lessons 的轻量回读。

## Operator Entry Points

- 用例入口: [`src/ptsm/application/use_cases/run_playbook.py`](../src/ptsm/application/use_cases/run_playbook.py)
- 运行时入口: [`src/ptsm/agent_runtime/runtime.py`](../src/ptsm/agent_runtime/runtime.py)
- checkpoint 适配: [`src/ptsm/infrastructure/memory/checkpoint.py`](../src/ptsm/infrastructure/memory/checkpoint.py)
- 内存适配: [`src/ptsm/infrastructure/memory/store.py`](../src/ptsm/infrastructure/memory/store.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 发布后检查: [`src/ptsm/application/use_cases/xhs_publish_status.py`](../src/ptsm/application/use_cases/xhs_publish_status.py)
