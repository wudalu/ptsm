from __future__ import annotations

from copy import deepcopy
import json
import tempfile
from pathlib import Path

import pytest

import ptsm.application.use_cases.psychology_learning_series as psychology_learning_series_use_case
import ptsm.domain.psychology_learning as psychology_learning_domain
from ptsm.application.use_cases.eval_artifact import (
    _gate_counts,
    _is_catalog_managed_psychology_learning,
    run_eval_artifact,
)
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.domain.psychology_learning import (
    build_psychology_learning_catalog_receipt,
    list_psychology_learning_series,
    psychology_learning_series_catalog_snapshot_path,
    render_psychology_learning_draft,
    require_sealed_psychology_learning_preflight_bundle,
    resolve_psychology_learning_selection,
    seal_psychology_learning_preflight_bundle,
)
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
            "周一早高峰地铁通勤，门一关，我的工牌像被挤成闸机口贴纸。"
            "人在车厢，心已请假，嘴上还要装作今天也能准点开机。"
            "这句我先写在卡套背面：收到，但灵魂正在下一站换乘，先让工牌替我排队喘口气。"
            "今天先把这口气写在卡套背面。"
            "评论区接一句你最想写在闸机口的打工人暗号。"
        ),
        "image_text": "灵魂请下一站下车",
        "hashtags": ["#发疯文学", "#通勤崩溃实录"],
    },
    "publish_result": {"status": "dry_run"},
}


def _learning_artifact(lesson_id: str = "notice_the_loop", *, bundle=None) -> dict[str, object]:
    if bundle is None:
        bundle = resolve_psychology_learning_selection(
            series_id="after_work_rumination",
            lesson_id=lesson_id,
        )
    contract = bundle.runtime_contract
    artifact = {
        "playbook_id": "modern_psychology_post",
        "account": {
            "account_id": "acct-psychology-local",
            "platform": "xiaohongshu",
        },
        "platform": "xiaohongshu",
        "scene": (
            f"心理学学习专题：{contract['series_badge']}｜{contract['lesson_title']}"
        ),
        "publish_mode": "dry-run",
        "activated_skills": [],
        "activated_skill_details": [],
        "final_content": render_psychology_learning_draft(contract),
        "format_patterns_used": {"status": "not_used"},
        "publish_result": {"status": "dry_run"},
        "topic_selection": {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": bundle.series_id,
                "curriculum_version": contract["curriculum_version"],
                "lesson_id": bundle.lesson_id,
                "lesson_number": bundle.lesson_number,
            },
        },
        "psychology_learning_mode": "learning_series",
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": contract["curriculum_version"],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
        "psychology_learning_evidence_manifest": bundle.manifest,
        "psychology_learning_gate": {
            "status": "passed",
            "series_id": bundle.series_id,
            "lesson_id": bundle.lesson_id,
            "validator": "psychology_learning_draft_contract",
            "validator_version": "1",
            "errors": [],
        },
    }
    catalog_receipt = build_psychology_learning_catalog_receipt(bundle)
    if catalog_receipt is not None:
        artifact["psychology_learning_catalog_receipt"] = catalog_receipt
    return artifact


class FakeJudgeBackend:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0

    def judge(self, *, prompt: str) -> str:
        self.calls += 1
        return self.response


class TestRunEvalArtifact:
    def test_catalog_receipt_marker_routes_a_tampered_custom_artifact_to_learning_eval(self):
        assert _is_catalog_managed_psychology_learning(
            {
                "playbook_id": "modern_psychology_post",
                "psychology_learning_catalog_receipt": {},
            }
        )

    def test_confirmed_custom_catalog_artifact_passes_the_same_offline_receipt_eval(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        store = PsychologyLearningSeriesStore(trusted_provision=True, )
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {"id": "notice", "title": "先识别重复时刻"},
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store.persist_proposal(proposal)
        catalog = store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )
        bundle = resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
        )
        artifact_path = tmp_path / "custom-learning-artifact.json"
        artifact_path.write_text(
            json.dumps(_learning_artifact(bundle=bundle), ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_eval_artifact(
            artifact_path=artifact_path,
            evals_base_dir=tmp_path / "evals",
        )

        assert result["status"] == "passed"

    def test_historic_v1_catalog_artifact_still_passes_offline_receipt_eval(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        store = PsychologyLearningSeriesStore(trusted_provision=True)
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {"id": "notice", "title": "先识别重复时刻"},
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store.persist_proposal(proposal)

        def build_v1(proposal_value, *, curriculum_version: str):
            return psychology_learning_domain._build_confirmed_psychology_learning_catalog_for_template(
                proposal_value,
                curriculum_version=curriculum_version,
                controlled_template_version="1",
            )

        monkeypatch.setattr(
            psychology_learning_series_use_case,
            "_build_confirmed_psychology_learning_catalog",
            build_v1,
        )
        catalog = store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )
        bundle = resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
        )
        artifact = _learning_artifact(bundle=bundle)
        artifact_path = tmp_path / "historic-v1-learning-artifact.json"
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_eval_artifact(
            artifact_path=artifact_path,
            evals_base_dir=tmp_path / "evals",
        )

        assert bundle.runtime_contract["controlled_template_version"] == "1"
        assert "slides" not in artifact["final_content"]["image_plan"]
        assert artifact["psychology_learning_catalog_receipt"][
            "catalog_digest"
        ] == catalog.catalog_digest
        assert result["status"] == "passed"

    def test_preflight_bundle_keeps_eval_off_the_mutable_catalog_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """A live guarded eval must not resolve a catalog path for a second time."""
        monkeypatch.chdir(tmp_path)
        store = PsychologyLearningSeriesStore(trusted_provision=True, )
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {"id": "notice", "title": "先识别重复时刻"},
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store.persist_proposal(proposal)
        catalog = store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )
        capability = seal_psychology_learning_preflight_bundle(
            resolve_psychology_learning_selection(
                series_id=catalog.series_id,
                lesson_id="notice",
                curriculum_version=catalog.curriculum_version,
            )
        )
        bundle = require_sealed_psychology_learning_preflight_bundle(capability)

        def fail_catalog_reresolution(**_: object) -> object:
            pytest.fail("guarded eval must use the preflight bundle")

        monkeypatch.setattr(
            psychology_learning_domain,
            "resolve_psychology_learning_selection",
            fail_catalog_reresolution,
        )

        result = run_eval_artifact(
            artifact_path=tmp_path / "not-reopened.json",
            artifact_payload=_learning_artifact(bundle=bundle),
            psychology_learning_preflight_capability=capability,
            evals_base_dir=tmp_path / "evals",
        )

        assert result["status"] == "passed"

    def test_custom_catalog_artifact_fails_closed_when_its_snapshot_is_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        private_goal = "确认前私有目标，不得出现在离线评估结果"
        store = PsychologyLearningSeriesStore(trusted_provision=True, )
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {
                    "id": "notice",
                    "title": "先识别重复时刻",
                    "goal": private_goal,
                },
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store.persist_proposal(proposal)
        catalog = store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )
        bundle = resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id="notice",
            curriculum_version=catalog.curriculum_version,
        )
        artifact_path = tmp_path / "custom-learning-artifact.json"
        artifact_path.write_text(
            json.dumps(_learning_artifact(bundle=bundle), ensure_ascii=False),
            encoding="utf-8",
        )
        snapshot_path = psychology_learning_series_catalog_snapshot_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=store.catalog_root,
        )
        snapshot_path.unlink()

        result = run_eval_artifact(
            artifact_path=artifact_path,
            evals_base_dir=tmp_path / "evals",
        )

        assert result["status"] == "failed"
        assert private_goal not in json.dumps(result, ensure_ascii=False)

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

    def test_supplied_artifact_payload_does_not_require_source_path(self):
        """A caller with a verified in-memory receipt must not reread its path."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing_path = root / "missing-artifact.json"

            result = run_eval_artifact(
                artifact_path=missing_path,
                artifact_payload=SAMPLE_ARTIFACT,
                evals_base_dir=root / "evals",
            )

            assert result["status"] in {"passed", "failed", "warning"}
            assert result["source"]["path"] == str(missing_path)

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

    @pytest.mark.parametrize(
        "lesson_id",
        [
            lesson.lesson_id
            for lesson in list_psychology_learning_series(
                series_id="after_work_rumination"
            )
        ],
    )
    def test_catalog_learning_lessons_use_their_exact_receipt_contract(
        self,
        lesson_id: str,
    ) -> None:
        """Each closed lesson is evaluated by its catalog contract, not open-post copy rules."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact_path = root / f"{lesson_id}.json"
            artifact_path.write_text(
                json.dumps(_learning_artifact(lesson_id), ensure_ascii=False),
                encoding="utf-8",
            )

            result = run_eval_artifact(
                artifact_path=artifact_path,
                evals_base_dir=root / "evals",
            )

            assert result["status"] == "passed"
            results_path = root / "evals" / result["eval_run_id"] / "results.jsonl"
            rows = [
                json.loads(line)
                for line in results_path.read_text(encoding="utf-8").splitlines()
            ]
            assert any(
                row["evaluator_id"] == "psychology.learning_receipt"
                and row["status"] == "passed"
                for row in rows
            )
            assert not any(
                row["evaluator_id"] == "playbook.node_contract"
                and row["status"] == "failed"
                for row in rows
            )

    def test_eval_artifact_rejects_tampered_learning_carousel_order(
        self,
        tmp_path: Path,
    ) -> None:
        artifact = deepcopy(_learning_artifact())
        artifact["final_content"]["image_plan"]["slides"][1]["order"] = 7
        artifact_path = tmp_path / "tampered-learning-carousel.json"
        artifact_path.write_text(
            json.dumps(artifact, ensure_ascii=False),
            encoding="utf-8",
        )

        result = run_eval_artifact(
            artifact_path=artifact_path,
            evals_base_dir=tmp_path / "evals",
        )

        assert result["status"] == "failed"
        assert result["gate"]["required_failed"] > 0

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

    def test_scopes_ai_tech_receipt_evaluator_to_ai_final_artifacts_only(self):
        ai_artifact = {
            **SAMPLE_ARTIFACT,
            "playbook_id": "ai_tech_daily_post",
            "scene": "AI 科技证据模式",
            "account": {"account_id": "acct-ai-tech-local", "platform": "xiaohongshu"},
            "final_content": {
                "title": "AI 三条更新",
                "image_text": "今天的三条已核验变化",
                "body": "模型发布：已开放推理能力。\n开发者工具：新增批处理。\n行业应用：支持团队协作。",
                "hashtags": ["#AI资讯"],
            },
            "ai_tech_content_mode": "news_brief",
            "ai_tech_evidence_manifest": {
                "source_refs": ["source:official-1"],
                "test_evidence_refs": [],
                "event_fingerprints": [
                    "event:model-1",
                    "event:tool-2",
                    "event:industry-3",
                ],
                "trend_support": [],
            },
            "ai_tech_evidence_gate": {
                "status": "passed",
                "mode": "news_brief",
                "validator": "ai_tech_draft_contract",
                "validator_version": "1",
                "errors": [],
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            non_ai_path = root / "non-ai.json"
            ai_path = root / "ai.json"
            non_ai_path.write_text(
                json.dumps(SAMPLE_ARTIFACT, ensure_ascii=False), encoding="utf-8"
            )
            ai_path.write_text(json.dumps(ai_artifact, ensure_ascii=False), encoding="utf-8")

            non_ai_result = run_eval_artifact(
                artifact_path=non_ai_path,
                evals_base_dir=root / "non-ai-evals",
                playbook_definitions_root=root / "missing-definitions",
            )
            ai_result = run_eval_artifact(
                artifact_path=ai_path,
                evals_base_dir=root / "ai-evals",
                playbook_definitions_root=root / "missing-definitions",
            )

            non_ai_rows = [
                json.loads(line)
                for line in (
                    root / "non-ai-evals" / non_ai_result["eval_run_id"] / "results.jsonl"
                ).read_text(encoding="utf-8").splitlines()
            ]
            ai_rows = [
                json.loads(line)
                for line in (
                    root / "ai-evals" / ai_result["eval_run_id"] / "results.jsonl"
                ).read_text(encoding="utf-8").splitlines()
            ]

        assert all(row["evaluator_id"] != "ai_tech.evidence_receipt" for row in non_ai_rows)
        ai_receipt_rows = [
            row for row in ai_rows if row["evaluator_id"] == "ai_tech.evidence_receipt"
        ]
        assert len(ai_receipt_rows) == 1
        assert ai_receipt_rows[0]["status"] == "passed"

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
