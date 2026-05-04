"""Tests for LLM output schema validation."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from topic_radar.analysis.schemas import (
    LLMTopicSignal,
    LLMVertical,
    LLMAngle,
    LLMScanOutput,
)


VALID_SCAN_OUTPUT = {
    "scan_summary": "本次扫描覆盖微博和抖音，核心发现是体育赛事和AI职场话题跨平台扩散明显。",
    "cross_platform_signals": [
        {
            "topic": "国羽汤杯卫冕",
            "platforms": ["weibo", "douyin"],
            "velocity": "accelerating",
            "discussion_value": "民族荣誉感+赛事结果自带讨论，评论区会分化为庆祝派和复盘派",
        }
    ],
    "discovered_verticals": [
        {
            "name": "体育赛事情绪",
            "keywords": ["国乒", "汤杯", "卫冕", "爆冷", "男团"],
            "confidence": 0.85,
            "discussion_density": "high",
            "sample_topics": ["国乒男团2比3瑞典", "国羽汤杯卫冕"],
            "suggested_angles": [
                "从国乒爆冷看'期待越大失望越大'——体育为什么成了情绪出口",
                "汤杯卫冕现场：当所有人都不看好你，你拿什么证明自己",
            ],
            "comment_themes": ["阵营争论", "情绪释放", "技术复盘"],
        },
        {
            "name": "AI职场焦虑",
            "keywords": ["AI", "裁员", "降薪", "替代", "效率"],
            "confidence": 0.72,
            "discussion_density": "medium",
            "sample_topics": ["湖南广电AI播新闻", "公司引进AI后将员工降薪裁员"],
            "suggested_angles": [
                "当AI开始做你的工作：一个被'优化'的普通人的自述",
            ],
            "comment_themes": ["焦虑共鸣", "职业规划", "吐槽公司"],
        },
    ],
    "recommended_angles": [
        {
            "vertical": "体育赛事情绪",
            "angle": "汤杯卫冕现场：当所有人都不看好你，你拿什么证明自己",
            "why": "逆袭叙事+身份认同，评论区会自发分享'被低估'的个人经历",
        },
    ],
    "noise_topics": ["五一档票房破5亿", "黄灿灿blackpink都没这么累"],
}


class TestLLMScanOutput:
    def test_valid_full_output(self):
        output = LLMScanOutput(**VALID_SCAN_OUTPUT)
        assert len(output.discovered_verticals) == 2
        assert output.discovered_verticals[0].name == "体育赛事情绪"
        assert len(output.recommended_angles) == 1
        assert len(output.noise_topics) == 2

    def test_minimal_valid_output(self):
        output = LLMScanOutput(scan_summary="空扫描，无数据。")
        assert output.cross_platform_signals == []
        assert output.discovered_verticals == []

    def test_confidence_range_enforced(self):
        data = {
            "name": "测试",
            "keywords": ["a"],
            "confidence": 1.5,
            "discussion_density": "high",
            "sample_topics": [],
            "suggested_angles": [],
            "comment_themes": [],
        }
        with pytest.raises(ValidationError):
            LLMVertical(**data)

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            LLMScanOutput()  # missing scan_summary

    def test_extra_fields_ignored(self):
        data = {**VALID_SCAN_OUTPUT, "extra_field": "should be ignored"}
        output = LLMScanOutput(**data)
        assert output.scan_summary

    def test_serializes_to_dict(self):
        output = LLMScanOutput(**VALID_SCAN_OUTPUT)
        d = output.model_dump()
        assert d["scan_summary"]
        assert len(d["discovered_verticals"]) == 2

    def test_roundtrip_json(self):
        output = LLMScanOutput(**VALID_SCAN_OUTPUT)
        js = output.model_dump_json(ensure_ascii=False)
        parsed = LLMScanOutput(**json.loads(js))
        assert parsed.scan_summary == output.scan_summary
