from __future__ import annotations

from pathlib import Path

from ptsm.agent_runtime.nodes.planner import build_planner_node
from ptsm.playbooks.loader import PlaybookLoader
from ptsm.playbooks.registry import PlaybookRegistry
from ptsm.skills.loader import SkillLoader
from ptsm.skills.registry import SkillRegistry


class FakeSkillContextResolver:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def resolve(self, *, state, playbook, loaded_skills) -> dict[str, str]:
        self.calls.append(
            {
                "scene": state["scene"],
                "playbook_id": playbook.playbook_id,
                "loaded_skills": [item.skill.skill_name for item in loaded_skills],
            }
        )
        return {
            "xhs_trend_scan": (
                "# XHS Trend Scan Live Context\n"
                "主切口：怎么才周四 + 打工人发疯文学 + 下班前被新需求拽回工位"
            )
        }


def test_planner_separates_runtime_skill_contexts_from_static_skills() -> None:
    playbook_root = Path("src/ptsm/playbooks/definitions")
    skill_root = Path("src/ptsm/skills/builtin")
    playbooks = PlaybookRegistry(playbook_root=playbook_root)
    playbook_loader = PlaybookLoader(playbook_root=playbook_root)
    skills = SkillRegistry(skill_root=skill_root)
    skill_loader = SkillLoader(skills)
    resolver = FakeSkillContextResolver()

    planner = build_planner_node(
        domain="发疯文学",
        playbook_id="fengkuang_daily_post",
        playbooks=playbooks,
        playbook_loader=playbook_loader,
        skills=skills,
        skill_loader=skill_loader,
        skill_context_resolver=resolver,
    )

    result = planner(
        {
            "scene": "周四下午四点半，老板还在群里发新需求",
            "platform": "xiaohongshu",
            "account_id": "acct-fk-local",
        }
    )

    assert result["activated_skills"][0] == "xhs_trend_scan"
    assert "普通打工人" in result["persona_prompt"]
    assert all(
        "XHS Trend Scan Live Context" not in item for item in result["loaded_skill_contents"]
    )
    assert any(
        "XHS Trend Scan Live Context" in item for item in result["runtime_skill_contents"]
    )
    assert resolver.calls == [
        {
            "scene": "周四下午四点半，老板还在群里发新需求",
            "playbook_id": "fengkuang_daily_post",
            "loaded_skills": [
                "xhs_trend_scan",
                "fengkuang_style",
                "positive_reframe",
                "xhs_hashtagging",
            ],
        }
    ]
