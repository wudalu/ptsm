---
title: PTSM Architecture
status: active
owner: ptsm
last_verified: 2026-07-22
source_of_truth: true
related_paths:
  - src/ptsm
  - src/ptsm/application
  - src/ptsm/application/services/account_publisher_context.py
  - src/ptsm/application/services/side_effect_ledger.py
  - src/ptsm/application/use_cases/harness_evals.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/xhs_domain_opportunity.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/agent_runtime
  - src/ptsm/agent_runtime/state.py
  - src/ptsm/domain
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/playbooks/registry.py
  - src/ptsm/evaluations
  - src/ptsm/infrastructure
  - src/ptsm/infrastructure/evaluations
  - src/ptsm/infrastructure/reddit
  - src/ptsm/infrastructure/xhs_patterns
  - src/topic_radar/cli.py
  - src/topic_radar/platforms/xiaohongshu.py
  - src/topic_radar/analysis/evidence.py
  - src/ptsm/interfaces
---

# Architecture

PTSM 当前已支持九个垂直领域（发疯文学、古诗词金句、武侠人物评述、AI科技资讯、每日英语学习、现代心理困境观察、人类丰容实验、世界杯主题、Reddit英文讨论转译），通过 playbook + skill + account 注册表实现多领域并行运营。

提示词构建 / 好用 prompt 不是第十个 playbook；当前证据只支持把它作为
`ai_tech_daily_post` 下的 AI 工作流子线。它复用 AI 科技资讯的账号、playbook、
skill 和 eval contract，只在本地 `guide-post` topic pack 与 deterministic dry-run
helper 中增加 prompt 构建方向。

## Package Boundaries

- `src/ptsm/interfaces/cli/`
  CLI 入口，负责参数解析和命令分发。
- `src/ptsm/application/`
  用例层，连接请求模型、账号、playbook、发布器和运行时。
- `src/ptsm/agent_runtime/`
  LangGraph 运行时、节点和状态契约。
- `src/ptsm/playbooks/`
  playbook 定义、加载和路由。
- `src/ptsm/skills/`
  builtin skill metadata、选择、surface 和加载。
- `src/ptsm/infrastructure/`
  artifacts、observability、publishers、LLM backend、image backend、memory 等适配层。
- `src/ptsm/accounts/`
  本地账号定义和注册表。
- `src/ptsm/evaluations/`
  evaluation 领域层：EvalTarget 提取、rule/contract evaluator、playbook-local evaluation contract 加载和内容质量 LLM judge adapter。
- `src/ptsm/infrastructure/evaluations/`
  eval run / result 文件存储（EvalStore），以及把 evaluation 领域 judge 封装成运行时可调用 gate 的适配器。

## Stable Architectural Facts

- CLI 和 bootstrap 已是稳定入口。
- 发布链路当前以小红书为主，支持 dry-run 和 MCP 实发。
- 平台抽象正在形成，已支持九个垂直领域的 playbook 注册和账号矩阵管理。
- playbook 目录现在不仅承载 planner / reflection，还可以承载 persona 这类账号口吻资产；`agent_runtime` 负责把这些资产作为显式状态传给 drafting backend，而不是把风格写死在 agent 类里。
- 运行时还会把 `xhs_trend_scan` 这类 research skill 的动态结果单独放进 `runtime_skill_contents`，与静态 `SKILL.md` 文本分离，避免 prompt 组装时丢失实时上下文边界。
- reporting / eval / inspection surface 优先放在 `application/use_cases` 上，并复用本地 artifact stores，而不是引入独立服务层。
- deterministic artifact evaluation 仍保持在 runtime graph 之外：`agent_runtime` 写 step evidence，`application/use_cases/eval_artifact.py` 负责抽 target、跑 rule/contract evaluator、写 `.ptsm/evals`。例外是 XHS 内容质量 judge：当 LLM judge backend 可用时，`reflector` 会把它作为生成链路里的 required retry gate 使用。
- composed operator snapshots such as `harness-report` 也留在 `application/use_cases`，只读复用现有 harness surfaces，而不是新增 orchestration service。
- single-case diagnostics such as `diagnose-publish` 同样留在 `application/use_cases`，通过组合 `doctor`、logs 和 artifact readers 来输出归因，而不是把诊断逻辑塞进 publisher 或 CLI。
- side-effect replay control 也放在 `application/services + application/use_cases`，避免让 `agent_runtime` 直接承担发布副作用策略。
- provider-backed image generation、本地 social screenshot renderer 和 generated image asset ledger 都留在 `infrastructure`，由 `application/use_cases/run_playbook.py` 在发布前编排调用，避免把外部 API 协议、Pillow 绘制细节或 JSONL 资产记录塞进 runtime graph。image backend 负责声明生成图的 no-watermark provider controls，并把 `watermark_policy` / `provenance` 返回给应用层；`run_playbook()` 只做归一化、provenance-aware post-processing 和 artifact 持久化。`final_content.image_plan` 可以让 LLM 主动选择 `local_social_screenshot` 或 `provider_image`；`PlaybookRequest.local_image_style` 是显式本地 override，即使外部 provider 已配置也会走本地 renderer。
- XHS format pattern library 分成三层：`topic_radar` 负责外部 MCP 采样，`ptsm.domain.xhs_patterns` 定义本地样本和 pattern 领域模型，`ptsm.infrastructure.xhs_patterns` 只做本地 JSON snapshot 存储，`application/use_cases/collect_xhs_patterns.py` / `analyze_xhs_patterns.py` 负责编排 CLI 用例。普通生成只读取本地 snapshot，不直接依赖 live MCP。
- `topic_radar` 仍是独立的研究边界：它拥有八平台 collection、canonical source evidence、scan quality、event clustering、推荐多样性和历史 novelty；不依赖或 import `ptsm`。它的 public `topic_radar.cli.run_scan()` API 才是 PTSM 的唯一 fresh-research 接口，PTSM 不复制 collector、平台识别或事件聚类逻辑。默认平台集合为 `xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai`；XHS HTTP MCP 与 trends-hub stdio MCP 按 server 隔离加载，工具发现也有 bounded timeout，所以一个服务失败或卡住只产生对应平台的 partial diagnostics。XHS 以 feed ID 为权威，完整 title+author 只桥接一条缺 ID 观察到首个真实 ID；后续不同真实 ID 保持独立，多个真实 ID 后的缺 ID 观察保持 unresolved。feed 去重和平台内热度归一化都在该边界完成。
- 跨领域发帖前选题引导同样保持分层：`ptsm.domain.topic_guidance` 定义本地确定性 lane/direction 选择器、多个 open-scene candidate composer、动态 diversity reranker 和公开 `format_recommendation` 结构，`application/use_cases/topic_guidance_packs.py` 保存非心理学 playbook 的产品化 topic pack，心理学方向仍由 `application/use_cases/guide_post.py` 的专业边界 brief 组合；`guide_post.py` 只编排只读 CLI/OpenClaw 输出。selector 把用户 scene 关键词、lane affinity、direction source type、diversity family 和 open-scene mechanism 分开处理，并在公开方向中写出 `scene_fit` 和格式建议；`guide-post` 对当前九个 playbook 返回 4 个由 `selection_policy == "dynamic_scene_diversity_rerank"` 选出的场景相关方向，不再保留固定 curated 槽位。`open_scene` 方向由当前 scene/lane facets 和可复用内容机制本地组合，不来自固定候选池，也不触发 live research。这个路径不属于 `agent_runtime`，不会启动 workflow、创建 run 或发布。每条方向的 `format_recommendation` 说明 `format_archetype`、`cover_role`、`body_shape`、`visual_evidence_need` 和 `avoid_format`；例如人类丰容/手作/Colorwalk 方向优先视觉证据或轮播，AI prompt 和心理睡眠恢复方向优先低密度保存卡。`topic_guidance.image_recommendation` 也由 `guide-post` 生成：它只在方向确认后作为图片方式建议展示，按场景推荐 `local_social_screenshot` 的 `wechat_chat` / `iphone_notes` / `note_card`，或推荐 `provider_image` + `bailian` / `qwen-image-2.0-pro`，OpenClaw wrapper 不复制这层策略。
- `PlaybookRequest.scene` 在 `--fresh-topic-research` 模式下可为空。`run_playbook()` 只在该显式路径调用 public `topic_radar.cli.run_scan()` 一次，并根据结果的 `completed` / `partial` / `insufficient_evidence` 状态决定是否继续：没有有效 evidence 会在 workflow 前返回诊断，不会用静态映射伪造热点方向。交互选择只把 evidence-backed 的选题角度、讨论诱因和构造场景写入 drafting；原始标题、作者、URL、feed ID、token 永不进入 drafting context，canonical-equivalent 或较具体 title 的内嵌复写、以及 raw author/URL/feed/token 都会在 `vertical` / `angle` / `why` 进入该边界前被拒绝；短泛 title 不会误杀新角度里的普通语言，短 provenance 值仍严格拒绝。普通/local-only `topic_research` builder 不回读旧 artifact；fresh builder 也只消费本次 receipt 明示且存在的 artifact，缺失 receipt 则 fail closed。`cluster_id`、`event_fingerprint`、`evidence_ids`、scan quality 和 artifact/report path 仅作为 `topic_selection` traceability metadata 写入 response/run/artifact，终端 `scan_summary` 不会进入该 metadata。写入选择后，runtime 会关闭后续 fresh context builder，避免第二次 live scan 或竞争性 `topic_research` 方向。`PlaybookRequest.topic_direction_id` 仍是 guide-post/OpenClaw handoff key，不改变 playbook 路由或重新选题；`run_playbook()` 会解析该 id 对应的公开方向 payload，把 `topic_selection.direction` 写入 workflow payload、response、run payload 和 artifact，并由 planner 渲染成 `# XHS Topic Direction Guidance` runtime context。
- `ExecutionState` 现在携带 `activated_skill_details`、`runtime_skill_details`、`topic_selection` 和 `memory_hits` 等 observability 字段，记录每个 skill 的元信息（display_name、source_path、resource_type）、确认选题方向和本次回读的账号 lessons，供 artifact 写入、drafting context 和 harness evals 聚合消费。
- `human_enrichment_daily_post` 以新增 playbook/account/skill/evaluation 资产接入人类丰容实验，不需要 runtime 增加领域分支；它的 artifact `content_review` 会额外写出 `image_form`，供 3:4 封面和轮播式人工 review 使用。
- `world_cup_daily_post` 以新增 playbook/account/skill/evaluation 资产接入世界杯主题，默认绑定 `acct-world-cup-local`；正文质量约束通过 playbook-local contract 禁止赌球、盘口、预测比分、内部/官方消息伪装等高风险表达，离线 deterministic helper 只服务本地 dry-run 验证。
- `reddit_curation_daily_post` 以新增 playbook/account/skill/evaluation 资产接入 Reddit英文讨论转译，默认绑定 `acct-reddit-curation-local`。实时素材通过已获批 Reddit app-only OAuth 的 `reddit_discussion_scan` runtime context 读取公开讨论；如果 app 创建被验证码或审批挡住，也可在设置非占位 `REDDIT_USER_AGENT` 后用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 走 Reddit public `.json` 页面做低频只读扫描。缺少 `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` / `REDDIT_USER_AGENT` 且没有可用 public JSON fallback 时会写出缺配置/缺权限上下文。最终读者可见内容只呈现中文热点帖，不暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL。
- `application/services/account_publisher_context.py` 提供 `PublisherContext` 解析：按 account cookie profile > settings defaults > CLI overrides 的优先级决定发布服务器、可见性和 cookie 路径。
- `side_effect_ledger` 现在支持 `scope_id` 参数，通过 `thread_id/scope_id` 组合键实现多维度的副作用去重，而不仅限于 thread 级别。
- `harness_evals` 新增 `_aggregate_skill_stats`，按 skill 维度聚合 runs/completed/runtime_context_runs/completion_rate，输出到 harness-report 的 `skills` 字段。
- evaluation gates 区分 `required` 和 `warning`：deterministic required failures 可以阻塞 local harness；XHS executor content-quality judge 在显式启用 eval 或生成链路配置 judge backend 时使用 `required` gate，但最终发布仍需人工确认。
- playbook contract evaluator 现在承担通用正文质量硬约束，包括标题/封面反泛化、必需标签、禁用标签、必需/禁用正文词、评论提示、保存触发、正文长度区间、正文现场/真人锚点和实验指令泄漏；新增约束应优先扩展 `src/ptsm/evaluations/contracts_eval.py`，避免在 runtime 或单个 playbook 中写领域分支。
- 小红书的人设和真人感现在属于 playbook/skill 资产层：九个 XHS playbook 共享 `xhs_human_voice` 的 `xhs_compact_native_v1` 默认合同，再叠加各自 style、persona、planner 和 reflection 规则；运行时只负责加载这些资产，不为“温暖、有调性、不格式化”新增领域分支。合同要求 2–4 个短节拍：先给现场/真人锚点，再交付一个领域可用细节，并用自然的一句完成保存或回复入口；不是面向读者的四段写作课。
- 标题吸引力和正文组织也保持在资产/合同层：标题仍优先 12-18 字、最多 22 字，并需给出领域适配的具体入口（场景、物件、关系或一句原话），同时拦截泛标题。它不再以一套跨所有领域的张力关键词作统一硬门槛；playbook-local contract 按领域声明真正需要的具体标题与安全限制，DeepSeek / deterministic drafting backend 只读取这些资产，不新增领域 orchestration 分支。
- 正文人味同样保持在资产/合同层：`xhs_human_voice` 定义现场锚点、真人视角、少总述、自然保存和可接话结尾；每个 XHS playbook 在 `evaluation.yaml` 中声明本领域的 `body_scene_signal_any` 和共享 `body_human_anchor_any`，并使用更短的领域长度带。所有既有安全、标签、来源和专业帮助合同保持不变。
- playbook contract evaluator 现在支持 `title_must_include_any`、`title_must_not_include_any`、可选领域 title constraints、body length band、`body_must_include_scene_signal` / `body_scene_signal_any` / `body_human_anchor_any` 和 `combined_must_not_include_any`，用于让标题保留具体物件/场景钩子、限制在短标题上限内、拦截泛标题，让正文保留现场锚点和真人视角，并跨标题、封面文案和正文拦截 `首先`、`其次`、`综上`、`作为AI` 这类模板化或元叙事语言。
- `modern_psychology_post` 的浏览/点赞优化仍放在既有心理学资产层：睡眠恢复、轻养生、办公室恢复被建模为现代心理学子线实验，由 `guide-post`、`psychology_style`、playbook prompt 和 deterministic dry-run helper 承接，不新增 domain/playbook/runtime 分支。2026-06-02 的 XHS domain opportunity live scan 因本地 MCP 缺少 `search_feeds` 没有采到样本，所以这条子线只按弱证据推进为本地可验证实验，不声称已完成趋势排名。
- `ai_tech_daily_post` 的提示词构建方向同样保持在资产层：2026-06-04 的 prompt / AI提问 domain-opportunity scan 因本地 XHS MCP 缺少可用 `search_feeds` 未拿到真实样本，但 deterministic mapping 将 AI提问、普通人用AI、AI工具和AI工作流归入现有 AI tech playbook fit。因此本次只新增 `提示词构建 / 好用 prompt` lane、`ai_prompt_context_card` 等 guide-post 方向和 deterministic 可复制 prompt 成品 dry-run，不新增账号、playbook 或 runtime 分支。

## Current Design Pressure

- 从单一 `fengkuang` 纵切抽出通用运行时。
- 让 playbook 和 skill 真正 request-scoped，而不是硬编码约定。
- 把内存态执行状态升级成可恢复的本地系统能力。

## Dependency Direction

当前代码基线下，稳定且已经成立的 dependency direction 规则如下：

- `interfaces`
  只负责入口和分发，可以依赖 `application`、`config`、`plan_runner`，不应直接依赖 `infrastructure` 或 `agent_runtime`。
- `application`
  负责用例编排，可以依赖 `agent_runtime`、`accounts`、`playbooks`、`config`、`infrastructure`。
- `agent_runtime`
  负责图执行和节点逻辑，可以依赖 `config`、`infrastructure`、`playbooks`、`skills`，不应依赖 `interfaces` 或 `application.use_cases`。
- `infrastructure`
  负责外部适配和持久化，不应依赖 `application`、`interfaces` 或 `agent_runtime`。
- `playbooks`
  负责定义和加载，不应依赖 `application`、`interfaces` 或 `agent_runtime`。
- `skills`
  负责 skill metadata、selection 和 loading，不应依赖 `application`、`interfaces` 或 `agent_runtime`。

这些规则会通过 mechanical enforcement 落到结构测试里，而不是只停留在文档说明层。

当前结构测试位置：

- `tests/unit/architecture/`

## Related Maps

- 运行时细节见 [`runtime.md`](runtime.md)
- Playbook 结构见 [`playbooks.md`](playbooks.md)
- Skill 结构见 [`skills.md`](skills.md)
- 观测与回放见 [`observability.md`](observability.md)

## Discovery-First Hotspot Routing

`ptsm hotspot-discovery` 是发帖前的只读 application use case：它先调用 public
`topic_radar.cli.run_scan()`，且不传 account、playbook、domain、platform 或 keywords；
只有 scan 完成后才消费校验通过的 `topic_clusters`。PTSM 不使用 Topic Radar 规则回退的
vertical labels 作为路由事实。

后置路由在 `ptsm.domain.hotspot_routing` 中是纯函数。每个现有 playbook 的
`hotspot_routing` YAML metadata 与 `trend_keywords` 分离：前者只描述发现后的保守覆盖，
后者仍只可为已经选择的 playbook 提供 fresh research hints。结果必须是
`existing_playbook_fit`、`ambiguous` 或 `unmapped`；跨平台、证据充分的未映射事件才标记
`new_domain_candidate` 进入人工新领域复盘，绝不自动创建 playbook/account。

进入路由前，cluster 的每个 evidence id、fingerprint、platform 和 `representative_title` 都必须一致：
代表标题必须来自本 cluster 的 canonical evidence。非有限 score 归零，未知 scan quality fail closed 为
`insufficient_evidence`，避免损坏 scan 被误写成 completed 或误路由到既有 playbook。

artifact 保留一个按 score 的全平台 Top-N 主列表，并可从同一批已验证 cluster 提供不重复的
`routed_hotspots` 补充视图。每条补充行必须引入至少一个未展示的 playbook；`ambiguous` 行保留
完整候选集。后者只帮助运营者发现主列表外的已有 playbook 候选，不改变发现
或全平台排序，也不回写任何 scan 输入。

该用例写独立 routing artifact；`operator_headline` 仅供操作者理解热点。任何原始标题、
作者、URL、feed id、token 和 headline 都不进入 drafting handoff，后续仍需用户选择已有
playbook/account 后才能进入 `guide-post` / `run-playbook`。Topic Radar 仍不 import PTSM。
