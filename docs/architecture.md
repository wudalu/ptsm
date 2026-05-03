---
title: PTSM Architecture
status: active
owner: ptsm
last_verified: 2026-05-03
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
  artifacts、observability、publishers、LLM backend、image backend、memory 等适配层。
- `src/ptsm/accounts/`
  本地账号定义和注册表。

## Stable Architectural Facts

- CLI 和 bootstrap 已是稳定入口。
- 发布链路当前以小红书为主，支持 dry-run 和 MCP 实发。
- 平台抽象正在形成，但第二垂直领域和持久化 memory 仍未完成。
- playbook 目录现在不仅承载 planner / reflection，还可以承载 persona 这类账号口吻资产；`agent_runtime` 负责把这些资产作为显式状态传给 drafting backend，而不是把风格写死在 agent 类里。
- 运行时还会把 `xhs_trend_scan` 这类 research skill 的动态结果单独放进 `runtime_skill_contents`，与静态 `SKILL.md` 文本分离，避免 prompt 组装时丢失实时上下文边界。
- reporting / eval / inspection surface 优先放在 `application/use_cases` 上，并复用本地 artifact stores，而不是引入独立服务层。
- composed operator snapshots such as `harness-report` 也留在 `application/use_cases`，只读复用现有 harness surfaces，而不是新增 orchestration service。
- single-case diagnostics such as `diagnose-publish` 同样留在 `application/use_cases`，通过组合 `doctor`、logs 和 artifact readers 来输出归因，而不是把诊断逻辑塞进 publisher 或 CLI。
- side-effect replay control 也放在 `application/services + application/use_cases`，避免让 `agent_runtime` 直接承担发布副作用策略。
- provider-backed image generation 也留在 `infrastructure`，由 `application/use_cases/run_playbook.py` 在发布前编排调用，避免把外部 API 协议直接塞进 runtime graph。

## Current Design Pressure

- 从单一 `fengkuang` 纵切抽出通用运行时。
- 让 playbook 和 skill 真正 request-scoped，而不是硬编码约定。
- 把内存态执行状态升级成可恢复的本地系统能力。

## Dependency Direction

当前代码基线下，稳定且已经成立的 dependency direction 规则如下：

- `interfaces`
  只负责入口和分发，可以依赖 `application`、`config`、`plan_runner`，不应直接依赖 `infrastructure` 或 `agent_runtime`。
- `application`
  负责用例编排，可以依赖 `agent_runtime`、`accounts`、`playbooks`、`config`、`infrastructure`。
- `agent_runtime`
  负责图执行和节点逻辑，可以依赖 `config`、`infrastructure`、`playbooks`、`skills`，不应依赖 `interfaces` 或 `application.use_cases`。
- `infrastructure`
  负责外部适配和持久化，不应依赖 `application`、`interfaces` 或 `agent_runtime`。
- `playbooks`
  负责定义和加载，不应依赖 `application`、`interfaces` 或 `agent_runtime`。
- `skills`
  负责 skill metadata、selection 和 loading，不应依赖 `application`、`interfaces` 或 `agent_runtime`。

这些规则会通过 mechanical enforcement 落到结构测试里，而不是只停留在文档说明层。

当前结构测试位置：

- `tests/unit/architecture/`

## Related Maps

- 运行时细节见 [`runtime.md`](runtime.md)
- Playbook 结构见 [`playbooks.md`](playbooks.md)
- Skill 结构见 [`skills.md`](skills.md)
- 观测与回放见 [`observability.md`](observability.md)
