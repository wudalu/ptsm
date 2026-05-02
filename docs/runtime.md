---
title: PTSM Runtime
status: active
owner: ptsm
last_verified: 2026-05-02
source_of_truth: true
related_paths:
  - src/ptsm/agent_runtime/runtime.py
  - src/ptsm/agent_runtime/graph
  - src/ptsm/agent_runtime/nodes
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/runs.py
  - src/ptsm/infrastructure/llm
  - src/ptsm/infrastructure/images
  - src/ptsm/infrastructure/memory/checkpoint.py
  - src/ptsm/infrastructure/memory/store.py
---

# Runtime

当前运行时围绕 `plan -> execute -> reflect -> finalize` 组织，并由应用层用例负责把账号、playbook 和发布链路拼起来。

## Main Flow

1. `run_playbook()` 接收 `PlaybookRequest`，解析账号和 playbook。
2. `build_playbook_workflow()` 按所选 playbook/domain 组装 LangGraph 图。
3. graph 依次运行 ingest、planner、executor、reflector、finalize。
4. finalize 写入 artifact 和执行 lessons memory。
5. 应用层根据结果决定是否生成发布图片、发布、查状态、开浏览器。

## Current Runtime Facts

- 当前通用运行时入口是 `build_playbook_workflow()`，`build_fengkuang_workflow()` 只是兼容 wrapper。
- 运行结果会落到 artifact，并写入本地 run store。
- `run_playbook()` 默认会在 `.ptsm/agent_runtime/` 下创建持久 execution memory 和 checkpoint。
- `run_playbook()` 现在也会在 `.ptsm/agent_runtime/side-effects.json` 下记录成功副作用结果，用于同一 `thread_id` 的安全重放。
- `run_playbook()` 现在可以在真实发布缺图时调用 provider-backed image backend，默认把生成图写到 `outputs/generated_images/`；即梦配置优先于百炼配置。
- deterministic / deepseek drafting backend 现在会读取 playbook prompt 与 scoped skills，不再只面向发疯文学。
- 显式注入依赖时，运行时仍兼容 `InMemoryExecutionMemory` 和 `InMemorySaver`。
- 持久 checkpoint 以 `thread_id` 为键保存；复用同一个 `thread_id` 才能跨进程读取同一条执行线程。
- 当前 side-effect ledger 只复用成功 publish 结果，不缓存失败 publish 或只读状态检查。

## Practical Implications

- lessons memory 现在可以跨 CLI 调用保留，不再只活在单进程里。
- graph checkpoint 现在可跨进程保留，用于后续调试、回读和 thread 续跑。
- publish side effects 现在可按 `thread_id` 去重，避免 resume 或重复调用时再次执行成功 publish。
- 图片生成现在是发布前的一段显式步骤，会把 prompt、模型和生成路径写回 artifact，便于后续验收和排障。
- 当前仍没有更高阶的 cross-thread lookup、状态压缩或远端 state backend。

## Operator Entry Points

- 用例入口: [`src/ptsm/application/use_cases/run_playbook.py`](../src/ptsm/application/use_cases/run_playbook.py)
- 运行时入口: [`src/ptsm/agent_runtime/runtime.py`](../src/ptsm/agent_runtime/runtime.py)
- checkpoint 适配: [`src/ptsm/infrastructure/memory/checkpoint.py`](../src/ptsm/infrastructure/memory/checkpoint.py)
- 内存适配: [`src/ptsm/infrastructure/memory/store.py`](../src/ptsm/infrastructure/memory/store.py)
- 运行查询: [`src/ptsm/application/use_cases/runs.py`](../src/ptsm/application/use_cases/runs.py)
- 发布后检查: [`src/ptsm/application/use_cases/xhs_publish_status.py`](../src/ptsm/application/use_cases/xhs_publish_status.py)
