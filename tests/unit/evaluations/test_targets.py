from __future__ import annotations

from pathlib import Path
import pytest
from ptsm.evaluations.targets import extract_targets_from_artifact


SAMPLE_ARTIFACT = {
    "playbook_id": "fengkuang_daily_post",
    "scene": "Monday morning commute",
    "account": {
        "account_id": "acct-fk-local",
        "platform": "xiaohongshu",
    },
    "publish_mode": "dry-run",
    "activated_skills": ["fengkuang_style", "xhs_hashtagging"],
    "activated_skill_details": [
        {"skill_name": "fengkuang_style", "display_name": "Fengkuang Style"},
        {"skill_name": "xhs_hashtagging", "display_name": "XHS Hashtagging"},
    ],
    "final_content": {
        "title": "test title",
        "body": "test body content",
        "image_text": "image description",
        "hashtags": ["#fakelit", "#test"],
    },
    "runtime_skill_details": [],
    "drafting_provider": "deepseek",
}


class TestTargetExtraction:
    def test_extracts_final_content_target(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        final_targets = [t for t in targets if t.phase == "final"]
        assert len(final_targets) == 1
        assert final_targets[0].target_type == "artifact_slice"
        assert final_targets[0].playbook_id == "fengkuang_daily_post"

    def test_extracts_skill_activation_target(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        skill_targets = [
            t for t in targets if t.target_type == "node_output" and "skill" in t.target_id
        ]
        assert len(skill_targets) >= 1

    def test_all_targets_have_required_fields(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        for target in targets:
            assert target.target_id
            assert target.run_id == "run-1"
            assert target.playbook_id
            assert target.account_id
            assert target.phase

    def test_target_metadata_includes_skills(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        final = [t for t in targets if t.phase == "final"][0]
        assert final.metadata is not None
        assert "skill_names" in final.metadata

    def test_executor_target_has_output_ref(self):
        targets = extract_targets_from_artifact(SAMPLE_ARTIFACT, run_id="run-1")
        executor = [t for t in targets if t.phase == "executor"][0]
        assert executor.output_ref is not None
        assert "final_content" in executor.output_ref

    def test_artifact_without_skills_has_no_planner_target(self):
        artifact = {**SAMPLE_ARTIFACT, "activated_skill_details": []}
        targets = extract_targets_from_artifact(artifact, run_id="run-2")
        planner = [t for t in targets if t.phase == "planner"]
        assert len(planner) == 0

    def test_extracts_step_and_side_effect_targets_when_evidence_exists(self):
        artifact = {
            **SAMPLE_ARTIFACT,
            "step_outputs": {
                "planner": {
                    "selected_playbook": "fengkuang_daily_post",
                    "planner_prompt": "# planner",
                    "persona_prompt": "# persona",
                },
                "executor": {
                    "attempt_count": 2,
                    "draft_content": SAMPLE_ARTIFACT["final_content"],
                },
                "reflector": {
                    "reflection_decision": "finalize",
                    "reflection_feedback": "",
                    "required_revision": False,
                },
            },
            "image_generation": {
                "status": "completed",
                "generated_image_paths": ["outputs/generated_images/cover.png"],
            },
            "publish_result": {
                "status": "published",
                "post_id": "post-1",
            },
            "post_publish_checks": {
                "publish_status": "published_search_verified",
            },
        }

        targets = extract_targets_from_artifact(artifact, run_id="run-3")
        phases = {target.phase for target in targets}

        assert {
            "planner",
            "executor",
            "reflector",
            "final",
            "image",
            "publish",
            "post_publish",
        }.issubset(phases)
        reflector = [target for target in targets if target.phase == "reflector"][0]
        assert reflector.output_ref == artifact["step_outputs"]["reflector"]
        publish = [target for target in targets if target.phase == "publish"][0]
        assert publish.output_ref == artifact["publish_result"]
