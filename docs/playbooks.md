---
title: PTSM Playbooks
status: active
owner: ptsm
last_verified: 2026-07-23
source_of_truth: true
related_paths:
  - src/ptsm/playbooks/registry.py
  - src/ptsm/playbooks/loader.py
  - src/ptsm/playbooks/definitions
  - src/ptsm/evaluations/playbook_contracts.py
  - src/ptsm/evaluations/contracts_eval.py
  - src/ptsm/accounts/registry.py
  - src/ptsm/accounts/definitions
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/infrastructure/llm/factory.py
  - src/ptsm/infrastructure/llm/contextual_drafts.py
  - src/ptsm/evaluations/llm_judge.py
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
---

# Playbooks

Playbook 是 PTSM 的业务编排单元。它把领域、平台、技能需求和反思规则绑定成一个可加载定义。

## Current State

- 当前仓库里有九个真实 playbook：`fengkuang_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`modern_psychology_post`、`human_enrichment_daily_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。
- 九个小红书 playbook 都加载共享 `xhs_image_strategy` 和 `xhs_human_voice`。前者让正文生成阶段可以同时给出图片后端和样式计划；后者以 `xhs_compact_native_v1` 把温暖、有调性、像真人、不格式化、少运营腔、短节拍和自然互动入口放进所有 XHS 内容。两个共享 skill 都与各领域 style / hashtag skill 并列，不替代领域内容约束。
- `classic_poetry_quote_post` 专门输出古诗词金句短帖，用一句经典诗词接住当代生活瞬间。`guide-post` 会按唐诗金句/低谷打气、宋词清醒/情绪安放、月亮乡愁、山水松弛、杜甫现实感、节气四季和苏轼定风波等方向动态返回 4 个场景相关方向；泛诗词 scene 默认走古诗词金句宽入口，明确提到苏轼时才把苏轼作为子方向。正文必须围绕一句可核验的古诗词金句展开，作者或篇名不确定时不伪造，默认标签要求 `#古诗词`。默认绑定 `acct-classic-poetry-local`。
- `wuxia_character_post` 是九个 playbook 中保留长文空间的武侠人物评述，用当代流行文化视角解读金庸古龙人物；其 compact 合同例外仍为 450-750 字，以保证人物出处、原文佐证和论证连贯。`guide-post` 会按老款人格、当代职场、主体性/边界、人情债等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。默认绑定 `acct-wuxia-local`。
- `ai_tech_daily_post` 专门输出证据可追溯的 AI/科技短帖，不接受场景文字、泛泛感受或万能 prompt 作为事实来源。每次 `run-playbook` 必须带 `--ai-content-mode` 与 `--ai-evidence-file`，只允许三种结构：`news_brief` 为 3–5 个独立核验快讯；`hands_on` 为一个产品/版本、日期、任务、输入、观察输出和局限齐全的可复现实测；`fact_translation` 为一个主题、至少两条核验事实及“谁该关注 / 谁可等待”。`guide-post` 也先选 mode，只返回相同 `content_mode` 的静态方向；`topic_direction_id` 与 mode 不匹配会在创建 run 前被拒绝。提示词/AI 提问方向只属于 `hands_on`，应写成一次测试记录与局限，不交付通用可复制模板。默认绑定 `acct-ai-tech-local`。
- `daily_english_post` 是每日英语单词学习内容，陪伴式教育风格。`guide-post` 会按职场表达、情绪词、每日一词、评论区造句等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。默认绑定 `acct-daily-english-local`。
- `modern_psychology_post` 专门输出现代心理困境观察内容，现在优先写小红书生活号式的具体瞬间：标题只保留一个让人停住的关系、消息、睡前或职场场景，不在标题里提前抛出心理学术语或 `不是你...` 破梗。正文按“具体场景继续推进 -> 一句轻机制 -> 自然保存动作或可选小工具 -> 角色/阵营/填空式评论入口 -> 专业帮助边界”组织，工具不是每篇都硬塞，但安全边界始终保留；`psychology_safety` 约束诊断、治疗承诺、药物建议和危机处理边界。它现在要求按选题 lane 轮换：职场复盘/低控制感、亲密关系/不确定感、关系边界/消息压力、数字生活/信息过载、孤独/比较焦虑、情绪调节/恢复练习、睡眠恢复/轻养生/办公室恢复、热点心理化重构，避免所有候选都退化成“下班复盘一句话”。睡眠恢复/轻养生只作为既有心理学子线实验，落到下班信号、身体收口、睡前降噪和 5 分钟低成本动作，不写医疗养生建议、营养方案或治疗承诺；2026-06-02 live XHS opportunity scan 未拿到真实样本，因此这不是新领域结论。睡眠恢复方向的格式建议保持 `note_card` / `save_tool` / low visual evidence，用 5 分钟恢复卡承接，不写成疗效 before/after。亲密关系里“没回消息、想到分手、复合挽留、猫归谁、忽冷忽热要不要问清楚”这类 scene 会优先走 `事实 / 脑补 / 我需要什么` 或 `事实 / 信号 / 我要不要问清楚`，不再落成职场式消息边界回复。`guide-post` 还包含三类增长假设方向：`relationship_mixed_signal_camp_vote` 用 A/B 阵营承接忽冷忽热，`social_battery_cancel_plan_boundary` 用取消局三句承接社交电量，`after_hours_message_body_alarm` 用下班消息三步承接身体被拉回工位；这些是待真实 metrics 验证的选题假设，不是已证明的浏览/点赞提升结论。`guide-post` 会把当前适合该 playbook 的热点机制和当前 scene/lane 现场组合为 4 个动态重排方向；每个方向会说明 `direction_type`、`scene_fit`、趋势信号、病毒式内容 hook 和 `format_recommendation`。OpenClaw caller 必须先展示这些方向，确认后再生成。默认绑定 `acct-psychology-local`。
- `modern_psychology_post` 另有严格的 `learning_series` 子模式，首期目录是“下班后脑子停不下来”（`after_work_rumination`）的六个固定课次。它不接受自由 scene、热点标题或 operator-written 概念来生成课程：先由 `guide-post` 返回 `selection_required` 的 `catalog_learning_series` roadmap，用户选中返回的 `learning_series_lesson` 后，才取得该课的 distinct title/cover hook 和 `run-playbook` command。只有本 playbook 的 `run-playbook` 才接受准确且显式 pin 的 series、lesson、curriculum version 和 matching direction id。该模式把正文、标题、封面文案、标签和 catalog-owned image plan 都收敛为 catalog-derived controlled lesson template，不能用 manual local style 或图片文件覆盖，保持 200–380 字、专业帮助边界与既有心理学安全约束；其 catalog receipt、草稿 gate 与 metrics 是课次级别的，普通心理学帖不受该 receipt 强制。
- `human_enrichment_daily_post` 专门输出人类丰容 / 日常变量实验内容，用一个具体角落、物件或路线写「原本惯性 -> 一个变量 -> 三步清单 -> 轻量结果 -> 评论区例子」。它要求低成本、非医疗化、非购物清单式表达，并会优先借鉴本地 XHS pattern library 的 hook / 清单 / 轮播结构，而不是普通发帖时实时检索小红书。`guide-post` 已支持该 playbook 的本地 topic pack，会按书桌/角落、床头下线、通勤 Colorwalk、手作材料等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。这些方向的 `format_recommendation` 默认强调视觉证据：书桌/包/床头等空间角落走 `provider_scene`，通勤 Colorwalk 和手作材料流走 `carousel`，`cover_role=evidence_or_scene`、`visual_evidence_need=high`，避免把人类丰容写成密集文字海报或购物清单。离线 deterministic 草稿会按桌面/角落、路线/感官、手作/材料流生成不同标题和正文结构。它通过 `content_review.image_form` 暴露 3:4 封面、轮播形式建议、pattern ids 和每页文字约束。默认绑定 `acct-enrichment-local`。
- `world_cup_daily_post` 专门输出世界杯看球笔记，用普通球迷能懂的赛前看点、赛后复盘、看球清单和评论区讨论组织内容。`guide-post` 会按看球清单、球迷情绪、赛前人话看点、赛后复盘等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。它要求明确区分 scene 提供的事实和观察角度，禁止赌球、盘口、预测比分、内部消息或官方消息伪装。默认绑定 `acct-world-cup-local`。
- `reddit_curation_daily_post` 专门把 Reddit 英文 hot/top 讨论作为内部素材，选 AI 热点、心理困境、效率工作流等适合中文读者的角度，改写成自然中文热点帖。`guide-post` 会按 AI 工具焦虑、效率工作流、生活压力非诊断观察、中文读者角度等方向动态返回 4 个场景相关方向，输出仍不展示 raw source URL 或 provenance。默认绑定 `acct-reddit-curation-local`。读者可见标题、封面、正文和标签不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL；来源追踪只留在 runtime context / artifact。读取最新 Reddit 讨论优先按 Reddit Responsible Builder Policy 为该用途取得 explicit approval，并配置获批 app 的 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT`；如果 app 创建暂时受阻，也可用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 走低频只读 public JSON fallback。缺配置时 dry-run 仍可完成，但不能声称来自最新热点。
- 九个真实 XHS 内容质量 playbook 都有 playbook-local `evaluation.yaml`，声明 executor 内容质量 judge 为 `required`，并用确定性 node contract 检查领域标签、短正文合同、自然评论/保存入口、正文现场/真人锚点、实验指令泄漏和跨字段模板化语言。所有 XHS playbook 都会通过 `combined_must_not_include_any` 拦截 `首先`、`其次`、`最后`、`综上`、`本文`、`作为AI`、`建议大家`、`小红书爆款` 这类格式化或元叙事词，通过 `title_max_chars: 22` 与领域化具体入口/禁用词要求拦截泛标题；不再以 `title_must_include_tension_any` 的统一张力词表强行约束全部领域。每个 playbook 用领域化 `body_min_chars` / `body_max_chars` 控制紧凑长度，并声明 `body_must_include_scene_signal: true`、领域化 `body_scene_signal_any` 和共享 `body_human_anchor_any`，要求正文至少落到一个本领域现场词和一个真人视角词上。现代心理学仍用 `title_must_not_include_any` 阻断 `不是你`、`反刍思维`、`低控制感`、`边界压力`、`情绪调节`、`灾难化思维`、`心理机制` 等标题破梗词，并要求正文用 `哪派`、`A.` / `B.` 或 `____` 这类认领式评论入口。
- `modern_psychology_post` 的 deterministic fallback 会按场景簇生成不同候选：周日/周一预焦虑、亲密关系等待消息后的不确定感、忽冷忽热要不要问清楚、社交电量取消局、被说想太多后的边界压力、下班后被消息拉回工位、会议尴尬复盘、脑内复盘会、普通回复复盘接龙、睡前短视频/信息过载、睡眠恢复/轻养生/办公室恢复、孤独/比较焦虑。离线草稿标题不暴露心理机制或 `不是你` 句式，机制名只在场景铺开后轻量出现一次以内，并以自然保存动作和角色/阵营/填空式评论提示收束；亲密关系等待消息和忽冷忽热场景禁止退化成职场协作、处理时间或优先级话术，社交电量取消局不能教人失联，睡眠恢复/轻养生场景禁止写成医疗养生号或睡眠改善承诺。
- `modern_psychology_post` 的图片策略默认使用低密度平实贴图：三栏工具、5 分钟练习、边界句和消息草稿优先 `iphone_notes` / `save_tool`；单句重构可用 `note_card` / `cover_hook`；只有真实聊天对话或消息气泡本身是首屏内容时才用 `wechat_chat`。心理机制解释、专业边界和长正文不应进入封面图。发帖前 `guide-post` 会把同一规则浓缩成 `topic_guidance.image_recommendation`，供 OpenClaw/Codex 在用户确认选题方向后展示图片生成建议。
- `PlaybookRegistry` 支持列出定义、按 id 查询，以及按账号选择。
- `PlaybookDefinition.reflection` 是结构化规则字典，支持必需规则（如 `required_hashtag`、非空 `must_include_phrase`）、可选内容质量规则（如 `title_must_not_equal_any`、`body_must_include_any`、`body_must_not_include_any`）和推荐规则（如 `recommended_phrases`）。推荐词只作为风格提示，不应被 runtime 当成硬门槛。
- `PlaybookLoader` 负责把 markdown 资产读出来供运行时使用，包括 planner、persona 和 reflection 三类文本输入。

## Definition Layout

每个 playbook 定义目录至少应包含：

- `playbook.yaml`
- `planner.md`
- `persona.md`
- `reflection.md`

可选:

- `evaluation.yaml` — 播放本地 evaluation contract 绑定，定义每个 phase 的 node contracts、约束和 invariant

其中：

- `planner.md` 定义任务目标和输出约束
- `persona.md` 定义这个领域账号该像什么样的人在发帖
- `reflection.md` 定义 revise / finalize 阶段的检查标准
- `evaluation.yaml` 引用 shared contract ID 并对每个 node 补充业务约束

`playbook.yaml` 的 `reflection` 字段可以包含非字符串值，例如 `recommended_phrases`、`title_must_not_equal_any`、`body_must_include_any`、`body_must_not_include_any` 列表。runtime reflector 会强制必需项和明确配置的 deterministic quality rules；如果某个 playbook 只是建议使用某类收束词，应该放在推荐字段或 markdown 标准里，避免把所有输出锁成同一个句式。

所有小红书 playbook 的 prompt 资产现在都把 2026-05-23 爆品梗调研消化成各自主题的表达方式，而不是简单贴热词：发疯文学优先职场物件、丝瓜汤式沟通和体面外壳/狼狈内核；现代心理学优先具体生活瞬间、轻机制、角色认领和非诊断化边界，可承接爱你老己、三明治拒绝法和 AI 陪伴边界，但不能把标题写成心理学科普；人类丰容优先适我主义、新独居、手作心流和一平米角落；古诗词金句优先李白、李清照、王维、杜甫、月亮乡愁、山水松弛、节气小动作和可保存的“这一句”读法，苏轼只作为明确场景下的子方向；AI 科技、武侠人物、每日英语和世界杯也分别以生活搭子、老款人格、学习搭子、看球搭子这类本账号能承接的语气进入正文。

所有 XHS playbook 共享 `xhs_compact_native_v1` 标题/正文合同：标题最多 22 字、优先 12-18 字，用该领域自然的具体场景、物件、关系或一句原话切入，不能只写栏目名；不要求所有领域共用一批冲突/反差/戏剧张力 cue。除武侠长文例外外，正文用 2–4 个短节拍组织：先给现场锚点和真人视角，交付一个领域可用细节，再以自然的一句完成保存或回复入口。保存和评论可以合并，读者可见正文不能直接露出“可复制疯话”“可收藏小结”“可保存单元”“评论交接”这类内部功能标签。正文少用总述文章腔，像朋友安利一样少解释多交付；所有既有安全、标签、来源、专业帮助和领域事实合同保持不变。当前正文长度带如下：

| Playbook | Body band |
| --- | --- |
| `fengkuang_daily_post` | 90-220 chars |
| `modern_psychology_post` | 200-380 chars |
| `human_enrichment_daily_post` | 120-280 chars |
| `classic_poetry_quote_post` | 120-280 chars |
| `daily_english_post` | 140-300 chars |
| `ai_tech_daily_post` | 40-360 chars；`news_brief` 用 3–5 条编号事实，`hands_on` 保留可复现实测字段与局限，`fact_translation` 写事实与人群决策；不得用长度或互动模板填充 |
| `world_cup_daily_post` | 180-420 chars |
| `reddit_curation_daily_post` | 180-420 chars |
| `wuxia_character_post` | 450-750 chars（长文例外） |

`guide-post` 的跨领域 topic pack 现在覆盖当前九个 playbook：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`classic_poetry_quote_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。它只做发帖前选题引导，不新增 playbook，也不把 live research 接进普通生成；每个 pack 以本地确定性 lane/direction 数据把热点机制产品化为用户可选方向。除 AI 科技外，非心理学 pack 的候选池必须大于展示数，selector 会把用户 scene 关键词、lane affinity、`diversity_key`、direction source type 和 open-scene mechanism 分开处理，并在每条公开方向里写出 `direction_type` 和 `scene_fit`。公开输出采用 `dynamic_scene_diversity_rerank`：从 curated 候选和多个当前 scene/lane facets 组合出的 `open_scene` 候选中动态选出 4 个方向，让不同场景既有稳定锚点，也不会被固定 curated 槽位锁住。AI 科技是明确例外：必须先选 `news_brief` / `hands_on` / `fact_translation`，selector 只返回该 mode 的 authored direction，且禁用 `open_scene` 与 scene-only fallback。AI topic direction 只帮助组织安全结构，不提供 facts、test record 或 trend source。公开 payload 还带 `topic_guidance.image_recommendation`，把选定方向后的封面建议限定为本地社交截图样式或 provider image，不让 wrapper 自己决定模型、provider 或截图形式。

`fengkuang_daily_post` 的当前 reflection 规则要求 `#发疯文学`，拒绝 `打工人地铁生存实录`、`会议连环暴击实录`、`社畜崩溃边缘实录` 这类泛标题，并要求正文至少出现评论区/接一句/可复制/模板/写在等平台原生机制之一，同时禁止把心理疾病、医院、治疗、用药当笑点。

发疯文学和现代心理学 playbook 的 `playbook.yaml` reflection rules 与 `evaluation.yaml` 都会拦截内容实验操作词泄漏，例如 `想让评论区`、`想存一组`、`变体要求`、`模板要求`、`comment_chain`、`save_tool`、`identity_conflict`。这些词可以出现在 operator 选题记录或实验日志里，但不能进入最终正文。

九个真实 XHS 内容质量 playbook 的 `evaluation.yaml` 都配置了 `quality_judges.executor_content_quality`，gate level 为 `required`。显式启用 eval judge 时，失败会计入 `required_failed`；运行时配置 LLM judge backend 时，reflector 会按 playbook contract 自动启用 judge，并把失败的 `rewrite_hint` 作为下一轮生成反馈。无论 judge 是否通过，最终 artifact 仍会写出 `content_review`，供人工确认后再决定是否发布。

AI 科技 playbook 还声明 `ai_content_policy`，把模式名、news 条目范围和各模式字段要求作为可读元数据；领域 contract 才是强制 authority。它在 runtime 复核 completed draft，并在 finalize 写入 `ai_tech_content_mode`、opaque `ai_tech_evidence_manifest` 和 `ai_tech_evidence_gate`。相同 contract 的离线 evaluator 用于回归审计，不能用普通 text contract 替代。

当前定义目录位于 [`src/ptsm/playbooks/definitions/`](../src/ptsm/playbooks/definitions/)。

`human_enrichment_daily_post` 的 `evaluation.yaml` 还会禁止 `pattern_id`、`hook_archetypes` 等 pattern library 内部字段泄漏到正文，同时要求正文具备变量、低成本/十分钟/今天能试这类行动边界、可保存结构和评论区例子。

`world_cup_daily_post` 的 `evaluation.yaml` 要求 `#世界杯`、赛前/看点/看球/评论区/清单等内容机制，并禁止 `稳赚`、`下注`、`盘口`、`预测比分`、`内部消息`、`官方消息` 等高风险表达。

`reddit_curation_daily_post` 的 `evaluation.yaml` 要求中文话题标签、中文热点解释、收藏触发和评论区问题，并禁止 `#Reddit`、Reddit/source URL、subreddit、英文讨论、翻译过程、伪亲历、心理诊断/治愈承诺、投资建议和实验指令泄漏。

## Routing Rules

- 账号注册表提供 `account_id -> domain/platform` 基础映射。
- 请求可以显式指定 `playbook_id`，否则按账号域和平台做默认选择。
- `acct-fk-local` 默认落到 `fengkuang_daily_post`，`acct-classic-poetry-local` 默认落到 `classic_poetry_quote_post`，`acct-daily-english-local` 默认落到 `daily_english_post`，`acct-psychology-local` 默认落到 `modern_psychology_post`，`acct-enrichment-local` 默认落到 `human_enrichment_daily_post`，`acct-world-cup-local` 默认落到 `world_cup_daily_post`，`acct-reddit-curation-local` 默认落到 `reddit_curation_daily_post`。
- `caller=openclaw` 不是新的 playbook 路由条件；它只是在已解析为 `modern_psychology_post` 后启用发帖前选题引导门禁。没有 `guidance_ack` 时返回 `topic_guidance_required`，不会启动生成或发布。非心理学 playbook 的 OpenClaw 选题顺序由通用 wrapper 引导，runtime 不对这些 playbook 增加 hard preflight gate。确认后的 `topic_direction_id` 只作为 artifact/run 元数据持久化，不参与 playbook 选择。
- 兼容入口 `run-fengkuang` 仍保留，但多 playbook 场景优先使用通用 `run-playbook`。
- `hotspot-discovery` 发生在 playbook 选择之前，但它不按静态领域词筛选扫描。各 YAML 的可选 `hotspot_routing` 仅在 evidence-backed cluster 已发现后表达保守覆盖，字段为 `include_any`、`require_all` 和可选 `exclude_any`；它与已选 playbook 的 `trend_keywords` 明确分离。一个命中返回 `existing_playbook_fit`，多个返回 `ambiguous`，没有命中返回 `unmapped`，不得用心理学、养生或任何默认 playbook 兜底。`reddit_curation_daily_post` 没有泛热点直连 coverage。
- `unmapped` 是合法且有价值的输出；只有至少两个 evidence、至少两个平台支持的未映射 cluster 才会附带 `new_domain_candidate`，作为人工新领域评估信号，不新增 playbook、账号、skill 或发布权限。

## Related Files

- Registry: [`src/ptsm/playbooks/registry.py`](../src/ptsm/playbooks/registry.py)
- Loader: [`src/ptsm/playbooks/loader.py`](../src/ptsm/playbooks/loader.py)
- Accounts: [`src/ptsm/accounts/registry.py`](../src/ptsm/accounts/registry.py)
