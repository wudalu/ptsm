# Codex Plan Runner V2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 把 `ptsm run-plan` 从 v1 升级到 v2，支持任务级结构化配置、执行状态持久化和 `--resume` 续跑。

**Architecture:** 在现有 markdown task parser 基础上增加可选的 fenced YAML 元数据块，用它声明 `prompt`、`verify`、`done_when`、`max_attempts`。执行层新增 JSON state store，在每次任务尝试后落盘；续跑时读取该 state 并跳过已完成任务，从失败或未完成任务继续。

**Tech Stack:** Python 3.11+, argparse, pathlib, dataclasses, json, PyYAML, pytest

### Task 1: Write failing parser tests for structured task metadata

**Files:**
- Modify: `tests/unit/plan_runner/test_parser.py`
- Modify: `src/ptsm/plan_runner/parser.py`

**Step 1: Write the failing tests**

- 覆盖 task 下的 fenced YAML metadata block 解析
- 覆盖 `prompt`、`verify`、`done_when`、`max_attempts`
- 覆盖 metadata block 从 task body 中剥离

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/plan_runner/test_parser.py -q`
Expected: FAIL because parser does not expose metadata fields yet

**Step 3: Write minimal implementation**

- 扩展 `PlanTask`
- 解析 metadata block
- 保持旧 plan 向后兼容

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/plan_runner/test_parser.py -q`
Expected: PASS

### Task 2: Write failing runner tests for task overrides and persisted state

**Files:**
- Modify: `tests/unit/plan_runner/test_runner.py`
- Create: `src/ptsm/plan_runner/state.py`
- Modify: `src/ptsm/plan_runner/runner.py`

**Step 1: Write the failing tests**

- 覆盖 task 级 `verify` 和 `max_attempts` 覆盖全局默认值
- 覆盖执行后写入 state 文件
- 覆盖 `resume` 时跳过已完成 task 并继续后续 task

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: FAIL because runner has no state persistence or resume support

**Step 3: Write minimal implementation**

- 增加 state dataclass 和 JSON store
- runner 在每次尝试后持久化状态
- 支持 resume 跳过已完成 task

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/plan_runner/test_runner.py -q`
Expected: PASS

### Task 3: Write failing CLI tests for state-path and resume flags

**Files:**
- Modify: `tests/unit/test_bootstrap.py`
- Modify: `src/ptsm/interfaces/cli/main.py`

**Step 1: Write the failing tests**

- 覆盖 `--state-path`
- 覆盖 `--resume`
- 覆盖 CLI 调用把新参数传给 `run_plan_cli`

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: FAIL because CLI does not expose these flags

**Step 3: Write minimal implementation**

- CLI 暴露 `--state-path` 和 `--resume`
- 新建 run 时生成默认 state 目录和文件
- `run-plan` 输出 state 路径

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: PASS

### Task 4: Verify v2 behavior

**Files:**
- No code changes required

**Step 1: Run focused test suite**

Run: `uv run pytest tests/unit/plan_runner/test_parser.py tests/unit/plan_runner/test_runner.py tests/unit/test_bootstrap.py -q`
Expected: PASS

**Step 2: Run dry-run smoke**

Run: `.venv/bin/python -m ptsm.bootstrap run-plan --plan docs/plans/2026-03-14-ptsm-agent-platform.md --dry-run --verify-command "uv run pytest -q"`
Expected: exit 0 and print task list plus state path

**Step 3: Run resume smoke on a temporary structured plan**

Run: `.venv/bin/python -m ptsm.bootstrap run-plan --plan <tmp-plan> --state-path <tmp-state> --resume --dry-run`
Expected: exit 0 and load existing state without errors
