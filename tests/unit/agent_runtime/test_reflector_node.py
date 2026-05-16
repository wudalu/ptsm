from __future__ import annotations

from ptsm.agent_runtime.nodes.reflector import build_reflector_node


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
