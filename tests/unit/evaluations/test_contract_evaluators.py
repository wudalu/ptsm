from __future__ import annotations

from copy import deepcopy

import pytest
from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.contracts_eval import (
    contract_ai_tech_evidence_receipt,
    contract_psychology_learning_receipt,
    contract_artifact_root_fields,
    contract_playbook_node_contract,
    contract_skill_details_match,
    ALL_CONTRACT_EVALUATORS,
)
from ptsm.domain.psychology_learning import (
    build_psychology_learning_catalog_receipt,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
)
from ptsm.evaluations.playbook_contracts import PlaybookEvalContract


def _target(**overrides):
    defaults = {
        "target_id": "t:final:ac",
        "run_id": "r",
        "playbook_id": "fengkuang_daily_post",
        "account_id": "acct",
        "phase": "final",
        "target_type": "artifact_slice",
    }
    defaults.update(overrides)
    return EvalTarget(**defaults)


class TestArtifactRootFields:
    def test_passes_with_all_required(self):
        target = _target(
            output_ref={
                "playbook_id": "fengkuang_daily_post",
                "final_content": {"title": "T", "body": "B", "hashtags": ["#h"]},
                "activated_skill_details": [{"skill_name": "fs"}],
                "scene": "test",
                "publish_mode": "dry-run",
            },
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "passed"

    def test_fails_with_missing_root_field(self):
        target = _target(
            output_ref={"playbook_id": "pb"},
        )
        result = contract_artifact_root_fields(target)
        assert result.status == "failed"

    def test_skipped_without_output_ref(self):
        target = _target(output_ref=None)
        result = contract_artifact_root_fields(target)
        assert result.status == "skipped"


class TestSkillDetailsMatch:
    def test_passes_when_skills_match(self):
        target = _target(
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                    {"skill_name": "s2"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "passed"

    def test_fails_when_skill_missing_details(self):
        target = _target(
            phase="planner",
            target_type="node_output",
            output_ref={
                "activated_skills": ["s1", "s2", "s3"],
                "activated_skill_details": [
                    {"skill_name": "s1"},
                ],
            },
        )
        result = contract_skill_details_match(target)
        assert result.status == "failed"

    def test_skipped_without_output_ref(self):
        target = _target(phase="planner", target_type="node_output", output_ref=None)
        result = contract_skill_details_match(target)
        assert result.status == "skipped"


def _ai_tech_receipt(
    *,
    mode: str = "news_brief",
    manifest: dict | None = None,
    gate: dict | None = None,
) -> dict:
    default_manifest = {
        "source_refs": ["source:official-1"],
        "test_evidence_refs": [],
        "event_fingerprints": [
            "event:model-1",
            "event:tool-2",
            "event:industry-3",
        ],
        "trend_support": [],
    }
    return {
        "ai_tech_content_mode": mode,
        "ai_tech_evidence_manifest": (
            default_manifest if manifest is None else manifest
        ),
        "ai_tech_evidence_gate": gate
        if gate is not None
        else {
            "status": "passed",
            "mode": mode,
            "validator": "ai_tech_draft_contract",
            "validator_version": "1",
            "errors": [],
        },
    }


class TestAiTechEvidenceReceipt:
    def test_accepts_complete_news_receipt(self):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref={
                **_ai_tech_receipt(),
                "final_content": {
                    "title": "AI 三条更新",
                    "body": "模型发布：已开放推理能力。\n开发者工具：新增批处理。\n行业应用：支持团队协作。",
                    "hashtags": ["#AI资讯"],
                },
            },
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "passed"
        assert result.evaluator_id == "ai_tech.evidence_receipt"

    def test_rejects_missing_receipt_fields_without_echoing_raw_values(self):
        raw_url = "https://private.example.com/release?token=secret"
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref={
                "ai_tech_content_mode": "news_brief",
                "ai_tech_evidence_manifest": {"source_url": raw_url},
                "final_content": {"body": raw_url},
            },
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "failed"
        assert "ai_tech_evidence_gate" in result.reason
        serialized = str(result.to_dict())
        assert raw_url not in serialized
        assert "private.example.com" not in serialized

    @pytest.mark.parametrize(
        ("mode", "manifest"),
        [
            (
                "hands_on",
                {
                    "source_refs": [],
                    "test_evidence_refs": ["test:run-1"],
                    "event_fingerprints": [],
                    "trend_support": [],
                },
            ),
            (
                "fact_translation",
                {
                    "source_refs": ["source:official-1"],
                    "test_evidence_refs": [],
                    "event_fingerprints": [],
                    "trend_support": [],
                },
            ),
        ],
    )
    def test_accepts_mode_specific_safe_manifest(self, mode, manifest):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref=_ai_tech_receipt(mode=mode, manifest=manifest),
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "passed"

    def test_rejects_wrong_news_item_count_and_non_hands_on_experience(self):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref={
                **_ai_tech_receipt(
                    manifest={
                        "source_refs": ["source:official-1"],
                        "test_evidence_refs": [],
                        "event_fingerprints": ["event:only-1", "event:only-2"],
                        "trend_support": [],
                    }
                ),
                "final_content": {
                    "title": "AI 更新",
                    "body": "我实测后发现这次更新很好用。",
                    "hashtags": ["#AI资讯"],
                },
            },
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "failed"
        assert "event fingerprints" in result.reason
        assert "experiential language" in result.reason

    def test_rejects_duplicate_news_event_fingerprints(self):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref=_ai_tech_receipt(
                manifest={
                    "source_refs": ["source:official-1"],
                    "test_evidence_refs": [],
                    "event_fingerprints": [
                        "event:duplicate",
                        "event:duplicate",
                        "event:industry-3",
                    ],
                    "trend_support": [],
                }
            ),
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "failed"
        assert "distinct event fingerprints" in result.reason

    def test_rejects_non_hands_on_experience_without_an_explicit_test_claim(self):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref={
                **_ai_tech_receipt(),
                "final_content": {
                    "title": "AI 更新",
                    "body": "上手体验后，这项功能比预期顺手。",
                    "hashtags": ["#AI资讯"],
                },
            },
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "failed"
        assert "experiential language" in result.reason

    def test_rejects_gate_that_does_not_prove_the_matching_validator(self):
        target = _target(
            playbook_id="ai_tech_daily_post",
            output_ref=_ai_tech_receipt(
                gate={
                    "status": "passed",
                    "mode": "fact_translation",
                    "validator": "other_gate",
                    "validator_version": "2",
                    "errors": ["raw source https://private.example.com"],
                }
            ),
        )

        result = contract_ai_tech_evidence_receipt(target)

        assert result.status == "failed"
        assert "gate mode does not match receipt mode" in result.reason
        assert "https://private.example.com" not in str(result.to_dict())


def _psychology_learning_receipt(*, bundle=None) -> dict:
    if bundle is None:
        bundle = resolve_psychology_learning_selection(
            series_id="after_work_rumination",
            lesson_id="notice_the_loop",
        )
    contract = bundle.runtime_contract
    receipt = {
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
        "final_content": render_psychology_learning_draft(contract),
    }
    catalog_receipt = build_psychology_learning_catalog_receipt(bundle)
    if catalog_receipt is not None:
        receipt["psychology_learning_catalog_receipt"] = catalog_receipt
    return receipt


class TestPsychologyLearningReceipt:
    def test_accepts_complete_catalog_receipt(self):
        target = _target(
            playbook_id="modern_psychology_post",
            output_ref=_psychology_learning_receipt(),
        )

        result = contract_psychology_learning_receipt(target)

        assert result.status == "passed"
        assert result.evaluator_id == "psychology.learning_receipt"

    def test_rejects_a_tampered_catalog_owned_carousel_page(self):
        receipt = _psychology_learning_receipt()
        receipt["final_content"]["image_plan"]["slides"][2]["body_lines"][0] = (
            "一条没有经过目录确认的新解释"
        )

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "visible content" in result.reason

    def test_accepts_confirmed_custom_catalog_receipt(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {"id": "notice", "title": "先识别重复时刻"},
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store = PsychologyLearningSeriesStore(trusted_provision=True, )
        store.persist_proposal(proposal)
        catalog = store.confirm(
            proposal_id=proposal.proposal_id,
            proposal_fingerprint=proposal.proposal_fingerprint,
        )
        bundle = resolve_psychology_learning_selection(
            series_id=catalog.series_id,
            lesson_id=catalog.lessons[0].lesson_id,
            curriculum_version=catalog.curriculum_version,
        )

        assert bundle.catalog is not None
        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=_psychology_learning_receipt(bundle=bundle),
            )
        )

        assert result.status == "passed"

    @pytest.mark.parametrize(
        "tamper_field",
        (
            "missing",
            "catalog_digest",
            "approval_id",
            "proposal_fingerprint",
            "publication_plan",
        ),
    )
    def test_rejects_every_tampered_custom_catalog_receipt_field(
        self,
        tamper_field: str,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        private_goal = "只在确认前可见的私人目标"
        proposal = plan_psychology_learning_series(
            topic="下班后的脑内回放",
            outline=(
                {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
                {"id": "practice", "title": "练习一个小步骤"},
            ),
        )
        store = PsychologyLearningSeriesStore(trusted_provision=True, )
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
        receipt = _psychology_learning_receipt(bundle=bundle)
        catalog_receipt = deepcopy(receipt["psychology_learning_catalog_receipt"])
        if tamper_field == "missing":
            receipt.pop("psychology_learning_catalog_receipt")
        elif tamper_field == "publication_plan":
            catalog_receipt["publication_plan"]["items"][0]["rationale"] = "另一个安全理由"
            receipt["psychology_learning_catalog_receipt"] = catalog_receipt
        else:
            catalog_receipt[tamper_field] = f"{tamper_field}:tampered"
            receipt["psychology_learning_catalog_receipt"] = catalog_receipt

        result = contract_psychology_learning_receipt(
            _target(playbook_id="modern_psychology_post", output_ref=receipt)
        )

        assert result.status == "failed"
        assert "catalog receipt" in result.reason
        assert private_goal not in str(result.to_dict())

    def test_accepts_the_framework_owned_catalog_topic_selection_marker(self):
        receipt = _psychology_learning_receipt()
        receipt["topic_selection"] = {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": "after_work_rumination",
                "curriculum_version": "1",
                "lesson_id": "notice_the_loop",
                "lesson_number": 1,
            },
        }
        receipt["image_generation"] = {
            "status": "generated",
            "renderer": "ptsm_local_renderer",
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "passed"

    def test_skips_ordinary_psychology_artifacts_without_learning_receipt(self):
        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref={"final_content": {"body": "普通心理学帖"}},
            )
        )

        assert result.status == "skipped"

    def test_rejects_tampered_lesson_or_visible_source_without_echoing_it(self):
        raw_url = "https://private.example.com/psychology-source"
        receipt = _psychology_learning_receipt()
        receipt["psychology_learning_lesson_id"] = "close_the_replay"
        receipt["final_content"] = {
            **receipt["final_content"],
            "body": str(receipt["final_content"]["body"]) + raw_url,
        }
        target = _target(
            playbook_id="modern_psychology_post",
            output_ref=receipt,
        )

        result = contract_psychology_learning_receipt(target)

        assert result.status == "failed"
        assert "lesson" in result.reason
        assert raw_url not in str(result.to_dict())

    def test_rejects_raw_provenance_outside_the_opaque_manifest(self):
        raw_url = "https://private.example.com/psychology-source"
        receipt = _psychology_learning_receipt()
        receipt["source_url"] = raw_url

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_url not in str(result.to_dict())

    def test_rejects_generic_source_and_headline_fields_outside_the_manifest(self):
        raw_source_title = "APA rumination study title and author"
        raw_headline = "原始研究标题"
        receipt = _psychology_learning_receipt()
        receipt["source"] = raw_source_title
        receipt["headline"] = raw_headline

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_source_title not in str(result.to_dict())
        assert raw_headline not in str(result.to_dict())

    def test_rejects_plain_source_ref_outside_the_opaque_manifest(self):
        raw_source_ref = "APA Rumination Study by Author"
        receipt = _psychology_learning_receipt()
        receipt["source_ref"] = raw_source_ref

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_source_ref not in str(result.to_dict())

    def test_rejects_untrusted_raw_publisher_response(self):
        raw_response = "APA Rumination Study by Author"
        receipt = _psychology_learning_receipt()
        receipt["publish_result"] = {
            "status": "published",
            "raw_response": raw_response,
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_response not in str(result.to_dict())

    def test_rejects_unknown_root_field_that_contains_raw_provenance(self):
        raw_value = "APA Rumination Study by Author"
        receipt = _psychology_learning_receipt()
        receipt["provider_message"] = raw_value

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_value not in str(result.to_dict())

    def test_rejects_unknown_nested_publish_metadata(self):
        raw_value = "APA Rumination Study by Author"
        receipt = _psychology_learning_receipt()
        receipt["publish_result"] = {
            "status": "published",
            "provider_message": raw_value,
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason
        assert raw_value not in str(result.to_dict())

    def test_rejects_external_post_identifiers_even_when_the_url_looks_canonical(self):
        receipt = _psychology_learning_receipt()
        canonical_post_url = "https://www.xiaohongshu.com/explore/note-123"
        receipt["publish_result"] = {
            "status": "published",
        }
        receipt["post_publish_checks"] = {
            "requested": True,
            "browser_opened": False,
            "publish_status": "published_visible",
            "status_result": {
                "status": "published_visible",
                "source": "mcp_search",
            }
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "passed"

        receipt["publish_result"].update(
            {
                "post_id": "note-123",
                "post_url": canonical_post_url,
            }
        )
        rejected = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert rejected.status == "failed"
        assert "provenance" in rejected.reason

    @pytest.mark.parametrize(
        "operational_metadata",
        (
            {"publish_result": {"status": "Smith_2024_Rumination_MetaAnalysis"}},
            {
                "post_publish_checks": {
                    "requested": True,
                    "browser_opened": False,
                    "publish_status": "Smith_2024_Rumination_MetaAnalysis",
                    "status_result": {
                        "status": "Smith_2024_Rumination_MetaAnalysis",
                        "source": "mcp",
                    },
                }
            },
            {
                "account": {
                    "account_id": "Smith_2024_Rumination_MetaAnalysis",
                    "platform": "xiaohongshu",
                }
            },
            {"run": {"run_id": "Smith_2024_Rumination_MetaAnalysis"}},
            {
                "image_generation": {
                    "provider": "Smith_2024_Rumination_MetaAnalysis",
                }
            },
            {
                "image_generation": {
                    "generated_image_paths": [
                        "outputs/generated_images/Smith_2024_Rumination_MetaAnalysis.png"
                    ]
                }
            },
            {
                "image_generation": {
                    "asset_ledger": {
                        "status": "recorded",
                        "entry_count": "Smith_2024_Rumination_MetaAnalysis",
                    }
                }
            },
            {
                "watermark_removal": {
                    "status": "skipped",
                    "result_count": "Smith_2024_Rumination_MetaAnalysis",
                }
            },
        ),
        ids=(
            "publish_status",
            "post_publish_status",
            "account_id",
            "run_id",
            "image_provider",
            "image_path",
            "asset_ledger_count",
            "watermark_result_count",
        ),
    )
    def test_rejects_free_form_values_in_closed_operational_metadata(
        self,
        operational_metadata: dict,
    ):
        receipt = _psychology_learning_receipt()
        receipt.update(operational_metadata)

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason

    def test_rejects_catalog_marker_that_does_not_match_the_receipt_lesson(self):
        receipt = _psychology_learning_receipt()
        receipt["topic_selection"] = {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": "after_work_rumination",
                "curriculum_version": "1",
                "lesson_id": "close_the_replay",
                "lesson_number": 5,
            },
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=receipt,
            )
        )

        assert result.status == "failed"
        assert "provenance" in result.reason

    def test_rejects_catalog_marked_artifact_when_its_learning_receipt_is_missing(self):
        receipt = _psychology_learning_receipt()
        incomplete_artifact = {
            key: value
            for key, value in receipt.items()
            if not key.startswith("psychology_learning_")
        }
        incomplete_artifact["topic_selection"] = {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": "after_work_rumination",
                "lesson_id": "notice_the_loop",
                "curriculum_version": "1",
            },
        }

        result = contract_psychology_learning_receipt(
            _target(
                playbook_id="modern_psychology_post",
                output_ref=incomplete_artifact,
            )
        )

        assert result.status == "failed"
        assert "receipt" in result.reason


class TestPlaybookNodeContract:
    def test_fails_when_executor_required_field_missing(self):
        contract = PlaybookEvalContract(
            suite_id="pb.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "短标题",
                    "body": "正文",
                    "hashtags": ["#tag"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "image_text" in result.reason
        assert result.evaluator_id == "playbook.node_contract"

    def test_fails_when_executor_title_exceeds_contract_limit(self):
        contract = PlaybookEvalContract(
            suite_id="pb.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {"title_max_chars": 3},
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "超过三字",
                    "body": "正文",
                    "hashtags": ["#tag"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "title_max_chars" in result.reason

    def test_passes_when_phase_contract_is_satisfied(self):
        contract = PlaybookEvalContract(
            suite_id="pb.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "title_max_chars": 10,
                        "hashtags_min_count": 1,
                        "hashtags_max_count": 3,
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "短标题",
                    "body": "正文",
                    "hashtags": ["#tag"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "passed"

    def test_fails_when_required_hashtag_is_missing(self):
        contract = PlaybookEvalContract(
            suite_id="psych.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "hashtags_must_include_any": ["#心理学", "#情绪管理"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "复盘停不下来",
                    "body": "这是一种反刍思维。",
                    "hashtags": ["#自我成长"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "hashtags_must_include_any" in result.reason

    def test_fails_when_forbidden_hashtag_is_present(self):
        contract = PlaybookEvalContract(
            suite_id="reddit.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "hashtags_must_not_include_any": ["#Reddit"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "AI用顺了以后，人反而更累了",
                    "body": "AI 工具越多，越需要守住判断边界。",
                    "hashtags": ["#热点观察", "#Reddit"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "hashtags_must_not_include_any" in result.reason

    def test_fails_when_forbidden_body_text_is_present(self):
        contract = PlaybookEvalContract(
            suite_id="psych.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_must_not_include_any": ["你就是抑郁症", "治好焦虑"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "别再忽略这个信号",
                    "body": "你就是抑郁症，这样做能治好焦虑。",
                    "hashtags": ["#心理学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_must_not_include_any" in result.reason

    def test_fails_when_title_or_image_text_matches_forbidden_quality_values(self):
        contract = PlaybookEvalContract(
            suite_id="fengkuang.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                    "constraints": {
                        "title_must_not_equal_any": ["打工人地铁生存实录"],
                        "image_text_must_not_equal_any": ["今日已疯"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "打工人地铁生存实录",
                    "image_text": "今日已疯",
                    "body": "周一早高峰地铁通勤。评论区接一句你的通勤疯话。",
                    "hashtags": ["#发疯文学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "title_must_not_equal_any" in result.reason
        assert "image_text_must_not_equal_any" in result.reason

    def test_fails_when_title_lacks_required_hook_or_scene_terms(self):
        contract = PlaybookEvalContract(
            suite_id="human_voice.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                    "constraints": {
                        "title_must_include_any": ["工牌", "群聊", "边界", "丰容"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "今天也要好好生活",
                    "image_text": "先慢一点",
                    "body": "今天先写一个具体场景，评论区交一个例子。",
                    "hashtags": ["#小红书"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "title_must_include_any" in result.reason

    def test_fails_when_title_lacks_required_tension_marker(self):
        contract = PlaybookEvalContract(
            suite_id="human_voice.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                    "constraints": {
                        "title_must_include_tension_any": ["那一秒", "不是", "别", "却"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "今天也要好好生活",
                    "image_text": "先慢一点",
                    "body": "今天先写一个具体场景，评论区交一个例子。",
                    "hashtags": ["#小红书"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "title_must_include_tension_any" in result.reason

    def test_fails_when_title_contains_forbidden_generic_marker(self):
        contract = PlaybookEvalContract(
            suite_id="title.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "title_must_not_include_any": ["实录", "小红书爆款"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "打工人地铁生存实录",
                    "body": "评论区接一句。",
                    "hashtags": ["#发疯文学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "title_must_not_include_any" in result.reason

    def test_fails_when_template_markers_appear_across_title_image_or_body(self):
        contract = PlaybookEvalContract(
            suite_id="human_voice.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                    "constraints": {
                        "combined_must_not_include_any": ["首先", "综上", "作为AI"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "首先，今天讲一个话题",
                    "image_text": "先存这句",
                    "body": "评论区交一个例子。",
                    "hashtags": ["#小红书"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "combined_must_not_include_any" in result.reason

    def test_fails_when_comment_prompt_or_save_trigger_is_missing(self):
        contract = PlaybookEvalContract(
            suite_id="quality.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "image_text", "hashtags"],
                    "constraints": {
                        "body_must_include_comment_prompt_any": ["评论区", "你最"],
                        "body_must_include_save_trigger_any": ["三栏", "模板", "可复制"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "领导18:57发在吗那一秒",
                    "image_text": "我的工牌先替我发疯",
                    "body": "领导下班前发来一句在吗，我的工牌已经想先下班。",
                    "hashtags": ["#发疯文学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_must_include_comment_prompt_any" in result.reason
        assert "body_must_include_save_trigger_any" in result.reason

    def test_fails_when_body_lacks_required_scene_signal(self):
        contract = PlaybookEvalContract(
            suite_id="human_voice.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_must_include_scene_signal": True,
                        "body_scene_signal_any": ["领导", "工牌", "下班"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "下班那一秒",
                    "body": "职场压力需要被合理释放。评论区接一句。",
                    "hashtags": ["#发疯文学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_must_include_scene_signal" in result.reason

    def test_passes_when_body_contains_scene_signal_and_human_anchor(self):
        contract = PlaybookEvalContract(
            suite_id="human_voice.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_must_include_scene_signal": True,
                        "body_scene_signal_any": ["领导", "工牌", "下班"],
                        "body_human_anchor_any": ["我", "今天", "那一秒"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "下班那一秒",
                    "body": "领导18:57发在吗那一秒，我的工牌已经想先下班。评论区接一句。",
                    "hashtags": ["#发疯文学"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "passed"

    def test_passes_when_body_contains_required_psychology_safety_signals(self):
        contract = PlaybookEvalContract(
            suite_id="psych.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_must_include_any": ["心理机制", "反刍思维"],
                        "body_must_not_include_any": ["治好焦虑"],
                        "hashtags_must_include_any": ["#心理学", "#情绪管理"],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "复盘停不下来",
                    "body": "心理机制上，这更像反刍思维。痛苦持续时要寻求专业帮助。",
                    "hashtags": ["#心理学", "#情绪管理"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "passed"

    def test_fails_when_body_shorter_than_min_chars(self):
        contract = PlaybookEvalContract(
            suite_id="length.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {"body_min_chars": 10},
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "短正文",
                    "body": "太短",
                    "hashtags": ["#测试"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_min_chars" in result.reason

    def test_fails_when_body_longer_than_max_chars(self):
        contract = PlaybookEvalContract(
            suite_id="length.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {"body_max_chars": 5},
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "长正文",
                    "body": "这段正文超过五个字",
                    "hashtags": ["#测试"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_max_chars" in result.reason

    def test_allows_documented_extended_prompt_asset_only_with_every_marker(self):
        contract = PlaybookEvalContract(
            suite_id="ai_prompt_asset.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_max_chars": 20,
                        "body_extended_asset_max_chars": 240,
                        "body_extended_asset_must_include_all": [
                            "任务：",
                            "背景：",
                            "输出格式：",
                            "不要编造",
                        ],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "AI提示词",
                    "body": (
                        "任务：整理会议记录。背景：给直属领导看。"
                        "输出格式：三条短句。不要编造数据。"
                    ),
                    "hashtags": ["#AI资讯"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "passed"

    def test_rejects_extended_prompt_asset_when_a_required_marker_is_missing(self):
        contract = PlaybookEvalContract(
            suite_id="ai_prompt_asset.default",
            node_contracts={
                "executor": {
                    "required_fields": ["title", "body", "hashtags"],
                    "constraints": {
                        "body_max_chars": 20,
                        "body_extended_asset_max_chars": 240,
                        "body_extended_asset_must_include_all": [
                            "任务：",
                            "背景：",
                            "输出格式：",
                            "不要编造",
                        ],
                    },
                }
            },
        )
        target = _target(
            phase="executor",
            target_type="artifact_slice",
            output_ref={
                "final_content": {
                    "title": "AI提示词",
                    "body": "任务：整理会议记录。背景：给直属领导看。输出格式：三条短句。",
                    "hashtags": ["#AI资讯"],
                }
            },
        )

        result = contract_playbook_node_contract(target, contract)

        assert result.status == "failed"
        assert "body_max_chars" in result.reason


class TestAllContractEvaluators:
    def test_all_registered(self):
        assert len(ALL_CONTRACT_EVALUATORS) >= 2
