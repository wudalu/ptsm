---
title: PTSM Observability
status: active
owner: ptsm
last_verified: 2026-05-17
source_of_truth: true
related_paths:
  - src/ptsm/infrastructure/observability/run_store.py
  - src/ptsm/infrastructure/evaluations/eval_store.py
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
- `outputs/artifacts/xhs-pattern-library/samples-*.json`
- `outputs/artifacts/xhs-pattern-library/patterns-*.json`
- `outputs/artifacts/xhs-pattern-library/current.json`
- `outputs/generated_images/*`
- `.ptsm/evals/<eval_run_id>/summary.json`
- `.ptsm/evals/<eval_run_id>/results.jsonl`

## Current Capabilities

- `RunStore.start()` 创建 run summary 和事件流。
- `RunStore.append_event()` 记录步骤事件。
- `RunStore.finish()` 结束并写回 summary。
- workflow artifact 现在会持久化 `activated_skill_details` 和 `runtime_skill_details`，与已有的 `runtime_skill_contents` 一起回答本次运行读了哪些静态 skills 和哪些动态上下文资源。
- workflow artifact 现在还会持久化 `step_outputs`，把 planner、executor、reflector 的关键产物保存成 bounded evidence，供 rule/contract/LLM evaluator 对 step outcome 做评价。
- artifact 写入会保留同一个 `run_key` 下的多次 dry-run；当目标文件已存在时追加数字后缀，避免内容实验批量生成时覆盖前一个候选。
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
- real publish 或显式 `--auto-generate-image` 运行现在会把 `image_generation` metadata 落进 artifact，包含 provider、model/style、prompt 或本地渲染输入、`generated_image_paths`，以及从 `runtime_skill_contents` 提炼出的 `runtime_context_summary`；当前 provider 可为 `jimeng`、`bailian` 或本地 `local_note_card`。本地 renderer 的 `style` 会记录为 `xhs_note_card_v1`、`iphone_notes_v1` 或 `wechat_chat_v1`，用于复盘本次封面采用了默认笔记卡、iPhone 记事本或微信聊天记录样式。
- `collect-xhs-patterns` 会把 XHS 原始样本写入 `outputs/artifacts/xhs-pattern-library/samples-*.json`，包含关键词级成功/失败、互动指标、feed identifiers、封面宽高和采集时间；失败关键词留在 `keyword_errors`，不会覆盖已成功样本。
- `analyze-xhs-patterns` 会把样本蒸馏为 `patterns-*.json` 和 `current.json`。生成链路命中本地 snapshot 时，artifact 和 CLI 响应会写入 `format_patterns_used`，记录 pattern ids、hook archetypes、body structures、image sequences、freshness 和来源 snapshot。
- `ptsm eval-artifact --artifact <path>` 对单个 artifact 运行所有确定性 rule/contract evaluator，将结构化 EvalResult 写入 `.ptsm/evals/<eval_run_id>/results.jsonl`，并返回 eval run summary（status、counts、gate）。
- `eval-artifact` 现在会读取 playbook-local `evaluation.yaml`，对已有 `node_contracts` 做确定性 contract enforcement；缺失 playbook evaluation contract 时仍保持非 fatal，便于迁移。当前 executor 约束支持 anti-generic `title_must_not_equal_any` / `image_text_must_not_equal_any`、`body_min_chars` / `body_max_chars`、`body_must_include_comment_prompt_any`、`body_must_include_save_trigger_any`、必需/禁用正文词和必需标签，也会把 `变体要求`、`comment_chain`、`save_tool`、`identity_conflict` 这类实验操作指令当作正文泄漏来拦截。
- LLM judge adapter 默认不会被 `eval-artifact` 和 `harness-check` 调用，因此默认 harness 不需要网络或模型凭据。显式启用后，executor content-quality judge 会输出 `hook_specificity`、`save_trigger`、`comment_trigger`、`platform_native_format`、`persona_fit`、`safety` 六个标签和 `rewrite_hint`；当前 XHS 内容质量 playbook 将该 judge 配置为 `required`，失败会进入 `required_failed`。
- 运行时 artifact 现在会持久化 `content_review`，记录生成逻辑、质量信号、LLM 内容质量门状态和人工确认建议；它是发布前人工确认材料，不是自动发布授权。
- `human_enrichment_daily_post` 的 `content_review` 还会持久化 `image_form`，包含 `primary_ratio=3:4`、封面风格、推荐轮播顺序、`carousel_brief`、封面/清单文字约束，以及命中的 `image_pattern_id` / `carousel_pattern_id`。这个字段用于人工 review 与图片生成 prompt 提示，不改变 `final_content.v1` 的必需字段，也不代表已经自动生成多图轮播。
- `EvalStore` 持久化 eval runs：`.ptsm/evals/<eval_run_id>/summary.json` + `results.jsonl`，支持 `list_eval_runs()` 和 `read_results()` 查询。
- `EvalStore` 的 summary source 现在记录 run/account/platform/playbook scope metadata，便于 scoped harness views 只聚合相关 eval runs。
- `harness-evals` 现在聚合并报告 eval results：eval run 总数、按 status 和 suite 分布、按 passed/failed/warnings/errors 汇总，并区分 `required_failed` 和 `warning_failed`。
- `harness-report` 支持 `max_required_eval_failures` 阈值检查，可在 CI 或本地 gate 中对确定性 evaluator 失败做门槛控制。

## Current Limits

- 只有轻量聚合分析层，还没有时序报表或 dashboard。
- 没有跨账号指标报表。
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
- image backend: [`src/ptsm/infrastructure/images/`](../src/ptsm/infrastructure/images/)
- 日志读取: [`src/ptsm/application/use_cases/logs.py`](../src/ptsm/application/use_cases/logs.py)
- 事件查询: [`src/ptsm/application/use_cases/run_events.py`](../src/ptsm/application/use_cases/run_events.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 运维命令索引: [`operations.md`](operations.md)
