# Codex Plan Runner Standalone Project Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把当前嵌在 `ptsm` 里的 plan-runner 封装成一个独立、可复用的 Python 项目 `codex-plan-runner`，并提供面向任意仓库的 README 使用说明。

**Architecture:** 在仓库根目录创建独立子项目 `codex-plan-runner/`，包含自己的 `pyproject.toml`、`src/`、`tests/` 和 `README.md`。核心逻辑从现有实现抽象为通用 parser/runner/CLI，不依赖 `ptsm` 业务代码。

**Tech Stack:** Python 3.11+, argparse, pathlib, json, subprocess, PyYAML, pytest, uv

### Task 1: Write failing standalone parser tests

**Files:**
- Create: `codex-plan-runner/tests/test_parser.py`
- Create: `codex-plan-runner/src/codex_plan_runner/parser.py`

**Step 1: Write the failing tests**

- 覆盖 task/milestone heading 解析
- 覆盖 task-level YAML metadata block 解析

**Step 2: Run test to verify it fails**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_parser.py -q`
Expected: FAIL because standalone package does not exist yet

**Step 3: Write minimal implementation**

- 实现通用 parser
- 暴露 `PlanTask`

**Step 4: Run test to verify it passes**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_parser.py -q`
Expected: PASS

### Task 2: Write failing standalone runner tests

**Files:**
- Create: `codex-plan-runner/tests/test_runner.py`
- Create: `codex-plan-runner/src/codex_plan_runner/runner.py`

**Step 1: Write the failing tests**

- 覆盖串行执行、task-level verify override
- 覆盖状态持久化与 resume
- 覆盖默认 state directory 约定

**Step 2: Run test to verify it fails**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_runner.py -q`
Expected: FAIL because runner module does not exist yet

**Step 3: Write minimal implementation**

- 实现通用 runner
- 默认状态目录为 `.codex-plan-runner/runs/`

**Step 4: Run test to verify it passes**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_runner.py -q`
Expected: PASS

### Task 3: Write failing CLI and documentation tests

**Files:**
- Create: `codex-plan-runner/tests/test_cli.py`
- Create: `codex-plan-runner/src/codex_plan_runner/cli.py`
- Create: `codex-plan-runner/README.md`
- Create: `codex-plan-runner/pyproject.toml`

**Step 1: Write the failing tests**

- 覆盖 `--plan`, `--verify-command`, `--state-path`, `--resume`, `--dry-run`
- 覆盖默认 state path 注入 runner

**Step 2: Run test to verify it fails**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_cli.py -q`
Expected: FAIL because CLI module does not exist yet

**Step 3: Write minimal implementation**

- 实现独立 CLI 入口
- 写 README，说明任意项目如何安装、准备 plan、执行、resume

**Step 4: Run test to verify it passes**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests/test_cli.py -q`
Expected: PASS

### Task 4: Verify the standalone project

**Files:**
- No code changes required

**Step 1: Run standalone test suite**

Run: `uv run --project codex-plan-runner pytest codex-plan-runner/tests -q`
Expected: PASS

**Step 2: Run standalone dry-run smoke**

Run: `uv run --project codex-plan-runner codex-plan-runner --plan docs/plans/2026-03-14-ptsm-agent-platform.md --dry-run --verify-command "uv run pytest -q"`
Expected: exit 0 and print parsed tasks plus generated state path
