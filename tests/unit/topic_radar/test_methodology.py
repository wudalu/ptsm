"""Tests for the methodology prompt module."""

from __future__ import annotations

from topic_radar.analysis.methodology import META_PROMPT


class TestMETA_PROMPT:
    def test_exists(self):
        assert META_PROMPT

    def test_is_string(self):
        assert isinstance(META_PROMPT, str)

    def test_token_count_within_budget(self):
        """Rough token estimate: CJK chars ~1.5 chars/token, ASCII ~4 chars/token.
        Budget: 600-1000 tokens."""
        cjk = sum(1 for c in META_PROMPT if ord(c) > 0x4E00)
        ascii_ = len(META_PROMPT) - cjk
        estimated_tokens = int(cjk / 1.5 + ascii_ / 4)
        assert 550 <= estimated_tokens <= 1050, f"Estimated tokens: {estimated_tokens}"

    def test_contains_key_frameworks(self):
        """Should reference core frameworks from the methodology."""
        assert "胡塞尔" in META_PROMPT or "意向性" in META_PROMPT
        assert "尼采" in META_PROMPT or "权力意志" in META_PROMPT
        assert "荣格" in META_PROMPT or "原型" in META_PROMPT
        assert "福柯" in META_PROMPT or "话语权力" in META_PROMPT

    def test_contains_archetypes(self):
        assert "英雄" in META_PROMPT
        assert "叛逆者" in META_PROMPT
        assert "智者" in META_PROMPT

    def test_contains_platforms(self):
        assert "小红书" in META_PROMPT
        assert "微博" in META_PROMPT
        assert "抖音" in META_PROMPT

    def test_contains_emotion_dimension(self):
        assert "社交货币" in META_PROMPT or "高唤醒" in META_PROMPT

    def test_no_curly_placeholders(self):
        """Should not contain jinja2/python template placeholders."""
        assert "{" not in META_PROMPT

    def test_focused_on_analysis_not_creation(self):
        """Prompt should be about analyzing discussion value, not writing content."""
        assert "讨论价值" in META_PROMPT or "讨论" in META_PROMPT
