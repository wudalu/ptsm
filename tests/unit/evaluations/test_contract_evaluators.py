from __future__ import annotations

import pytest
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.contracts_eval import (
    contract_artifact_root_fields,
    contract_playbook_node_contract,
    contract_skill_details_match,
    ALL_CONTRACT_EVALUATORS,
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


class TestAllContractEvaluators:
    def test_all_registered(self):
        assert len(ALL_CONTRACT_EVALUATORS) >= 2
