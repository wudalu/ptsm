---
title: PTSM Architecture
status: active
owner: ptsm
last_verified: 2026-08-21
source_of_truth: true
related_paths:
  - src/ptsm
  - src/ptsm/application
  - src/ptsm/application/services/account_publisher_context.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - src/ptsm/application/services/side_effect_ledger.py
  - src/ptsm/application/use_cases/harness_evals.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/psychology_learning_series.py
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
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/playbooks/registry.py
  - src/ptsm/playbooks/definitions/ai_tech_daily_post
  - src/ptsm/evaluations
  - src/ptsm/infrastructure
  - src/ptsm/infrastructure/images/asset_ledger.py
  - src/ptsm/infrastructure/images/note_card_backend.py
  - src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py
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

`ai_tech_daily_post` 不是泛泛的 AI 感想或 prompt 模板线。它仍复用既有账号、
playbook、skill 与 eval contract，但每次生成必须先选择一种证据模式：3–5 条核验
快讯的 `news_brief`、单一且可复现的 `hands_on` 测试记录，或带人群决策的
`fact_translation`。提示词相关内容只可作为已记录测试的 `hands_on` 方向，不构成
第四种模式。

`modern_psychology_post` 的 `learning_series` 是同一心理学 playbook 的受控子模式，
不是第十个领域或新的账号。它同时保留 builtin `after_work_rumination`，并支持经
`provision-psychology-learning-storage` → `plan-psychology-series` → review → exact
`confirm-psychology-series --confirm` 创建的 immutable `user_confirmed` curriculum revision。
首次 provision 只能在可信操作者独占存储父目录、所有 writer 已停止时执行；它创建并验证仅当前
用户可访问的 `proposals`、`confirmations`、`catalogs`、`progress` 固定树。后续 proposal、确认和
进度写入不会补建、重绑或修复运行时目录。`psychology_learning_series.py` 只持久化安全化的 proposal
和确认后的快照；proposal 本身绝不可运行。运行时从 frozen series / version / lesson identity
重新构建并逐字段比对课程合同，而不是信任 caller payload。读者可见文案由受控模板渲染，artifact
只保留 opaque audit receipt。系列 checkpoint 使用课程派生的私有 thread lane，不会复用普通心理学帖的
scene/history。普通心理学场景帖仍沿用既有 lane/guide flow，不能被自动编号或转化为课程。路线图查询明确
停在 `selection_required`；推荐顺序只是建议，用户明确选择一课后才会取得该课的 catalog-owned title、
cover hook、image plan 和可运行方向。任何 topic、outline 或热点都不能直接进入 lesson run。

心理学图片合同现在是同一 playbook 内的领域扩展，不是通用多图 schema：普通
`modern_psychology_post` 可在同一次 drafting pass 产出**一个主题、一组** 4–7 张语义文字卡；
learning-series 则由 frozen catalog 的 controlled template 重建固定页面。历史上已确认的
controlled-template-v1 继续按原单卡字节与 receipt 验证，builtin 和新确认目录使用
controlled-template-v2 的 catalog-owned carousel。两者都不能由第二次模型调用改写或按正文长度盲分段。
这不是 12 张或任意页数的批量图片 API：显式要求超过 7 页（例如 12 张）时，wrapper/operator 必须先走
三路 router：`one_carousel` 是支持的一组 4–7 页普通帖；`multiple_posts` 只有逐帖明确确认、各自独立
run/receipt 时才支持；`independent_assets`（8–12 张 **independent image assets**，不是帖子或 carousel）
是当前心理学路径 unsupported，必须转交另行授权的素材流程。不得静默拆分、循环运行、复用一组或把
unsupported 请求伪装为 batch。`max_text_units` 描述单页文字密度，不是图片/页数。

普通心理学 carousel 另有 per-account/per-playbook 的私有 inner-page identity：它只取除封面外的
canonical `role/headline/body_lines`，所以只换标题或封面不能把同一内页组伪装成新变体。最近窗口只读
the **recent 12 successful complete ordinary carousel receipts**；workflow 交出的 reservation 必须是绑定当前
execution-memory 与 account namespace 的 exact runtime capability，应用层复制该已验证能力并以 canonical
lifecycle 方法使用，不能接受 duck-typed look-alike 或 workflow 自己覆盖的方法。应用层会在 ledger 之前持久化
receipt intent；只有完整本地渲染、canonical receipt 验证、完整有序的 page-aware asset-ledger projection 和
atomic intent commit 都成功后才提升到 recent-12。图片/manifest/ledger 失败、非-carousel 退出都会 release；
过期 intent 只能由应用层用 durable ledger verifier 对账，未知 legacy pending marker 保持 fail-closed；
learning-series 使用独立合同和记忆，不进入该窗口。

运行期以 no-follow descriptor、目录/叶子 identity pin 和私有 regular-file 校验防御单次事务内的目录
重绑、symlink、hardlink、临时源替换和 payload 竞态；每次不可信 workflow invoke 前都会创建并 pin 自己的
artifact root，tracker 只认本次直接创建的文件，根路径或 inode 改变即拒绝写入、scrub、merge、publish。
遇到异常即 fail closed。它不会沿可变路径在线
unlink、覆盖或“修复”不可信 artifact/progress，残留只能交给 `trusted offline maintenance`，在所有
writer 停止后检查、重建或移除。这不是对持续拥有同一 UID 任意写权限的进程的永久 at-rest 防篡改保证：
such a same-UID writer can still modify an inode after a transaction's final check. 需要这一保证时，必须使用
独立 OS principal、签名或不可变存储边界。

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
- provider-backed image generation、本地 social screenshot renderer 和 generated image asset ledger 都留在 `infrastructure`，由 `application/use_cases/run_playbook.py` 在发布前编排调用，避免把外部 API 协议、Pillow 绘制细节或 JSONL 资产记录塞进 runtime graph。image backend 负责声明生成图的 no-watermark provider controls，并把 `watermark_policy` / `provenance` 返回给应用层；`run_playbook()` 只做归一化、provenance-aware post-processing 和 artifact 持久化。asset-ledger writer 会固定 caller 的 `base_dir` 目录句柄，再以 `dir_fd` + no-follow 逐级创建或打开固定的 `outputs/artifacts/generated-image-assets` 目录链，并在持锁后、replace 前和父目录 fsync 后重验每一级 name-to-descriptor identity；因此中间祖先被 symlink 或 rename/recreate 重绑时会 fail closed。`final_content.image_plan` 可以让 LLM 主动选择 `local_social_screenshot` 或 `provider_image`；普通帖的 `PlaybookRequest.local_image_style` 是显式本地 override，即使外部 provider 已配置也会走既有单图 renderer。
- 心理学文字轮播的组编排位于 `application/services/image_carousel_transaction.py`，而不是扩张单图 backend protocol。严格的 parent plan 保留 `backend/style/role/text_density/max_text_units/cover_text_strategy/reason/prompt_focus`，并增加 `carousel_style=psychology_text_card_v1` 与 ordered `slides`；每个 slide 只有 `slide_id/order/role/headline/body_lines`。服务先验证全部 4–7 页，再让 `note_card_backend` 逐页本地渲染到 runtime-owned staging，写入带 set/page/file hashes 的 canonical manifest，最后在同一 destination filesystem 原子 rename 为 immutable committed set。只有该完整 set 的 ordered `generated_image_paths` 能进入 page-aware asset ledger 和 publisher；ordinary carousel 的私有 inner fingerprint 也必须在这份完整 receipt + ledger 成功后才 commit，不能在 draft artifact 写入时提前占用。current v2 learning carousel 也记录该 operational ledger，但 sealed learning artifact/response 只复制 safe manifest-hash receipt，不暴露 ledger、路径或 page text。任一页、manifest 或 ledger 失败都以 `psychology_carousel_generation_failed` 在外部发布前停止。已提交 set 在后续发布失败时保留，供安全重试。ordinary run 只有在 `carousel_delivery.status=ready` 时才给外层 relay 交付完整有序 `attachments`；每页以 canonical `page_sha256`（页面内容）和 `file_sha256`（PNG bytes）核验。该 ready receipt 不是聊天/IM 已送达证明：PTSM 只拥有本地渲染和 receipt，不拥有外部 sender；relay 的 ACK、outcome 和 retry 是独立的非 PTSM record，不能回写或改变 immutable receipt。
- XHS format pattern library 分成三层：`topic_radar` 负责外部 MCP 采样，`ptsm.domain.xhs_patterns` 定义本地样本和 pattern 领域模型，`ptsm.infrastructure.xhs_patterns` 只做本地 JSON snapshot 存储，`application/use_cases/collect_xhs_patterns.py` / `analyze_xhs_patterns.py` 负责编排 CLI 用例。普通生成只读取本地 snapshot，不直接依赖 live MCP。
- `topic_radar` 仍是独立的研究边界：它拥有八平台 collection、canonical source evidence、scan quality、event clustering、推荐多样性和历史 novelty；不依赖或 import `ptsm`。它的 public `topic_radar.cli.run_scan()` API 才是 PTSM 的唯一 fresh-research 接口，PTSM 不复制 collector、平台识别或事件聚类逻辑。默认平台集合为 `xiaohongshu,weibo,douyin,zhihu,bilibili,toutiao,douban,sspai`；XHS HTTP MCP 与 trends-hub stdio MCP 按 server 隔离加载，工具发现也有 bounded timeout，所以一个服务失败或卡住只产生对应平台的 partial diagnostics。XHS 以 feed ID 为权威，完整 title+author 只桥接一条缺 ID 观察到首个真实 ID；后续不同真实 ID 保持独立，多个真实 ID 后的缺 ID 观察保持 unresolved。feed 去重和平台内热度归一化都在该边界完成。
- 跨领域发帖前选题引导同样保持分层：`ptsm.domain.topic_guidance` 定义本地 selector、open-scene composer、动态 diversity reranker 和公开 `format_recommendation`，`application/use_cases/topic_guidance_packs.py` 保存非心理学 topic packs，`guide_post.py` 只编排只读 CLI/OpenClaw 输出。八个非 AI-evidence playbook 从 curated 与 local `open_scene` 候选中返回 4 个场景相关方向；这个路径不属于 `agent_runtime`，不会创建 run 或发布。AI 科技是显式例外：selector 先接收 mode，只返回同 mode 的 authored direction，不产生 open-scene 或 scene-only fallback；prompt direction 也只能是 `hands_on` 测试复盘。所有方向仍可带 `format_recommendation` 与 `topic_guidance.image_recommendation`，但 wrapper 只展示，不自行扩写。
- `PlaybookRequest.scene` 在非 AI-evidence 的 `--fresh-topic-research` 模式下可为空。`run_playbook()` 只在该路径调用 public `topic_radar.cli.run_scan()` 一次，并根据 `completed` / `partial` / `insufficient_evidence` 决定是否继续；安全选择只把 angle/why/constructed scene 与 opaque traceability metadata 写入下游，原始 title、author、URL、feed ID、token 和 `scan_summary` 永不进入 drafting。普通/local-only builder 不回读旧 artifact，fresh builder 也只消费本次可读 receipt 并关闭后续 live context，避免第二次 scan。`ai_tech_daily_post` 不执行这条 scan 路径；它只接受 evidence file 内的 facts/test record，Topic Radar 输出最多以 opaque `trend_support` 参与选择。`topic_direction_id` 是 guide-post/OpenClaw handoff key：一般 playbook 将公开 payload 写入 `topic_selection.direction`，AI 科技则在启动前校验 id 与 evidence mode 匹配。
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
- AI 科技证据边界属于领域与应用层，不是泛用 runtime 分支：`ptsm.domain.ai_tech_content` 严格解析 operator 提供的证据文件，分别产出无 provenance 的 drafting contract 与只含 opaque ID 的 manifest。`run_playbook()` 在创建 run、workflow、artifact、图片或 publisher 前 fail closed；runtime 只绑定该 safe contract，并在 LangGraph checkpoint 前重建 allowlisted input。来源 URL、作者、feed ID、原始标题及整份 evidence bundle 不进入 prompt、state、checkpoint、读者可见内容或 artifact。`finalize` 仅写 `ai_tech_content_mode`、`ai_tech_evidence_manifest` 与通过的 `ai_tech_evidence_gate` receipt；离线 evaluator 再审计该 receipt。Topic Radar 保持独立 discovery surface：它可以贡献 opaque `trend_support`，但不提供可发布事实或实测记录。
- 心理学学习系列同样有两段边界：operator 可先提议 2–6 个安全 lesson outline，并在 review publication plan 与 exact proposal fingerprint 后确认 immutable `user_confirmed` revision；随后 runtime 只接受显式 frozen version、lesson 与 matching direction。确认后 revision 不能就地重排或改课，变更必须走新 proposal/version。Topic Radar 仍是 discovery-only，不能把热点标题、evidence 或路由结果变成课程事实、outline 或 lesson input。
- 心理学 carousel 是领域级可选扩展，因此跨领域最小合同 `shared_contracts/evaluation/final_content.schema.yaml` 保持不变；严格 shape 与 exactness 由 psychology domain/runtime/artifact/eval 边界承担。Topic Radar discovery/routing 和 task-completion automation 的状态语义也不因图片集而改变。

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
