---
title: PTSM Observability
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - src/ptsm/infrastructure/observability/run_store.py
  - src/ptsm/application/use_cases/logs.py
  - src/ptsm/application/use_cases/runs.py
  - outputs/artifacts
  - .ptsm/runs
---

# Observability

PTSM 当前的观测性核心是本地文件系统里的 run store 和 artifacts，而不是独立 dashboard。

## What Gets Persisted

- `.ptsm/runs/<run_id>/summary.json`
- `.ptsm/runs/<run_id>/events.jsonl`
- `outputs/artifacts/*.json`

## Current Capabilities

- `RunStore.start()` 创建 run summary 和事件流。
- `RunStore.append_event()` 记录步骤事件。
- `RunStore.finish()` 结束并写回 summary。
- `run_logs()` 支持按 `run_id` 或 artifact 反查运行记录。
- `RunStore.list_runs()` 和 `ptsm runs` 支持按账号、平台、playbook、状态筛选最近运行。

## Current Limits

- 没有聚合分析层。
- 没有跨账号指标报表。
- 没有 traces/metrics dashboard。
- 现在已经比“纯文件可读”更进一步，但还不是 fully agent-queryable observability surface。

## Related Entry Points

- 存储实现: [`src/ptsm/infrastructure/observability/run_store.py`](../src/ptsm/infrastructure/observability/run_store.py)
- 日志读取: [`src/ptsm/application/use_cases/logs.py`](../src/ptsm/application/use_cases/logs.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 运维命令索引: [`operations.md`](operations.md)
