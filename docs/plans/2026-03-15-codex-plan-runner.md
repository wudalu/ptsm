# Codex Plan Runner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 增加一个 Python 版 `plan-runner`，让本地脚本能基于 markdown plan 串行驱动 `codex exec`，并在每个任务后强制执行验证命令。

**Architecture:** 采用一个轻量的本地 orchestrator。它读取 plan 并抽取任务，按任务构造 Codex prompt，调用 `codex exec`，然后由 wrapper 自己执行验证命令并决定是否进入下一任务或带失败日志重试。

**Tech Stack:** Python 3.11+, argparse, subprocess, pathlib, dataclasses, pytest

### Task 1: Add failing parser tests

**Files:**
- Create: `tests/unit/plan_runner/test_parser.py`
- Create: `src/ptsm/plan_runner/__init__.py`
- Create: `src/ptsm/plan_runner/parser.py`

**Step 1: Write the failing tests**

- 覆盖 `### Task ...` 和 `### 里程碑 ...` 两种 heading 的任务抽取。
- 验证能读取任务标题和对应 markdown 段落。

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/plan_runner/test_parser.py -q`
Expected: FAIL because `ptsm.plan_runner.parser` does not exist yet

**Step 3: Write minimal implementation**

- 实现 plan parser
- 定义最小任务数据结构

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/plan_runner/test_parser.py -q`
Expected: PASS

### Task 2: Add failing runner tests

**Files:**
- Create: `tests/unit/plan_runner/test_runner.py`
- Create: `src/ptsm/plan_runner/runner.py`

**Step 1: Write the failing tests**

- 覆盖串行执行任务
- 覆盖验证成功直接进入下一任务
- 覆盖验证失败时把失败日志带入重试 prompt
- 覆盖超过最大重试次数时报错

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/plan_runner/test_runner.py -q`
Expected: FAIL because runner module does not exist yet

**Step 3: Write minimal implementation**

- 实现 Codex 调用器接口
- 实现验证命令执行器接口
- 实现串行执行和重试逻辑

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/plan_runner/test_runner.py -q`
Expected: PASS

### Task 3: Add CLI wiring tests

**Files:**
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing tests**

- 覆盖 `run-plan` 子命令参数解析
- 覆盖 `main()` 将参数传给 `plan-runner`

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_bootstrap.py -q`
Expected: FAIL because parser does not expose `run-plan`

**Step 3: Write minimal implementation**

- 加入 `run-plan` CLI
- 支持 `--plan`, `--verify-command`, `--max-attempts`, `--dry-run`

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_bootstrap.py -q`
Expected: PASS

### Task 4: Verify the MVP end to end

**Files:**
- No code changes required

**Step 1: Run focused test suite**

Run: `pytest tests/unit/plan_runner/test_parser.py tests/unit/plan_runner/test_runner.py tests/unit/test_bootstrap.py -q`
Expected: PASS

**Step 2: Run one CLI smoke check**

Run: `python -m ptsm.bootstrap run-plan --plan docs/plans/2026-03-14-ptsm-agent-platform.md --dry-run --verify-command "pytest -q"`
Expected: exit 0 and print parsed tasks plus planned verification commands without invoking Codex
