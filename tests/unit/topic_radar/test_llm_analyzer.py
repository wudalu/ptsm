"""Tests for LLM analyzer — prompt construction, JSON extraction, fallback."""

from __future__ import annotations

import pytest

from topic_radar.analysis.llm_analyzer import (
    LLMAnalyzer,
    _build_user_prompt,
    _extract_json,
)
from topic_radar.platforms.weibo import TrendingItem


SAMPLE_ITEMS: dict[str, list[TrendingItem]] = {
    "weibo": [
        TrendingItem(rank=1, title="国乒男团2比3瑞典", hot_score=1174594, platform="weibo"),
        TrendingItem(rank=2, title="2026五一档总票房已破5亿", hot_score=684031, platform="weibo"),
        TrendingItem(rank=3, title="公司引进AI后将员工降薪裁员", hot_score=120000, platform="weibo"),
    ],
}


class TestBuildPrompt:
    def test_renders_platforms_and_topics(self):
        prompt = _build_user_prompt(SAMPLE_ITEMS, "2026-05-04")
        assert "weibo" in prompt
        assert "国乒男团2比3瑞典" in prompt
        assert "2026五一档总票房已破5亿" in prompt
        assert "2026-05-04" in prompt

    def test_includes_output_schema(self):
        prompt = _build_user_prompt(SAMPLE_ITEMS, "2026-05-04")
        assert "scan_summary" in prompt
        assert "cross_platform_signals" in prompt
        assert "discovered_verticals" in prompt

    def test_truncates_at_30_items_per_platform(self):
        many_items = {
            "weibo": [
                TrendingItem(rank=i, title=f"话题{i}", hot_score=100, platform="weibo")
                for i in range(50)
            ]
        }
        prompt = _build_user_prompt(many_items, "2026-05-04")
        assert "话题29" in prompt
        assert "话题30" not in prompt


class TestExtractJson:
    def test_plain_json(self):
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_markdown_code_block(self):
        raw = '```\n{"a": 1}\n```'
        assert _extract_json(raw) == {"a": 1}

    def test_json_code_block(self):
        raw = '```json\n{"a": 1}\n```'
        assert _extract_json(raw) == {"a": 1}

    def test_leading_text_stripped(self):
        raw = '一些解释\n{"a": 1}'
        with pytest.raises(ValueError):
            _extract_json(raw)

    def test_array_rejected(self):
        with pytest.raises(ValueError):
            _extract_json('[1, 2, 3]')


class TestLLMAnalyzer:
    def test_unavailable_without_api_key(self):
        analyzer = LLMAnalyzer(api_key="")
        assert analyzer.available is False
        result, method = analyzer.analyze(SAMPLE_ITEMS, "2026-05-04")
        assert result is None
        assert method == "rules"

    def test_available_with_api_key(self):
        analyzer = LLMAnalyzer(api_key="sk-test")
        assert analyzer.available is True

    def test_returns_rules_on_api_failure(self):
        analyzer = LLMAnalyzer(api_key="sk-invalid", base_url="https://invalid.example.com")
        result, method = analyzer.analyze(SAMPLE_ITEMS, "2026-05-04")
        assert result is None
        assert method == "rules"
