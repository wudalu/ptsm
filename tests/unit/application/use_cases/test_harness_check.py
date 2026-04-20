from __future__ import annotations

from pathlib import Path

from ptsm.application.use_cases.harness_check import run_harness_check


def test_run_harness_check_composes_docs_sync_report_and_pytest(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_active_doc(tmp_path / "docs" / "runtime.md", last_verified="2026-04-20")
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)

    captured: dict[str, object] = {}

    def fake_subprocess_run(command, **kwargs):
        captured["command"] = list(command)
        captured["env"] = kwargs["env"]

        class Result:
            returncode = 0
            stdout = "all good\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("ptsm.application.use_cases.harness_check.subprocess.run", fake_subprocess_run)

    result = run_harness_check(
        project_root=tmp_path,
        changed_paths=["src/ptsm/demo.py", "docs/runtime.md"],
    )

    assert result["status"] == "ok"
    assert result["docs_sync"]["status"] == "ok"
    assert result["harness_report"]["status"] == "ok"
    assert result["pytest"]["status"] == "ok"
    assert captured["command"] == ["uv", "run", "pytest", "-q"]
    assert captured["env"]["DEFAULT_LLM_PROVIDER"] == "deterministic"
    assert captured["env"]["DEEPSEEK_API_KEY"] == ""


def test_run_harness_check_fails_when_docs_sync_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    _write_active_doc(tmp_path / "docs" / "runtime.md", last_verified="2026-04-20")
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)

    def fake_subprocess_run(command, **kwargs):
        class Result:
            returncode = 0
            stdout = "all good\n"
            stderr = ""

        return Result()

    monkeypatch.setattr("ptsm.application.use_cases.harness_check.subprocess.run", fake_subprocess_run)

    result = run_harness_check(
        project_root=tmp_path,
        changed_paths=["src/ptsm/demo.py"],
    )

    assert result["status"] == "error"
    assert result["docs_sync"]["status"] == "error"


def test_run_harness_check_is_non_strict_for_retention_warnings(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_active_doc(tmp_path / "docs" / "runtime.md", last_verified="2026-04-20")
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)
    stale_run = tmp_path / ".ptsm" / "runs" / "run-1"
    stale_run.mkdir(parents=True, exist_ok=True)
    (stale_run / "summary.json").write_text(
        (
            '{"run_id":"run-1","status":"completed","started_at":"2026-03-01T00:00:00+00:00",'
            '"finished_at":"2026-03-01T00:01:00+00:00"}'
        ),
        encoding="utf-8",
    )

    def fake_subprocess_run(command, **kwargs):
        class Result:
            returncode = 0
            stdout = "all good\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "ptsm.application.use_cases.harness_check.subprocess.run",
        fake_subprocess_run,
    )

    result = run_harness_check(
        project_root=tmp_path,
        changed_paths=["src/ptsm/demo.py", "docs/runtime.md"],
        strict=False,
    )

    assert result["harness_report"]["status"] == "warning"
    assert result["status"] == "ok"


def test_run_harness_check_strict_mode_fails_on_harness_report_warning(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_active_doc(tmp_path / "docs" / "runtime.md", last_verified="2026-04-20")
    (tmp_path / "outputs" / "artifacts").mkdir(parents=True)
    stale_run = tmp_path / ".ptsm" / "runs" / "run-1"
    stale_run.mkdir(parents=True, exist_ok=True)
    (stale_run / "summary.json").write_text(
        (
            '{"run_id":"run-1","status":"completed","started_at":"2026-03-01T00:00:00+00:00",'
            '"finished_at":"2026-03-01T00:01:00+00:00"}'
        ),
        encoding="utf-8",
    )

    def fake_subprocess_run(command, **kwargs):
        class Result:
            returncode = 0
            stdout = "all good\n"
            stderr = ""

        return Result()

    monkeypatch.setattr(
        "ptsm.application.use_cases.harness_check.subprocess.run",
        fake_subprocess_run,
    )

    result = run_harness_check(
        project_root=tmp_path,
        changed_paths=["src/ptsm/demo.py", "docs/runtime.md"],
        strict=True,
    )

    assert result["harness_report"]["status"] == "warning"
    assert result["status"] == "error"


def _write_active_doc(path: Path, *, last_verified: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        (
            "---\n"
            "title: Demo Doc\n"
            "status: active\n"
            "owner: ptsm\n"
            f"last_verified: {last_verified}\n"
            "source_of_truth: true\n"
            "related_paths:\n"
            "  - src/ptsm/demo.py\n"
            "---\n\n"
            "# Demo\n"
        ),
        encoding="utf-8",
    )
