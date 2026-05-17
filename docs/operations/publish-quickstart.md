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
