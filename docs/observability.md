---
title: PTSM Observability
status: active
owner: ptsm
last_verified: 2026-04-18
source_of_truth: true
related_paths:
  - src/ptsm/infrastructure/observability/run_store.py
  - src/ptsm/application/use_cases/logs.py
  - src/ptsm/application/use_cases/run_events.py
  - src/ptsm/application/use_cases/runs.py
  - src/ptsm/plan_runner/runner.py
  - outputs/artifacts
  - .ptsm/runs
  - .ptsm/plan_runs
---

# Observability

PTSM 当前的观测性核心是本地文件系统里的 run store 和 artifacts，而不是独立 dashboard。

## What Gets Persisted

- `.ptsm/runs/<run_id>/summary.json`
- `.ptsm/runs/<run_id>/events.jsonl`
- `.ptsm/plan_runs/<run_id>.json`
- `.ptsm/plan_runs/<run_id>.evidence.json`
- `outputs/artifacts/*.json`

## Current Capabilities

- `RunStore.start()` 创建 run summary 和事件流。
- `RunStore.append_event()` 记录步骤事件。
- `RunStore.finish()` 结束并写回 summary。
- `run_logs()` 支持按 `run_id` 或 artifact 反查运行记录。
- `RunStore.list_runs()` 和 `ptsm runs` 支持按账号、平台、playbook、状态筛选最近运行。
- `RunStore.list_events()`、`RunStore.aggregate_events()` 和 `ptsm run-events` 支持按 run 维度和 event 维度过滤最近事件，并做轻量聚合。
- `run-plan` 现在会把 verify 命令的 attempt history、stdout/stderr 和 normalized `failure_reason` 落成 sibling evidence artifact，便于审计和 resume 后回看。
- `ptsm plan-runs` 支持按 `status`、`failure_reason`、`plan_path` 查询最近 plan-run evidence。
- `doctor` 现在会额外报告 harness drift，包括 stale active docs、orphan plan-run evidence 和 malformed run dirs。
- `ptsm gc` 默认以 dry-run 方式列出可安全清理的 completed run artifacts 和 orphan evidence，`--apply` 才会删除。

## Current Limits

- 只有轻量聚合分析层，还没有时序报表或 dashboard。
- 没有跨账号指标报表。
- 没有 traces/metrics dashboard。
- 现在已经比“纯文件可读”更进一步，但还不是 fully agent-queryable observability surface。
- 现在的 cleanup 仍是人工触发 CLI，不是后台定时回收。

## Related Entry Points

- 存储实现: [`src/ptsm/infrastructure/observability/run_store.py`](../src/ptsm/infrastructure/observability/run_store.py)
- plan-runner evidence: [`src/ptsm/plan_runner/runner.py`](../src/ptsm/plan_runner/runner.py)
- plan-run evidence query: [`src/ptsm/application/use_cases/plan_runs.py`](../src/ptsm/application/use_cases/plan_runs.py)
- harness drift / gc: [`src/ptsm/application/use_cases/harness_gc.py`](../src/ptsm/application/use_cases/harness_gc.py)
- 日志读取: [`src/ptsm/application/use_cases/logs.py`](../src/ptsm/application/use_cases/logs.py)
- 事件查询: [`src/ptsm/application/use_cases/run_events.py`](../src/ptsm/application/use_cases/run_events.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 运维命令索引: [`operations.md`](operations.md)
