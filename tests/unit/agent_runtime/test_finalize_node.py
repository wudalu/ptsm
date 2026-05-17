from __future__ import annotations

import json
from pathlib import Path

from ptsm.agent_runtime.runtime import build_finalize_node
from ptsm.infrastructure.artifacts.file_store import FileArtifactStore
from ptsm.infrastructure.memory.store import InMemoryExecutionMemory


def test_finalize_persists_step_outputs_for_evaluation(tmp_path: Path) -> None:
    memory = InMemoryExecutionMemory()
    finalize = build_finalize_node(
        execution_memory=memory,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
    )

    result = finalize(
        {
            "account_id": "acct-fk-local",
            "playbook_id": "fengkuang_daily_post",
            "drafting_provider": "deterministic",
            "selected_playbook": "fengkuang_daily_post",
            "candidate_skills": ["fengkuang_style"],
            "activated_skills": ["fengkuang_style"],
            "activated_skill_details": [{"skill_name": "fengkuang_style"}],
            "runtime_skill_details": [{"skill_name": "xhs_trend_scan"}],
            "runtime_skill_contents": ["# live context"],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
            "reflection_prompt": "# reflection",
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "attempt_count": 1,
            "draft_content": {
                "title": "标题",
                "body": "场景正文",
                "image_text": "图文",
                "hashtags": ["#发疯文学"],
            },
            "required_revision": False,
            "reflection_decision": "finalize",
            "reflection_feedback": "",
            "scene": "周五下班前",
            "final_content": {
                "title": "标题",
                "body": "场景正文",
                "image_text": "图文",
                "hashtags": ["#发疯文学"],
            },
        }
    )

    artifact = json.loads(Path(str(result["artifact_path"])).read_text(encoding="utf-8"))

    assert artifact["step_outputs"]["planner"]["selected_playbook"] == "fengkuang_daily_post"
    assert artifact["step_outputs"]["planner"]["planner_prompt"] == "# planner"
    assert artifact["step_outputs"]["planner"]["persona_prompt"] == "# persona"
    assert artifact["step_outputs"]["executor"]["attempt_count"] == 1
    assert artifact["step_outputs"]["reflector"]["reflection_decision"] == "finalize"
    assert artifact["step_outputs"]["reflector"]["reflection_feedback"] == ""
    assert artifact["content_review"]["status"] == "needs_human_review"
    assert artifact["content_review"]["generation_logic"]["playbook_id"] == (
        "fengkuang_daily_post"
    )
    assert artifact["content_review"]["quality_signals"]["comment_trigger"] is False
    assert "人工确认" in artifact["content_review"]["review_notes"][0]
    assert result["content_review"] == artifact["content_review"]

    lessons = memory.search(namespace=("accounts", "acct-fk-local", "lessons"))
    assert lessons == [
        {
            "playbook_id": "fengkuang_daily_post",
            "scene": "周五下班前",
            "attempt_count": 1,
            "title": "标题",
            "image_text": "图文",
            "hashtags": ["#发疯文学"],
            "final_body": "场景正文",
        }
    ]


def test_finalize_adds_image_form_review_for_human_enrichment(tmp_path: Path) -> None:
    memory = InMemoryExecutionMemory()
    finalize = build_finalize_node(
        execution_memory=memory,
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
    )

    result = finalize(
        {
            "account_id": "acct-enrichment-local",
            "playbook_id": "human_enrichment_daily_post",
            "drafting_provider": "deterministic",
            "selected_playbook": "human_enrichment_daily_post",
            "candidate_skills": ["human_enrichment_style"],
            "activated_skills": ["human_enrichment_style"],
            "activated_skill_details": [{"skill_name": "human_enrichment_style"}],
            "runtime_skill_details": [],
            "runtime_skill_contents": [],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
            "reflection_prompt": "# reflection",
            "reflection_rules": {"required_hashtag": "#人类丰容计划"},
            "attempt_count": 1,
            "draft_content": {
                "title": "给书桌加一个零成本变量",
                "body": "三步清单，评论区交一个角落。",
                "image_text": "今天先丰容这个角落",
                "hashtags": ["#人类丰容计划"],
            },
            "required_revision": False,
            "reflection_decision": "finalize",
            "reflection_feedback": "",
            "scene": "把下班后的书桌改成手作角",
            "final_content": {
                "title": "给书桌加一个零成本变量",
                "body": "三步清单，评论区交一个角落。",
                "image_text": "今天先丰容这个角落",
                "hashtags": ["#人类丰容计划"],
            },
        }
    )

    review = result["content_review"]

    assert review["image_form"]["primary_ratio"] == "3:4"
    assert review["image_form"]["cover_style"] == "real-life creator cover"
    assert review["image_form"]["recommended_sequence"] == [
        "cover",
        "before state",
        "variable/material flat lay",
        "mini checklist",
        "after state",
        "comment invitation",
    ]
    assert review["image_form"]["text_constraints"]["cover_max_chars"] == 14
    assert review["image_form"]["text_constraints"]["forbid_hashtags"] is True
    assert review["image_form"]["carousel_brief"][0]["role"] == "cover"
    assert review["image_form"]["carousel_brief"][3]["role"] == "mini checklist"


def test_finalize_adds_image_plan_review_when_final_content_contains_plan(
    tmp_path: Path,
) -> None:
    finalize = build_finalize_node(
        execution_memory=InMemoryExecutionMemory(),
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
    )

    result = finalize(
        {
            "account_id": "acct-fk-local",
            "playbook_id": "fengkuang_daily_post",
            "drafting_provider": "deterministic",
            "selected_playbook": "fengkuang_daily_post",
            "candidate_skills": ["fengkuang_style", "xhs_image_strategy"],
            "activated_skills": ["fengkuang_style", "xhs_image_strategy"],
            "activated_skill_details": [
                {"skill_name": "fengkuang_style"},
                {"skill_name": "xhs_image_strategy"},
            ],
            "runtime_skill_details": [],
            "runtime_skill_contents": [],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
            "reflection_prompt": "# reflection",
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "attempt_count": 1,
            "draft_content": {
                "title": "领导18:57发在吗",
                "body": "领导：在吗\n我：收到，但灵魂已下班。",
                "image_text": "收到，但灵魂已下班",
                "hashtags": ["#发疯文学"],
                "image_plan": {
                    "backend": "local_social_screenshot",
                    "style": "wechat_chat",
                    "reason": "聊天记录更符合正文的群聊形态",
                },
            },
            "required_revision": False,
            "reflection_decision": "finalize",
            "reflection_feedback": "",
            "scene": "领导18:57发在吗让我补材料",
            "final_content": {
                "title": "领导18:57发在吗",
                "body": "领导：在吗\n我：收到，但灵魂已下班。",
                "image_text": "收到，但灵魂已下班",
                "hashtags": ["#发疯文学"],
                "image_plan": {
                    "backend": "local_social_screenshot",
                    "style": "wechat_chat",
                    "reason": "聊天记录更符合正文的群聊形态",
                },
            },
        }
    )

    artifact = json.loads(Path(str(result["artifact_path"])).read_text(encoding="utf-8"))
    image_plan = result["content_review"]["image_plan"]

    assert image_plan["backend"] == "local_social_screenshot"
    assert image_plan["style"] == "wechat_chat"
    assert image_plan["reason"] == "聊天记录更符合正文的群聊形态"
    assert artifact["content_review"]["image_plan"] == image_plan


def test_finalize_image_form_uses_pattern_ids_from_runtime_context(tmp_path: Path) -> None:
    finalize = build_finalize_node(
        execution_memory=InMemoryExecutionMemory(),
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
    )

    result = finalize(
        {
            "account_id": "acct-enrichment-local",
            "playbook_id": "human_enrichment_daily_post",
            "drafting_provider": "deterministic",
            "selected_playbook": "human_enrichment_daily_post",
            "candidate_skills": ["human_enrichment_style"],
            "activated_skills": ["human_enrichment_style"],
            "activated_skill_details": [{"skill_name": "human_enrichment_style"}],
            "runtime_skill_details": [{"skill_name": "xhs_trend_scan"}],
            "runtime_skill_contents": [
                "# XHS Format Pattern Library Context\n"
                "- status: available\n"
                "- lane: human_enrichment\n"
                "- pattern_ids: human_enrichment.sudden_realization.001, human_enrichment.saveable_list.002\n"
                "- image_sequences: cover -> before state -> variable/material flat lay -> mini checklist -> after state -> comment invitation\n"
                "- primary_ratio: 3:4"
            ],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
            "reflection_prompt": "# reflection",
            "reflection_rules": {"required_hashtag": "#人类丰容计划"},
            "attempt_count": 1,
            "draft_content": {
                "title": "突然意识到书桌也需要丰容",
                "body": "三步清单，评论区交一个角落。",
                "image_text": "今天先丰容这个角落",
                "hashtags": ["#人类丰容计划"],
            },
            "required_revision": False,
            "reflection_decision": "finalize",
            "reflection_feedback": "",
            "scene": "把下班后的书桌改成手作角",
            "final_content": {
                "title": "突然意识到书桌也需要丰容",
                "body": "三步清单，评论区交一个角落。",
                "image_text": "今天先丰容这个角落",
                "hashtags": ["#人类丰容计划"],
            },
        }
    )

    image_form = result["content_review"]["image_form"]
    assert image_form["image_pattern_id"] == "human_enrichment.sudden_realization.001"
    assert image_form["carousel_pattern_id"] == "human_enrichment.saveable_list.002"


def test_finalize_content_review_detects_domain_save_mechanics(tmp_path: Path) -> None:
    finalize = build_finalize_node(
        execution_memory=InMemoryExecutionMemory(),
        artifact_store=FileArtifactStore(base_dir=tmp_path / "artifacts"),
    )

    result = finalize(
        {
            "account_id": "acct-ai-tech-local",
            "playbook_id": "ai_tech_daily_post",
            "drafting_provider": "deterministic",
            "selected_playbook": "ai_tech_daily_post",
            "candidate_skills": ["ai_tech_style"],
            "activated_skills": ["ai_tech_style"],
            "activated_skill_details": [{"skill_name": "ai_tech_style"}],
            "runtime_skill_details": [],
            "runtime_skill_contents": [],
            "planner_prompt": "# planner",
            "persona_prompt": "# persona",
            "reflection_prompt": "# reflection",
            "reflection_rules": {"required_hashtag": "#AI资讯"},
            "attempt_count": 1,
            "draft_content": {
                "title": "这次AI更新，普通人先看这三点",
                "image_text": "先看能不能真省事",
                "body": "可以先收藏清单：1. 看它能不能读懂文件。评论区聊聊你会怎么用。",
                "hashtags": ["#AI资讯"],
            },
            "required_revision": False,
            "reflection_decision": "finalize",
            "reflection_feedback": "",
            "scene": "AI工具更新",
            "final_content": {
                "title": "这次AI更新，普通人先看这三点",
                "image_text": "先看能不能真省事",
                "body": "可以先收藏清单：1. 看它能不能读懂文件。评论区聊聊你会怎么用。",
                "hashtags": ["#AI资讯"],
            },
        }
    )

    review = result["content_review"]
    assert review["quality_signals"]["save_trigger"] is True
    assert review["generation_logic"]["save_strategy"] == "已包含可复制或可保存元素"
    assert "建议补充可复制句、模板、三栏工具或可截图清单。" not in review["review_notes"]
