# Publish Quickstart

这份是简洁版发布手册。完整排障流程看 [`local-runbook.md`](local-runbook.md)。

## Three Choices

### 1. 是否使用 XHS MCP

- 不用 XHS MCP: 普通 dry-run，只生成内容和 artifact。
- 用 XHS MCP 做实时选题: 加 `--fresh-topic-research`，需要先启动并登录 `xiaohongshu-mcp`。
- 用 XHS MCP 真实发布: 加 `--publish-mode mcp-real`，需要先启动并登录 `xiaohongshu-mcp`。

普通 `run-playbook` 默认读取本地 `outputs/artifacts/xhs-pattern-library/current.json`，不会每次都检索小红书高互动笔记。周期采集用 `collect-xhs-patterns` / `analyze-xhs-patterns`。

### 2. 是否让系统生图

- 只生成正文: 不传图片相关参数，dry-run 默认不生图。
- 强制生图: 加 `--auto-generate-image`。
- 强制不生图: 加 `--no-auto-generate-image`，即使真实发布也不自动补图。
- 手动用本地图片: 加一个或多个 `--publish-image-path <path>`。
- 主动选择本地截图风格: 加 `--local-image-style note_card|iphone_notes|wechat_chat`。

真实发布如果没有 `--publish-image-path` 且没有 `--no-auto-generate-image`，默认会自动补图。图片路由由运行时决定：operator 的 `--local-image-style` 优先；正文里的 `final_content.image_plan` 可要求 `local_social_screenshot` 或 provider image；没有策略时再按已配置的图片 provider 或本地 renderer 选择。

`wechat_chat` 现在是内容区聊天转录封面，不是完整手机截图：不画头部、输入栏或头像。适合真实聊天、群聊、可复制回复和评论触发；检查 artifact 时看 `image_generation.image_plan` 里的 `theme`、`chat_title`、`chat_times` 等字段是否符合预期。

### 3. 去水印

真实发布只要最终有图片，就必须经过 `watermark_removal` 后处理。dry-run 的图片实验仍可用 `WATERMARK_REMOVAL_ENABLED=true` 选择是否预览去水印结果。

发布后检查 artifact:

- `content_review`
- `content_review.image_plan`
- `image_generation`
- `image_generation.image_plan`
- `watermark_removal`
- `publish_result`
- `post_publish_checks`

## 对话式发布引导

用户不需要一次性想清楚所有 CLI 参数。可以先用自然语言告诉 agent 发布目标，让 agent 逐步确认风险开关，再给出 dry-run、私密发布或公开发布命令。

推荐对话节奏:

1. 先说清楚账号、主题和发布目标。
2. 让 agent 先 dry-run，不要跳过内容和图片策略 review。
3. 明确是否使用 XHS MCP、是否自动生图、是否强制本地截图风格。
4. 真实发布先用 `仅自己可见` 验货；确认无误后再公开发布。
5. 真实发布有图片时不要跳过去水印检查，artifact 里必须有 `watermark_removal`。

示例一：只做内容和图片预览，不发布。

```text
用户: 我要给发疯文学账号做一条“领导18:57发来一句在吗”的帖子，先 dry-run，不要发布。封面想看微信聊天记录风格。
助手: 我会先走 dry-run，并主动选择本地 `wechat_chat` 封面。不会调用 XHS MCP 发布。
助手: 运行命令：
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57发来一句在吗" \
  --account-id acct-fk-local \
  --auto-generate-image \
  --local-image-style wechat_chat
助手: 跑完后请重点看 artifact 里的 `content_review`、`content_review.image_plan`、`image_generation.image_plan` 和正文是否适合发布。
```

示例二：先私密发布验货。

```text
用户: 这条内容可以了，用 XHS MCP 发到小红书，但先仅自己可见。图片让系统按主题决定，不要我手动传图。
助手: 我会使用 `--publish-mode mcp-real`，保留默认自动补图，并设置 `--publish-visibility "仅自己可见"`。真实发布有图片时会强制记录 `watermark_removal`。
助手: 运行前请确认 `.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64` 已启动，并且 `xhs-login-status` 是已登录。
助手: 运行命令：
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57发来一句在吗" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "仅自己可见"
助手: 发布后请用小红书 App 人工检查样式。私密帖如果没有 `post_id`，自动核验可能会返回 `manual_check_required`，这不等于发布失败。
```

示例三：确认后公开发布并等待核验。

```text
用户: 私密帖看过了，正文和图都没问题。现在公开发布同一个主题，自动等待发布状态。
助手: 我会走公开发布，并加 `--wait-for-publish-status` 做短轮询核验。不要跳过 artifact 检查：`publish_result`、`post_publish_checks` 和 `watermark_removal` 都要看。
助手: 运行命令：
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57发来一句在吗" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "公开" \
  --wait-for-publish-status
助手: 如果状态没有自动确认，再运行 `diagnose-publish --artifact outputs/artifacts/<artifact>.json` 排查。
```

## Safe Dry-Run

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周五下班前又被拉去开会" \
  --account-id acct-fk-local
```

## Dry-Run With Local Screenshot Cover

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "领导18:57发来一句在吗" \
  --account-id acct-fk-local \
  --auto-generate-image \
  --local-image-style wechat_chat
```

## Private Real Publish

先启动 MCP:

```bash
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

再发仅自己可见:

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周五下班前又被拉去开会" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "仅自己可见"
```

私密帖通常以小红书 App 人工确认样式为准，因为上游 MCP 可能不会返回可自动核验的 `post_id`。

## Public Real Publish

```bash
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周五下班前又被拉去开会" \
  --account-id acct-fk-local \
  --publish-mode mcp-real \
  --auto-generate-image \
  --publish-visibility "公开" \
  --wait-for-publish-status
```

公开帖可以用标题精确匹配做短轮询核验。失败时再用 `diagnose-publish` 或 `xhs-open-browser` 排查。
