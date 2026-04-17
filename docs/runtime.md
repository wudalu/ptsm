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
  - src/ptsm/application/use_cases/runs.py
  - src/ptsm/infrastructure/memory/checkpoint.py
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
- `run_playbook()` 默认会在 `.ptsm/agent_runtime/` 下创建持久 execution memory 和 checkpoint。
- 显式注入依赖时，运行时仍兼容 `InMemoryExecutionMemory` 和 `InMemorySaver`。
- 持久 checkpoint 以 `thread_id` 为键保存；复用同一个 `thread_id` 才能跨进程读取同一条执行线程。

## Practical Implications

- lessons memory 现在可以跨 CLI 调用保留，不再只活在单进程里。
- graph checkpoint 现在可跨进程保留，用于后续调试、回读和 thread 续跑。
- 当前仍没有更高阶的 cross-thread lookup、状态压缩或远端 state backend。

## Operator Entry Points

- 用例入口: [`src/ptsm/application/use_cases/run_playbook.py`](../src/ptsm/application/use_cases/run_playbook.py)
- 运行时入口: [`src/ptsm/agent_runtime/runtime.py`](../src/ptsm/agent_runtime/runtime.py)
- checkpoint 适配: [`src/ptsm/infrastructure/memory/checkpoint.py`](../src/ptsm/infrastructure/memory/checkpoint.py)
- 内存适配: [`src/ptsm/infrastructure/memory/store.py`](../src/ptsm/infrastructure/memory/store.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 发布后检查: [`src/ptsm/application/use_cases/xhs_publish_status.py`](../src/ptsm/application/use_cases/xhs_publish_status.py)
