---
title: PTSM Architecture
status: active
owner: ptsm
last_verified: 2026-04-17
source_of_truth: true
related_paths:
  - src/ptsm
  - src/ptsm/application
  - src/ptsm/agent_runtime
  - src/ptsm/infrastructure
  - src/ptsm/interfaces
---

# Architecture

PTSM 当前不是“多领域平台已全部完成”的状态，而是一个已经跑通的 `fengkuang -> xiaohongshu` 单纵切 MVP，上面正在抽象通用平台能力。

## Package Boundaries

- `src/ptsm/interfaces/cli/`
  CLI 入口，负责参数解析和命令分发。
- `src/ptsm/application/`
  用例层，连接请求模型、账号、playbook、发布器和运行时。
- `src/ptsm/agent_runtime/`
  LangGraph 运行时、节点和状态契约。
- `src/ptsm/playbooks/`
  playbook 定义、加载和路由。
- `src/ptsm/skills/`
  builtin skill metadata、选择、surface 和加载。
- `src/ptsm/infrastructure/`
  artifacts、observability、publishers、LLM backend、memory 等适配层。
- `src/ptsm/accounts/`
  本地账号定义和注册表。

## Stable Architectural Facts

- CLI 和 bootstrap 已是稳定入口。
- 发布链路当前以小红书为主，支持 dry-run 和 MCP 实发。
- 平台抽象正在形成，但第二垂直领域和持久化 memory 仍未完成。

## Current Design Pressure

- 从单一 `fengkuang` 纵切抽出通用运行时。
- 让 playbook 和 skill 真正 request-scoped，而不是硬编码约定。
- 把内存态执行状态升级成可恢复的本地系统能力。

## Related Maps

- 运行时细节见 [`runtime.md`](runtime.md)
- Playbook 结构见 [`playbooks.md`](playbooks.md)
- Skill 结构见 [`skills.md`](skills.md)
- 观测与回放见 [`observability.md`](observability.md)
