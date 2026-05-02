# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
uv run pytest -q                          # run all tests
uv run pytest -q tests/unit/path/to_test.py  # single test file
uv run pytest -q -k "test_name"           # filter by test name
uv run python -m ptsm.bootstrap --help    # CLI help
ptsm run-fengkuang --scene "场景描述"      # run fengkuang playbook
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

Start at `docs/index.md` — the agent-readable docs map. Key docs: `architecture.md`, `runtime.md`, `playbooks.md`, `skills.md`, `harness-engineering.md`. When changing code, the `docs-sync` gate checks whether corresponding docs in `related_paths` were also updated.

### Harness engineering conventions

- **先读 docs/ 再写代码。** 每次开发前，先查阅 `docs/index.md` 找到相关文档，了解当前架构、运行时、playbook/skill 结构和操作规范。`docs-sync` gate 会强制要求代码变更伴随文档更新。
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
