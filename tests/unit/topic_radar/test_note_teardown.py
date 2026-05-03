from __future__ import annotations

import pytest

from topic_radar.analysis.note_teardown import (
    teardown,
    analyze_comment_signals,
    _classify_hook,
    _classify_body,
    _detect_triggers,
    CommentSignals,
    TeardownResult,
)
from topic_radar.platforms.xiaohongshu import FeedDetail, Comment


class TestHookClassification:
    def test_suspense_hook(self):
        hook, conf = _classify_hook("你绝对想不到这个方法有多简单")
        assert hook == "悬念"
        assert conf > 0.9

    def test_counterintuitive_hook(self):
        hook, conf = _classify_hook("其实你根本不需要周末休息")
        assert hook == "反常识"
        assert conf > 0.8

    def test_emotional_resonance_hook(self):
        hook, conf = _classify_hook("打工人终于下班了")
        assert hook == "情绪共鸣"
        assert conf > 0.8

    def test_identity_hook(self):
        hook, conf = _classify_hook("30岁独居女孩的日常生活")
        assert hook == "身份认同"
        assert conf > 0.8

    def test_benefit_driven_hook(self):
        hook, conf = _classify_hook("保姆级教程一篇搞懂AI写作")
        assert hook == "利益驱动"
        assert conf > 0.8

    def test_fallback_for_plain_title(self):
        hook, conf = _classify_hook("今天天气真好")
        assert hook == "信息直述"
        assert conf == 0.3


class TestBodyClassification:
    def test_question_opening(self):
        assert _classify_body("你是不是也有这样的困扰？每天加班到很晚") == "问题导入式"

    def test_tutorial_style(self):
        assert _classify_body("首先准备这些材料：一块旧布，一瓶胶水，然后") == "教程式"

    def test_story_style(self):
        assert _classify_body("昨天下午五点，老板突然又扔来一个新需求") == "故事式"

    def test_question_driven(self):
        assert _classify_body("为什么会这样？到底怎么回事？我们今天来聊聊") == "问题驱动式"

    def test_default_opinion(self):
        assert _classify_body("我觉得这个方法挺好的可以试试") == "观点陈述式"

    def test_short_post(self):
        assert _classify_body("  ") == "短帖"


class TestTriggerDetection:
    def test_voting_trigger(self):
        triggers = _detect_triggers("好用的方法", "你们会选择哪一种呢？")
        assert "投票式提问" in triggers

    def test_experience_exchange(self):
        triggers = _detect_triggers("求助", "有没有好用的推荐？怎么办")
        assert "经验交换" in triggers

    def test_hook_ending_trigger(self):
        triggers = _detect_triggers("标题", "最后想问一下你们呢？")
        assert "留白邀请" in triggers


class TestCommentSignals:
    def test_empty_comments(self):
        sigs = analyze_comment_signals([])
        assert sigs.question_density == 0.0
        assert sigs.is_real_discussion is False

    def test_question_density(self):
        comments = [
            Comment(author="a", content="怎么做？"),
            Comment(author="b", content="写得很好"),
            Comment(author="c", content="这个在哪里买吗？"),
            Comment(author="d", content="不错不错"),
        ]
        sigs = analyze_comment_signals(comments)
        assert sigs.question_density == 0.5

    def test_real_discussion_detection(self):
        comments = [Comment(author=f"user{i}", content=f"好喜欢这个做法，能出教程吗？") for i in range(8)]
        sigs = analyze_comment_signals(comments)
        assert sigs.is_real_discussion is True


class TestEndToEndTeardown:
    def test_full_teardown(self):
        detail = FeedDetail(
            feed_id="abc123",
            title="你绝对不知道的低成本治愈方法",
            body="最近发现一个超棒的方法，你们平时会怎么放松呢？",
            author="test_user",
            likes=500,
            comments_count=100,
            comments=[
                Comment(author="u1", content="好治愈，求教程！"),
                Comment(author="u2", content="真的有用吗？"),
                Comment(author="u3", content="什么时候出下一期？"),
                Comment(author="u4", content="已经在试了，效果很好！"),
                Comment(author="u5", content="这是什么原理呢？"),
            ],
            tags=["治愈", "修复系手作"],
        )
        result = teardown(detail)
        assert result.hook_type == "悬念"
        assert "留白邀请" in result.engagement_triggers
        assert result.trigger_confidence > 0.25
        assert result.comment_signals is not None
        assert result.comment_signals.is_real_discussion is True
