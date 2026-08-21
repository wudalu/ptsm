---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-08-21
source_of_truth: true
related_paths:
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/agent_runtime/graph
  - src/ptsm/agent_runtime/nodes
  - src/ptsm/agent_runtime/nodes/planner.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - src/ptsm/application/use_cases/psychology_learning_series.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/skills/runtime_context.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/topic_guidance_packs.py
  - src/ptsm/application/models.py
  - src/ptsm/domain/topic_guidance.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/psychology_carousel.py
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
6. finalize 写入 draft artifact，并生成 `content_review` 供人工确认。普通 psychology carousel 可在此取得私有
   fingerprint reservation，但不能在此 commit lessons memory；它必须等完整本地图片 receipt 与 ledger 成功。
7. 应用层根据结果决定是否生成发布图片。普通单图继续走既有 backend；经过严格验证的心理学
   `psychology_text_card_v1` plan 则作为 4–7 页事务一次性生成和提交，任一页失败都不暴露部分结果。
8. 只有完整图片结果才进入 asset ledger、发布、状态检查或浏览器步骤；ordinary carousel 的 recent-memory
   fingerprint 也只在这一步的完整 receipt + ledger 成功后才落盘。

## AI Tech Evidence Boundary

`ai_tech_daily_post` 在任何 run、workflow、artifact、图片生成或 publisher 建立前先经过
application preflight。operator 必须同时传入 `--ai-content-mode` 和
`--ai-evidence-file`；缺失、JSON/结构无效或 mode 不匹配会返回
`ai_tech_evidence_required` 或 `ai_tech_evidence_invalid`，不创建 run，也不会退回到
free-text scene 草稿。AI run 的 scene 由已验证 contract 重建，不能把 operator 的原始
headline、URL、作者或 feed 值回显到 response。

- `news_brief` 只能由 3–5 个不同事件组成；每项只有显示 label 和已核验 facts 可进入
  drafting，不能写成第一人称体验。
- `hands_on` 只能写一个主题，且必须有 product、version、tested_at、task、input summary、
  observed output、limitation 和 opaque test-evidence ref；它是唯一允许写实测/观察的模式。
- `fact_translation` 只能写一个主题、至少两个已核验 facts，以及 `who_should_care` /
  `who_can_wait` 判断；不能伪装成测试。

`guide-post --playbook-id ai_tech_daily_post` 也必须显式选择 mode，只显示相同
`content_mode` 的静态方向，不生成 `open_scene` 兜底方向；传回的
`topic_direction_id` 必须仍存在且匹配 evidence mode，否则 `run-playbook` 在启动前返回
`ai_tech_topic_direction_invalid`。提示词方向仅归入 `hands_on`，输出应是一次可复现实验
记录，而不是无条件可复制模板。

通过 preflight 后，runtime 只接收 provenance-safe contract（mode、safe facts/测试字段和
mode policy）及独立 opaque manifest。AI workflow facade 在 LangGraph 写入初始 checkpoint
之前重建 allowlisted input；planner 的 `# AI Tech Evidence Contract`、draft validator、
reflector retry 和应用层 publish 前复核都使用同一 contract。原始 source URL、author、feed
ID、raw title、完整 evidence bundle 和无效 model draft 不进入 prompt、state、checkpoint、
reader-visible content 或 artifact。

对 AI evidence mode，`--fresh-topic-research` 不在 `run-playbook` 内执行 scan，而是返回
`ai_tech_fresh_research_separate`。先用 `hotspot-discovery` 找全平台热点；只有 operator
自行整理出的 opaque `trend_support` 可放进 evidence manifest，不能把 Topic Radar headline、
cluster 或热度当成事实/测试证据。

## Psychology Learning Series Boundary

`modern_psychology_post` 的 `learning_series` 有两种受控 catalog origin：builtin
`after_work_rumination`，以及经 `plan-psychology-series` proposal review 后用 exact
`proposal_fingerprint` 和 `confirm-psychology-series --confirm` 创建的 immutable
`user_confirmed` revision。proposal 只用于审核，绝不是 runnable catalog；topic、2–6 项 outline、
热点或自由 scene 都不能绕过确认边界直接变成 lesson run。更改课次、标题、目标或 publication
order 必须产生新 proposal/version，既有 version 保持可审计。

首次 custom proposal 前，可信操作者必须在所有 writer 停止且独占存储父目录时运行
`provision-psychology-learning-storage`。它只在 trusted setup 创建/验证私有的
`proposals`、`confirmations`、`catalogs`、`progress` 固定目录；普通 plan、confirm、guide、run 和
progress mutation 只打开既有树，缺失、重绑、symlink、hardlink 或非私有叶子都会 fail closed，绝不
把 provision 当作 runtime repair。事务内的 descriptor/identity checks 防御路径替换竞态，但不承诺
防御持续拥有同一 UID 写权限者在最终检查之后的 at-rest 修改；可疑残留不在线删除，交给
`trusted offline maintenance`。

有效 lesson run 必须同时给出 `--psychology-content-mode learning_series`、
`--psychology-series-id`、`--psychology-lesson-id`、显式
`--psychology-curriculum-version`，以及与 frozen catalog lesson 完全匹配的
`--topic-direction-id`。这些 flags 只允许 `modern_psychology_post`；缺失、伪造、跨课次、
缺失/tampered catalog 或 receipt 会在 `RunStore.start`、workflow、图片和 publisher 之前 fail
closed，返回 `psychology_learning_required`、`psychology_learning_invalid` 或
`psychology_learning_topic_direction_invalid`（其他 playbook 为
`psychology_learning_playbook_invalid`）。

无 lesson 的 `guide-post` 对 `user_confirmed` custom catalog 会返回 `selection_required`、frozen
`series.roadmap`、`series.publication_plan`、`series.recommended_next_lesson` 和
`series.production_progress`；其 `kind` is `operator_content_production`。推荐只是发布顺序建议，
不会自动选择或生成课次，PTSM 也不会默认生成第一课。用户可明确选择非推荐课，但必须在再次
`guide-post` 时传回该 custom series 的 explicit frozen curriculum version，随后仅用该响应返回的 matching
direction id dry-run。builtin roadmap omits `series.publication_plan`, `series.recommended_next_lesson`, and
`series.production_progress`；builtin `after_work_rumination` 的 catalog flow 保持原样。

bound workflow 从 catalog 重建 scene 和 allowlisted input，并把 public `thread_id` 映射到
checkpoint-isolated 的课程私有 thread；planner 只收到课程字段，memory、live skill context 与
fresh scan 都不参与该课。`--fresh-topic-research` 返回
`psychology_learning_fresh_research_separate`：Topic Radar 只能协助发现/决定是否规划系列，不能提供
learning-series lesson facts、证据、outline 或 run input。

executor、reflector、finalize 和应用层都调用同一个
`psychology_learning_draft_contract`：成稿必须逐字段等于 catalog-derived 的 `controlled lesson template`
（四个紧凑短拍），不只是“包含”概念、解释、微练习、适用/范围说明和专业帮助边界。custom artifact
另外必须有 trusted `psychology_learning_catalog_receipt`，其中只含 `schema_version`、
`origin=user_confirmed`、`controlled_template_version`、`catalog_digest`、`approval_id`、
`proposal_fingerprint` 与 `publication_plan`；builtin artifact 不写该字段。runtime、offline eval 与
metrics 都从 frozen catalog 重建并验证此 receipt，缺失或被篡改时 fail closed。原始 topic、outline
goal、source、URL、作者、local path、自由场景和额外临床主张均不能进入 prompt、checkpoint、
reader-visible content 或 artifact。

课程目录同时拥有该课的标题、封面钩子和图片计划；`--local-image-style`、手工图片路径都不能
覆盖它。custom `series.production_progress` 仅在安全 completed artifact 与严格 receipt 都已写入后记录：
dry-run 和内容成功但 publish 失败可计为 operator 产出，preflight/workflow/eval/final-artifact failure
则不可计；它不是读者学习进度，也不会触发自动发布。catalog exact gate 是本模式的正文质量真相来源：
普通自由场景的心理学反思规则或 LLM judge 不会用不相容的开放式条件推翻已通过的课程合同，既有安全
边界仍然保留。progress replacement 在 rename 已发生后若后续边界校验失败，返回
`psychology_learning_progress_persist_failed`；这具有 at-least-once 语义，不能把该状态解读为
sidecar 一定未写入，也不能在线回滚或删除。恢复可信存储后重试同一课次是幂等的；任何不可信
progress/artifact 仍交给 `trusted offline maintenance`。

controlled lesson template 有独立版本语义。已持久化的 template v1 catalog/receipt 保持原有单张
`iphone_notes` image plan 和 digest，不会迁移或静默重写；builtin lesson 与新确认 custom revision 使用
template v2，并从 `cover_text`、scene、concept、approved explanation、micro exercise、scope、professional
boundary 和 comment prompt 确定性重建 7 张 catalog-owned 文字卡。runtime、artifact evaluator 与 metrics
都按 receipt 中的 `controlled_template_version` 重建相同草稿；模型不能补写、改页或改变顺序。

learning-series 仍禁止 `--local-image-style` 与 `--publish-image-path`。当请求没有图片生成时，既有的
safe content-artifact 进度时机保持不变；当请求了图片生成时，只有完整 committed carousel、page-aware asset ledger、严格学习
artifact 与 receipt 都再次验证通过后才记录 production progress。任一页面、manifest 或
发布前图片门失败都设置 `psychology_carousel_generation_failed`，因此不会误推进课次。sealed learning
artifact 的成功图片证据只含 `status=committed`、`renderer=ptsm_local_renderer`、
`carousel_style=psychology_text_card_v1`、`image_count` 和 `manifest_sha256`；失败只记录同样有界的
renderer/style/count 与稳定 `reason`，绝不写本地路径、页文案或 catalog source。

## Current Runtime Facts

- 当前通用运行时入口是 `build_playbook_workflow()`，`build_fengkuang_workflow()` 只是兼容 wrapper。
- 心理学轮播计划的 schema 校验由 runtime carousel draft gate 拥有：drafting backend 的 JSON 解析层（`factory.py`）对滑出枚举或漏填必填字段的轮播 `image_plan` 不再直接抛异常，而是原样传给 gate；gate 归一化失败时返回带 pydantic 字段级详情的 `invalid psychology carousel plan: <detail>`，executor 把该详情带进 `psychology_carousel_executor_errors`，reflector 再写入 `reflection_feedback` 触发重试。最终进入状态和 artifact 的成稿仍以 `normalize_psychology_carousel_plan` 的严格归一化结果为准，解析层只负责不短路重试闭环。
- 运行结果会落到 artifact，并写入本地 run store。
- `run_playbook()` 默认会在 `.ptsm/agent_runtime/` 下创建持久 execution memory 和 checkpoint。普通心理学除既有
  recent lesson 文案回读外，还有一个 per-account/per-playbook、cover-excluded 的内页 fingerprint 窗口；它只保留
  recent 12 successful complete ordinary carousel receipts，learning-series 不参与。
- PTSM 有两个显式 live research application surface：`hotspot-discovery` 是 playbook 前的开放发现（不启动 workflow/run/publish），`--fresh-topic-research` 是非 AI-evidence playbook 的兼容路径。后者调用 public `topic_radar.cli.run_scan()`，不传 `platforms`，因此由 Topic Radar 统一控制当前八平台默认集合、canonical evidence、事件簇、history novelty 与 quality 状态；普通 `run-playbook`、deterministic provider、`guide-post` 和本地 topic pack 路径都不触发该 scan，也不会回读当天或其他运行遗留的 `topic-scan-*.json`。`ai_tech_daily_post` 使用 `--fresh-topic-research` 时返回 `ai_tech_fresh_research_separate`，避免把 scan 结果误当成可发表 evidence。
- fresh scan 为 `insufficient_evidence` 时，`run_playbook()` 在 workflow/发布前返回 operator-safe receipt（quality、platform diagnostics、artifact/report path），不会继续拿静态建议冒充实时热点。`partial` 可以继续到交互选择，但 artifact 会保留失败平台/关键词/LLM 诊断，operator 不得把它解释为完整全平台覆盖。
- fresh 交互只允许选择已经绑定真实 cluster/evidence 的角度。drafting runtime context 只接收安全的 `vertical`、`angle`、`why_discussion_likely` 与构造场景；it never receives raw source titles, authors, URLs, feed IDs, or tokens。canonical evidence title guard 会拒绝等价 title 和较具体 title 的内嵌复写；像 `AI` 这样的短泛词可作为新角度语言。author/URL/feed/token 的规范化值仍无论长短一律阻断，避免异常 LLM/旧 artifact 穿透。builder 只接受本次 fresh `run_scan()` receipt 明示且存在的常规 artifact 文件，缺失或不可读 receipt 会 fail closed；`fresh_topic_research=False` 或 local-only builder 只保留本地 pattern context。`cluster_id`、`event_fingerprint`、`evidence_ids`、quality 和 artifact receipt 留在 `topic_selection` metadata 供审计；终端展示用的 `scan_summary` 和一切原始来源材料都不写入该 metadata。选择完成后 workflow payload 关闭 fresh builder，does not start a second live scan，也不会把竞争性的 `topic_research` context 叠加进同一草稿。
- `guide-post` 是应用层只读选题引导，不启动 workflow、不创建 run、不发布、不调用 live XHS / Topic Radar。八个非 AI-evidence playbook 使用 `ptsm.domain.topic_guidance` 的动态 selector、open-scene composer、本地 topic packs 和心理学 brief，返回 4 个场景相关 directions，并附 `direction_type`、`scene_fit`、hook、format recommendation 与 image recommendation。AI 科技不走 `dynamic_scene_diversity_rerank`：必须显式选择 `news_brief`、`hands_on` 或 `fact_translation`，只得到同 mode 的 authored directions，且没有 `open_scene` / scene-only fallback。提示词方向只在 `hands_on` 中出现，提示的是记录一次任务、输出与局限的复现，而不是让模型生成通用 prompt。所有 guide payload 均不含 research 路径、raw source 或 provenance。
- `classic_poetry_quote_post` 的 topic pack 把诗词、古诗词金句、经典诗句、李白、李清照、王维、杜甫、月亮乡愁、节气和明确苏轼场景路由到古诗词金句方向。默认标签是 `#古诗词`，苏轼只是可选子方向；泛诗词场景不再强制 `#苏轼`、怀民或苏轼赏析入口。古诗词金句方向的图片建议通常是低密度 `note_card` / `iphone_notes` 保存卡。
- 心理学 `guide-post` 还把睡眠恢复、轻养生、办公室恢复作为既有 `modern_psychology_post` 子线实验处理：相关场景会路由到 `睡眠恢复 / 轻养生` lane，优先返回 `sleep_recovery_shutdown_card` 等低成本保存工具方向。普通心理学默认时，每个 returned direction 的 `format_recommendation` 使用 `format_archetype=text_carousel` / `cover_role=cover_hook`；顶层图片建议使用 `format_archetype=text_carousel` / `role=text_carousel`，再给出 `local_style=psychology_text_card_v1`、4–7 页以及从 `cover_hook` 开始的 ordered semantic roles。命令提示仍只有 `--auto-generate-image`，没有手工分页或 carousel-style CLI。心理学动态开放方向只从 copyable line、micro task、comment pattern 与 save card 机制中选择，不允许世界杯 `watch_checklist` 或 AI 科技 `tool_handoff` 语义借稳定轮换进入心理学 payload。operator 若在普通帖向 `guide-post` 明确传 `--image-style iphone_notes|note_card|wechat_chat`，才保留既有单图 recommendation；后续生成命令使用对应的 `run-playbook --local-image-style ...`，并在运行时注入方向中保持同一单图格式。该路径仍不 live-scan；2026-06-02 的 domain opportunity 尝试没有真实样本，只能作为子线假设背景。
- 心理学 `guide-post` 还包含三类本地 authored 增长假设方向：`relationship_mixed_signal_camp_vote` 命中忽冷忽热、暧昧和要不要问清楚场景，输出 `事实 / 信号 / 我要不要问清楚` 与 A/B 阵营评论；`social_battery_cancel_plan_boundary` 命中社交电量、约好的局临时不想去和扫兴愧疚场景，输出取消局三句；`after_hours_message_body_alarm` 命中 18:57 在吗、下班消息和身体被拉回工位场景，输出下班消息三步和 A/B/C 评论入口。这些方向只是 deterministic guidance payload 和后续 metrics loop 的分组维度，不代表已经有真实浏览/点赞 uplift。
- `run_playbook()` 现在支持 caller-aware preflight：当 `PlaybookRequest.caller == "openclaw"` 且目标 playbook 是 `modern_psychology_post` 时，如果没有 `guidance_ack`，会在启动 workflow、创建 run 或执行发布前返回 `topic_guidance_required`。这个硬 runtime gate 只覆盖心理学，因为心理学方向还带专业边界；OpenClaw 确认方向后再带 `--guidance-ack` 重新调用。非心理学 playbook 由 `integrations/openclaw/ptsm-xhs-topic-guide/SKILL.md` 在 wrapper 层先调用 `guide-post`，但 `run-playbook --caller openclaw` 不会因为缺少非心理学 guide ack 而被 runtime 拦截。确认方向后的 `run-playbook --topic-direction-id` 会解析 guide-post 方向 id，把公开方向 payload 写入 workflow payload、response、run payload 和 artifact 的 `topic_selection.direction`，并在 planner 阶段追加 `# XHS Topic Direction Guidance` runtime context，让 drafting backend 按已确认方向的 hook、正文角度、保存工具、评论入口和 `format_recommendation` 生成。
- workflow 会在 drafting 前读取最近 3 条同账号、同 playbook 的 lessons，形成 `# Recent Account Memory` runtime context，提示 drafting backend 避免重复标题形状、开头、热词和收尾。普通心理学另把最近成功 carousel 的**哈希**内页 identity 作为独立 gate，而不是把旧页文案回灌；identity 排除封面，只有完全相同的 canonical inner cards 被拒绝。它由 reservation 防并发，is **committed only after the complete local receipt and asset ledger**；render/manifest/ledger failure、非-carousel exit 会 release，stale lease 可恢复。对 `reddit_curation_daily_post`，memory 注入 prompt 前会隐藏旧帖里的 Reddit/source/翻译痕迹，避免历史样例把已废弃的来源披露写法带回新草稿。
- `run_playbook()` 现在也会在 `.ptsm/agent_runtime/side-effects.json` 下记录成功副作用结果，用于同一 `thread_id` 的安全重放。
- `run_playbook()` 现在可以在真实发布缺图或显式 `--auto-generate-image` 时生成图片，默认写到 `outputs/generated_images/`。普通单图仍按既有策略选择即梦、百炼或本地 `note_card` / `iphone_notes` / `wechat_chat`；operator 的普通帖 `--local-image-style` 仍显式覆盖成该单图路径。若现代心理学 `final_content.image_plan` 携带严格 `role=text_carousel`、`carousel_style=psychology_text_card_v1` 和 `slides`，provider 配置不会接管它：应用层只使用本地 renderer，按 `slides.order` 渲染**一个主题的一组** 4–7 张 1080×1440 PNG，并把 canonical `manifest.json` 与图片原子提交到 content-addressed set 目录。超过 7 页（包括“要 12 张”）不是 batch 参数：caller 必须在 run 前明确选择支持的一组 `one_carousel`，或逐帖确认、独立 run 的 `multiple_posts`；`independent_assets`（8–12 张 **independent image assets**）在当前心理学路径 unsupported，不能通过本 runtime 伪装成前两者。`max_text_units` 仅是每页文字密度。cover 保持低密度，inner cards 只画已验证的短 headline/body lines；不执行第二次模型改写或正文长度切页。
- 心理学 carousel 的完整性在 ledger 与 publisher 前再次检查：manifest、set id、页数、order、filename、regular/readable PNG 和 page/file hashes 必须一致，`generated_image_paths` 的顺序就是发布顺序。发布边界会无符号链接跟随地同时保持整组文件描述符，在全部页面完成哈希后再做集合级 identity/snapshot 终检，避免校验后页时前页被替换。ordinary 与 current v2 learning carousel 都必须先完成 page-aware ledger projection；ordinary inner fingerprint 只在此后 commit 到最近 12 次成功窗口。sealed learning artifact 随后会移除 ledger/path/page text，只保留安全 receipt。全部本地图作为一组跳过去水印；若事务或 ledger 失败，run 以 `psychology_carousel_generation_failed` 完成失败记录，不调用 watermark/publisher，也不留下可发布的部分 ledger projection 或 ready delivery receipt。成功提交后若外部 publish 失败，immutable set 保留供重试。
- deterministic / deepseek drafting backend 现在会读取 playbook prompt、playbook persona prompt、静态 scoped skills，以及 planner 注入的 runtime skill contexts，不再只面向发疯文学。runtime contexts 可能包含本地 format pattern、Reddit/research context、最近账号记忆，以及确认选题后的 `# XHS Topic Direction Guidance`。DeepSeek prompt assembly 会额外注入共享 `xhs_compact_native_v1` 标题/正文合同：标题最多 22 字、优先 12-18 字，以领域适配的具体场景、物件、关系或一句原话切入，避免泛标题；不再把一组跨领域 tension cue 当作统一硬门槛。正文用 2–4 个短节拍完成场景/真人锚点、一个领域可用细节和自然的保存或回复入口，而不是四个独立的文章段落。
- DeepSeek prompt assembly 还会注入正文人味硬约束：正文要先有现场锚点和真人视角，用时间、物件、关系、一句原话、材料、路线或动作开场，少用 `本文`、`本篇`、`建议大家`、`从本质上`、`核心逻辑是`、`总体来说` 这类总述/文章腔；正文还要像朋友安利一个刚发现或刚试出来的东西，少解释多交付，给出一个可抄作业式模板、prompt、清单、句式、判断框架或动作。保存和评论/回复可以自然合在同一句，不能露出内部写作标签或靠通用补字段落凑长度。
- `xhs_trend_scan` 的 runtime context 读取本地 `outputs/artifacts/xhs-pattern-library/current.json` 里的 approved/candidate format patterns；普通 `run-playbook` 不实时搜索小红书，snapshot 缺失时回退静态 skill guidance。显式 fresh research 的 live collection 统一由 `run_playbook` 的 public Topic Radar scan 完成，选定方向进入 workflow 后不会让 `xhs_trend_scan` 再回退到 live MCP。`topic_research` 在普通路径可追加同一份本地 pattern summary；fresh selection 已存在时不再追加竞争性 Topic Radar 方向。
- `reddit_discussion_scan` 的 runtime context 服务 `reddit_curation_daily_post`，优先通过已获批的 Reddit app-only OAuth 读取公开英文讨论的 hot/top 列表；当 OAuth app 创建受阻时，可用 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT` 读取 Reddit public `.json` 列表页作为低频只读 fallback。两种路径都会按 AI 工具焦虑、心理/生活压力和工作流相关性筛选适合中文读者的内部素材。缺少可用 Reddit 环境变量时会注入 `missing_credentials` 上下文，提示配置 public JSON fallback 或按 Reddit Responsible Builder Policy 取得 explicit approval 后配置 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT`。读者可见内容不得暴露 Reddit、subreddit、英文讨论、翻译过程或来源 URL，来源追踪只保留在 runtime context / artifact。
- deterministic drafting backend 可以通过小型 contextual draft helper 为特定 playbook 提供离线 dry-run 草稿，供 harness 和 e2e 测试在没有真实 LLM 调用时验证领域硬约束；当前覆盖现代心理学、武侠人物评述、古诗词金句、AI 科技资讯、每日英语学习、人类丰容实验、世界杯主题和 Reddit英文讨论转译的基础结构。所有 deterministic XHS 标题都要落在 22 字以内，并满足该领域的具体入口/禁用词规则，而不是机械插入同一组张力 cue。AI 科技 deterministic 分支只读取已绑定的 `# AI Tech Evidence Contract`：news 输出 3–5 条编号事实，hands-on 输出可复现任务/观察/局限，fact translation 输出 facts + audience decision；contract 缺失时 fail closed，不退化为泛感受或可复制 prompt。现代心理学 deterministic 分支覆盖职场反刍、亲密关系不确定感、忽冷忽热、社交电量取消局、关系边界、消息压力、数字生活/信息过载、孤独/比较焦虑、三明治拒绝法、睡眠恢复/轻养生/办公室恢复等 lane，避免所有离线样例退化成同一标题形状；其中“他3小时没回消息，我已经想好分手后猫归谁了”这类 scene 会输出 `事实 / 脑补 / 我需要什么`，忽冷忽热 scene 会输出 `事实 / 信号 / 我要不要问清楚`，社交电量取消局 scene 会输出取消局三句，并禁止 `你这边多久能回`、`处理优先级` 等工作式回复口吻或教人失联；睡眠恢复/轻养生 scene 会输出 5 分钟下班信号和身体收口，不给医疗养生建议或睡眠改善承诺。它还会保持标题不暴露心理机制或 `不是你` 句式，把机制名放在场景铺开后轻量出现一次以内，正文控制在 200-380 字，并使用角色/阵营/填空式评论提示。人类丰容 deterministic 分支覆盖桌面/角落、路线/感官、手作/材料流、适我主义/新独居角落等场景；发疯文学 deterministic fallback 也覆盖丝瓜汤式沟通和职场物件发疯样例；世界杯 deterministic 分支覆盖赛前看点、赛后复盘和看球局/球迷氛围三类场景，并禁止输出赌球、盘口、预测比分或伪装内部消息；Reddit英文讨论转译 deterministic 分支要求把外网素材改写成中文热点帖，保留自然可保存的小结和评论区问题，同时禁止读者可见内容泄漏 Reddit/source URL、subreddit、英文讨论、翻译过程或“可收藏小结：”这类内部标签。contextual draft 领域识别只使用明确 playbook/style skill 标记或 scene 语义，不能因为共享 `xhs_image_strategy` catalog 里提到其他领域而误路由。
- 显式注入依赖时，运行时仍兼容 `InMemoryExecutionMemory` 和 `InMemorySaver`。
- 持久 checkpoint 以 `thread_id` 为键保存；复用同一个 `thread_id` 才能跨进程读取同一条执行线程。
- 当前 side-effect ledger 只复用成功 publish 结果，不缓存失败 publish 或只读状态检查。
- planner 现在会把每个激活 skill 的元信息（`activated_skill_details`）和 runtime context 元信息（`runtime_skill_details`）注入 state，供 finalize 写入 artifact 和 harness evals 消费。
- LLM JSON 解析现在对模型把 hashtags 内嵌在 body 中的情况有容错：缺失 `hashtags` key 时从 body 尾部提取并剥离，避免因输出格式微小偏差导致整个 run 失败。
- finalize 现在会把 planner / executor / reflector 的 bounded step evidence 写入 artifact 的 `step_outputs`，包括 selected playbook、prompt refs、attempt count、draft content、reflection decision 和 feedback，供 online evaluation 抽取 phase targets。
- finalize 写入 lessons memory 时会记录 title、image_text、hashtags 和 final_body，供后续 memory 节点做跨帖去重参考。
- deterministic drafting fallback 会消费 recent account memory 做轻量去重；发疯文学和现代心理困境观察都会在近期标题/封面撞车时切换到备用表达，而不是只证明 memory 被读到。
- finalize 现在还会写入 `content_review`，包含生成逻辑、互动/收藏/安全信号、LLM 内容质量门状态和人工确认建议。这个 review 不等于自动发布批准；当前人工调整流程是 operator 基于该说明继续对话修改，而不是进入独立审核队列。
- 对 `human_enrichment_daily_post`，`content_review` 还会写入 `image_form`，记录 3:4 竖版封面、真实创作者封面风格和推荐轮播顺序（封面、原本状态、变量/材料平铺、清单、改变后细节、评论区提问）。该领域当前发布链路仍只自动生成单张封面图；本次自动多图能力明确只扩展 `modern_psychology_post`。
- 当本地 pattern library 命中时，`run-playbook` 会在 response 和 artifact 中写入 `format_patterns_used`，包含 pattern ids、hook archetypes、body structures、image sequences 和 snapshot 来源。人类丰容的 `content_review.image_form` 还会带上 `image_pattern_id`、`carousel_pattern_id`、`carousel_brief` 和封面/清单页文字约束。

## Practical Implications

- lessons memory 现在可以跨 CLI 调用保留，不再只活在单进程里。
- lessons memory 不只是写入；后续同账号同 playbook 运行会在 executor 前回读，并以 runtime context 进入 drafting backend。
- graph checkpoint 现在可跨进程保留，用于后续调试、回读和 thread 续跑。
- publish side effects 现在可按 `thread_id` 去重，避免 resume 或重复调用时再次执行成功 publish。
- planner 现在会把 playbook 的 persona prompt 一起送入 executor，让不同领域的账号口吻保留在版本化资产里，而不是硬编码在 runtime。
- `xhs_trend_scan` 这类动态 research skill 输出现在以独立 `runtime_skill_contents` 进入 drafting backend，不再和静态 `SKILL.md` 文本混在同一个字段里。
- 图片生成现在是发布前的一段显式步骤，会把 prompt、模型、生成路径、`watermark_policy`、`provenance`，以及适用时的 generated image asset ledger 结果写回 artifact，便于后续验收和排障。自动生成图片会更新本地 JSONL `outputs/artifacts/generated-image-assets/assets.jsonl`，记录图片路径、provider/style/model、playbook/account、artifact、image_plan、provenance source 和 hashes。写入前会固定 `base_dir` 与固定 `outputs/artifacts/generated-image-assets` 全部目录句柄，以 `dir_fd` + no-follow 逐级创建/打开，并在加锁后、replace 前和父目录 fsync 后重验整条 name-to-descriptor chain；任一级 symlink、rename 或重建竞态都会使 ledger fail closed。current v2 learning carousel 同样记录 operational ledger；sealed learning artifact/response 不复制该字段或本地路径。ledger 只积累元数据，不复制或提交图片文件。
- 对 psychology text carousel，immutable `manifest.json` 是图片集权威 receipt，JSONL ledger 是按 manifest order 的 page-aware operational projection。ordinary artifact 可见 set/page/path/hash 证据；只有验证后的 ordinary receipt 才可生成 `carousel_delivery.status=ready`，其 `attachments` 必须与 `pages.order` 完全一致，并保留每页 `page_sha256`（canonical visible-page content）与 `file_sha256`（PNG bytes）。PTSM 把这作为外层 relay handoff，不调用外部 chat/IM sender，也不把 ready 表示成 delivered。relay 的 `relay_attempt_id`、ACK/outcome/retry record 是 relay-owned、not a PTSM response schema；PTSM 不写、推断或因其变化而改写 ready receipt。sealed learning artifact 只保留安全的 carousel status、renderer、style、count 与 manifest hash，即使 operational ledger 已成功落盘。
- 图片生成 prompt 现在也会读取 `runtime_skill_contents` 里的实时切口和场景张力，让封面图和正文共享同一层热点上下文。
- 图片生成 prompt 现在也会读取 artifact `content_review.image_form` 中的图片形式摘要；当人类丰容 playbook 提供轮播式建议时，单张封面生成会保留“原本状态、材料平铺、清单、改变后细节”等视觉提示，并明确 AI 生成图只是氛围参考，不应伪装成真实前后证据。
- 本地 note-card renderer 生成 3:4 竖版 PNG，使用已验证的可见短文字绘制，不调用外部图片 API。跨领域单图仍可选择 `wechat_chat`、`iphone_notes`、`note_card` 或 `provider_image`；普通心理学自动路径则使用 `psychology_text_card_v1` 轮播。其 parent plan 精确字段为 `backend/style/role/text_density/max_text_units/cover_text_strategy/reason/prompt_focus/carousel_style/slides`，每个 slide 精确字段为 `slide_id/order/role/headline/body_lines`；页数 4–7、order 从 1 连续、ID 唯一且第一页必须是 `cover_hook`。允许的 inner role 是 `concrete_scene`、`light_mechanism`、`save_tool`、`scope_boundary`、`professional_boundary` 和 `comment_prompt`，所以一个 carousel 始终只解释一个主题。operator 仍可在普通帖通过 `--local-image-style iphone_notes|wechat_chat|note_card` 改走 legacy single cover；learning-series 不允许该覆盖。
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
