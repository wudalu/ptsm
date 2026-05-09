# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run pytest -q                          # run all tests
uv run pytest -q tests/unit/path/to_test.py  # single test file
uv run pytest -q -k "test_name"           # filter by test name
uv run python -m ptsm.bootstrap --help    # CLI help
ptsm run-fengkuang --scene "场景描述"      # run fengkuang playbook
ptsm run-fengkuang --scene "..." --eval      # run with evaluation enabled
ptsm run-playbook --scene "..." --account-id <id> --playbook-id <id>  # generic playbook
ptsm harness-check                        # pre-push docs-sync + drift + test gate
ptsm harness-check --strict               # full gate (used in CI)
ptsm install-git-hooks                    # install pre-push harness gate
ptsm docs-sync                            # check changed paths have matching doc updates
ptsm doctor --server-url <url>            # MCP connectivity check
ptsm logs --run-id <id>                   # view run logs
ptsm runs --account-id <id> --limit 5     # list recent runs
ptsm gc --apply                           # clean stale artifacts
ptsm harness-report                       # snapshot: doctor + gc + evals
topic-radar scan                          # multi-platform topic scan
topic-radar scan --platforms xhs --mcp-check  # check MCP health only
topic-radar teardown <feed_id>            # deconstruct a XHS post
```

## Architecture

PTSM is a playbook-driven social media agent runtime. It currently has a working `fengkuang → xiaohongshu` vertical slice with platform abstractions being extracted on top.

### Package dependency direction (enforced by `tests/unit/architecture/`)

```
interfaces ──► application ──► agent_runtime ──► infrastructure
                                  │                    ▲
                                  ▼                    │
                              playbooks ───────────────┘
                              skills
```

- `interfaces/cli/` — CLI entrypoint. May depend on `application`, `config`, `plan_runner`. Must NOT depend on `infrastructure` or `agent_runtime`.
- `application/` — use-case orchestration. May depend on `agent_runtime`, `accounts`, `playbooks`, `config`, `infrastructure`.
- `agent_runtime/` — LangGraph graph execution with nodes: `ingest → planner → executor → reflector`. Depends on `config`, `infrastructure`, `playbooks`, `skills`.
- `infrastructure/` — external adapters: LLM, image generation, publishers (XHS MCP), artifacts, observability, memory/checkpoints. Must NOT depend on `application` or `interfaces`.
- `playbooks/` — playbook YAML definitions and loader. No upward dependencies.
- `skills/` — builtin skill metadata, selection, surface, loading. No upward dependencies.

### Key runtime flow

1. `planner` node selects a playbook + skills based on the scene
2. `executor` node drafts content using the LLM, persona, and skill prompts
3. `reflector` node evaluates the draft and decides: `continue | retry | replan | finalize | fail`
4. Publishing is orchestrated by `application/use_cases/run_playbook.py`, not inside the graph

### Settings

`pydantic-settings` reads from `.env`. Key env vars: `DEEPSEEK_API_KEY`, `PIC_MODEL_API_KEY` (Bailian image gen), `JIMENG_API_KEY`/`JIMENG_SECRET_KEY` (Jimeng image gen), `XHS_MCP_SERVER_URL`. Never commit `.env`.

All settings aliases are defined in `src/ptsm/config/settings.py`.

### Docs as source of truth

Start at `docs/index.md` — the agent-readable docs map. Key docs: `architecture.md`, `runtime.md`, `playbooks.md`, `skills.md`, `harness-engineering.md`, `development-workflow.md`. When changing code, the `docs-sync` gate checks whether corresponding docs in `related_paths` were also updated.

### Harness engineering conventions

- **NEVER skip the development workflow.** 任何新增功能、重构、架构变更，必须严格遵循 `docs/development-workflow.md` 的 8 步流程：读 docs → 澄清需求 → 写计划 → 定义验证 → 小任务实现 → 端到端验证 → 同步 docs → 跑 harness gate。不允许跳过任何步骤，不允许"先写代码再补计划"。即使看起来"很简单"的改动，也要先读相关 docs 再动手。
- **先读 docs/ 再写代码。** 每次开发前，先查阅 `docs/index.md` 找到相关文档，了解当前架构、运行时、playbook/skill 结构和操作规范。`docs-sync` gate 会强制要求代码变更伴随文档更新。
- **开发完成后必须更新文档。** 代码变更后，同步更新对应的 source-of-truth docs（如 `docs/architecture.md`、`docs/runtime.md`、`docs/harness-engineering.md` 等），并更新文档中的 `last_verified` 日期。
- **大型新增开发先走 workflow。** 新增功能、新增领域、新增 runtime skill、新增发布链路、观测面或 harness 规则时，先读 `docs/development-workflow.md`，再写 `docs/plans/YYYY-MM-DD-<topic>.md`，并在计划里定义 `verify:` / `done_when:`。
- **所有设计和计划文档写入 `docs/plans/`。** 不另开 `docs/superpowers/` 或其他目录。命名规范：`YYYY-MM-DD-<topic>.md`。历史计划也放在同一目录下，与 `docs/index.md` 的 Historical Context 一致。
- **新增领域只加文件不改旧代码。** 新增账号域（playbook + skills + account）时，优先通过添加新定义文件实现，不修改已有运行时逻辑、现有 playbook/skill 定义和基础设施代码。需要新行为时，通过扩展点（registry、配置、回调注入）追加新模块，而非在旧文件内部加 if-else 分支。
- Pre-push hook runs `harness-check` (docs-sync + drift checks + pytest)
- Import boundary tests in `tests/unit/architecture/`
- Run artifacts stored locally in `outputs/`
- Side-effect ledger prevents duplicate publishes on the same thread_id

### Dry-run & testing workflow

```bash
# 标准 dry-run（不发布，不生成图片）
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周四晚上加班后回家" \
  --account-id acct-fk-local

# 带图片生成的 dry-run
uv run python -m ptsm.bootstrap run-fengkuang \
  --scene "周六社畜躺平" \
  --account-id acct-fk-local \
  --auto-generate-image

# 通用 playbook dry-run
uv run python -m ptsm.bootstrap run-playbook \
  --scene "夜里读到《定风波》" \
  --account-id acct-sushi-local \
  --playbook-id sushi_poetry_daily_post
```

开发完成后用 dry-run 测试端到端效果，操作细节见 `docs/operations/local-runbook.md`。
