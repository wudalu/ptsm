---
title: PTSM Operations
status: active
owner: ptsm
last_verified: 2026-05-02
source_of_truth: true
related_paths:
  - docs/operations/cloud-bootstrap.md
  - docs/operations/local-runbook.md
  - docs/operations/task-completion-automation.md
  - src/ptsm/interfaces/cli/main.py
  - src/ptsm/application/use_cases/run_playbook.py
  - src/ptsm/application/use_cases/docs_sync.py
  - src/ptsm/application/use_cases/harness_check.py
  - src/ptsm/application/use_cases/install_git_hooks.py
  - .github/workflows/harness.yml
  - .github/workflows/docs-sync.yml
  - .github/pull_request_template.md
---

# Operations

这个页面只做操作索引，不重复复制 runbook 内容。

## Primary Runbooks

- 云上 clone 与启动: [`docs/operations/cloud-bootstrap.md`](operations/cloud-bootstrap.md)
- 本地运行与排障: [`docs/operations/local-runbook.md`](operations/local-runbook.md)
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
- `uv run python -m ptsm.bootstrap diagnose-publish --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap diagnose-publish --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --run-id <run_id>`
- `uv run python -m ptsm.bootstrap logs --artifact outputs/artifacts/<artifact>.json`
- `uv run python -m ptsm.bootstrap runs --account-id <account_id> --status completed`
- `uv run python -m ptsm.bootstrap run-events --account-id <account_id> --event publish_finished --group-by status`
- `uv run python -m ptsm.bootstrap plan-runs --status failed --failure-reason pytest_failed`
- `uv run python -m ptsm.bootstrap run-playbook --scene "夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析" --account-id acct-sushi-local --playbook-id sushi_poetry_daily_post`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local`
- `uv run python -m ptsm.bootstrap run-fengkuang --scene "..." --account-id acct-fk-local --auto-generate-image`
- `uv run python -m ptsm.bootstrap xhs-check-publish --artifact outputs/artifacts/<artifact>.json`

## Usage Notes

- 默认校验门禁优先使用 `pytest` 和 `doctor`。
- `docs-sync` 会读取 source-of-truth 文档 front matter 里的 `related_paths`，要求相关代码变更至少伴随一个最具体候选文档面的更新。
- `harness-check` 会串起 `docs-sync`、本地 `harness-report` 和 deterministic `pytest -q`，是本地 pre-push 和 CI 的统一入口。
- `docs-sync --base-ref ...` 和 `harness-check --base-ref ...` 比较的是 `<base-ref>...HEAD` 的已提交 diff；如果要在 commit 之前预检当前工作树改动，改用 `--changed-path ...` 显式传入。
- 本地默认 `harness-check` 只把 `docs-sync`、source-of-truth docs freshness 和 deterministic pytest 当成阻塞门禁；`--strict` 会把完整 `harness-report` warning 也变成阻塞。
- `install-git-hooks` 会写入 `.git/hooks/pre-push`，默认记录 `origin/main` 作为 base ref，并在 push 前先计算 `git merge-base HEAD origin/main`，再执行 `harness-check --base-ref <merge-base-sha>`。
- `gc` 默认只报告候选项；只有 `--apply` 才会删除本地 harness artifacts。
- `harness-evals` 只输出本地 JSON 汇总，不负责修改 artifact 或触发修复动作。
- `harness-report` 是对 `doctor`、`gc`、`harness-evals` 的只读组合入口；需要把 warning 当成 gate 时，再显式加 `--fail-on-warning`。
- `diagnose-publish` 是对单次发布问题的只读诊断入口，适合排查 “为什么没法自动确认已发布” 或 “为什么发布后状态不明确”。
- `run-playbook` 是多 playbook 的通用入口；`run-fengkuang` 只保留给已有发疯文学兼容脚本和习惯命令。
- `run-fengkuang --auto-generate-image` 会在缺少 `--publish-image-path` 时尝试调用已配置的图片后端生成封面；即梦配置优先于百炼配置，真实发布模式下默认也会尝试自动补图。
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
