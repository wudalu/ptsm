---
title: PTSM Playbooks
status: active
owner: ptsm
last_verified: 2026-06-04
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
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
---

# Playbooks

Playbook 是 PTSM 的业务编排单元。它把领域、平台、技能需求和反思规则绑定成一个可加载定义。

## Current State

- 当前仓库里有九个真实 playbook：`fengkuang_daily_post`、`sushi_poetry_daily_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`modern_psychology_post`、`human_enrichment_daily_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。
- 九个小红书 playbook 都加载共享 `xhs_image_strategy` 和 `xhs_human_voice`。前者让正文生成阶段可以同时给出图片后端和样式计划；后者把温暖、有调性、像真人、不格式化、少运营腔这些横向 persona 要求放进所有 XHS 内容。两个共享 skill 都与各领域 style / hashtag skill 并列，不替代领域内容约束。
- `sushi_poetry_daily_post` 专门输出苏轼诗词赏析短帖，用当代生活瞬间接住诗词情绪。`guide-post` 会按黄州自救、赤壁大江、烟火饮食、怀民关系、旧友旧物、中秋月亮、节气小动作、定风波坏天气等方向动态返回 4 个场景相关方向；泛苏轼 scene 默认走黄州自救这类宽入口，不再把未命中的场景锁到怀民。默认绑定 `acct-sushi-local`。
- `wuxia_character_post` 专门输出长篇武侠人物评述（800-1500字），用当代流行文化视角解读金庸古龙人物。`guide-post` 会按老款人格、当代职场、主体性/边界、人情债等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。默认绑定 `acct-wuxia-local`。
- `ai_tech_daily_post` 专门输出 AI/科技资讯速递，结构化拆解科技进展。`guide-post` 会按模型更新、普通人工作流、工具选择、提示词构建、普通人影响等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。提示词构建 / 好用 prompt 是该 playbook 的 AI 工作流子线，不是新 playbook；相关场景优先返回 `ai_prompt_context_card`，正文必须给一段可直接复制的完整 prompt 成品，再拆成 `任务 / 背景 / 输出格式 / 反例`，并推荐 `iphone_notes` 低密度工具卡封面。默认绑定 `acct-ai-tech-local`。
- `daily_english_post` 是每日英语单词学习内容，陪伴式教育风格。`guide-post` 会按职场表达、情绪词、每日一词、评论区造句等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。默认绑定 `acct-daily-english-local`。
- `modern_psychology_post` 专门输出现代心理困境观察内容，现在优先写小红书生活号式的具体瞬间：标题只保留一个让人停住的关系、消息、睡前或职场场景，不在标题里提前抛出心理学术语或 `不是你...` 破梗。正文按“具体场景继续推进 -> 一句轻机制 -> 自然保存动作或可选小工具 -> 角色/阵营/填空式评论入口 -> 专业帮助边界”组织，工具不是每篇都硬塞，但安全边界始终保留；`psychology_safety` 约束诊断、治疗承诺、药物建议和危机处理边界。它现在要求按选题 lane 轮换：职场复盘/低控制感、亲密关系/不确定感、关系边界/消息压力、数字生活/信息过载、孤独/比较焦虑、情绪调节/恢复练习、睡眠恢复/轻养生/办公室恢复、热点心理化重构，避免所有候选都退化成“下班复盘一句话”。睡眠恢复/轻养生只作为既有心理学子线实验，落到下班信号、身体收口、睡前降噪和 5 分钟低成本动作，不写医疗养生建议、营养方案或治疗承诺；2026-06-02 live XHS opportunity scan 未拿到真实样本，因此这不是新领域结论。亲密关系里“没回消息、想到分手、复合挽留、猫归谁、忽冷忽热要不要问清楚”这类 scene 会优先走 `事实 / 脑补 / 我需要什么` 或 `事实 / 信号 / 我要不要问清楚`，不再落成职场式消息边界回复。`guide-post` 还包含三类增长假设方向：`relationship_mixed_signal_camp_vote` 用 A/B 阵营承接忽冷忽热，`social_battery_cancel_plan_boundary` 用取消局三句承接社交电量，`after_hours_message_body_alarm` 用下班消息三步承接身体被拉回工位；这些是待真实 metrics 验证的选题假设，不是已证明的浏览/点赞提升结论。`guide-post` 会把当前适合该 playbook 的热点机制和当前 scene/lane 现场组合为 4 个动态重排方向；每个方向会说明 `direction_type`、`scene_fit`、趋势信号和病毒式内容 hook。OpenClaw caller 必须先展示这些方向，确认后再生成。默认绑定 `acct-psychology-local`。
- `human_enrichment_daily_post` 专门输出人类丰容 / 日常变量实验内容，用一个具体角落、物件或路线写「原本惯性 -> 一个变量 -> 三步清单 -> 轻量结果 -> 评论区例子」。它要求低成本、非医疗化、非购物清单式表达，并会优先借鉴本地 XHS pattern library 的 hook / 清单 / 轮播结构，而不是普通发帖时实时检索小红书。`guide-post` 已支持该 playbook 的本地 topic pack，会按书桌/角落、床头下线、通勤 Colorwalk、手作材料等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。离线 deterministic 草稿会按桌面/角落、路线/感官、手作/材料流生成不同标题和正文结构。它通过 `content_review.image_form` 暴露 3:4 封面、轮播形式建议、pattern ids 和每页文字约束。默认绑定 `acct-enrichment-local`。
- `world_cup_daily_post` 专门输出世界杯看球笔记，用普通球迷能懂的赛前看点、赛后复盘、看球清单和评论区讨论组织内容。`guide-post` 会按看球清单、球迷情绪、赛前人话看点、赛后复盘等方向动态返回 4 个场景相关方向，方向可来自 curated 候选或 PTSM 本地组合的 `open_scene`。它要求明确区分 scene 提供的事实和观察角度，禁止赌球、盘口、预测比分、内部消息或官方消息伪装。默认绑定 `acct-world-cup-local`。
- `reddit_curation_daily_post` 专门把 Reddit 英文 hot/top 讨论作为内部素材，选 AI 热点、心理困境、效率工作流等适合中文读者的角度，改写成自然中文热点帖。`guide-post` 会按 AI 工具焦虑、效率工作流、生活压力非诊断观察、中文读者角度等方向动态返回 4 个场景相关方向，输出仍不展示 raw source URL 或 provenance。默认绑定 `acct-reddit-curation-local`。读者可见标题、封面、正文和标签不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL；来源追踪只留在 runtime context / artifact。读取最新 Reddit 讨论优先按 Reddit Responsible Builder Policy 为该用途取得 explicit approval，并配置获批 app 的 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT`；如果 app 创建暂时受阻，也可用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 走低频只读 public JSON fallback。缺配置时 dry-run 仍可完成，但不能声称来自最新热点。
- 九个真实 XHS 内容质量 playbook 都有 playbook-local `evaluation.yaml`，声明 executor 内容质量 judge 为 `required`，并用确定性 node contract 检查领域标签、正文结构、评论提示、收藏触发、正文现场/真人锚点、实验指令泄漏和跨字段模板化语言。所有 XHS playbook 都会通过 `combined_must_not_include_any` 拦截 `首先`、`其次`、`最后`、`综上`、`本文`、`作为AI`、`建议大家`、`小红书爆款` 这类格式化或元叙事词，通过 `title_max_chars: 22` 和 `title_must_include_tension_any` 要求标题短且带冲突/反差/戏剧 cue，通过 `title_must_not_include_any` 拦截 `日常`、`实录`、`干货分享` 等泛标题，并用领域化 `body_min_chars` / `body_max_chars` 控制正文不要过长或过短；每个 XHS playbook 还声明 `body_must_include_scene_signal: true`、领域化 `body_scene_signal_any` 和共享 `body_human_anchor_any`，要求正文至少落到一个本领域现场词和一个真人视角词上。重点研究映射 playbook 还会通过 `title_must_include_any` 要求标题保留具体物件、人物、关系或场景钩子。现代心理学例外地取消标题正向机制词门槛，改用 `title_must_not_include_any` 阻断 `不是你`、`反刍思维`、`低控制感`、`边界压力`、`情绪调节`、`灾难化思维`、`心理机制` 等标题破梗词，并要求正文用 `哪派`、`A.` / `B.` 或 `____` 这类认领式评论入口。
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

所有小红书 playbook 的 prompt 资产现在都把 2026-05-23 爆品梗调研消化成各自主题的表达方式，而不是简单贴热词：发疯文学优先职场物件、丝瓜汤式沟通和体面外壳/狼狈内核；现代心理学优先具体生活瞬间、轻机制、角色认领和非诊断化边界，可承接爱你老己、三明治拒绝法和 AI 陪伴边界，但不能把标题写成心理学科普；人类丰容优先适我主义、新独居、手作心流和一平米角落；苏轼诗词既可承接怀民角色认领，也要覆盖黄州自救、赤壁大江、东坡烟火、月亮想念、节气仪式和定风波重读；AI 科技、武侠人物、每日英语和世界杯也分别以生活搭子、老款人格、学习搭子、看球搭子这类本账号能承接的语气进入正文。

所有 XHS playbook 共享同一条标题/正文组织合同：标题最多 22 字、优先 12-18 字，要用具体场景、物件、关系或一句原话叠加冲突、反差、身份代入、工具感或戏剧张力，不能只写栏目名；正文按 `首屏钩子 -> 领域要素 -> 可保存单元 -> 评论交接` 组织，但读者可见正文不能直接露出“可复制疯话”“可收藏小结”“可保存单元”“评论交接”这类内部功能标签。正文还要有现场锚点和真人视角：先写时间、物件、关系、一句原话、材料、路线或动作，少用总述文章腔；中段要像朋友安利一样少解释多交付，给出可抄作业式模板、prompt、清单、句式、判断框架或步骤；把收藏/模板/三栏写成自然句子。当前正文长度带如下：

| Playbook | Body band |
| --- | --- |
| `fengkuang_daily_post` | 120-380 chars |
| `modern_psychology_post` | 260-580 chars |
| `human_enrichment_daily_post` | 180-520 chars |
| `sushi_poetry_daily_post` | 180-520 chars |
| `daily_english_post` | 180-520 chars |
| `ai_tech_daily_post` | 220-650 chars |
| `world_cup_daily_post` | 220-620 chars |
| `reddit_curation_daily_post` | 220-700 chars |
| `wuxia_character_post` | 700-1100 chars |

`guide-post` 的跨领域 topic pack 现在覆盖当前九个 playbook：`modern_psychology_post`、`fengkuang_daily_post`、`human_enrichment_daily_post`、`sushi_poetry_daily_post`、`wuxia_character_post`、`ai_tech_daily_post`、`daily_english_post`、`world_cup_daily_post`、`reddit_curation_daily_post`。它只做发帖前选题引导，不新增 playbook，也不把 live research 接进普通生成；每个 pack 以本地确定性 lane/direction 数据把热点机制产品化为用户可选方向。非心理学 pack 的候选池必须大于展示数，selector 会把用户 scene 关键词、lane affinity、`diversity_key`、direction source type 和 open-scene mechanism 分开处理，并在每条公开方向里写出 `direction_type` 和 `scene_fit`。公开输出采用 `dynamic_scene_diversity_rerank`：从 curated 候选和多个当前 scene/lane facets 组合出的 `open_scene` 候选中动态选出 4 个方向，让不同场景既有稳定锚点，也不会被固定 curated 槽位锁住。AI tech 的 prompt / 提示词场景在这里作为 sublane_first 处理：2026-06-04 的 live opportunity scan 因 XHS MCP 工具不可用没有真实样本，不能声称是新趋势排名；本地方向只把用户指定的帖子模式产品化成可验证的可复制 prompt 成品和拆解卡。公开 payload 还带 `topic_guidance.image_recommendation`，把选定方向后的封面建议限定为本地社交截图样式或 provider image，不让 wrapper 自己决定模型、provider 或截图形式。

`fengkuang_daily_post` 的当前 reflection 规则要求 `#发疯文学`，拒绝 `打工人地铁生存实录`、`会议连环暴击实录`、`社畜崩溃边缘实录` 这类泛标题，并要求正文至少出现评论区/接一句/可复制/模板/写在等平台原生机制之一，同时禁止把心理疾病、医院、治疗、用药当笑点。

发疯文学和现代心理学 playbook 的 `playbook.yaml` reflection rules 与 `evaluation.yaml` 都会拦截内容实验操作词泄漏，例如 `想让评论区`、`想存一组`、`变体要求`、`模板要求`、`comment_chain`、`save_tool`、`identity_conflict`。这些词可以出现在 operator 选题记录或实验日志里，但不能进入最终正文。

九个真实 XHS 内容质量 playbook 的 `evaluation.yaml` 都配置了 `quality_judges.executor_content_quality`，gate level 为 `required`。显式启用 eval judge 时，失败会计入 `required_failed`；运行时配置 LLM judge backend 时，reflector 会按 playbook contract 自动启用 judge，并把失败的 `rewrite_hint` 作为下一轮生成反馈。无论 judge 是否通过，最终 artifact 仍会写出 `content_review`，供人工确认后再决定是否发布。

当前定义目录位于 [`src/ptsm/playbooks/definitions/`](../src/ptsm/playbooks/definitions/)。

`human_enrichment_daily_post` 的 `evaluation.yaml` 还会禁止 `pattern_id`、`hook_archetypes` 等 pattern library 内部字段泄漏到正文，同时要求正文具备变量、低成本/十分钟/今天能试这类行动边界、可保存结构和评论区例子。

`world_cup_daily_post` 的 `evaluation.yaml` 要求 `#世界杯`、赛前/看点/看球/评论区/清单等内容机制，并禁止 `稳赚`、`下注`、`盘口`、`预测比分`、`内部消息`、`官方消息` 等高风险表达。

`reddit_curation_daily_post` 的 `evaluation.yaml` 要求中文话题标签、中文热点解释、收藏触发和评论区问题，并禁止 `#Reddit`、Reddit/source URL、subreddit、英文讨论、翻译过程、伪亲历、心理诊断/治愈承诺、投资建议和实验指令泄漏。

## Routing Rules

- 账号注册表提供 `account_id -> domain/platform` 基础映射。
- 请求可以显式指定 `playbook_id`，否则按账号域和平台做默认选择。
- `acct-fk-local` 默认落到 `fengkuang_daily_post`，`acct-sushi-local` 默认落到 `sushi_poetry_daily_post`，`acct-daily-english-local` 默认落到 `daily_english_post`，`acct-psychology-local` 默认落到 `modern_psychology_post`，`acct-enrichment-local` 默认落到 `human_enrichment_daily_post`，`acct-world-cup-local` 默认落到 `world_cup_daily_post`，`acct-reddit-curation-local` 默认落到 `reddit_curation_daily_post`。
- `caller=openclaw` 不是新的 playbook 路由条件；它只是在已解析为 `modern_psychology_post` 后启用发帖前选题引导门禁。没有 `guidance_ack` 时返回 `topic_guidance_required`，不会启动生成或发布。非心理学 playbook 的 OpenClaw 选题顺序由通用 wrapper 引导，runtime 不对这些 playbook 增加 hard preflight gate。确认后的 `topic_direction_id` 只作为 artifact/run 元数据持久化，不参与 playbook 选择。
- 兼容入口 `run-fengkuang` 仍保留，但多 playbook 场景优先使用通用 `run-playbook`。

## Related Files

- Registry: [`src/ptsm/playbooks/registry.py`](../src/ptsm/playbooks/registry.py)
- Loader: [`src/ptsm/playbooks/loader.py`](../src/ptsm/playbooks/loader.py)
- Accounts: [`src/ptsm/accounts/registry.py`](../src/ptsm/accounts/registry.py)
