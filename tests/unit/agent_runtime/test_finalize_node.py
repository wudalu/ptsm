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
