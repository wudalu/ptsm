"""Pydantic schemas for LLM structured output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMTopicSignal(BaseModel):
    """A topic found spreading across multiple platforms."""

    topic: str = Field(description="Normalized topic name shared across platforms")
    platforms: list[str] = Field(description="Platforms where this topic appears")
    velocity: str = Field(description="accelerating | steady | fading")
    discussion_value: str = Field(
        description="Why this topic is likely to generate comments, 1-2 sentences in Chinese"
    )


class LLMAngle(BaseModel):
    """A recommended content angle."""

    vertical: str = Field(description="Which vertical this angle belongs to")
    angle: str = Field(description="Concrete angle description in Chinese, no placeholders")
    why: str = Field(description="Why this angle would trigger discussion, 1-2 sentences in Chinese")


class LLMVertical(BaseModel):
    """A discovered content vertical from the data."""

    name: str = Field(description="Vertical name in Chinese, 2-8 chars, descriptive not generic")
    keywords: list[str] = Field(description="Key terms defining this vertical, 3-6 items")
    confidence: float = Field(description="0.0-1.0 confidence this is a real vertical", ge=0, le=1)
    discussion_density: str = Field(description="high | medium | low")
    sample_topics: list[str] = Field(description="2-5 representative topic titles from the data")
    suggested_angles: list[str] = Field(
        description="2-3 concrete content angles in Chinese, no {placeholders}"
    )
    comment_themes: list[str] = Field(
        description="Predicted comment themes, e.g. ['经验交换', '情绪共鸣', '打卡记录']"
    )


class LLMScanOutput(BaseModel):
    """Full LLM analysis output for one scan."""

    scan_summary: str = Field(
        description="1-paragraph summary in Chinese of overall findings and key themes"
    )
    cross_platform_signals: list[LLMTopicSignal] = Field(
        default_factory=list, description="Topics spreading across platforms"
    )
    discovered_verticals: list[LLMVertical] = Field(
        default_factory=list, description="Discovered content verticals, ordered by confidence"
    )
    recommended_angles: list[LLMAngle] = Field(
        default_factory=list, description="Top concrete content angles, max 6"
    )
    noise_topics: list[str] = Field(
        default_factory=list,
        description="Topics that are trending but unlikely to generate valuable discussion",
    )
