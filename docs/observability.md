---
title: PTSM Observability
status: active
owner: ptsm
last_verified: 2026-07-23
source_of_truth: true
related_paths:
  - src/ptsm/infrastructure/observability/run_store.py
  - src/ptsm/infrastructure/evaluations/eval_store.py
  - src/ptsm/application/use_cases/xhs_post_metrics.py
  - src/ptsm/application/use_cases/diagnose_publish.py
  - src/ptsm/application/use_cases/eval_artifact.py
  - src/ptsm/application/use_cases/logs.py
  - src/ptsm/application/use_cases/run_events.py
  - src/ptsm/application/use_cases/runs.py
  - src/ptsm/application/use_cases/harness_report.py
  - src/ptsm/infrastructure/images
  - src/ptsm/infrastructure/xhs_patterns
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/xhs_domain_opportunity.py
  - src/ptsm/application/use_cases/hotspot_discovery.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/domain/ai_tech_content.py
  - src/ptsm/domain/psychology_learning.py
  - src/ptsm/domain/hotspot_routing.py
  - src/ptsm/skills/runtime_context.py
  - src/topic_radar/cli.py
  - src/topic_radar/analysis/evidence.py
  - src/ptsm/plan_runner/runner.py
  - outputs/artifacts
  - outputs/generated_images
  - .ptsm/runs
  - .ptsm/plan_runs
  - .ptsm/evals
---

# Observability

PTSM 当前的观测性核心是本地文件系统里的 run store 和 artifacts，而不是独立 dashboard。

## What Gets Persisted

- `.ptsm/runs/<run_id>/summary.json`
- `.ptsm/runs/<run_id>/events.jsonl`
- `.ptsm/plan_runs/<run_id>.json`
- `.ptsm/plan_runs/<run_id>.evidence.json`
- `outputs/artifacts/*.json`
- `outputs/artifacts/topic-scan-*.json`
- `outputs/artifacts/topic-brief-*.md`
- `outputs/artifacts/topic-radar-history.jsonl`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-*.json`
- `outputs/artifacts/xhs-domain-opportunity/domain-opportunity-*.md`
- `outputs/artifacts/xhs-pattern-library/samples-*.json`
- `outputs/artifacts/xhs-pattern-library/patterns-*.json`
- `outputs/artifacts/xhs-pattern-library/current.json`
- `outputs/artifacts/xhs-post-metrics/metrics.jsonl`
- `outputs/generated_images/*`
- `.ptsm/evals/<eval_run_id>/summary.json`
- `.ptsm/evals/<eval_run_id>/results.jsonl`

## Current Capabilities

- `RunStore.start()` 创建 run summary 和事件流。
- `RunStore.append_event()` 记录步骤事件。
- `RunStore.finish()` 结束并写回 summary。
- workflow artifact 现在会持久化 `activated_skill_details` 和 `runtime_skill_details`，与已有的 `runtime_skill_contents` 一起回答本次运行读了哪些静态 skills 和哪些动态上下文资源。
- workflow artifact 现在还会持久化 `step_outputs`，把 planner、executor、reflector 的关键产物保存成 bounded evidence，供 rule/contract/LLM evaluator 对 step outcome 做评价。
- completed `ai_tech_daily_post` artifact 额外保留一个最小 evidence receipt：`ai_tech_content_mode`、`ai_tech_evidence_manifest` 与 `ai_tech_evidence_gate`。manifest 只含 opaque `source_refs` / `test_evidence_refs` / event fingerprints / 可选 trend IDs，gate 固定记录 draft contract 已通过；它不保存 operator evidence 文件、原始标题、source URL、author、feed ID 或完整 Topic Radar scan。若 custom workflow 的 artifact 不在受控 artifact root、final content 不一致，或含 provenance 字段，应用层会在图片/发布前标为 AI artifact invalid，而不是 merge receipt。
- completed `modern_psychology_post` learning-series artifact 额外保留 `psychology_learning_mode`、`psychology_learning_series_id`、`psychology_learning_curriculum_version`、`psychology_learning_lesson_id`、`psychology_learning_lesson_number`、opaque `psychology_learning_evidence_manifest` 和通过的 `psychology_learning_gate`。它不保留自由 scene、原始研究链接、作者或课程外心理学主张；`psychology.learning_receipt` 可离线重建 catalog 并审计 the entire artifact，而不只检查 receipt。受控 artifact root 内若被 custom workflow 写入 raw provenance，应用层会先删除它，再返回 invalid 状态，避免留下可被后续流程误用的文件。
- artifact 写入会保留同一个 `run_key` 下的多次 dry-run；当目标文件已存在时追加数字后缀，避免内容实验批量生成时覆盖前一个候选。
- Topic Radar scan artifact 现在是 schema v2：`scan_quality` 明确记录 `completed` / `partial` / `insufficient_evidence`，`platform_errors` 记录安全化 collector/LLM diagnostics（包括 isolated server 的工具发现 timeout），`evidence` 记录 canonical source rows 和平台内归一化热度，`topic_clusters` 记录保守 event clusters。LLM prompt 在 48 条 evidence / 24 个 cluster 上限内 round-robin 覆盖平台，且 cluster 只引用 prompt 内可见的 evidence。`recommended_angles` 带 `cluster_id`、`event_fingerprint`、`evidence_ids`、`angle_signature`、`novelty_state` 和 `ranking_score`，因此推荐、跨平台信号和 scan-quality 都可从同一 artifact 回溯。跨平台信号只记录真实平台共现；没有时序观测时 `velocity` 为 `unknown`，不得由单次热度快照推断加速。
- Topic Radar 同日重跑会为 JSON/Markdown 使用成对 suffix，避免覆盖旧 artifact；`outputs/artifacts/topic-radar-history.jsonl` append-only 记录已选 event+angle 的近期 cooldown。它是推荐去重依据，不是长期热度 dashboard。
- fresh Topic Radar 选择写入 PTSM response/run/artifact 的 `topic_selection` 时，只保留选定角度、讨论诱因、构造场景、`cluster_id`、`event_fingerprint`、`evidence_ids`、scan quality、platform diagnostics 和 artifact/report receipt。receipt 必须来自本次 scan 且指向可读 artifact；终端 `scan_summary`、原始 source title、author、URL、feed ID、token 不进入 PTSM drafting context 或 selection metadata。
- `xhs-domain-opportunity` artifact 记录每个 keyword 的去重后 `sample_count`、`duplicate_sample_count`、partial errors 和状态。去重优先以 `feed_id` 为准；完整 title+author 只桥接缺 ID 的同一观察到首个真实 ID，之后同 title/author 的不同真实 ID 仍独立；一旦可见身份已有多个真实 ID，后来的缺 ID 样本也保持 unresolved，标题单独不作为 identity。ASCII `,`、中文 `，` 可分隔显式关键词；separator-only 输入会在采集前被拒绝，不存在默认关键词 fallback。只有至少一个成功 unique sample 才会出现 evidence-backed domain recommendation；全空/全错为 `insufficient_evidence`，不能从静态 mapping 推导 ranked opportunity。
- finished run summary 现在也会写入 `activated_skills`、`activated_skill_details` 和 `runtime_skill_details`，便于先查 `.ptsm/runs/*/summary.json`，只有需要全文时再回读 artifact。
- `run_logs()` 支持按 `run_id` 或 artifact 反查运行记录。
- `RunStore.list_runs()` 和 `ptsm runs` 支持按账号、平台、playbook、状态筛选最近运行。
- `RunStore.list_events()`、`RunStore.aggregate_events()` 和 `ptsm run-events` 支持按 run 维度和 event 维度过滤最近事件，并做轻量聚合。
- `run-plan` 现在会把 verify 命令的 attempt history、stdout/stderr 和 normalized `failure_reason` 落成 sibling evidence artifact，便于审计和 resume 后回看。
- `ptsm plan-runs` 支持按 `status`、`failure_reason`、`plan_path` 查询最近 plan-run evidence。
- real publish artifacts now persist the requested publish payload, including `visibility`, and will retain `post_id` / `post_url` when upstream XiaoHongShu MCP responses expose identifiers.
- `xhs-check-publish` now has a narrow public-post fallback: when upstream publish responses omit identifiers, it can use MCP `search_feeds` to verify a post only if the requested visibility is not `仅自己可见` and an exact title match is found.
- `run-fengkuang --wait-for-publish-status` now gives that public `search_feeds` fallback a short bounded retry window, so posts that become searchable a few seconds after publish can still settle into `published_search_verified` during the initial run.
- `doctor` 现在会额外报告 harness drift，包括 stale active docs、orphan plan-run evidence 和 malformed run dirs。
- `ptsm gc` 默认以 dry-run 方式列出可安全清理的 completed run artifacts 和 orphan evidence，`--apply` 才会删除。
- `ptsm harness-evals` 会把 runs、events 和 plan-run evidence 聚成一个本地 eval 视图，输出 completion rate、status breakdown、failure reason breakdown 和 recent failures。
- `ptsm harness-evals` 现在还会输出 `skills` 视图，聚合每个 activated skill 的 runs、completed、completion_rate 和 `runtime_context_runs`，用于回答“某个 skill 打开以后运行是否更稳”这类局部问题。
- `ptsm harness-report` 会把 `doctor`、`gc` 和 `harness-evals` 合成一个本地快照，并支持对 stale docs、gc candidate、run completion rate、plan-run completion rate 做 threshold 检查。
- `ptsm diagnose-publish` 会把 `doctor`、run logs、artifact metadata 和 `xhs-check-publish` 的结果组合成一次只读诊断，给出 `likely_cause`、`evidence` 和 `next_actions`。
- real publish 或显式 `--auto-generate-image` 运行现在会把 `image_generation` metadata 落进 artifact，包含 provider、model/style、prompt 或本地渲染输入、`generated_image_paths`，以及从 `runtime_skill_contents` 提炼出的 `runtime_context_summary`；当前 provider 可为 `jimeng`、`bailian` 或本地 `local_note_card`。生成图还会记录 `image_generation.watermark_policy`，其中 `requested` 为 `no_provider_watermark`，`provider_controls` 记录百炼 `watermark=false` / negative prompt 合并、即梦 `logo_info.add_logo=false`，或本地 renderer 的 runtime policy。本地 renderer 还会记录 `image_generation.provenance.source == "ptsm_local_renderer"` 和 `watermark_removal == "skip"`；`style` 会记录为 `xhs_note_card_v1`、`iphone_notes_v1` 或 `wechat_chat_v1`，用于复盘本次封面采用了默认笔记卡、iPhone 记事本或微信聊天记录样式。若草稿或 operator 指定了图片策略，artifact 还会写入 `content_review.image_plan` 和 `image_generation.image_plan`，记录 source、requested_backend、selected_backend、requested_style、role、text_density、max_text_units、cover_text_strategy、reason、fallback_reason 和可选 `golden_line` 等字段，便于复盘封面是低密度钩子、保存工具、评论触发还是证据/场景图。`wechat_chat` 本地渲染输入还会保留 `theme`、`chat_title` / `conversation_title`、`chat_times`、`status_time`、`show_avatars` 和结构化/多行聊天内容；缺省时间和 generic nickname 会由 renderer 确定性生成，方便确认最终图片不是固定时间或意外回退到默认气泡。
- 每次 PTSM 自动生成图片还会把 `image_generation.asset_ledger` 写入 artifact，指向本地 append-only JSONL `outputs/artifacts/generated-image-assets/assets.jsonl`。ledger entry 记录 image path、provider/style/model、playbook/account、artifact path、image_plan、provenance source 和 prompt hash，用于后续人工积累、筛选和复盘，不复制图片字节。
- real publish 的 `watermark_removal` 字段现在按 provenance 记录：本地 renderer 图片会写 `status=skipped` / `policy=skipped_for_local_renderer`，并直接把原图传给发布器；provider/LLM 生成图和手动图片会把去水印结果写入 artifact，并且发布器收到清理后的图片路径。dry-run 只有在 `WATERMARK_REMOVAL_ENABLED=true` 时才预览 provider/manual 图片清理。
- `collect-xhs-patterns` 会把 XHS 原始样本写入 `outputs/artifacts/xhs-pattern-library/samples-*.json`，包含关键词级成功/失败、互动指标、feed identifiers、封面宽高和采集时间；失败关键词留在 `keyword_errors`，不会覆盖已成功样本。
- `analyze-xhs-patterns` 会把样本蒸馏为 `patterns-*.json` 和 `current.json`。生成链路命中本地 snapshot 时，artifact 和 CLI 响应会写入 `format_patterns_used`，记录 pattern ids、hook archetypes、body structures、image sequences、freshness 和来源 snapshot。
- `ptsm eval-artifact --artifact <path>` 对单个 artifact 运行所有确定性 rule/contract evaluator，将结构化 EvalResult 写入 `.ptsm/evals/<eval_run_id>/results.jsonl`，并返回 eval run summary（status、counts、gate）。
- `eval-artifact` 现在会读取 playbook-local `evaluation.yaml`，对已有 `node_contracts` 做确定性 contract enforcement；缺失 playbook evaluation contract 时仍保持非 fatal，便于迁移。当前 executor 约束支持 anti-generic `title_must_not_equal_any` / `image_text_must_not_equal_any`、`body_min_chars` / `body_max_chars`、`body_must_include_comment_prompt_any`、`body_must_include_save_trigger_any`、必需/禁用正文词和必需标签，也会把 `变体要求`、`comment_chain`、`save_tool`、`identity_conflict` 这类实验操作指令当作正文泄漏来拦截。
- AI 科技 artifact 还会运行 `ai_tech.evidence_receipt`：它离线检查三件事是否一致——mode、opaque manifest 与 `ai_tech_draft_contract` gate，并依 mode 审计新闻条目数量、hands-on test ref 或事实转译的 source ref。它是回归/审计层；运行时 preflight、draft retry 与 publish 前复核才是阻断门禁。失败说明使用固定诊断，不回显可能带 provenance 的历史 artifact 内容。
- LLM judge adapter 默认不会被 `eval-artifact` 和 `harness-check` 调用，因此默认 harness 不需要网络或模型凭据。显式启用后，executor content-quality judge 会输出 `hook_specificity`、`save_trigger`、`comment_trigger`、`platform_native_format`、`persona_fit`、`safety` 六个标签和 `rewrite_hint`；当前 XHS 内容质量 playbook 将该 judge 配置为 `required`，失败会进入 `required_failed`。
- 运行时 artifact 现在会持久化 `content_review`，记录生成逻辑、质量信号、LLM 内容质量门状态和人工确认建议；它是发布前人工确认材料，不是自动发布授权。
- `human_enrichment_daily_post` 的 `content_review` 还会持久化 `image_form`，包含 `primary_ratio=3:4`、封面风格、推荐轮播顺序、`carousel_brief`、封面/清单文字约束，以及命中的 `image_pattern_id` / `carousel_pattern_id`。这个字段用于人工 review 与图片生成 prompt 提示，不改变 `final_content.v1` 的必需字段，也不代表已经自动生成多图轮播。
- `EvalStore` 持久化 eval runs：`.ptsm/evals/<eval_run_id>/summary.json` + `results.jsonl`，支持 `list_eval_runs()` 和 `read_results()` 查询。
- `EvalStore` 的 summary source 现在记录 run/account/platform/playbook scope metadata，便于 scoped harness views 只聚合相关 eval runs。
- `harness-evals` 现在聚合并报告 eval results：eval run 总数、按 status 和 suite 分布、按 passed/failed/warnings/errors 汇总，并区分 `required_failed` 和 `warning_failed`。
- `harness-report` 支持 `max_required_eval_failures` 阈值检查，可在 CI 或本地 gate 中对确定性 evaluator 失败做门槛控制。
- `xhs-record-metrics` 会把人工或只读收集到的小红书单帖表现追加到 `outputs/artifacts/xhs-post-metrics/metrics.jsonl`。记录会读取原始 run artifact，带上 `playbook_id`、`account_id`、`topic_selection.topic_direction_id`、标题、封面文案、图片样式、发布标识和 `2h` / `24h` / `72h` checkpoint，并计算 `interaction_score = likes + collects*2 + comments*4 + shares*6`、`interaction_rate` 和 `like_rate`。
- `xhs-record-metrics` 对 learning-series artifact 会先重建并验证 closed receipt，才写入 `psychology_learning_mode`、`psychology_learning_series_id`、`psychology_learning_curriculum_version`、`psychology_learning_lesson_id` 和 lesson number；这些是课程内容实验标签，不追踪读者个人学习进度。partial 或 tampered receipt 不会制造课程 cohort。
- 同一 artifact + checkpoint 的 metrics record 会以最新值 upsert，而不是向 JSONL 追加重复观测；已有 post id 时则按 platform/account/post/checkpoint 去重。这样更正 24h 数字不会抬高同一课的样本量。
- `xhs-metrics-report` 会按 `topic_direction_id`、`image_style`、`psychology_learning_series_id`、`psychology_learning_curriculum_version`、`psychology_learning_lesson_id`、`checkpoint`、`account_id` 或 `playbook_id` 聚合 metrics JSONL。按课程维度报告时只取已验证的 learning rows，普通心理学场景帖不会形成 `unknown` cohort。它是本地实验读数，不自动证明选题胜出；少于 3 条的 group 标记为 `needs_more_data`。

## Current Limits

- 只有轻量聚合分析层，还没有时序报表或 dashboard。
- 只有本地 JSONL 级 post metrics 汇总，还没有跨账号 dashboard 或自动趋势告警。
- 没有 traces/metrics dashboard。
- 现在已经比“纯文件可读”更进一步，但还不是 fully agent-queryable observability surface。
- 现在的 cleanup 仍是人工触发 CLI，不是后台定时回收。
- 现在的 eval surface 仍然是本地只读 JSON 汇总，不是持续回归系统或外部 dashboard。
- skill-level eval 目前只按 run summary 聚合，不会解析 draft 质量、人工评分或更细颗粒度 step outcome。
- LLM judge 目前支持 DeepSeek-backed backend 和 fake-backend tests；默认 harness 仍不主动调用 LLM。尚未完成离线校准集；当前人审方式是读取 artifact/CLI 响应里的 `content_review`，再通过 operator 对话提出调整，不计划单独建设人工 review 队列或操作台。
- 现在的 report surface 仍是本地单次 snapshot，不是长期历史报表或外部告警系统。
- 现在的 publish diagnostic 仍然是单次 case diagnosis，不是自动批量归因或跨运行统计。
- `仅自己可见` 的帖子如果上游仍未回传 `post_id/post_url`，当前工具链仍然无法自动核验，只能人工确认或等待上游补齐标识。

## Related Entry Points

- 存储实现: [`src/ptsm/infrastructure/observability/run_store.py`](../src/ptsm/infrastructure/observability/run_store.py)
- plan-runner evidence: [`src/ptsm/plan_runner/runner.py`](../src/ptsm/plan_runner/runner.py)
- plan-run evidence query: [`src/ptsm/application/use_cases/plan_runs.py`](../src/ptsm/application/use_cases/plan_runs.py)
- harness drift / gc: [`src/ptsm/application/use_cases/harness_gc.py`](../src/ptsm/application/use_cases/harness_gc.py)
- harness evals: [`src/ptsm/application/use_cases/harness_evals.py`](../src/ptsm/application/use_cases/harness_evals.py)
- harness report: [`src/ptsm/application/use_cases/harness_report.py`](../src/ptsm/application/use_cases/harness_report.py)
- publish diagnostics: [`src/ptsm/application/use_cases/diagnose_publish.py`](../src/ptsm/application/use_cases/diagnose_publish.py)
- post metrics loop: [`src/ptsm/application/use_cases/xhs_post_metrics.py`](../src/ptsm/application/use_cases/xhs_post_metrics.py)
- image backend: [`src/ptsm/infrastructure/images/`](../src/ptsm/infrastructure/images/)
- 日志读取: [`src/ptsm/application/use_cases/logs.py`](../src/ptsm/application/use_cases/logs.py)
- 事件查询: [`src/ptsm/application/use_cases/run_events.py`](../src/ptsm/application/use_cases/run_events.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 运维命令索引: [`operations.md`](operations.md)

## Hotspot Discovery Receipts

`hotspot-discovery` 会在 `outputs/artifacts/hotspot-discovery/` 写 JSON 与 Markdown
routing receipt，并保留来源 scan artifact/report path、scan quality、platform diagnostics、
cluster id、event fingerprint、evidence ids/count 和平台集合。默认按 score 返回前 12 个，receipt
以 `eligible_hotspot_count`、`returned_hotspot_count`、`hotspot_limit` 明示是否截断；该 limit 不是
赛道筛选。`route_status_counts` 覆盖完整已验证 cluster 集合的路由分布，`routed_hotspots` 是与主 Top-N 不重复的
补充已有-playbook 候选；每行至少引入一个未展示 playbook，`ambiguous` 行仍保留完整候选集，并由自身的 limit/count 字段说明范围；它不改变全平台排名。`completed`、`partial`、
`insufficient_evidence` 原样透传；partial 不能被观测面或 operator 文案描述为完整全平台结果。
未知 scan quality 会 fail closed 为 `insufficient_evidence`；cluster 的代表标题必须可由 receipt 内的 evidence
title 追溯，非有限 score 归零，避免写出无效 JSON 或将损坏输入当作可信热点。

receipt 只保存 `operator_headline` 作为人读热点标签，绝不复制 raw evidence、作者、URL、
feed id 或 token。路由候选只包含现有 playbook id、matched terms、静态 generation seed 和
下一步；未映射的 `new_domain_candidate` 是 review signal，不是自动变更事件。
