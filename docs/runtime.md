---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/agent_runtime/graph
  - src/ptsm/agent_runtime/nodes
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/infrastructure/memory/store.py
---

# Runtime

当前运行时围绕 `plan -> execute -> reflect -> finalize` 组织，并由应用层用例负责把账号、playbook 和发布链路拼起来。

## Main Flow

1. `run_playbook()` 接收 `PlaybookRequest`，解析账号和 playbook。
2. `build_fengkuang_workflow()` 组装 LangGraph 图。
3. graph 依次运行 ingest、planner、executor、reflector、finalize。
4. finalize 写入 artifact 和执行 lessons memory。
5. 应用层根据结果决定是否发布、查状态、开浏览器。

## Current Runtime Facts

- 当前兼容入口仍是 `build_fengkuang_workflow()`。
- 运行结果会落到 artifact，并写入本地 run store。
- 长期 memory 目前仍是 `InMemoryExecutionMemory`。
- checkpoint 目前仍是 `InMemorySaver`，不支持跨进程恢复。

## Practical Implications

- 单次命令执行内可以复用 graph 状态。
- 跨 CLI 调用不能依赖 checkpoint 或 memory 自动恢复。
- 文档和计划里提到的 thread resume / cross-thread lookup 仍属于下一阶段能力。

## Operator Entry Points

- 用例入口: [`src/ptsm/application/use_cases/run_playbook.py`](../src/ptsm/application/use_cases/run_playbook.py)
- 运行时入口: [`src/ptsm/agent_runtime/runtime.py`](../src/ptsm/agent_runtime/runtime.py)
- 内存适配: [`src/ptsm/infrastructure/memory/store.py`](../src/ptsm/infrastructure/memory/store.py)
- 发布后检查: [`src/ptsm/application/use_cases/xhs_publish_status.py`](../src/ptsm/application/use_cases/xhs_publish_status.py)
