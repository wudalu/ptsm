---
title: PTSM Operations
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - docs/operations/local-runbook.md
  - docs/operations/task-completion-automation.md
  - src/ptsm/interfaces/cli/main.py
---

# Operations

这个页面只做操作索引，不重复复制 runbook 内容。

## Primary Runbooks

- 本地运行与排障: [`docs/operations/local-runbook.md`](operations/local-runbook.md)
- 任务完成后的自动校验: [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md)

## Stable Operator Commands

- `uv run python -m ptsm.bootstrap --help`
- `uv run python -m ptsm.bootstrap doctor`
- `uv run python -m ptsm.bootstrap logs --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap runs --account-id <account_id> --status completed`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json`

## Usage Notes

- 默认校验门禁优先使用 `pytest` 和 `doctor`。
- 浏览器动作保留为人工或条件触发，不应成为默认无人值守 gate。
- 更细的触发策略以 [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md) 为准。
