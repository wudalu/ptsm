# PTSM PRD Status Realignment Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 `docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md` 重新校准 `prd.md` 与当前仓库真实能力，明确当前完成情况与下一步执行顺序。

**Architecture:** 当前仓库已经具备 `发疯文学 -> 小红书 -> dry-run / MCP 实发` 的单纵切 MVP，但尚未形成通用 agent platform。下一阶段应先把这条纵切抽象成通用 `plan -> execute -> reflect` 运行时、请求级 skill surface、通用 playbook routing 与本地可恢复 memory，然后再用第二个垂直领域验证泛化。

**Tech Stack:** Python 3.12, `uv`, LangGraph, LangChain, Pydantic v2, YAML/Markdown asset loading, local JSON/JSONL persistence, pytest

## 1. Context Alignment

- `prd.md` 的文档尾部仍标注“当前版本：P2 阶段 - 多账户多领域运营系统”和“最后更新：2025年1月”。
- `docs/plans/2026-03-24-ptsm-agent-platform-rebaseline.md` 明确指出：仓库真实状态并不是 PRD 里描述的“四大领域 + 多账号矩阵 + 通用平台”，而是一个已经可运行的 `fengkuang` 单纵切 MVP。
- 截至 `2026-03-29`，代码现实与重基线文档的 `Current Baseline` 一致，和 `prd.md` 中的 P2 完成口径不一致。

结论：后续执行应以 `2026-03-24` 的 rebaseline 文档为实现真源，`prd.md` 暂时只保留目标态和路线图价值，不能再直接当作“已完成事实”使用。

## 2. Current Completion Against PRD

| PRD 模块 | PRD 口径 | 当前工程现状 | 判断 |
| --- | --- | --- | --- |
| 平台基础骨架 | 已具备 P2 级多领域平台底座 | 已有 CLI、bootstrap、playbook/skill/account registry、plan runner、artifact/run store，且 `uv run pytest -q` 通过 | `MVP 已完成` |
| 多账号运营 | 支持多账号矩阵化运营 | 账户注册表已存在，但当前只有 `src/ptsm/accounts/definitions/acct-fk-local.yaml` 一个本地账号定义 | `部分完成` |
| 多垂直领域 | 四大领域均已实现 | 当前只有 `fengkuang_daily_post` 一个 playbook，没有 AI、英语、武侠第二条纵切 | `未完成` |
| LangGraph Plan-Execute 平台 | 通用 Plan-Execute 工作流 | `src/ptsm/agent_runtime/runtime.py` 仍是 `DOMAIN_FENGKUANG` 专用工作流，只有 ingest/select/load/draft/reflect/finalize 一条硬编码路径 | `部分完成` |
| Skill 体系 | 多领域可扩展 skill 编排 | 已有 `SkillRegistry` 和 `SkillLoader`，但没有 request-scoped selector/surface，也没有作用域标签 | `部分完成` |
| Playbook 路由 | 面向账号/平台/领域的通用路由 | `src/ptsm/application/models.py` 只有 `FengkuangRequest`，`run_playbook.py` 只有 `run_fengkuang_playbook()` | `未完成` |
| 小红书发布 | 完整发布集成 | dry-run 与 MCP 实发、登录预检、二维码、状态查询、浏览器打开链路已具备 | `单平台单纵切完成` |
| 可观测性 | 监控、日志、效果追踪 | 已有本地 `RunStore`、artifact、`logs` 命令；没有 dashboard、业务指标分析、跨账号报表 | `部分完成` |
| 记忆与恢复 | 支持 thread resume / 记忆复用 | 当前使用 `InMemorySaver` 和 `InMemoryExecutionMemory`，仅进程内有效，不支持跨调用恢复 | `未完成` |
| 安全与合规 | 加密、合规审核、风控 | 当前代码里没有 `Fernet`、敏感词审核、去重、风险告警等实现 | `未完成` |
| 调度与批量工具 | 多账号调度、批量管理 | 未发现 scheduler、batch tool、审批流等实现 | `未完成` |
| 微信/图片/Dashboard/分析 | P3 持续推进中 | 当前仓库没有公众号、图片生成、Dashboard、高级分析相关实现 | `未开始` |

## 3. Rebaseline Task Status

### Task 1: Harden Local Plan Execution And Baseline Docs

**Status:** `部分完成`

已完成部分：

- `run-plan` CLI 已存在。
- 默认 state path 已落在 `.ptsm/plan_runs/`。
- `tests/unit/test_bootstrap.py` 已覆盖 `run-plan` 解析与分发。

未完成部分：

- `src/ptsm/interfaces/cli/main.py` 仍未传 `--skip-git-repo-check`。
- `README.md` 仍是两行 stub，没有重基线说明。
- `tests/unit/interfaces/cli/test_main.py` 尚不存在。

### Task 2: Extract A Generic Runtime Kernel From The Fengkuang Workflow

**Status:** `未开始`

当前缺口：

- 没有 `src/ptsm/agent_runtime/state.py`。
- 没有 `src/ptsm/agent_runtime/graph/` 和 `src/ptsm/agent_runtime/nodes/`。
- `runtime.py` 仍使用 `FengkuangState` 和硬编码 `DOMAIN_FENGKUANG`。

### Task 3: Add Request-Scoped Skill Surface And Runtime Activation

**Status:** `未开始`

当前缺口：

- `SkillSpec` 只有基础 metadata，没有 `domain_tags`、`platform_tags`、`playbook_tags` 等作用域信息。
- 不存在 `src/ptsm/skills/selector.py` 与 `src/ptsm/skills/surface.py`。
- builtin skills front matter 还没有选择器可用的标签。

### Task 4: Normalize Playbook Routing Around Accounts And Generic Requests

**Status:** `未开始`

当前缺口：

- 没有通用 `PlaybookRequest`。
- `PlaybookRegistry.select()` 仍以 `domain + platform` 为输入，没有 account-driven routing。
- `run_playbook.py` 仍是 `run_fengkuang_playbook()` 单入口。

### Task 5: Add Local Persistent Checkpoint And Memory Services

**Status:** `未开始`

当前缺口：

- 不存在 `src/ptsm/infrastructure/persistence/checkpointer.py`。
- `src/ptsm/infrastructure/memory/store.py` 仍是纯内存实现。
- 没有 `MemoryService` / `MemoryWritePolicy`。

### Task 6: Prove Platform Generality With A Second Vertical Slice And Generic CLI

**Status:** `未开始`

当前缺口：

- CLI 只有 `run-fengkuang`，没有 `run-playbook`。
- 当前只有一个 playbook：`fengkuang_daily_post`。
- 当前只有一个 builtin account：`acct-fk-local`。
- 没有 `daily_english_post`、英语技能或第二领域 e2e 验证。

## 4. Recommended Next Plan

原则：不要继续按 `prd.md` 的 P3/P4 事项发散。先完成 rebaseline 的平台化最小闭环，再讨论公众号、图片、Dashboard 和调度器。

### Task 1: 修正执行入口并同步基线文档

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `README.md`
- Create: `tests/unit/interfaces/cli/test_main.py`

**Step 1: 写一个失败测试锁定 CLI 约束**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py -q`

期望：

- 覆盖 `run_plan_cli()` 生成的 `codex exec` 参数。
- 断言包含 `-C <cwd>`、`--skip-git-repo-check`、`--full-auto`、`--sandbox workspace-write`。

**Step 2: 最小修复实现**

- 在 `run_plan_cli()` 的 `codex_exec()` 中补上 `--skip-git-repo-check`。
- 把 `README.md` 扩写为当前真实基线说明，而不是继续保留 stub。

**Step 3: 回归验证**

Run: `uv run pytest tests/unit/interfaces/cli/test_main.py tests/unit/plan_runner/test_runner.py tests/unit/test_bootstrap.py -q`

### Task 2: 抽出通用 runtime kernel

**Files:**
- Create: `src/ptsm/agent_runtime/state.py`
- Create: `src/ptsm/agent_runtime/graph/builder.py`
- Create: `src/ptsm/agent_runtime/nodes/ingest.py`
- Create: `src/ptsm/agent_runtime/nodes/planner.py`
- Create: `src/ptsm/agent_runtime/nodes/executor.py`
- Create: `src/ptsm/agent_runtime/nodes/reflector.py`
- Modify: `src/ptsm/agent_runtime/runtime.py`
- Create: `tests/unit/agent_runtime/test_graph_flow.py`
- Create: `tests/integration/test_plan_execute_reflect_loop.py`

**Step 1: 先补失败测试，锁定 retry / replan / finalize 分支**

Run: `uv run pytest tests/unit/agent_runtime/test_graph_flow.py tests/integration/test_plan_execute_reflect_loop.py tests/integration/test_fengkuang_workflow.py -q`

**Step 2: 让 `fengkuang` 走通新的通用 graph builder**

- 兼容保留 `build_fengkuang_workflow()`，但内部不再直接构图。
- 新状态结构里显式保留 `selected_playbook`、`candidate_skills`、`activated_skills`、`attempt_count`、`artifact_path`。

**Step 3: 回归验证**

Run: `uv run pytest tests/unit/agent_runtime tests/integration/test_fengkuang_workflow.py -q`

### Task 3: 完成 skill surface 与通用 playbook routing

**Files:**
- Modify: `src/ptsm/skills/contracts.py`
- Modify: `src/ptsm/skills/registry.py`
- Modify: `src/ptsm/skills/loader.py`
- Create: `src/ptsm/skills/selector.py`
- Create: `src/ptsm/skills/surface.py`
- Modify: `src/ptsm/playbooks/registry.py`
- Modify: `src/ptsm/playbooks/loader.py`
- Modify: `src/ptsm/accounts/registry.py`
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`

**Step 1: 先把 skill 选择做成 request-scoped**

Run: `uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_skill_loader.py tests/unit/skills/test_selector.py -q`

**Step 2: 再把 routing 改成 account-driven 的通用入口**

Run: `uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/accounts/test_account_registry.py tests/integration/test_playbook_selection.py -q`

**Step 3: 兼容保留 `run-fengkuang`，但内部改成通用 `run_playbook()`**

Run: `uv run pytest tests/unit/skills tests/unit/playbooks tests/unit/accounts tests/unit/application/use_cases/test_run_playbook.py -q`

### Task 4: 增加本地持久化 memory/checkpoint，并补第二领域证明泛化

**Files:**
- Create: `src/ptsm/infrastructure/persistence/checkpointer.py`
- Modify: `src/ptsm/infrastructure/memory/store.py`
- Create: `src/ptsm/application/services/memory_service.py`
- Create: `src/ptsm/application/services/memory_write_policy.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/playbook.yaml`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/planner.md`
- Create: `src/ptsm/playbooks/definitions/daily_english_post/reflection.md`
- Create: `src/ptsm/accounts/definitions/acct-en-local.yaml`
- Create: `tests/integration/test_thread_memory_resume.py`
- Create: `tests/integration/test_cross_thread_memory_lookup.py`
- Create: `tests/e2e/test_daily_english_publish_dry_run.py`

**Step 1: 先让 thread resume 和 account-scoped memory 跨调用生效**

Run: `uv run pytest tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py -q`

**Step 2: 再加 `run-playbook` CLI 和第二个纵切**

Run: `uv run pytest tests/unit/test_bootstrap.py tests/e2e/test_fengkuang_publish_dry_run.py tests/e2e/test_daily_english_publish_dry_run.py -q`

**Step 3: 全量回归**

Run: `uv run pytest -q`

## 5. Execution Priority

按下面顺序执行，不要跳步：

1. 先完成 rebaseline Task 1，解决 `run-plan` 可信度和 README 基线失真问题。
2. 再完成 rebaseline Task 2-4，把现有单纵切抽象成真正的平台内核。
3. 最后完成 rebaseline Task 5-6，用持久化能力和第二领域验证平台泛化。

在 Task 6 完成前，不建议启动以下事项：

- 微信公众号集成
- 图片生成链路
- Dashboard
- 批量调度器
- 高级分析
- A/B 测试

## 6. Done Criteria For The Next Milestone

下一里程碑完成的判定标准：

- `ptsm run-plan` 在非 git 目录可稳定执行
- `fengkuang` 不再依赖 one-off runtime，而是通用 graph specialization
- skill access 变成 request-scoped + activation-based
- `run_playbook()` 成为通用入口，`run-fengkuang` 只保留兼容层
- memory/checkpoint 支持跨 CLI 调用恢复
- 至少两个垂直领域走通同一平台架构
- `uv run pytest -q` 持续通过
