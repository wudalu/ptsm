from __future__ import annotations

import json
import pytest
import tempfile
from pathlib import Path
from ptsm.application.use_cases.eval_artifact import _gate_counts, run_eval_artifact
from ptsm.evaluations.contracts import EvalResult


SAMPLE_ARTIFACT = {
    "playbook_id": "fengkuang_daily_post",
    "scene": "周一早高峰地铁通勤",
    "account": {"account_id": "acct-fk-local", "platform": "xiaohongshu"},
    "publish_mode": "dry-run",
    "activated_skills": ["fengkuang_style"],
    "activated_skill_details": [{"skill_name": "fengkuang_style"}],
    "runtime_skill_details": [],
    "step_outputs": {
        "planner": {
            "selected_playbook": "fengkuang_daily_post",
            "activated_skills": ["fengkuang_style"],
            "activated_skill_details": [{"skill_name": "fengkuang_style"}],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
        },
        "executor": {
            "attempt_count": 1,
        },
        "reflector": {
            "reflection_decision": "finalize",
            "reflection_feedback": "",
        },
    },
    "final_content": {
        "title": "地铁门关上那秒工牌先疯了",
        "body": (
            "周一早高峰地铁通勤，人在车厢，心已请假。"
            "评论区接一句你最想写在闸机口的打工人暗号。"
        ),
        "image_text": "灵魂请下一站下车",
        "hashtags": ["#发疯文学", "#通勤崩溃实录"],
    },
    "publish_result": {"status": "dry_run"},
}


class FakeJudgeBackend:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def judge(self, *, prompt: str) -> str:
        self.calls += 1
        return self.response


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

    def test_summary_source_includes_scope_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        **SAMPLE_ARTIFACT,
                        "run": {"run_id": "run-123"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
                run_id="run-123",
            )

            assert result["source"] == {
                "kind": "artifact",
                "path": str(artifact_path),
                "run_id": "run-123",
                "account_id": "acct-fk-local",
                "platform": "xiaohongshu",
                "playbook_id": "fengkuang_daily_post",
            }

            summary_path = Path(tmp) / "evals" / result["eval_run_id"] / "summary.json"
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            assert summary["source"]["run_id"] == "run-123"
            assert summary["source"]["playbook_id"] == "fengkuang_daily_post"

    def test_gate_counts_respect_warning_gate_level(self):
        results = [
            EvalResult(
                eval_result_id="r1",
                eval_run_id="er",
                target_id="t",
                evaluator_id="required.eval",
                evaluator_version="1",
                status="failed",
                reason="required failed",
                gate_level="required",
            ),
            EvalResult(
                eval_result_id="r2",
                eval_run_id="er",
                target_id="t",
                evaluator_id="judge.eval",
                evaluator_version="1",
                status="failed",
                reason="judge failed",
                gate_level="warning",
            ),
        ]

        assert _gate_counts(results) == {
            "required_failed": 1,
            "warning_failed": 1,
        }

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

    def test_applies_playbook_local_node_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definitions_root = root / "playbooks"
            _write_eval_contract(
                definitions_root,
                playbook_id="fengkuang_daily_post",
                title_max_chars=3,
            )
            artifact_path = root / "artifact.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        **SAMPLE_ARTIFACT,
                        "final_content": {
                            **SAMPLE_ARTIFACT["final_content"],
                            "title": "超过三字",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=root / "evals",
                playbook_definitions_root=definitions_root,
            )

            assert result["status"] == "failed"
            assert result["gate"]["required_failed"] > 0
            results_path = root / "evals" / result["eval_run_id"] / "results.jsonl"
            result_rows = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            assert any(
                row["evaluator_id"] == "playbook.node_contract"
                and "title_max_chars" in row["reason"]
                for row in result_rows
            )

    def test_eval_artifact_fails_deliberately_weak_content_quality_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            definitions_root = root / "playbooks"
            _write_eval_contract(
                definitions_root,
                playbook_id="fengkuang_daily_post",
                title_max_chars=30,
                extra_constraints={
                    "title_must_not_equal_any": ["打工人地铁生存实录"],
                    "image_text_must_not_equal_any": ["今日已疯"],
                    "body_must_include_comment_prompt_any": ["评论区", "你最"],
                    "body_must_include_save_trigger_any": ["可复制", "模板"],
                    "body_must_not_include_any": ["精神病"],
                },
            )
            artifact_path = root / "weak-quality.json"
            artifact_path.write_text(
                json.dumps(
                    {
                        **SAMPLE_ARTIFACT,
                        "final_content": {
                            "title": "打工人地铁生存实录",
                            "image_text": "今日已疯",
                            "body": "周一早高峰地铁通勤，我像个精神病一样累。",
                            "hashtags": ["#发疯文学"],
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=root / "evals",
                playbook_definitions_root=definitions_root,
            )

            assert result["status"] == "failed"
            assert result["gate"]["required_failed"] > 0
            results_path = root / "evals" / result["eval_run_id"] / "results.jsonl"
            result_rows = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            assert any("title_must_not_equal_any" in row["reason"] for row in result_rows)
            assert any(
                "body_must_include_comment_prompt_any" in row["reason"]
                for row in result_rows
            )
            assert any(
                "body_must_include_save_trigger_any" in row["reason"]
                for row in result_rows
            )

    def test_missing_playbook_local_contract_is_non_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
                playbook_definitions_root=Path(tmp) / "missing-definitions",
            )

            assert result["status"] == "passed"

    def test_llm_judges_do_not_run_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )
            backend = FakeJudgeBackend(
                json.dumps({"score": 0.1, "reason": "bad", "confidence": 0.7})
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
                llm_judge_backend=backend,
            )

            results_path = Path(tmp) / "evals" / result["eval_run_id"] / "results.jsonl"
            rows = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            assert backend.calls == 0
            assert all(not row["evaluator_id"].startswith("llm.") for row in rows)

    def test_llm_judges_run_when_explicitly_enabled_as_required_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifact_path = Path(tmp) / "artifact.json"
            artifact_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )
            backend = FakeJudgeBackend(
                json.dumps(
                    {
                        "score": 0.2,
                        "labels": {
                            "hook_specificity": "warn",
                            "save_trigger": "fail",
                            "comment_trigger": "pass",
                            "platform_native_format": "warn",
                            "persona_fit": "pass",
                            "safety": "pass",
                        },
                        "reason": "semantic quality is weak",
                        "rewrite_hint": "Add a reusable template line.",
                    }
                )
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=Path(tmp) / "evals",
                enable_llm_judges=True,
                llm_judge_backend=backend,
            )

            assert result["status"] == "failed"
            assert result["gate"]["required_failed"] == 1
            assert result["gate"]["warning_failed"] == 0
            results_path = Path(tmp) / "evals" / result["eval_run_id"] / "results.jsonl"
            rows = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            assert any(
                row["evaluator_id"] == "llm.executor.content_quality"
                and row["gate_level"] == "required"
                and row["evidence"][0]["labels"]["save_trigger"] == "fail"
                for row in rows
            )


def _write_eval_contract(
    definitions_root: Path,
    *,
    playbook_id: str,
    title_max_chars: int,
    extra_constraints: dict | None = None,
) -> None:
    playbook_dir = definitions_root / playbook_id
    playbook_dir.mkdir(parents=True, exist_ok=True)
    constraints = {
        "title_max_chars": title_max_chars,
        "hashtags_min_count": 1,
        "hashtags_max_count": 8,
    }
    constraints.update(extra_constraints or {})
    import yaml

    (playbook_dir / "evaluation.yaml").write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "suite_id": f"{playbook_id}.default",
                "node_contracts": {
                    "executor": {
                        "required_fields": ["title", "body", "image_text", "hashtags"],
                        "constraints": constraints,
                    }
                },
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
