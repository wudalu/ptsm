---
title: PTSM Cloud Bootstrap
status: active
owner: ptsm
last_verified: 2026-04-22
source_of_truth: true
related_paths:
  - README.md
  - .env.example
  - src/ptsm/config/settings.py
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/accounts/definitions/acct-fk-local.yaml
  - docs/operations/local-runbook.md
  - docs/operations/task-completion-automation.md
---

# PTSM Cloud Bootstrap

这份 runbook 说明：把仓库 clone 到一台新的云主机后，如何完成环境配置、跑通基线、执行第一条任务，以及怎样让另一个 agent 知道应该从哪里调用 PTSM。

## Recommended Placement

这份文档放在 `docs/operations/` 是合适的，因为它主要回答：

- 机器上要装什么
- `.env` 要配什么
- 第一条命令怎么跑
- 出问题先查什么
- 另一个 agent 应该从哪个稳定入口调用

这些都是操作问题，不是架构问题。

## Assumptions

- 目标机器能访问公网。
- 目标机器可安装 `uv`。
- 目标机器至少有 Python 3.11。
- 如果需要真实发布小红书，还需要一台可访问的 `xiaohongshu-mcp` 服务，并且该服务已经完成登录。

如果只是做开发、dry-run、计划执行、日志诊断，这台机器不需要浏览器和 GUI。

## Step 1: Clone And Install Dependencies

```bash
git clone <your-repo-url>
cd ptsm

curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync
```

项目元数据和 CLI 入口定义在 [`pyproject.toml`](../../pyproject.toml)。

## Step 2: Create `.env`

先复制环境模板：

```bash
cp .env.example .env
```

最小 dry-run 配置：

```env
DEFAULT_LLM_PROVIDER=deepseek
DEFAULT_LLM_MODEL=deepseek-chat
DEEPSEEK_API_KEY=your-deepseek-key
XHS_MCP_SERVER_URL=http://localhost:18060/mcp
XHS_DEFAULT_VISIBILITY=仅自己可见
```

如果要自动生成封面图，再补：

```env
PIC_MODEL_API_KEY=your-bailian-key
PIC_MODEL_BASE_URL=https://dashscope.aliyuncs.com/api/v1
PIC_MODEL_MODEL=qwen-image-2.0-pro
PIC_MODEL_SIZE=1104*1472
```

完整字段定义见 [`src/ptsm/config/settings.py`](../../src/ptsm/config/settings.py)。

## Step 3: Verify Baseline

先看 CLI 是否可用：

```bash
uv run python -m ptsm.bootstrap --help
```

再跑环境体检：

```bash
uv run python -m ptsm.bootstrap doctor
```

再跑测试基线：

```bash
uv run pytest -q
```

如果这里只有 dry-run 需求，`doctor` 通过且测试通过，就可以进入任务执行。

## Step 4: Run The First Task

默认本地账号定义是 [`src/ptsm/accounts/definitions/acct-fk-local.yaml`](../../src/ptsm/accounts/definitions/acct-fk-local.yaml)，所以最小命令是：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四晚上加班后回家" \
  --account-id acct-fk-local
```

这会走：

- account lookup
- playbook selection
- `plan -> execute -> reflect -> finalize`
- artifact 落盘
- dry-run publish receipt

真实运行时结构见 [`docs/runtime.md`](../runtime.md)。

## Step 5: Optional Image Generation

如果希望 dry-run 也验证出图链路：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local \
  --auto-generate-image
```

真实发布模式下，如果未显式传 `--publish-image-path`，且 Bailian 配置可用，PTSM 默认也会尝试自动补图。

## Step 6: Real Publish Prerequisites

真实发布前，先启动小红书 MCP 服务。PTSM 只会调用这个外部 HTTP 服务，不会自动把它拉起：

```bash
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

这个二进制默认监听 `:18060`，对应 `.env` 里的 `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`。

服务启动后，再确认小红书 MCP 服务可用：

```bash
uv run python -m ptsm.bootstrap xhs-login-status
```

如需扫码登录：

```bash
uv run python -m ptsm.bootstrap xhs-login-qrcode --output /tmp/xhs-login-qrcode.png
```

如果云主机没有 GUI，就把二维码文件取出来后人工扫码，不要依赖浏览器自动打开。

真实发布最小命令：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --wait-for-publish-status
```

如果你希望强制私密：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --publish-visibility "仅自己可见" \
  --wait-for-publish-status
```

更细的登录、发布和诊断说明见 [`docs/operations/local-runbook.md`](local-runbook.md)。

## Step 7: What Another Agent Should Call

推荐另一个 agent 把 PTSM 当成 `CLI runtime` 来用，而不是直接 import 内部模块。

最稳定的入口是：

- `uv run python -m ptsm.bootstrap ...`
- 或已经安装好的 `ptsm ...`

典型调用面：

```bash
uv run python -m ptsm.bootstrap doctor

uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local

uv run python -m ptsm.bootstrap logs --run-id <run_id>
uv run python -m ptsm.bootstrap diagnose-publish --run-id <run_id>
uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json
```

如果另一个 agent 的工作是“按计划完成开发任务”，它应该优先用：

```bash
uv run python -m ptsm.bootstrap run-plan \
  --plan docs/plans/your-plan.md \
  --verify-command "uv run pytest -q" \
  --verify-command "uv run python -m ptsm.bootstrap doctor"
```

这个模式的完整说明见 [`docs/operations/task-completion-automation.md`](task-completion-automation.md)。

## Step 8: What Another Agent Should Read First

推荐阅读顺序：

1. [`docs/index.md`](../index.md)
2. [`docs/architecture.md`](../architecture.md)
3. [`docs/runtime.md`](../runtime.md)
4. [`docs/operations.md`](../operations.md)
5. [`docs/operations/local-runbook.md`](local-runbook.md)
6. [`docs/operations/task-completion-automation.md`](task-completion-automation.md)

如果它只是“调用 PTSM 去完成一条内容任务”，看到第 4 步通常就够了。

如果它要“把 PTSM 纳入自己的开发闭环”，第 6 步是重点。

## Cloud-Specific Notes

- 无 GUI 环境下，不要把 `xhs-open-browser` 当默认路径。
- 小红书真实发布仍依赖 `xiaohongshu-mcp` 服务和有效登录态。
- `仅自己可见` 的帖子在上游未返回 `post_id/post_url` 时，仍然不能完全自动核验。
- 最稳定的云上用途仍然是：`dry-run + run-plan + diagnostics + harness-report`。
