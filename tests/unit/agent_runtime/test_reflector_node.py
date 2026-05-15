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
