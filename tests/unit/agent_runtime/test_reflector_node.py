from __future__ import annotations

import json

from ptsm.agent_runtime.nodes.reflector import build_reflector_node
from ptsm.domain.ai_tech_content import (
    parse_ai_tech_evidence_bundle,
    validate_ai_tech_draft_contract,
)
from ptsm.domain.psychology_carousel import normalize_psychology_carousel_plan
from ptsm.domain.psychology_learning import (
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
)
from ptsm.infrastructure.evaluations.content_quality_gate import (
    build_content_quality_judge_gate,
)
from ptsm.infrastructure.llm.factory import DeterministicDraftBackend


class FakeJudgeBackend:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def judge(self, *, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def _news_brief_contract() -> dict[str, object]:
    return parse_ai_tech_evidence_bundle(
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
    ).runtime_contract


def _hands_on_contract() -> dict[str, object]:
    return parse_ai_tech_evidence_bundle(
        {
            "mode": "hands_on",
            "topic": {"label": "Kimi K3 更新"},
            "hands_on": {
                "product": "Kimi",
                "version": "K3",
                "tested_at": "2026-07-22",
                "task": "把一段会议纪要整理成待办清单",
                "input_summary": "一段脱敏会议纪要",
                "observed_output": "输出了 5 条带负责人的待办",
                "limitation": "长文本仍会漏掉上下文",
                "test_evidence_refs": ["test-kimi-001"],
            },
        }
    ).runtime_contract


def _fact_translation_contract() -> dict[str, object]:
    return parse_ai_tech_evidence_bundle(
        {
            "mode": "fact_translation",
            "topic": {"label": "模型更新"},
            "facts": [
                {
                    "statement": "更新说明新增了接入方式。",
                    "source_refs": ["official-001"],
                },
                {
                    "statement": "团队权限有变化。",
                    "source_refs": ["official-002"],
                },
            ],
            "audience": {
                "who_should_care": "正在接入的开发者",
                "who_can_wait": "暂不迁移的用户",
            },
        }
    ).runtime_contract


def _bound_ai_gate(contract: dict[str, object]):
    return lambda _state, draft: validate_ai_tech_draft_contract(contract, draft)


def _psychology_learning_contract(*, lesson_id: str) -> dict[str, object]:
    return resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id=lesson_id,
    ).runtime_contract


def _bound_psychology_learning_gate(contract: dict[str, object]):
    return lambda _state, draft: validate_psychology_learning_draft_contract(
        contract, draft
    )


def _ordinary_psychology_carousel_draft() -> dict[str, object]:
    return DeterministicDraftBackend().generate(
        scene="下班后身体还在工位，需要5分钟恢复信号",
        planner_prompt="modern_psychology_post 现代心理困境观察",
        skill_contents=[
            "# Psychology Style\n#心理学，使用具体场景和低风险工具。",
            "# XHS Image Strategy\n输出 image_plan。",
        ],
    )


def _ordinary_psychology_carousel_gate(
    _state: dict[str, object],
    draft: dict[str, object],
) -> list[str]:
    image_plan = draft.get("image_plan")
    if not isinstance(image_plan, dict) or "slides" not in image_plan:
        return []
    try:
        normalize_psychology_carousel_plan(image_plan)
    except ValueError:
        return ["invalid psychology carousel plan"]
    return []


def test_reflector_accepts_required_hashtag_without_optional_phrase() -> None:
    node = build_reflector_node(max_attempts=2)

    result = node(
        {
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "draft_content": {
                "body": "领导18:57发在吗，我的工牌先替我下班。评论区接一句工牌背面的疯话。",
                "hashtags": ["#发疯文学"],
            },
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert result["required_revision"] is False


def test_reflector_retries_when_required_hashtag_is_missing() -> None:
    node = build_reflector_node(max_attempts=2)

    result = node(
        {
            "attempt_count": 0,
            "reflection_prompt": "检查标签",
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "draft_content": {
                "body": "领导18:57发在吗，我的工牌先替我下班。评论区接一句工牌背面的疯话。",
                "hashtags": ["#打工人"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert result["required_revision"] is True
    assert "#发疯文学" in result["reflection_feedback"]


def test_reflector_retries_when_forbidden_hashtag_is_present() -> None:
    node = build_reflector_node(max_attempts=2)

    result = node(
        {
            "attempt_count": 0,
            "reflection_prompt": "检查标签",
            "reflection_rules": {
                "required_hashtag": "#热点观察",
                "hashtags_must_not_include_any": ["#Reddit"],
            },
            "draft_content": {
                "body": "AI 工具越多，越需要守住判断边界。评论区想问问，你现在更像是在用 AI，还是在照看 AI？",
                "hashtags": ["#热点观察", "#Reddit"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert result["required_revision"] is True
    assert "hashtags_must_not_include_any" in result["reflection_feedback"]


def test_reflector_retries_generic_fengkuang_title_without_comment_mechanics() -> None:
    node = build_reflector_node(max_attempts=2)

    result = node(
        {
            "attempt_count": 0,
            "reflection_prompt": "检查互动机制",
            "reflection_rules": {
                "required_hashtag": "#发疯文学",
                "title_must_not_equal_any": ["打工人日常", "打工人地铁生存实录"],
                "body_must_include_any": ["评论区", "接一句", "可复制"],
                "body_must_not_include_any": ["精神病", "心理医生", "医院", "治疗", "用药"],
            },
            "draft_content": {
                "title": "打工人地铁生存实录",
                "body": "周一早高峰地铁通勤，今天又被挤到灵魂出窍。",
                "hashtags": ["#发疯文学"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert result["required_revision"] is True
    assert "title_must_not_equal_any" in result["reflection_feedback"]
    assert "body_must_include_any" in result["reflection_feedback"]


def test_reflector_enforces_explicit_must_include_phrase_for_compatibility() -> None:
    node = build_reflector_node(max_attempts=2)

    result = node(
        {
            "attempt_count": 0,
            "reflection_prompt": "检查关键词",
            "reflection_rules": {
                "required_hashtag": "#苏轼",
                "must_include_phrase": "苏轼",
            },
            "draft_content": {
                "body": "今天借宋词聊一个普通人的情绪拐弯。",
                "hashtags": ["#苏轼"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert result["required_revision"] is True
    assert "苏轼" in result["reflection_feedback"]


def test_reflector_retries_when_content_quality_judge_fails() -> None:
    backend = FakeJudgeBackend(
        json.dumps(
            {
                "score": 0.31,
                "labels": {
                    "hook_specificity": "pass",
                    "save_trigger": "fail",
                    "comment_trigger": "pass",
                    "platform_native_format": "warn",
                    "persona_fit": "pass",
                    "safety": "pass",
                },
                "reason": "save trigger is too thin",
                "rewrite_hint": "Add a reusable line users would save.",
            }
        )
    )
    node = build_reflector_node(
        max_attempts=2,
        content_quality_judge=build_content_quality_judge_gate(backend),
    )

    result = node(
        {
            "attempt_count": 1,
            "account_id": "acct-fk-local",
            "platform": "xiaohongshu",
            "playbook_id": "fengkuang_daily_post",
            "reflection_rules": {"required_hashtag": "#发疯文学"},
            "reflection_prompt": "检查互动质量",
            "draft_content": {
                "title": "领导18:57发「在吗」那一秒",
                "image_text": "我的工牌先替我发疯",
                "body": "我想把这句写在工牌背面：收到，但灵魂已下班。评论区接一句工牌背面的疯话。",
                "hashtags": ["#发疯文学"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert result["required_revision"] is True
    assert "content quality judge failed" in result["reflection_feedback"]
    assert "Add a reusable line users would save." in result["reflection_feedback"]
    assert result["content_quality_eval"]["status"] == "failed"
    assert result["content_quality_eval"]["gate_level"] == "required"
    assert backend.prompts


def test_reflector_retries_then_fails_news_draft_with_unsupported_hands_on_claims() -> None:
    node = build_reflector_node(
        max_attempts=1,
        ai_tech_draft_gate=_bound_ai_gate(_news_brief_contract()),
    )
    state = {
        "reflection_rules": {},
        "reflection_prompt": "按证据合同改写",
        "draft_content": {
            "title": "今天的 AI 更新",
            "image_text": "别只看参数",
            "body": "我实测后发现，这次速度提升明显。",
            "hashtags": ["#AI资讯"],
        },
    }

    retry = node({**state, "attempt_count": 0})
    failed = node({**state, "attempt_count": 1})

    assert retry["reflection_decision"] == "retry"
    assert "我实测" in retry["reflection_feedback"]
    assert "速度提升明显" in retry["reflection_feedback"]
    assert failed["reflection_decision"] == "fail"


def test_reflector_retries_hands_on_draft_without_recorded_task_output_and_limitation() -> None:
    node = build_reflector_node(
        max_attempts=2,
        ai_tech_draft_gate=_bound_ai_gate(_hands_on_contract()),
    )

    result = node(
        {
            "attempt_count": 0,
            "reflection_rules": {},
            "reflection_prompt": "按实测记录补全",
            "draft_content": {
                "title": "这个工具我试了",
                "body": "我这次只想分享结论。",
                "hashtags": ["#AI资讯"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert "recorded task" in result["reflection_feedback"]
    assert "recorded observed output" in result["reflection_feedback"]
    assert "recorded limitation" in result["reflection_feedback"]


def test_reflector_retries_fact_translation_with_unsupported_hands_on_claims() -> None:
    node = build_reflector_node(
        max_attempts=2,
        ai_tech_draft_gate=_bound_ai_gate(_fact_translation_contract()),
    )

    result = node(
        {
            "attempt_count": 0,
            "reflection_rules": {},
            "reflection_prompt": "按事实翻译合同改写",
            "draft_content": {
                "title": "AI 更新怎么看",
                "body": "我实测后觉得这次速度提升明显。",
                "hashtags": ["#AI资讯"],
            },
        }
    )

    assert result["reflection_decision"] == "retry"
    assert "我实测" in result["reflection_feedback"]
    assert "速度提升明显" in result["reflection_feedback"]


def test_reflector_finalizes_hands_on_draft_with_recorded_test_evidence() -> None:
    node = build_reflector_node(
        max_attempts=2,
        ai_tech_draft_gate=_bound_ai_gate(_hands_on_contract()),
    )
    topic = "Kimi K3 更新"
    product = "Kimi"
    version = "K3"
    task = "把一段会议纪要整理成待办清单"
    observed_output = "输出了 5 条带负责人的待办"
    limitation = "长文本仍会漏掉上下文"

    result = node(
        {
            "attempt_count": 0,
            "reflection_rules": {},
            "draft_content": {
                "title": "这个工具我试了",
                "body": (
                    f"{topic}：2026-07-22，我用 {product} {version} 来{task}。"
                    f"输入是一段脱敏会议纪要，{observed_output}。但{limitation}。"
                ),
                "hashtags": ["#AI资讯"],
            },
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert result["required_revision"] is False


def test_reflector_uses_the_catalog_gate_instead_of_ordinary_psychology_rules() -> None:
    contract = _psychology_learning_contract(lesson_id="control_and_next_step")
    node = build_reflector_node(
        max_attempts=2,
        psychology_learning_draft_gate=_bound_psychology_learning_gate(contract),
    )

    result = node(
        {
            "attempt_count": 0,
            "reflection_rules": {
                # These are the ordinary psychology-post requirements.  This
                # catalog lesson intentionally uses its own approved exercise
                # and comment handoff instead.
                "body_must_include_any": ["反刍思维", "低控制感", "边界"],
                "body_must_include_save_trigger_any": ["三栏", "边界句"],
            },
            "draft_content": render_psychology_learning_draft(contract),
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert result["required_revision"] is False


def test_reflector_does_not_retry_a_catalog_lesson_on_open_post_judge_feedback() -> None:
    contract = _psychology_learning_contract(lesson_id="facts_and_stories")
    judge_calls: list[dict[str, object]] = []

    def ordinary_post_judge(
        state: object,
        draft: dict[str, object],
    ) -> dict[str, object]:
        judge_calls.append({"state": state, "draft": draft})
        return {"status": "failed", "reason": "open-post preference"}

    node = build_reflector_node(
        max_attempts=2,
        content_quality_judge=ordinary_post_judge,
        psychology_learning_draft_gate=_bound_psychology_learning_gate(contract),
    )

    result = node(
        {
            "attempt_count": 0,
            "reflection_rules": {},
            "draft_content": render_psychology_learning_draft(contract),
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert not judge_calls


def test_reflector_preserves_a_valid_ordinary_psychology_carousel() -> None:
    draft = _ordinary_psychology_carousel_draft()
    node = build_reflector_node(
        max_attempts=2,
        psychology_carousel_draft_gate=_ordinary_psychology_carousel_gate,
    )

    result = node(
        {
            "attempt_count": 1,
            "reflection_rules": {"required_hashtag": "#心理学"},
            "draft_content": draft,
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert result["final_content"] == draft


def test_reflector_keeps_learning_exact_gate_authoritative_over_ordinary_gate() -> None:
    contract = _psychology_learning_contract(lesson_id="facts_and_stories")
    ordinary_gate_calls: list[dict[str, object]] = []

    def reject_as_ordinary(
        _state: dict[str, object],
        draft: dict[str, object],
    ) -> list[str]:
        ordinary_gate_calls.append(draft)
        return ["ordinary carousel policy must not replace catalog exactness"]

    node = build_reflector_node(
        max_attempts=2,
        psychology_carousel_draft_gate=reject_as_ordinary,
        psychology_learning_draft_gate=_bound_psychology_learning_gate(contract),
    )

    result = node(
        {
            "attempt_count": 1,
            "reflection_rules": {},
            "draft_content": render_psychology_learning_draft(contract),
        }
    )

    assert result["reflection_decision"] == "finalize"
    assert ordinary_gate_calls == []
