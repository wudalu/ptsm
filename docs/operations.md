---
title: PTSM Operations
status: active
owner: ptsm
last_verified: 2026-05-23
source_of_truth: true
related_paths:
  - docs/operations/publish-quickstart.md
  - docs/operations/cloud-bootstrap.md
  - docs/operations/local-runbook.md
  - docs/operations/content-experiment-runbook.md
  - docs/operations/topic-radar-runbook.md
  - docs/operations/task-completion-automation.md
  - docs/research/2026-05-15-xhs-content-experiment-log.md
  - docs/research/2026-05-23-xhs-viral-meme-product-hooks.md
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/guide_post.py
  - src/ptsm/application/use_cases/collect_xhs_patterns.py
  - src/ptsm/application/use_cases/analyze_xhs_patterns.py
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/eval_artifact.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
  - .github/workflows/harness.yml
  - .github/workflows/docs-sync.yml
  - .github/pull_request_template.md
---

# Operations

这个页面只做操作索引，不重复复制 runbook 内容。

## Prerequisites: Start MCP Server

topic-radar 扫描和真实发布都需要 `xiaohongshu-mcp` 服务。在另一个终端启动：

```bash
# 默认启动（全局 cookie）
.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64

# 指定账号 cookie
COOKIES_PATH=cookies/fk-local.json .ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64
```

监听 `localhost:18060`，对应 `XHS_MCP_SERVER_URL=http://localhost:18060/mcp`。PTSM 不会自动拉起它。

## Primary Runbooks

- 简洁发布手册: [`docs/operations/publish-quickstart.md`](operations/publish-quickstart.md)
- 云上 clone 与启动: [`docs/operations/cloud-bootstrap.md`](operations/cloud-bootstrap.md)
- 本地运行与排障: [`docs/operations/local-runbook.md`](operations/local-runbook.md)
- 内容实验与指标回收: [`docs/operations/content-experiment-runbook.md`](operations/content-experiment-runbook.md)
- 任务完成后的自动校验: [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md)

## Stable Operator Commands

- `uv run python -m ptsm.bootstrap --help`
- `uv run python -m ptsm.bootstrap doctor`
- `uv run python -m ptsm.bootstrap docs-sync --base-ref origin/main`
- `uv run python -m ptsm.bootstrap docs-sync --changed-path src/ptsm/interfaces/cli/main.py --changed-path docs/operations/local-runbook.md`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`
- `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`
- `uv run python -m ptsm.bootstrap harness-check --changed-path src/ptsm/application/use_cases/harness_check.py --changed-path docs/operations.md`
- `uv run python -m ptsm.bootstrap install-git-hooks --base-ref origin/main`
- `uv run python -m ptsm.bootstrap gc`
- `uv run python -m ptsm.bootstrap gc --apply --runs-retention-days 14 --plan-runs-retention-days 14`
- `uv run python -m ptsm.bootstrap harness-evals --platform xiaohongshu --playbook-id fengkuang_daily_post`
- `uv run python -m ptsm.bootstrap harness-report --platform xiaohongshu --playbook-id fengkuang_daily_post --max-stale-docs 0 --min-run-completion-rate 0.8`
- `uv run python -m ptsm.bootstrap harness-report --fail-on-warning`
- `uv run python -m ptsm.bootstrap eval-artifact --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap diagnose-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap diagnose-publish --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap runs --account-id <account_id> --status completed`
- `uv run python -m ptsm.bootstrap run-events --account-id <account_id> --event publish_finished --group-by status`
- `uv run python -m ptsm.bootstrap plan-runs --status failed --failure-reason pytest_failed`
- `uv run python -m ptsm.bootstrap run-playbook --scene "夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析" --account-id acct-sushi-local --playbook-id sushi_poetry_daily_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --eval`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --publish-mode mcp-real --auto-generate-image --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
- `uv run python -m ptsm.bootstrap run-playbook --scene "分析令狐冲的自由人格与当代职场" --account-id acct-wuxia-local --playbook-id wuxia_character_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --auto-generate-image`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-playbook --scene "Google发布Gemini 3模型" --account-id acct-ai-tech-local --playbook-id ai_tech_daily_post`
- `uv run python -m ptsm.bootstrap run-playbook --scene "学一个表示坚持的高级词汇" --account-id acct-daily-english-local --playbook-id daily_english_post`
- Reddit英文讨论转译 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度" --account-id acct-reddit-curation-local --playbook-id reddit_curation_daily_post`
- 世界杯主题 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点" --account-id acct-world-cup-local --playbook-id world_cup_daily_post`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-fengkuang --scene "领导递来丝瓜汤式复盘，工牌当场想保持高雅" --account-id acct-fk-local --eval`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "同事临时加需求，想练一版三明治拒绝法边界句" --account-id acct-psychology-local --playbook-id modern_psychology_post --eval`
- 人设/爆品梗回归 dry-run:
  `uv run python -m ptsm.bootstrap run-playbook --scene "一个人住，想把床头角落改成十分钟适我主义手作位" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --eval`
- `uv run python -m ptsm.bootstrap guide-post`
- `uv run python -m ptsm.bootstrap guide-post --scene "看到别人周末都在聚会，自己突然觉得很失败" --non-interactive`
- `uv run python -m ptsm.bootstrap run-playbook --scene "下班后还在复盘会议上说错的那句话" --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-playbook --fresh-topic-research --account-id acct-psychology-local --playbook-id modern_psychology_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --fresh-topic-research --account-id acct-fk-local --auto-generate-image --publish-mode mcp-real --publish-visibility "仅自己可见"`
- `uv run python -m ptsm.bootstrap run-playbook --scene "..." --account-id acct-wuxia-local --playbook-id wuxia_character_post --publish-mode mcp-real --auto-generate-image --publish-visibility "公开" --wait-for-publish-status`
- `uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap collect-xhs-patterns --lane human_enrichment --keywords "人类丰容,家的丰容计划,低成本改造,钩织,拼豆" --sample-limit-per-keyword 8`
- `uv run python -m ptsm.bootstrap analyze-xhs-patterns --sample-path outputs/artifacts/xhs-pattern-library/samples-2026-05-17.json --lane human_enrichment`
- `uv run python -m ptsm.bootstrap run-playbook --scene "把书桌改成十分钟手作角" --account-id acct-enrichment-local --playbook-id human_enrichment_daily_post --format-pattern-path outputs/artifacts/xhs-pattern-library/current.json`

## Usage Notes

- 默认校验门禁优先使用 `pytest` 和 `doctor`。
- `docs-sync` 会读取 source-of-truth 文档 front matter 里的 `related_paths`，要求相关代码变更至少伴随一个最具体候选文档面的更新。
- `harness-check` 会串起 `docs-sync`、本地 `harness-report` 和 deterministic `pytest -q`，是本地 pre-push 和 CI 的统一入口。
- `docs-sync --base-ref ...` 和 `harness-check --base-ref ...` 比较的是 `<base-ref>...HEAD` 的已提交 diff；如果要在 commit 之前预检当前工作树改动，改用 `--changed-path ...` 显式传入。
- 本地默认 `harness-check` 只把 `docs-sync`、source-of-truth docs freshness 和 deterministic pytest 当成阻塞门禁；`--strict` 会把完整 `harness-report` warning 也变成阻塞。
- `install-git-hooks` 会写入 `.git/hooks/pre-push`，默认记录 `origin/main` 作为 base ref，并在 push 前先计算 `git merge-base HEAD origin/main`，再执行 `harness-check --base-ref <merge-base-sha>`。
- `gc` 默认只报告候选项；只有 `--apply` 才会删除本地 harness artifacts。
- `harness-evals` 只输出本地 JSON 汇总，不负责修改 artifact 或触发修复动作；现在也聚合 `.ptsm/evals` 中的 eval results。
- `harness-report` 是对 `doctor`、`gc`、`harness-evals` 的只读组合入口；需要把 warning 当成 gate 时，再显式加 `--fail-on-warning`。支持 `--max-required-eval-failures N` 对确定性 eval 失败做阈值控制。
- `eval` 默认关闭，每次运行时加 `--eval` 开启。CLI eval 只运行确定性 rule/contract evaluator；`eval-artifact` 显式启用 LLM judge 时会按 playbook `evaluation.yaml` 的 gate level 计入 `required_failed` 或 `warning_failed`。生成链路里的 XHS 内容质量 judge 由运行时 judge backend 配置决定，失败会触发重写而不是直接发布。
- 每个完成的 playbook artifact 和 CLI JSON 响应都会包含 `content_review`，用于人工确认生成逻辑、质量信号和发布前风险；review 不是自动发布批准。当前人审闭环通过 operator 阅读该说明并在对话中要求调整完成，不需要独立 review 操作台。
- `eval-artifact` 可对已有 artifact 独立跑 eval，不依赖运行时。
- `diagnose-publish` 是对单次发布问题的只读诊断入口，适合排查 “为什么没法自动确认已发布” 或 “为什么发布后状态不明确”。
- `--fresh-topic-research` 通过 topic-radar 先扫描平台热点，交互式让用户选题后再生成内容，此时 `--scene` 可选。
- `collect-xhs-patterns` / `analyze-xhs-patterns` 是周期采集和格式沉淀入口。普通 `run-playbook` 默认只读取本地 pattern snapshot，不会每次发帖都检索实时高互动帖子；需要实验特定 snapshot 时，用 `--format-pattern-path` 覆盖。
- `reddit_curation_daily_post` 会在 `reddit_discussion_scan` skill 激活时尝试读取 Reddit 英文讨论。按 Reddit Responsible Builder Policy，读取 Reddit API 前需要为该用途取得 explicit approval，并保持透明、限量、只读、不规避限制、不做 Reddit 数据商业化或 AI 训练。配置已获批 app 的 `REDDIT_CLIENT_ID`、`REDDIT_CLIENT_SECRET` 和 `REDDIT_USER_AGENT` 后会用 OAuth 形成真实最新 Reddit runtime context；如果 app 创建受验证码阻塞，可先设置 `REDDIT_PUBLIC_JSON_FALLBACK=true` 和非占位 `REDDIT_USER_AGENT`，用 Reddit public `.json` 页面低频只读扫描。未配置时 dry-run 会完成但上下文标记为 `missing_credentials`，不得声称内容来自最新 Reddit 热帖。
- `run-playbook` 是多 playbook 的通用入口；`run-fengkuang` 只保留给已有发疯文学兼容脚本和习惯命令。
- 做 XHS persona 或热梗映射回归时，优先用 dry-run 加 `--eval` 检查 artifact：标题应有具体物件/关系/场景钩子，正文应像真人账号在说话，eval 会通过 `combined_must_not_include_any` 拦截 `首先`、`其次`、`综上`、`本文`、`作为AI` 等模板化或元叙事表达。
- `guide-post` 是现代心理学发帖前的只读向导：默认走对话式引导，先问具体场景，再建议心理学 lane、机制、非诊断化重构、可保存小工具、评论提示和低密度封面，最后输出 Markdown brief 和可复制的 `run-playbook --publish-mode dry-run` 命令；脚本场景用 `--non-interactive` 输出 JSON。真正生成和发布仍走 `run-playbook`。
- `run-fengkuang --auto-generate-image` 会在缺少 `--publish-image-path` 时尝试调用已配置的图片后端生成封面；即梦配置优先于百炼配置，真实发布模式下默认也会尝试自动补图。
- `--no-auto-generate-image` 可以关闭自动补图；`--publish-image-path` 使用手动图片；`--local-image-style note_card|iphone_notes|wechat_chat` 可以主动选择本地截图式封面，即使外部图片 provider 已配置也生效。
- 真实发布只要最终有图片，就必须经过 `watermark_removal` 后处理；dry-run 图片实验仍可用 `WATERMARK_REMOVAL_ENABLED=true` 选择是否预览去水印结果。
- 小红书真实发布前，需要先单独启动外部 `xiaohongshu-mcp` 服务；PTSM 默认不会自动拉起 `.ptsm/bin/xhs-mcp/xiaohongshu-mcp-darwin-amd64`。
- 浏览器动作保留为人工或条件触发，不应成为默认无人值守 gate。
- 更细的触发策略以 [`docs/operations/task-completion-automation.md`](operations/task-completion-automation.md) 为准。

## Daily Enforcement

- 本地开发:
  `uv run python -m ptsm.bootstrap install-git-hooks --base-ref origin/main`
- 手动预检:
  `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main`
- 手动严格预检:
  `uv run python -m ptsm.bootstrap harness-check --base-ref origin/main --strict`
- CI:
  `.github/workflows/harness.yml` 会在 PR 和 `main` push 上运行 `harness-check --strict`
- GitHub 仓库设置:
  在 branch protection 里把 `harness` 设成 required status check；如果要更快失败，也可以把 `docs-sync` 一起设成 required
