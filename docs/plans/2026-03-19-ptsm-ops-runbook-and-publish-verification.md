# PTSM Ops Runbook And Publish Verification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 PTSM 增加可落地的启动、调试、查日志、打开浏览器、发布状态检查说明与自动化执行入口。

**Architecture:** 先补齐 bootstrap 和结构化日志基础，再把每次运行沉淀到本地 run 目录，围绕这个 run 目录提供 `doctor`、`logs`、`xhs-open-browser`、`xhs-check-publish` 命令。主工作流继续以 CLI 为中心，后续由 Codex/计划执行器只调用稳定命令，不依赖人工解释。

**Tech Stack:** Python 3.12, `uv`, argparse CLI, structlog, JSONL logs, local artifact files, stdlib `webbrowser`, optional Playwright fallback

## Todo Status

- [x] Task 1: Restore bootstrap and structured logging foundation
- [x] Task 2: Persist per-run metadata and local log streams
- [x] Task 3: Add operator docs and `doctor` / `logs` commands
- [x] Task 4: Add browser-open and publish-status verification commands
- [x] Task 5: Integrate verification into the publish workflow

### Task 1: Restore Bootstrap And Structured Logging Foundation

**Files:**
- Create: `.python-version`
- Create: `src/ptsm/config/logging.py`
- Modify: `src/ptsm/bootstrap.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing test**

Use the existing failing assertions in `tests/unit/test_bootstrap.py` as the red test set:

```python
def test_scaffold_files_pin_python_runtime() -> None:
    assert (PROJECT_ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.12"

def test_bootstrap_main_configures_logging_before_running_cli(monkeypatch) -> None:
    monkeypatch.setattr(bootstrap, "get_settings", lambda: settings)
    monkeypatch.setattr(bootstrap, "configure_logging", ...)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: FAIL with missing `.python-version`, missing `ptsm.config.logging`, and bootstrap lacking `get_settings` / `configure_logging`

**Step 3: Write minimal implementation**

Implement:

```python
# src/ptsm/config/logging.py
def configure_logging(log_level: str = "INFO") -> None: ...
def get_logger(name: str): ...

# src/ptsm/bootstrap.py
def run_cli(argv=None) -> int:
    return cli_main(argv)

def main(argv=None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    return run_cli(argv)
```

Also add `.python-version` with `3.12`.

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_bootstrap.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add .python-version src/ptsm/config/logging.py src/ptsm/bootstrap.py tests/unit/test_bootstrap.py
git commit -m "feat: restore bootstrap logging foundation"
```

### Task 2: Persist Per-Run Metadata And Local Log Streams

**Files:**
- Create: `src/ptsm/infrastructure/observability/run_store.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `src/ptsm/application/models.py`
- Test: `tests/unit/infrastructure/observability/test_run_store.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write the failing test**

Add tests that require:

```python
def test_run_store_writes_events_and_summary(tmp_path: Path) -> None:
    store = RunStore(base_dir=tmp_path)
    run = store.start(...)
    store.append_event(run.run_id, event="publish_started", step="publish")
    summary = store.finish(run.run_id, status="completed")
    assert (tmp_path / run.run_id / "events.jsonl").exists()

def test_run_fengkuang_playbook_returns_run_metadata(...) -> None:
    result = run_fengkuang_playbook(...)
    assert result["run"]["run_id"]
    assert result["run"]["events_path"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_playbook.py -q`
Expected: FAIL with missing `RunStore` and missing run metadata in playbook result

**Step 3: Write minimal implementation**

Implement a local run directory shape:

```text
.ptsm/runs/<run_id>/
  summary.json
  events.jsonl
```

And return:

```python
"run": {
    "run_id": run_id,
    "run_dir": str(run_dir),
    "events_path": str(events_path),
    "summary_path": str(summary_path),
}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_playbook.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/infrastructure/observability/run_store.py src/ptsm/application/use_cases/run_playbook.py src/ptsm/interfaces/cli/main.py src/ptsm/application/models.py tests/unit/infrastructure/observability/test_run_store.py tests/unit/application/use_cases/test_run_playbook.py
git commit -m "feat: persist local run metadata and logs"
```

### Task 3: Add Operator Docs And `doctor` / `logs` Commands

**Files:**
- Create: `docs/operations/local-runbook.md`
- Create: `src/ptsm/application/use_cases/doctor.py`
- Create: `src/ptsm/application/use_cases/logs.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/application/use_cases/test_doctor.py`
- Test: `tests/unit/application/use_cases/test_logs.py`
- Test: `tests/unit/test_bootstrap.py`

**Step 1: Write the failing test**

Add tests that require:

```python
def test_doctor_reports_env_and_mcp_status(...) -> None:
    result = run_doctor(...)
    assert result["checks"][0]["name"] == "settings"

def test_logs_command_reads_latest_run_events(tmp_path: Path) -> None:
    result = run_logs(run_id="run-123", ...)
    assert "publish_started" in result["events"][0]["event"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_logs.py tests/unit/test_bootstrap.py -q`
Expected: FAIL with missing commands and parser entries

**Step 3: Write minimal implementation**

Implement new commands:

```bash
ptsm doctor
ptsm logs --run-id <run_id>
ptsm logs --artifact outputs/artifacts/demo.json
```

Write `docs/operations/local-runbook.md` covering:
- environment bootstrap
- startup commands
- dry-run debugging
- login troubleshooting
- where logs/artifacts live
- how to inspect a failed publish

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_logs.py tests/unit/test_bootstrap.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add docs/operations/local-runbook.md src/ptsm/application/use_cases/doctor.py src/ptsm/application/use_cases/logs.py src/ptsm/interfaces/cli/main.py tests/unit/application/use_cases/test_doctor.py tests/unit/application/use_cases/test_logs.py tests/unit/test_bootstrap.py
git commit -m "feat: add ops runbook and diagnostics commands"
```

### Task 4: Add Browser-Open And Publish-Status Verification Commands

**Files:**
- Create: `src/ptsm/application/use_cases/xhs_browser.py`
- Create: `src/ptsm/application/use_cases/xhs_publish_status.py`
- Modify: `src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Test: `tests/unit/application/use_cases/test_xhs_browser.py`
- Test: `tests/unit/application/use_cases/test_xhs_publish_status.py`
- Test: `tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py`

**Step 1: Write the failing test**

Add tests that require:

```python
def test_open_browser_uses_local_qrcode_or_login_url(...) -> None:
    result = open_xhs_browser(target="login", qrcode_output_path="/tmp/xhs.png")
    assert result["opened"] is True

def test_check_publish_status_uses_mcp_result_when_available(...) -> None:
    result = check_xhs_publish_status(...)
    assert result["status"] == "published_visible"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_xhs_browser.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py -q`
Expected: FAIL with missing use cases / tool methods

**Step 3: Write minimal implementation**

Implement commands:

```bash
ptsm xhs-open-browser --target login
ptsm xhs-open-browser --artifact outputs/artifacts/demo.json
ptsm xhs-check-publish --artifact outputs/artifacts/demo.json
```

Status resolution order:
1. Use MCP tool if publisher exposes a status-check tool
2. Use artifact URL / post id if available
3. Return `manual_check_required` with browser instructions

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_xhs_browser.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptsm/application/use_cases/xhs_browser.py src/ptsm/application/use_cases/xhs_publish_status.py src/ptsm/infrastructure/publishers/xiaohongshu_mcp_publisher.py src/ptsm/interfaces/cli/main.py tests/unit/application/use_cases/test_xhs_browser.py tests/unit/application/use_cases/test_xhs_publish_status.py tests/unit/infrastructure/publishers/test_xiaohongshu_mcp_publisher.py
git commit -m "feat: add browser and publish status commands"
```

### Task 5: Integrate Verification Into The Publish Workflow

**Files:**
- Modify: `src/ptsm/application/models.py`
- Modify: `src/ptsm/application/use_cases/run_playbook.py`
- Modify: `src/ptsm/interfaces/cli/main.py`
- Modify: `docs/operations/local-runbook.md`
- Test: `tests/e2e/test_fengkuang_publish_dry_run.py`
- Test: `tests/unit/application/use_cases/test_run_playbook.py`

**Step 1: Write the failing test**

Add tests that require:

```python
def test_run_fengkuang_can_request_browser_open_and_status_check(...) -> None:
    result = run_fengkuang_playbook(...)
    assert result["post_publish_checks"]["requested"] is True
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_fengkuang_publish_dry_run.py -q`
Expected: FAIL with missing flags / missing post-publish check payload

**Step 3: Write minimal implementation**

Add optional CLI flags:

```bash
ptsm run-fengkuang --open-browser-if-needed
ptsm run-fengkuang --wait-for-publish-status
```

And emit structured follow-up metadata:

```python
"post_publish_checks": {
    "requested": True,
    "browser_opened": False,
    "publish_status": "skipped",
}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_fengkuang_publish_dry_run.py -q`
Expected: PASS

**Step 5: Run full verification**

Run: `uv run pytest -q`
Expected: PASS

Run: `uv run python -m compileall src`
Expected: PASS

**Step 6: Commit**

```bash
git add src/ptsm/application/models.py src/ptsm/application/use_cases/run_playbook.py src/ptsm/interfaces/cli/main.py docs/operations/local-runbook.md tests/unit/application/use_cases/test_run_playbook.py tests/e2e/test_fengkuang_publish_dry_run.py
git commit -m "feat: wire publish verification into workflow"
```
