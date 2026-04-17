# PTSM Task Completion Automation

## Goal

这份文档说明两件事：

1. 任务开发完成后，PTSM 这一套诊断 / 日志 / 发布校验流程应该怎么跑。
2. 后续在 Codex 工作流里，怎样让它在每个任务完成后自动触发，而不是靠人手动补跑。

## Core Principle

不要把“任务完成后记得跑这些命令”写成纯说明文字然后指望模型记住。

真正可靠的做法是：

- 把校验动作收敛成稳定命令
- 把这些命令写进计划文件的 `verify:` 段
- 让 `ptsm run-plan` 或 `codex-plan-runner` 在每个任务后自动执行

现在仓库里已经有这些稳定命令：

```bash
uv run python -m ptsm.bootstrap doctor
uv run python -m ptsm.bootstrap logs --run-id <run_id>
uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json
uv run python -m ptsm.bootstrap xhs-open-browser --target login
uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json
uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --wait-for-publish-status
```

## Recommended Trigger Strategy

推荐分两层：

### Layer 1: Default Verification Gate

这是大部分开发任务都应该执行的最小门槛。

```bash
uv run pytest -q
uv run python -m ptsm.bootstrap doctor
```

适用场景：

- 配置改动
- CLI 改动
- 运行时逻辑改动
- 日志 / artifact / run store 改动

### Layer 2: Task-Specific Smoke Or Publish Check

只有任务真的改到了发布链路、artifact、XHS 登录态、浏览器打开、状态检查时，才加额外校验。

典型命令：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --wait-for-publish-status
```

如果任务已知会产出某个 artifact，也可以加：

```bash
uv run python -m ptsm.bootstrap xhs-check-publish \
  --artifact outputs/artifacts/<artifact>.json
```

## The Important Distinction

### What Should Be Automatic

这些适合在每个任务结束后自动跑：

- `pytest`
- `doctor`
- dry-run smoke
- artifact-based status check

### What Should Usually Stay Manual Or Conditional

这些不建议作为默认自动动作：

- `xhs-open-browser`
- `run-fengkuang --open-browser-if-needed`

原因很直接：

- 它会拉起 GUI 浏览器
- 在无人值守或半自动 session 里容易打断流程
- 本地有头环境和 CI / 后台环境行为不同

所以浏览器动作更适合：

- 本地交互式调试
- 只在状态检查返回 `manual_check_required` 时再触发

## How To Auto-Trigger After Every Task

### Option A: Use `verify:` In The Plan File

这是推荐方案。每个任务自己定义它完成后必须跑什么。

示例：

````md
### Task 3: Add publish status handling

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py -q
  - uv run python -m ptsm.bootstrap doctor
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周三下班地铁没座位" --account-id acct-fk-local --wait-for-publish-status
```
````

效果：

- Codex 完成这个任务后
- `run-plan` / `codex-plan-runner` 会立刻跑上面这些命令
- 任意一个失败，这个任务就不会被判定为通过

### Option B: Use CLI-Level `--verify-command`

适合所有任务都共享同一组校验时使用。

```bash
uv run python -m ptsm.bootstrap run-plan \
  --plan docs/plans/your-plan.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m ptsm.bootstrap doctor"
```

效果：

- 计划中的每个任务结束后
- 都会执行这两条命令

### Option C: Mixed Mode

这是最实用的组合：

- 全局 `--verify-command` 放通用门槛
- 任务级 `verify:` 放特定 smoke / publish check

推荐写法：

```bash
uv run python -m ptsm.bootstrap run-plan \
  --plan docs/plans/your-plan.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m ptsm.bootstrap doctor"
```

然后在某些任务里额外写：

````md
```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_xhs_publish_status.py -q
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周三下班地铁没座位" --account-id acct-fk-local --wait-for-publish-status
```
````

## Recommended Patterns By Task Type

### Pure Code Task

```yaml
verify:
  - uv run pytest tests/unit/your_test.py -q
  - uv run python -m ptsm.bootstrap doctor
```

### Runtime / CLI Task

```yaml
verify:
  - uv run pytest -q
  - uv run python -m ptsm.bootstrap doctor
```

### Publish Pipeline Task

```yaml
verify:
  - uv run pytest -q
  - uv run python -m ptsm.bootstrap doctor
  - uv run python -m ptsm.bootstrap run-fengkuang --scene "周三下班地铁没座位" --account-id acct-fk-local --wait-for-publish-status
```

### Browser Fallback Task

```yaml
verify:
  - uv run pytest tests/unit/application/use_cases/test_xhs_browser.py -q
  - uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json
```

说明：

- 浏览器打开本身通常不要放进默认自动 gate
- 更推荐先跑状态检查
- 只有状态检查返回 `manual_check_required` 时，才人工或交互式触发 `xhs-open-browser`

## How To Make Codex Follow This Consistently

有两个层次：

### Deterministic Layer

把命令写进 `verify:` 或 `--verify-command`。

这是强约束，最可靠。

### Instruction Layer

可以在 `AGENTS.md` 里补一句：

```md
After completing each implementation task, rely on the plan's verify commands or explicit verify-command gates. Do not mark a task complete before those commands pass.
```

但要明确：

- `AGENTS.md` 只是行为约束
- 真正能保证自动触发的是 `run-plan` / `codex-plan-runner`

如果两者冲突，优先相信命令门禁，不要相信说明文字。

## Recommended Default For This Repo

后续新计划建议默认这样起步：

```bash
uv run python -m ptsm.bootstrap run-plan \
  --plan docs/plans/<your-plan>.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m ptsm.bootstrap doctor"
```

然后只给少数任务补任务级 `verify:`：

- 发布链路任务
- artifact / logs 任务
- XHS 登录 / 浏览器 / 状态检查任务

## Practical Rule

一句话总结：

任务完成后的自动触发，不要靠“完成后记得跑一下”，而要靠“任务定义里已经写死 verify 命令”。

## Verification Evidence Artifact

从现在开始，`ptsm run-plan` 在有 `state_path` 时，会额外写一个同目录 sibling artifact：

- state: `.ptsm/plan_runs/<run>.json`
- evidence: `.ptsm/plan_runs/<run>.evidence.json`

这个 evidence 文件会保留：

- 每个 task 的 attempt history
- 每条 verify 命令的 exit code
- verify 的 stdout / stderr
- 命令开始和结束时间，以及持续时长

这意味着：

- `state` 负责 resume
- `evidence` 负责审计和回看

对 playbook runtime 来说，现在还有第三类持久状态：

- side effects: `.ptsm/agent_runtime/side-effects.json`

这份 ledger 负责记录已经成功落地的副作用结果，当前主要用于：

- 同一 `thread_id` 下避免重复 publish
- 让 resume / rerun 先读 ledger，再决定是否真的再次执行副作用

边界也要明确：

- `state` 不是副作用 ledger
- `evidence` 不是 resume source of truth
- `side-effects` 不缓存失败 publish，也不缓存只读状态检查

如果任务第一次 verify 失败、第二次修好，最终 evidence 里会同时保留失败和成功两次记录，不会只剩最后一次覆盖结果。
