# PTSM Agent Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于 `prd.md` 从零搭建一个可扩展的社交媒体智能运营内核，先完成可运行的 agent 平台骨架，再逐步落地 skill、playbook、memory、多账号与发布能力。

**Architecture:** 采用 `LangChain + LangGraph` 的混合方案。顶层用 `LangGraph` 显式编排 `plan -> execute -> reflect` 生命周期、状态、持久化与中断恢复；节点内部使用 `LangChain` agent 承载“强 agent + tools/skills”的推理与工具调用。整体按分层架构和 ports/adapters 组织，先做单平台单 playbook 纵切，再扩展多领域与多账号矩阵。

**Tech Stack:** Python 3.12, `uv`, LangChain, LangGraph, `langchain-mcp-adapters`, Pydantic v2, PostgreSQL, pytest, structlog, FastAPI/CLI（CLI 先行，API 后补）

## 1. 当前判断与关键假设

### 1.1 当前仓库现状

- 当前 `ptsm` 仓库基本为空，只有 `prd.md`。
- 这意味着本项目更适合按“greenfield scaffold + 分阶段落地”推进，而不是在现有代码上做局部改造。

### 1.2 可借鉴资产

- `/Users/wudalu/llm-app/pub-to-social-media` 适合作为业务流程、发布链路、LangGraph 工作流和依赖管理参考。
- `/Users/wudalu/hsbc_code/aether-frame` 适合作为 skill catalog、skill runtime、MCP tool wrapper、memory adapter、分层抽象参考。

### 1.3 核心假设

- 第一阶段不是直接复制 `pub-to-social-media`，而是抽取其中经过验证的模式，重建一个更通用、更可维护的 agent 平台。
- 第一阶段验收范围应该收敛到“单平台 + 单账号 + 单 playbook + 可回放 memory + 可观测的 plan/execution/reflection 循环”。
- 多领域、多账号矩阵是第二阶段到第三阶段逐步扩展，不应在空仓库阶段一次性铺满。

## 2. 技术选型结论

### 2.1 Python 依赖管理

**推荐：`uv`**

推荐理由：

- `uv` 已经具备完整的项目依赖管理能力：`pyproject.toml`、锁文件、`uv sync`、`uv lock`、dependency groups、workspace。
- LangChain 官方文档与生态文档已经直接提供 `uv` 安装/运行方式。
- `langchain-mcp-adapters` 官方仓库本身包含 `uv.lock`，说明其维护者也在使用这套流。
- 你的参考项目 `pub-to-social-media` 也已经落了 `uv.lock`，团队迁移成本最低。

结论是一个**基于当前官方文档和参考仓库的工程判断**：对这个项目来说，`uv` 比 Poetry/PDM 更合适，不是因为它在所有项目里都绝对更优，而是因为它最匹配当前需求：

- greenfield 项目
- 需要锁定复杂 AI 依赖
- 需要较快的环境同步
- 后续可能拆 workspace 或多 package
- 需要兼容 CLI、worker、测试、MCP 工具链

配套建议：

- 用 `pyproject.toml` 作为唯一依赖声明入口。
- 用 `uv.lock` 做统一锁定。
- 用标准 `dependency-groups` 或 `uv add --group` 管理 `dev/test/lint`。
- 构建后端用 `hatchling`，不引入 Poetry。

### 2.2 Agent 框架

**推荐：LangChain 负责 agent/tool 抽象，LangGraph 负责执行图、状态、持久化与中断恢复。**

不建议把所有行为都塞进一个 `create_agent()` 黑盒里。原因：

- 你明确要求 `plan-execution-reflection` 循环。
- 你需要 memory、skill、playbook、可回放执行、故障恢复。
- 这些能力在 `LangGraph` 的显式状态机里更可控，也更容易测试。

### 2.3 Skill 方案

**推荐：采用 Deep Agents/Agent Skills 风格的 `SKILL.md + assets/scripts` 目录协议，但运行时自己实现，不直接引入整个 Deep Agents runtime。**

理由：

- 官方已经明确了 skill 的核心模式：`SKILL.md`、progressive disclosure、按需加载。
- `aether-frame` 现有 skill catalog / discovery / runtime 已经与这个思路高度一致。
- 你要求以 LangChain/LangGraph 为主体，直接把整个 Deep Agents 引入会让运行时过重、边界变模糊。

### 2.4 Memory 方案

**推荐：优先使用 LangGraph 原生两层 memory 模型**

- 短期记忆：`checkpointer`
- 长期记忆：`store`

建议：

- 开发期：`InMemorySaver + InMemoryStore`
- 生产期：`PostgresSaver + PostgresStore`

不建议第一阶段就引入额外 memory 服务作为主路径。`openmemory` 之类方案可以作为后续扩展，但当前需求下 first-party 方案已经足够，并且与 LangGraph 生命周期天然一致。

## 3. 总体架构

### 3.1 架构原则

- 分层明确：domain / application / agent runtime / infrastructure / interfaces
- 强 agent 驱动，但由 playbook 收敛目标、输入输出、反思规则与安全边界
- skill 以渐进披露方式接入，避免把所有上下文一次性塞给模型
- memory 分短期和长期，避免把 checkpoint 当作长期知识库
- 单一纵切先跑通，再扩展多领域与多账号

### 3.2 推荐目录结构

```text
ptsm/
├── pyproject.toml
├── uv.lock
├── README.md
├── .env.example
├── docker-compose.yml
├── docs/
│   └── plans/
├── src/ptsm/
│   ├── __init__.py
│   ├── bootstrap.py
│   ├── config/
│   │   ├── settings.py
│   │   ├── logging.py
│   │   └── models.py
│   ├── domain/
│   │   ├── accounts/
│   │   ├── content/
│   │   ├── playbooks/
│   │   ├── skills/
│   │   ├── memory/
│   │   └── common/
│   ├── application/
│   │   ├── ports/
│   │   ├── services/
│   │   ├── use_cases/
│   │   └── orchestrators/
│   ├── agent_runtime/
│   │   ├── graph/
│   │   ├── nodes/
│   │   ├── state.py
│   │   ├── policies.py
│   │   └── runtime.py
│   ├── skills/
│   │   ├── builtin/
│   │   ├── registry.py
│   │   ├── loader.py
│   │   └── contracts.py
│   ├── playbooks/
│   │   ├── registry.py
│   │   ├── loader.py
│   │   └── definitions/
│   ├── infrastructure/
│   │   ├── llm/
│   │   ├── mcp/
│   │   ├── persistence/
│   │   ├── memory/
│   │   ├── publishers/
│   │   ├── observability/
│   │   └── scheduler/
│   └── interfaces/
│       ├── cli/
│       ├── api/
│       └── workers/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

### 3.3 分层职责

#### `domain`

- 只放业务核心概念，不依赖 LangChain/LangGraph。
- 核心对象：
  - `AccountProfile`
  - `PlatformProfile`
  - `PlaybookDefinition`
  - `SkillDescriptor`
  - `MemoryRecord`
  - `ExecutionPlan`
  - `ReflectionResult`

#### `application`

- 负责编排用例与业务服务。
- 不直接持有第三方 SDK，统一通过 ports 调 infrastructure。
- 核心服务：
  - `PlaybookSelectionService`
  - `SkillSelectionService`
  - `ExecutionPlanningService`
  - `ReflectionService`
  - `MemoryWritePolicyService`

#### `agent_runtime`

- 这是 LangGraph 真正所在层。
- 负责状态机、循环控制、节点跳转、超时、重试、interrupt。
- 节点内部再调用 LangChain agent 或 tool chain。

#### `infrastructure`

- 封装 LLM provider、Postgres、MCP client、publisher adapter、embedding、日志、指标。

#### `interfaces`

- 第一阶段只做 CLI。
- 第二阶段增加 worker。
- 第三阶段视需要补 FastAPI 和 Dashboard。

## 4. 强 Agent + Skill + Playbook 设计

### 4.1 为什么用“强 agent”而不是多 agent swarm 起步

第一阶段建议采用一个主执行 agent，而不是 supervisor + 多 worker agent 大编排。

原因：

- 当前仓库是空白，先把 runtime kernel 做稳比同时做复杂多 agent 协调更重要。
- 多 agent 协调的复杂度主要来自共享状态、上下文切换、结果拼接和失败恢复。
- 你当前最关键的是“能稳定执行、能复盘、能收敛技能”，这更适合强 agent + skill。

后续只在以下场景引入子 agent：

- 深度 research
- 多平台并发发布
- 长链路素材加工
- 独立审校/合规评估

### 4.2 Skill 模型

采用 `SKILL.md` 作为统一 skill 入口，参考 Deep Agents 和 `aether-frame` 的组合模式。

每个 skill 目录结构：

```text
skills/builtin/xhs_copywriting/
├── SKILL.md
├── templates/
│   └── xhs_post.md.j2
└── scripts/
    └── validators.py
```

Skill 元信息至少包括：

- `name`
- `description`
- `triggers`
- `required_tools`
- `allowed_platforms`
- `input_schema`
- `output_schema`
- `safety_notes`

运行时模式：

- 主 agent 只先看到 skill 摘要
- 当需要某项能力时，通过 `load_skill` 工具按需读取完整 `SKILL.md`
- `SKILL.md` 可以再引用脚本、模板、知识文档
- 这样可以实现 progressive disclosure，降低上下文污染

### 4.3 Playbook 模型

**Playbook 不是 skill 的替代品，而是 skill 的编排约束层。**

建议把 playbook 定义为“版本化、可审计、可测试的任务策略包”，每个 playbook 指定：

- 适用场景
- 输入输出契约
- 必选 skill
- 可选 skill
- plan 模板
- reflection rubric
- memory 读写策略
- 失败重试与人工介入条件

建议定义为 `YAML + Markdown` 混合：

```text
playbooks/definitions/trend_to_xhs_post/
├── playbook.yaml
├── planner.md
├── reflection.md
└── output_schema.json
```

`playbook.yaml` 关键字段：

- `playbook_id`
- `version`
- `intent`
- `domain`
- `platforms`
- `required_skills`
- `optional_skills`
- `input_contract`
- `output_contract`
- `reflection_policy`
- `memory_policy`
- `approval_policy`

### 4.4 Skill 与 Playbook 的边界

- skill 解决“怎么做某类局部工作”
- playbook 解决“在这个业务场景里先做什么、后做什么、用哪些 skill、何时反思、何时中断”

例子：

- `skill: xhs_copywriting`
- `skill: trend_research`
- `skill: compliance_rewrite`
- `playbook: trend_to_xhs_post`

## 5. Plan -> Execute -> Reflect 执行循环

### 5.1 顶层图

推荐顶层 LangGraph 节点：

```text
ingest_request
  -> load_context
  -> retrieve_memory
  -> select_playbook
  -> discover_skills
  -> draft_plan
  -> execute_step
  -> reflect_step
  -> decide_next
      -> execute_step
      -> revise_plan
      -> request_approval
      -> finalize
  -> persist_artifacts
  -> persist_memory
```

### 5.2 节点职责

#### `ingest_request`

- 接收外部输入
- 规范化为统一任务请求
- 注入 `thread_id` / `run_id` / `account_id` / `platform`

#### `load_context`

- 载入账号配置、平台限制、环境设置

#### `retrieve_memory`

- 读取短期线程状态
- 检索长期 memory（账户偏好、平台经验、历史表现）

#### `select_playbook`

- 根据意图、平台、领域、任务类型选中 playbook

#### `discover_skills`

- 读取可用 skill catalog
- 结合 playbook 选出候选 skill

#### `draft_plan`

- 由 planner 生成结构化 plan
- plan 至少包含：
  - steps
  - success criteria
  - dependencies
  - fallback

#### `execute_step`

- 调用主 agent 执行当前 step
- agent 可使用 tools 和 skill

#### `reflect_step`

- 对当前产出打分
- 判断是否满足 playbook 的 rubric
- 输出：
  - `pass`
  - `retry`
  - `replan`
  - `needs_approval`

#### `decide_next`

- 根据 reflection 决定进入下一 step、修正 plan，或中断

### 5.3 反思机制

Reflection 不建议只靠一句“请自我反思”。建议结构化：

- completeness score
- correctness score
- compliance score
- style score
- platform fitness score
- required fixes

第一阶段先用规则化 rubric + LLM 评分结合：

- 必须项失败：直接 `retry/rewrite`
- 分数项低于阈值：允许 1~2 次修正
- 超出预算：转人工审批或终止

### 5.4 为什么不用纯 ReAct 循环

因为纯 ReAct 对以下能力支持弱：

- 明确的阶段边界
- 可测的 reflection 输出
- 可持久化的 plan 状态
- 中断恢复
- 多种失败路径的显式处理

所以推荐：**LangGraph 管生命周期，LangChain agent 管节点内推理。**

## 6. Memory 设计

### 6.1 Memory 分层

#### 短期记忆

用途：

- 单个线程内的消息历史
- 当前 plan、当前 step、工具结果摘要
- 审批中断点

实现：

- 开发期：`InMemorySaver`
- 生产期：`PostgresSaver`

#### 长期记忆

用途：

- 用户/账号偏好
- 平台经验
- playbook 历史表现
- 常见失败与修正策略
- 领域知识摘要

实现：

- 开发期：`InMemoryStore`
- 生产期：`PostgresStore`

### 6.2 Memory 类型

#### 语义记忆（semantic）

- 账号画像
- 风格偏好
- 平台限制
- 常用标签与禁用词

#### 情节记忆（episodic）

- 某次任务的执行总结
- 某次发布失败原因
- 某次修正后成功的案例

#### 程序性记忆（procedural）

- “这个账号一律先用 A playbook”
- “小红书标题不要超过 N 字”
- “英语学习内容必须包含例句和练习”

### 6.3 Namespace 设计

建议 namespace 统一规范：

- `("accounts", account_id, "profile")`
- `("accounts", account_id, "preferences")`
- `("accounts", account_id, "platform_rules")`
- `("playbooks", playbook_id, "lessons")`
- `("skills", skill_name, "usage_feedback")`
- `("domains", domain_name, "reference_notes")`

### 6.4 Memory 写入策略

不建议把所有消息都直接长期存储。

推荐策略：

- hot path：
  - 只写关键事实、最终摘要、失败原因
- background path：
  - 做 memory consolidation
  - 做重复合并
  - 做过期清理

### 6.5 首阶段 Memory 验收标准

- 同一 `thread_id` 下能恢复 plan/execution 状态
- 新线程能读到账户级长期偏好
- reflection 完成后能写入结构化经验
- 能查询“最近 5 次失败的共同原因”

## 7. MCP / Tools / Skill 接入策略

### 7.1 工具分层

- Local tools：项目内 Python 函数
- MCP tools：通过 `langchain-mcp-adapters` 接入
- Skill tools：通过 skill runtime 暴露的逻辑能力

### 7.2 MCP 策略

建议第一阶段只接最必要的 MCP 能力：

- 文档检索
- 搜索/趋势分析
- 结构化思考

暂不建议一开始接太多 server。原因：

- 调试复杂度高
- 超时和权限问题多
- 会掩盖 runtime 本身设计问题

### 7.3 可复用 skill 来源

优先顺序建议：

1. 官方/一方模式
   - Deep Agents skill 规范
   - LangChain multi-agent skill pattern
2. 本地已有资产
   - `aether-frame` 的 `SKILL.md` 格式、catalog、runtime
3. 第三方社区 skill
   - `playbooks.com`
   - `agentskills.so`

对于第三方 skill，不建议“运行时在线拉取即执行”。建议流程：

- 先人工挑选
- 固化到仓库
- 做安全审查
- 做最小化适配

## 8. 推荐的首个 MVP 范围

### 8.1 不建议的做法

- 一上来支持 4 个领域 + 多平台 + 多账号 + 真发布
- 一上来做 supervisor/multi-agent
- 一上来接入复杂 Dashboard

### 8.2 建议的首个纵切

**单账号 + 小红书 + 一个内容 playbook + mock/干跑发布**

推荐 playbook：

- `trend_to_xhs_post`

它最能验证以下关键能力：

- MCP/tool 使用
- skill 选择
- plan/execution/reflection 循环
- memory 读取与写入
- 平台格式化输出

## 8.3 当前状态快照（2026-03-20）

本节基于 2026-03-20 的新鲜验证结果，而不是历史记忆。

已执行的关键验证：

- `uv run pytest -q` -> `76 passed`
- `uv run pytest tests/unit/test_bootstrap.py tests/unit/config/test_settings.py tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_logs.py -q` -> `25 passed`
- `uv run pytest tests/unit/agent_runtime/test_fengkuang_drafting_agent.py tests/integration/test_fengkuang_workflow.py -q` -> `4 passed`
- `uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_skill_loader.py tests/unit/application/use_cases/test_run_playbook.py -q` -> `8 passed`
- `uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py tests/unit/application/use_cases/test_run_playbook.py -q` -> `8 passed`
- `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_xhs_browser.py tests/e2e/test_fengkuang_publish_dry_run.py -q` -> `11 passed`
- `uv run pytest tests/unit/accounts/test_account_registry.py -q` -> `2 passed`
- `uv run pytest tests/integration/test_thread_memory_resume.py tests/integration/test_cross_thread_memory_lookup.py tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_logs.py -q` -> `ERROR: file or directory not found: tests/integration/test_thread_memory_resume.py`
- `uv run python -m compileall src` -> exit `0`
- `uv run python -m ptsm.bootstrap doctor` -> 返回结构化 JSON，当前 `xhs_preflight` 仍为 `error`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "周四晚上加班后回家" --account-id acct-fk-local` -> 失败，缺少 LangGraph 所需 `thread_id`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "周三下班地铁没座位" --account-id acct-fk-local --thread-id review-status --wait-for-publish-status` -> `status=completed`

当前判断：

- 已完成：原 Task 1。`bootstrap -> logging -> CLI/doctor/logs` 基线已经稳定。
- 部分完成：原 Task 6。artifact、run store、publish status/browser 链路已经接通，但计划里的 CLI 验证命令还没补 `--thread-id`，dry-run 产物也只能给出 `manual_check_required`。
- 部分完成但结构仍不达标：原 Task 2、Task 3、Task 4。相关测试都绿，但 `runtime.py` 仍是单函数内联流程，skill 全文仍会预加载，playbook schema 也仍偏最小实现。
- 未开始：原 Task 5。目标测试文件尚不存在，持久 checkpoint / 跨线程 memory 还没有落地。
- 未开始：原 Task 7。当前只有 `acct-fk-local` 一个账号和 `fengkuang_daily_post` 一条 playbook 纵切。

> 从这里开始，`run-plan` 只应执行下面的 `### Task ...` 段落。已经完成的工作保留在本节快照里，不再作为直接执行单元。

## 8.4 剩余可执行任务清单

### Task 2.1: Extract reusable runtime state and node boundaries

```yaml
verify:
  - uv run pytest tests/unit/agent_runtime/test_fengkuang_drafting_agent.py tests/integration/test_fengkuang_workflow.py -q
  - uv run python -m compileall src
max_attempts: 3
done_when:
  - workflow state type is moved out of runtime.py
  - node responsibilities are split out of build_fengkuang_workflow without breaking fengkuang flow
```

目标：

- 把当前 `build_fengkuang_workflow()` 里的内联节点拆到独立 state / nodes 模块。
- 保持现有发疯文学链路和集成测试不回退。

涉及范围：

- `src/ptsm/agent_runtime/runtime.py`
- `src/ptsm/agent_runtime/state.py`
- `src/ptsm/agent_runtime/nodes/`
- `tests/integration/test_fengkuang_workflow.py`

### Task 2.2: Remove hardcoded fengkuang-only selection from the runtime path

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py -q
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周四晚上加班后回家" --account-id acct-fk-local --thread-id review-task-2-2
max_attempts: 3
done_when:
  - runtime no longer depends on DOMAIN_FENGKUANG or an equivalent hardcoded domain constant
  - account, domain, and playbook selection are explicit inputs instead of implicit happy-path defaults
```

目标：

- 去掉 runtime 对 `DOMAIN_FENGKUANG` 的硬编码依赖。
- 把账户、domain、playbook 的选择路径变成清晰的共享平台能力。

涉及范围：

- `src/ptsm/agent_runtime/runtime.py`
- `src/ptsm/application/use_cases/run_playbook.py`
- `src/ptsm/accounts/registry.py`
- `src/ptsm/playbooks/registry.py`

### Task 3.1: Expose skill summaries before full markdown content

```yaml
verify:
  - uv run pytest tests/unit/skills/test_skill_registry.py tests/unit/skills/test_skill_loader.py -q
  - uv run pytest tests/unit/application/use_cases/test_run_playbook.py -q
max_attempts: 3
done_when:
  - runtime state carries skill metadata or summaries before any full skill markdown is loaded
  - prompt assembly can proceed without preloading loaded_skill_contents
```

目标：

- 先让 runtime 只感知 skill 摘要，而不是全文。
- 为后面的真正按需加载铺平 state 结构。

涉及范围：

- `src/ptsm/skills/contracts.py`
- `src/ptsm/skills/registry.py`
- `src/ptsm/agent_runtime/`
- `tests/unit/skills/`

### Task 3.2: Load full skill markdown only at the step that needs it

```yaml
verify:
  - uv run pytest tests/unit/skills/test_skill_loader.py tests/integration/test_fengkuang_workflow.py tests/unit/application/use_cases/test_run_playbook.py -q
max_attempts: 3
done_when:
  - load_assets no longer materializes loaded_skill_contents eagerly
  - full skill content is loaded only inside the drafting or execution step that consumes it
```

目标：

- 把当前“预加载所有 skill 全文”的行为改成真正的按需加载。
- 保持现有 `SKILL.md` 发现和解析协议不变。

涉及范围：

- `src/ptsm/skills/loader.py`
- `src/ptsm/agent_runtime/runtime.py`
- `tests/unit/skills/`
- `tests/integration/test_fengkuang_workflow.py`

### Task 4.1: Expand playbook schema beyond the current minimal YAML

```yaml
verify:
  - uv run pytest tests/unit/playbooks/test_playbook_registry.py tests/unit/playbooks/test_playbook_loader.py -q
max_attempts: 3
done_when:
  - playbook definitions include input or output contract fields
  - playbook definitions include at least one structured policy such as memory_policy or approval_policy
```

目标：

- 把 playbook 定义从 `required_skills + reflection` 升级为更完整的策略契约。
- 先把 schema 和 loader/registry 的结构补起来。

涉及范围：

- `src/ptsm/playbooks/registry.py`
- `src/ptsm/playbooks/loader.py`
- `src/ptsm/playbooks/definitions/`
- `tests/unit/playbooks/`

### Task 4.2: Consume structured playbook constraints in the runtime and CLI path

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/integration/test_fengkuang_workflow.py -q
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周四晚上加班后回家" --account-id acct-fk-local --thread-id review-task-4-2
max_attempts: 3
done_when:
  - runtime reads contract or policy fields from playbook definitions instead of ad hoc assumptions
  - CLI verification path works with the required thread config and stays green
```

目标：

- 让 runtime 真正消费 playbook 的结构化约束。
- 顺手把当前 CLI 验证命令和 `thread_id` 约束对齐。

涉及范围：

- `src/ptsm/application/use_cases/run_playbook.py`
- `src/ptsm/agent_runtime/runtime.py`
- `src/ptsm/playbooks/`
- `tests/unit/application/use_cases/test_run_playbook.py`

### Task 5.1: Persist short-term checkpoints across separate invocations

```yaml
verify:
  - uv run pytest tests/integration/test_thread_memory_resume.py -q
  - uv run python -m compileall src
max_attempts: 3
done_when:
  - workflow checkpoint storage survives beyond a single process-local InMemorySaver
  - the same thread_id can be resumed across separate invocations
```

目标：

- 先把短期 checkpoint 持久化做出来。
- 用真实恢复测试替代当前“只在单次流程里传 config”的假恢复。

涉及范围：

- `src/ptsm/infrastructure/persistence/`
- `src/ptsm/agent_runtime/`
- `tests/integration/test_thread_memory_resume.py`

### Task 5.2: Persist long-term memory and enable cross-thread lookup

```yaml
verify:
  - uv run pytest tests/integration/test_cross_thread_memory_lookup.py tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_logs.py -q
max_attempts: 3
done_when:
  - long-term memory storage is injectable and persistent
  - different runs or threads can query prior lessons through the shared memory path
```

目标：

- 把长期 memory 从 `InMemoryExecutionMemory()` 升级成可持久注入的组件。
- 建立跨线程 lessons 查询的真实能力和测试覆盖。

涉及范围：

- `src/ptsm/infrastructure/memory/store.py`
- `src/ptsm/application/`
- `tests/integration/test_cross_thread_memory_lookup.py`
- `tests/unit/infrastructure/observability/`

### Task 6.1: Align publish verification with the required thread-aware CLI contract

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_xhs_browser.py tests/e2e/test_fengkuang_publish_dry_run.py -q
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周三下班地铁没座位" --account-id acct-fk-local --thread-id review-task-6-1 --wait-for-publish-status
max_attempts: 3
done_when:
  - publish verification no longer fails because thread config is missing
  - artifact, run summary, and post_publish_checks remain aligned after the CLI contract update
```

目标：

- 让计划里的验证命令和现在的 runtime 合约一致。
- 保持 dry-run / wait-for-publish-status 的产物结构稳定。

涉及范围：

- `src/ptsm/interfaces/cli/main.py`
- `src/ptsm/application/use_cases/run_playbook.py`
- `docs/operations/local-runbook.md`
- `tests/unit/application/use_cases/`

### Task 6.2: Make publish verification outputs actionable for automation and manual fallback

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/application/use_cases/test_xhs_browser.py tests/unit/application/use_cases/test_logs.py -q
  - uv run python -m ptsm.bootstrap doctor
max_attempts: 3
done_when:
  - dry-run and real-publish artifacts clearly distinguish automated verification from manual escalation
  - doctor, logs, browser, and status-check tools reference the same run or artifact contract
```

目标：

- 让自动校验和人工兜底在 artifact/run 维度上说同一种语言。
- 避免出现 stdout 有提示但日志和 artifact 无法追溯的状态。

涉及范围：

- `src/ptsm/application/use_cases/xhs_publish_status.py`
- `src/ptsm/application/use_cases/xhs_browser.py`
- `src/ptsm/application/use_cases/logs.py`
- `src/ptsm/infrastructure/observability/run_store.py`

### Task 7.1: Add a second domain or playbook through the shared platform path

```yaml
verify:
  - uv run pytest tests/unit/accounts/test_account_registry.py tests/unit/playbooks/test_playbook_registry.py tests/unit/skills/test_skill_registry.py -q
  - uv run pytest -q
max_attempts: 3
done_when:
  - at least one additional account or playbook definition exists beyond the fengkuang slice
  - platform selection is no longer fengkuang-only by construction
```

目标：

- 把平台推进到至少两条业务路径，而不是一条纵切的特例。
- 保证账号、playbook、skill 发现继续走共享平台路径。

涉及范围：

- `src/ptsm/accounts/`
- `src/ptsm/playbooks/definitions/`
- `src/ptsm/skills/builtin/`
- `src/ptsm/application/use_cases/`

## 9. 分阶段里程碑

#### 里程碑 M0：工程脚手架与基础约束

**目标：** 把项目从空仓库变成可运行、可测试、可扩展的 Python agent 工程。

**计划创建的文件：**

- `pyproject.toml`
- `.python-version`
- `.env.example`
- `README.md`
- `src/ptsm/__init__.py`
- `src/ptsm/bootstrap.py`
- `src/ptsm/config/settings.py`
- `src/ptsm/config/logging.py`
- `tests/unit/test_bootstrap.py`

**交付标准：**

- `uv sync` 可成功
- `pytest` 可运行
- `python -m ptsm.bootstrap` 可启动基础 CLI
- 配置、日志、目录结构确定

#### 里程碑 M1：Agent Runtime Kernel

**目标：** 落地最小可用 LangGraph 执行图，跑通 `plan -> execute -> reflect`。

**计划创建的文件：**

- `src/ptsm/agent_runtime/state.py`
- `src/ptsm/agent_runtime/runtime.py`
- `src/ptsm/agent_runtime/graph/builder.py`
- `src/ptsm/agent_runtime/nodes/ingest.py`
- `src/ptsm/agent_runtime/nodes/planner.py`
- `src/ptsm/agent_runtime/nodes/executor.py`
- `src/ptsm/agent_runtime/nodes/reflector.py`
- `tests/unit/agent_runtime/test_graph_flow.py`
- `tests/integration/test_plan_execute_reflect_loop.py`

**交付标准：**

- 用 mock model/mock tool 跑通完整循环
- reflection 能驱动 `continue/retry/replan/finalize`
- 短期 state 可持久化恢复

#### 里程碑 M2：Skill Catalog 与 Progressive Disclosure

**目标：** 让强 agent 能感知 skill 摘要，并按需加载 skill 内容。

**计划创建的文件：**

- `src/ptsm/skills/contracts.py`
- `src/ptsm/skills/registry.py`
- `src/ptsm/skills/loader.py`
- `src/ptsm/skills/builtin/trend_research/SKILL.md`
- `src/ptsm/skills/builtin/xhs_copywriting/SKILL.md`
- `src/ptsm/skills/builtin/compliance_rewrite/SKILL.md`
- `tests/unit/skills/test_registry.py`
- `tests/unit/skills/test_loader.py`

**交付标准：**

- skill 可以被发现、校验、列出
- agent 只拿到 skill 摘要
- 需要时能加载完整 skill 内容和引用资源

#### 里程碑 M3：Playbook Engine

**目标：** 引入 playbook 作为任务策略约束层。

**计划创建的文件：**

- `src/ptsm/playbooks/registry.py`
- `src/ptsm/playbooks/loader.py`
- `src/ptsm/playbooks/definitions/trend_to_xhs_post/playbook.yaml`
- `src/ptsm/playbooks/definitions/trend_to_xhs_post/planner.md`
- `src/ptsm/playbooks/definitions/trend_to_xhs_post/reflection.md`
- `tests/unit/playbooks/test_registry.py`
- `tests/integration/test_playbook_selection.py`

**交付标准：**

- 能基于输入选中 playbook
- playbook 能声明 required skills / reflection rubric / output contract
- 执行循环能读取 playbook 约束

#### 里程碑 M4：Memory 与 Persistence

**目标：** 把 memory 做成系统能力，而不是节点副产物。

**计划创建的文件：**

- `src/ptsm/infrastructure/persistence/checkpointer.py`
- `src/ptsm/infrastructure/memory/store.py`
- `src/ptsm/application/services/memory_service.py`
- `src/ptsm/application/services/memory_write_policy.py`
- `tests/integration/test_thread_memory_resume.py`
- `tests/integration/test_cross_thread_memory_lookup.py`

**交付标准：**

- thread 级恢复有效
- 长期 memory 跨线程可读
- memory namespace 设计稳定
- 有最小 compaction/summary 策略

#### 里程碑 M5：业务纵切 MVP

**目标：** 打通首个真实业务 playbook。

**计划创建的文件：**

- `src/ptsm/infrastructure/publishers/xiaohongshu_adapter.py`
- `src/ptsm/application/use_cases/run_playbook.py`
- `src/ptsm/interfaces/cli/main.py`
- `tests/e2e/test_trend_to_xhs_post_dry_run.py`

**交付标准：**

- 输入任务后可生成结构化小红书内容
- 经过 reflection 后给出最终可发布稿
- 支持 dry-run，不直接真发
- 完整链路可观察、可回放

#### 里程碑 M6：多领域与多账号扩展

**目标：** 从单 playbook 纵切扩展到 PRD 所需矩阵。

**扩展内容：**

- 发疯文学 playbook
- 每日英语 playbook
- 武侠文化 playbook
- 多账号配置
- 调度器
- 审批/限流/风控策略

## 10. 开发顺序建议

推荐顺序：

1. 先做 `M0`
2. 再做 `M1`
3. 再做 `M2 + M3`
4. 再做 `M4`
5. 最后做 `M5`

原因：

- 没有 runtime kernel，skill/playbook 只是静态文件
- 没有 skill/playbook，memory 很难定义写入策略
- 没有 memory，真实 agent 行为无法稳定复盘
- 没有业务纵切，平台价值无法验证

## 11. 暂不建议现在做的事

- 暂不做多 agent supervisor
- 暂不做复杂 Dashboard
- 暂不做 A/B test
- 暂不做跨平台协同
- 暂不把外部社区 skill 动态拉取接入生产链路

## 12. 待确认问题

下面这些不阻塞我先做骨架，但会影响 M5 之后的边界：

1. 第一阶段的真实目标，是不是明确收敛为“小红书单平台 dry-run + 单账号 + 单 playbook”？
2. 首发的业务纵切，你更想先打通哪个方向：
   - AI 科技资讯
   - 发疯文学
   - 英语学习
   - 武侠文化
3. 第一阶段是否需要直接兼容你现有 `pub-to-social-media` 的部分发布代码，还是只参考设计、重新实现更干净的 adapter？

## 13. 资料依据

外部官方资料：

- Astral `uv` 项目文档：
  - https://docs.astral.sh/uv/concepts/projects/
  - https://docs.astral.sh/uv/concepts/projects/dependencies/
  - https://docs.astral.sh/uv/concepts/projects/sync/
  - https://docs.astral.sh/uv/concepts/projects/workspaces/
- LangGraph 官方文档：
  - https://docs.langchain.com/oss/python/langgraph/overview
  - https://docs.langchain.com/oss/python/langgraph/persistence
  - https://docs.langchain.com/oss/python/langgraph/memory
- LangChain 官方文档：
  - https://docs.langchain.com/oss/python/langchain/mcp
  - https://docs.langchain.com/oss/python/langchain/multi-agent/skills
  - https://docs.langchain.com/oss/python/langchain/short-term-memory
  - https://docs.langchain.com/oss/python/langchain/long-term-memory
- Deep Agents 官方文档：
  - https://docs.langchain.com/oss/python/deepagents/overview
  - https://docs.langchain.com/oss/python/deepagents/skills
  - https://docs.langchain.com/oss/python/deepagents/long-term-memory
- `langchain-mcp-adapters` 官方仓库：
  - https://github.com/langchain-ai/langchain-mcp-adapters
- LangGraph 官方 PyPI：
  - https://pypi.org/project/langgraph-checkpoint-postgres/

本地参考：

- `/Users/wudalu/llm-app/pub-to-social-media/technical_design.md`
- `/Users/wudalu/llm-app/pub-to-social-media/graph/workflow.py`
- `/Users/wudalu/llm-app/pub-to-social-media/graph/state.py`
- `/Users/wudalu/llm-app/pub-to-social-media/pyproject.toml`
- `/Users/wudalu/hsbc_code/aether-frame/src/aether_frame/skills/registry/skill_catalog.py`
- `/Users/wudalu/hsbc_code/aether-frame/src/aether_frame/skills/registry/local_skill_discovery.py`
- `/Users/wudalu/hsbc_code/aether-frame/src/aether_frame/skills/runtime/skill_runtime.py`
- `/Users/wudalu/hsbc_code/aether-frame/src/aether_frame/infrastructure/adk/adk_memory_adapter.py`
- `/Users/wudalu/hsbc_code/aether-frame/src/aether_frame/tools/mcp/tool_wrapper.py`
