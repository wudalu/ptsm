---
title: PTSM Docs Index
status: active
owner: ptsm
last_verified: 2026-04-22
source_of_truth: true
related_paths:
  - README.md
  - docs/harness-engineering.md
  - docs/xhs-topics/index.md
  - docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md
  - docs/plans/2026-04-17-agent-readable-docs-map.md
  - docs/plans/2026-04-17-harness-engineering-first-stage.md
  - src/ptsm
---

# PTSM Docs Index

这是给人和 agent 共用的文档入口。先读这里，再按链接深入，不要把历史计划或零散研究笔记直接当成当前事实。

## Current Source Of Truth

- 项目基线: [`README.md`](../README.md)
- harness engineering 对照与落地: [`harness-engineering.md`](harness-engineering.md)
- 当前平台化实施真源: [`docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md`](plans/2026-03-24-ptsm-agent-platform-rebaseline.md)
- 本次文档治理实施计划: [`docs/plans/2026-04-17-agent-readable-docs-map.md`](plans/2026-04-17-agent-readable-docs-map.md)
- harness engineering 第一阶段计划: [`docs/plans/2026-04-17-harness-engineering-first-stage.md`](plans/2026-04-17-harness-engineering-first-stage.md)

## Core Maps

- Harness engineering 映射: [`harness-engineering.md`](harness-engineering.md)
- 架构地图: [`architecture.md`](architecture.md)
- 运行时地图: [`runtime.md`](runtime.md)
- Playbook 地图: [`playbooks.md`](playbooks.md)
- Skill 地图: [`skills.md`](skills.md)
- 小红书主题索引: [`xhs-topics/index.md`](xhs-topics/index.md)
- 观测性地图: [`observability.md`](observability.md)
- 操作文档索引: [`operations.md`](operations.md)
- Shared contracts 索引: [`shared-contracts.md`](shared-contracts.md)

## Reading Order

1. 先看 [`architecture.md`](architecture.md) 了解仓库分层和目录职责。
2. 再看 [`runtime.md`](runtime.md) 理解 `plan -> execute -> reflect` 运行时。
3. 做内容与策略改动时，先看 [`playbooks.md`](playbooks.md) 和 [`skills.md`](skills.md)，再按需进入 [`xhs-topics/index.md`](xhs-topics/index.md)。
4. 排查运行结果时，转到 [`observability.md`](observability.md) 和 [`operations.md`](operations.md)。
5. 设计未来扩展合同时，转到 [`shared-contracts.md`](shared-contracts.md)。

## Historical Context

- Greenfield 背景文档: [`docs/plans/2026-03-14-ptsm-agent-platform.md`](plans/2026-03-14-ptsm-agent-platform.md)
- 研究笔记目录: [`docs/research/`](research/)
- 历史实施计划目录: [`docs/plans/`](plans/)

历史文档保留参考价值，但如果与代码或 `README.md` 冲突，以代码和当前 source-of-truth 文档为准。
