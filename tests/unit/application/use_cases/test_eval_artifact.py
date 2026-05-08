from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.application.use_cases.eval_artifact import run_eval_artifact


SAMPLE_ARTIFACT = {
    "playbook_id": "fengkuang_daily_post",
    "scene": "test scene",
    "account": {"account_id": "acct-fk-local", "platform": "xiaohongshu"},
    "publish_mode": "dry-run",
    "activated_skills": ["fengkuang_style"],
    "activated_skill_details": [{"skill_name": "fengkuang_style"}],
    "final_content": {
        "title": "test title",
        "body": "test body",
        "image_text": "image",
        "hashtags": ["#fakelit", "#test"],
    },
    "publish_result": {"status": "dry_run"},
}


class TestRunEvalArtifact:
    def test_returns_summary_with_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
            )
            assert result["status"] in {"passed", "failed", "warning"}
            assert "counts" in result
            assert result["counts"]["targets"] >= 2
            assert result["counts"]["evaluators"] >= 5

    def test_missing_artifact_file_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_eval_artifact(
                artifact_path=Path(tmp) / "nonexistent.json",
                evals_base_dir=Path(tmp) / "evals",
            )
            assert result["status"] == "error"

    def test_results_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
            )
            eval_run_id = result.get("eval_run_id")
            assert eval_run_id is not None
            results_path = (
                Path(tmp) / "evals" / str(eval_run_id) / "results.jsonl"
            )
            assert results_path.exists()

    def test_fails_on_broken_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "broken.json"
            # Remove required fields to trigger failures
            broken = {k: v for k, v in SAMPLE_ARTIFACT.items()
                      if k not in ("final_content", "publish_mode")}
            artifact_path.write_text(
                json.dumps(broken, ensure_ascii=False), encoding="utf-8"
            )
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
            )
            assert result["status"] in {"failed", "error"}
            assert result["gate"]["required_failed"] > 0
