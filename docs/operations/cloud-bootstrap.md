---
title: PTSM Cloud Bootstrap
status: active
owner: ptsm
last_verified: 2026-08-21
source_of_truth: true
related_paths:
  - README.md
  - .env.example
  - src/ptsm/config/settings.py
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/application/services/image_carousel_transaction.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/domain/psychology_carousel.py
  - src/ptsm/infrastructure/memory/store.py
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

如果要自动生成封面图，优先使用即梦配置：

```env
JIMENG_API_KEY=your-volcengine-ak
JIMENG_SECRET_KEY=your-volcengine-sk
JIMENG_MODEL=jimeng_t2i_v40
JIMENG_BASE_URL=https://visual.volcengineapi.com
JIMENG_WIDTH=1536
JIMENG_HEIGHT=2048
```

没有即梦凭证时，也可以使用百炼配置：

```env
PIC_MODEL_API_KEY=your-bailian-key
PIC_MODEL_BASE_URL=https://dashscope.aliyuncs.com/api/v1
PIC_MODEL_MODEL=qwen-image-2.0-pro
PIC_MODEL_SIZE=1104*1472
```

系统自动生成的图片会请求源头不加 provider 水印：即梦使用 `logo_info.add_logo=false`，百炼使用 `watermark=false` 并保留水印/logo negative prompt。发布 artifact 的 `image_generation.watermark_policy.requested` 应为 `no_provider_watermark`；provider/manual 图片在真实发布时仍会执行 `watermark_removal`，PTSM 本地 renderer 图片则安全跳过。心理学 `psychology_text_card_v1` 是 local-only，不需要即梦或百炼凭证。

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

也可以主动选择本地截图式封面，不调用外部图片 provider：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57突然发来一句在吗" \
  --account-id acct-fk-local \
  --auto-generate-image \
  --local-image-style wechat_chat
```

`wechat_chat` 会生成内容区聊天转录封面，而不是完整手机截图；它不绘制头部、输入栏或头像。需要复刻真实对话时，让正文或 `final_content.image_plan` 提供多行 speaker 文本、`theme`、`chat_title` 和 `chat_times` 等字段。

真实发布模式下，如果未显式传 `--publish-image-path`，且没有传 `--no-auto-generate-image`，PTSM 默认会自动补图。普通帖的 operator `--local-image-style` 优先；否则运行时可根据 `final_content.image_plan` 选择本地截图式封面或 provider image。learning-series 不允许 image/style override。即梦和百炼同时配置时，普通 provider 路径优先使用即梦。

现代心理学默认不是一张 provider cover，而是本地原子图片集：

```bash
uv run python -m ptsm.bootstrap run-playbook \
  --scene "凌晨两点，我还在改白天会议那句话" \
  --account-id acct-psychology-local \
  --playbook-id modern_psychology_post \
  --publish-mode dry-run \
  --auto-generate-image
```

`guide-post` 会先给出 `text_carousel`、`psychology_text_card_v1`、4–7 页和 ordered roles；命令
仍只使用 `--auto-generate-image`。这是一个主题的一组 4–7 页，不是 batch；显式 >7 页/12 张请求必须
先由 caller 选择 `one_carousel`（支持的一组）、`multiple_posts`（逐帖确认并独立 run/receipt），或
unsupported `independent_assets`（8–12 张 **independent image assets** 必须转交另行授权的素材流程），
不能循环、拆分、重复、伪造 ready 或把 `max_text_units` 当成图片数。系统在 `outputs/generated_images/` 下先写 staging，再把全部
ordered PNG 与 `manifest.json` 原子 rename 为 content-addressed committed set。请把
`outputs/generated_images/` 放在持久磁盘上，并确保 staging 与 final set 位于同一 filesystem；不要把
它挂成每次任务结束即销毁的临时层。`outputs/artifacts/generated-image-assets/` 也应持久化，以保留
ordinary 与 current v2 learning carousel 的 page-aware operational ledger；sealed learning artifact/response 不复制 ledger 或路径。**`.ptsm/agent_runtime/` 也必须使用同一稳定、可写的持久卷**：File execution memory 保存 ordinary carousel 的 reservation 和 recent 12 successful complete receipt identities，丢失该目录会丢失跨重启去重窗口。不要在有 writer 时通过删除/复制该目录“释放” reservation；已知失败会 release，stale lease 自动恢复。容器/主机重启后，已提交 set 可用于发布失败重试。

成功 ordinary artifact 可检查 `image_generation.status=committed`、`image_count`、`set_id`、
`manifest_path`、`manifest_sha256` 和 ordered `pages`，其中每页包含 `page_sha256` / `file_sha256`。
只有该 receipt 和 ledger 都成功后才给 ordinary response `carousel_delivery.status=ready`，供外层 relay
按完整有序 `attachments` 转发；PTSM 本身不拥有 chat/IM sender，ready 不代表 delivered。relay 的 ACK、
outcome 和 retry 必须保存在 relay 自己的 receipt-keyed record，不能被 PTSM response/artifact 推断或回写。learning-series
artifact 为避免路径/课程内容泄漏，只保留 renderer/style/count/manifest hash 的安全 receipt；可信 operator 可从
持久输出卷检查 manifest。任一页、manifest 或 ledger 失败都会返回 `psychology_carousel_generation_failed`，
此时 PTSM 只能说明它 **emitted no ready handoff** 且 **invoked no external chat/IM sender**；它不能断言
外层 relay、目标平台或用户未收到任何页，**relay ACK/outcome is authoritative** for whether any page was
received or delivered.

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
  --auto-generate-image \
  --wait-for-publish-status
```

如果你希望强制私密：

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周三下班地铁没座位" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "仅自己可见"
```

真实发布按图片来源执行 `watermark_removal`：PTSM 本地 renderer 图会跳过去水印，provider/LLM 图和手动图片会先清理再把图片交给 XHS MCP。私密帖通常需要在小红书 App 人工确认样式，因为上游 MCP 可能不会返回可自动核验的 `post_id`。

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
- psychology carousel 本身不依赖图片 provider，但依赖 Pillow 字体/渲染环境和可持久、同 filesystem 的 `outputs/generated_images/`；部署时要备份 committed set manifest、page-aware asset ledger 和 `.ptsm/agent_runtime/` execution-memory store，后者保存 ordinary recent-12 receipt identities/reservations。
- `仅自己可见` 的帖子在上游未返回 `post_id/post_url` 时，仍然不能完全自动核验。
- 最稳定的云上用途仍然是：`dry-run + run-plan + diagnostics + harness-report`。
