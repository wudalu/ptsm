from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.infrastructure.evaluations.eval_store import EvalStore
from ptsm.evaluations.contracts import EvalResult


class TestEvalStore:
    def test_start_persists_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(
                suite_id="test_suite",
                source_kind="artifact",
                source_path="a.json",
            )
            summary_path = Path(tmp) / handle.eval_run_id / "summary.json"
            assert summary_path.exists()
            summary = json.loads(summary_path.read_text())
            assert summary["suite_id"] == "test_suite"
            assert summary["status"] == "running"

    def test_start_persists_source_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(
                suite_id="test_suite",
                source_kind="artifact",
                source_path="a.json",
                source_metadata={
                    "run_id": "run-1",
                    "account_id": "acct-fk-local",
                    "platform": "xiaohongshu",
                    "playbook_id": "fengkuang_daily_post",
                },
            )

            summary = json.loads(handle.summary_path.read_text())
            assert summary["source"] == {
                "kind": "artifact",
                "path": "a.json",
                "run_id": "run-1",
                "account_id": "acct-fk-local",
                "platform": "xiaohongshu",
                "playbook_id": "fengkuang_daily_post",
            }

    def test_append_result_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(suite_id="test_suite", source_kind="artifact")
            result = EvalResult(
                eval_result_id="er-1",
                eval_run_id=handle.eval_run_id,
                target_id="t-1",
                evaluator_id="eval-1",
                evaluator_version="1",
                status="passed",
                reason="ok",
            )
            store.append_result(handle.eval_run_id, result)
            results_path = Path(tmp) / handle.eval_run_id / "results.jsonl"
            lines = results_path.read_text().strip().split("\n")
            assert len(lines) == 1
            assert json.loads(lines[0])["status"] == "passed"

    def test_finalize_updates_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            handle = store.start(suite_id="test_suite", source_kind="artifact")
            store.finalize(
                handle.eval_run_id,
                status="passed",
                counts={
                    "targets": 3, "evaluators": 5, "passed": 5,
                    "failed": 0, "warnings": 0, "errors": 0,
                },
                gate={"required_failed": 0, "warning_failed": 0},
            )
            summary_path = Path(tmp) / handle.eval_run_id / "summary.json"
            summary = json.loads(summary_path.read_text())
            assert summary["status"] == "passed"
            assert summary["counts"]["passed"] == 5

    def test_list_eval_runs_returns_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            h1 = store.start(suite_id="s1", source_kind="artifact")
            store.finalize(
                h1.eval_run_id, status="passed",
                counts={"targets": 1, "evaluators": 1, "passed": 1, "failed": 0, "warnings": 0, "errors": 0},
                gate={"required_failed": 0, "warning_failed": 0},
            )
            h2 = store.start(suite_id="s2", source_kind="artifact")
            store.finalize(
                h2.eval_run_id, status="failed",
                counts={"targets": 2, "evaluators": 2, "passed": 1, "failed": 1, "warnings": 0, "errors": 0},
                gate={"required_failed": 1, "warning_failed": 0},
            )
            runs = store.list_eval_runs()
            assert len(runs) == 2

    def test_read_results_empty_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            assert store.read_results("nonexistent") == []

    def test_list_empty_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvalStore(base_dir=Path(tmp))
            assert store.list_eval_runs() == []
