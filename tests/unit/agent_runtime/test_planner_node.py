from __future__ import annotations

from pathlib import Path

from ptsm.agent_runtime.nodes.planner import build_planner_node
from ptsm.domain.ai_tech_content import parse_ai_tech_evidence_bundle
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
    assert result["activated_skill_details"][0]["skill_name"] == "xhs_trend_scan"
    assert result["activated_skill_details"][0]["source_path"].endswith(
        "src/ptsm/skills/builtin/xhs_trend_scan/SKILL.md"
    )
    assert result["activated_skill_details"][0]["resource_type"] == "static_skill"
    assert all(
        "XHS Trend Scan Live Context" not in item for item in result["loaded_skill_contents"]
    )
    assert any(
        "XHS Trend Scan Live Context" in item for item in result["runtime_skill_contents"]
    )
    assert result["runtime_skill_details"] == [
        {
            "skill_name": "xhs_trend_scan",
            "resource_type": "runtime_context",
            "resource_id": "xhs_trend_scan:runtime_context",
            "source_path": None,
            "content_preview": "# XHS Trend Scan Live Context",
        }
    ]
    assert resolver.calls == [
        {
            "scene": "周四下午四点半，老板还在群里发新需求",
            "playbook_id": "fengkuang_daily_post",
            "loaded_skills": [
                "xhs_trend_scan",
                "topic_research",
                "xhs_image_strategy",
                "xhs_human_voice",
                "fengkuang_style",
                "positive_reframe",
                "xhs_hashtagging",
            ],
        }
    ]


def test_planner_adds_topic_direction_guidance_runtime_context() -> None:
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
            "scene": "把书桌改成十分钟手作角",
            "platform": "xiaohongshu",
            "account_id": "acct-fk-local",
            "topic_selection": {
                "topic_direction_id": "fk_work_object_vent",
                "source": "guide-post",
                "direction": {
                    "id": "fk_work_object_vent",
                    "name": "职场物件替人发疯",
                    "viral_hook": "评论区补一句",
                    "content_angle": "不是人在发疯，是工牌终于替我把那句话说出来了。",
                    "saveable_tool": "物件 / 它想说的话 / 体面翻译",
                    "comment_prompt": "你今天想让哪个物件替你发疯？",
                    "avoid": "不要拿心理疾病、医院、治疗或用药当笑点。",
                    "format_recommendation": {
                        "format_archetype": "note_card",
                        "cover_role": "save_tool",
                        "body_shape": "scene hook / three-column save card / comment relay",
                        "visual_evidence_need": "low",
                        "avoid_format": ["dense_text_poster", "harmful_joke"],
                    },
                },
            },
        }
    )

    context = "\n".join(result["runtime_skill_contents"])
    assert "# XHS Topic Direction Guidance" in context
    assert "fk_work_object_vent" in context
    assert "note_card" in context
    assert "save_tool" in context
    assert "dense_text_poster" in context
    assert result["runtime_skill_details"][-1] == {
        "skill_name": "topic_direction_guidance",
        "resource_type": "runtime_context",
        "resource_id": "topic_direction_guidance:runtime_context",
        "source_path": None,
        "content_preview": "# XHS Topic Direction Guidance",
    }


def test_planner_uses_only_safe_ai_evidence_and_skips_live_context_resolver() -> None:
    playbook_root = Path("src/ptsm/playbooks/definitions")
    skill_root = Path("src/ptsm/skills/builtin")
    playbooks = PlaybookRegistry(playbook_root=playbook_root)
    playbook_loader = PlaybookLoader(playbook_root=playbook_root)
    skills = SkillRegistry(skill_root=skill_root)
    skill_loader = SkillLoader(skills)
    resolver = FakeSkillContextResolver()

    planner = build_planner_node(
        domain="AI科技资讯",
        playbook_id="ai_tech_daily_post",
        playbooks=playbooks,
        playbook_loader=playbook_loader,
        skills=skills,
        skill_loader=skill_loader,
        skill_context_resolver=resolver,
        ai_tech_evidence=parse_ai_tech_evidence_bundle(
            {
                "mode": "news_brief",
                "news_items": [
                    {
                        "label": "模型发布",
                        "event_fingerprint": "event-model-001",
                        "facts": ["产品发布了新的推理模型。"],
                        "source_refs": ["official-001"],
                    },
                    {
                        "label": "开发者工具",
                        "event_fingerprint": "event-tools-002",
                        "facts": ["开发者工具新增了批量处理能力。"],
                        "source_refs": ["official-002"],
                    },
                    {
                        "label": "行业应用",
                        "event_fingerprint": "event-industry-003",
                        "facts": ["功能面向团队协作场景开放。"],
                        "source_refs": ["official-003"],
                    },
                ],
            }
        ).runtime_contract,
    )

    result = planner(
        {
            "scene": "Raw release title https://example.com/release by Example Author",
            "platform": "xiaohongshu",
            "account_id": "acct-ai-tech-local",
            "topic_selection": {
                "raw_source_url": "https://example.com/release",
                "author": "Example Author",
                "feed": "example-feed",
                "source_title": "Example source headline",
            },
        }
    )

    runtime_context = "\n".join(result["runtime_skill_contents"])

    assert resolver.calls == []
    assert "# AI Tech Evidence Contract" in runtime_context
    assert "产品发布了新的推理模型。" in runtime_context
    assert "实测体验" in runtime_context
    assert "https://example.com/release" not in runtime_context
    assert "Example Author" not in runtime_context
    assert "example-feed" not in runtime_context
    assert "Example source headline" not in runtime_context
    assert "# XHS Trend Scan Live Context" not in runtime_context
