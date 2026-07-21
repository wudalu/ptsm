"""Pydantic schemas for LLM structured output."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LLMTopicSignal(BaseModel):
    """A topic found spreading across multiple platforms."""

    topic: str = Field(description="Normalized topic name shared across platforms")
    platforms: list[str] = Field(description="Platforms where this topic appears")
    velocity: str = Field(
        description=(
            "Use unknown for a single scan; temporal velocity is not inferable "
            "without time-series evidence"
        )
    )
    discussion_value: str = Field(
        description="Why this topic is likely to generate comments, 1-2 sentences in Chinese"
    )
    mechanism: str = Field(
        default="",
        description="Which cognitive hijack mechanism this topic triggers (from lens 1), e.g. 悬念型/反常识型/身份共鸣型",
    )
    archetype: str = Field(
        default="",
        description="Which Jung archetype this topic activates (from lens 2), e.g. 英雄/叛逆者/智者",
    )
    cluster_id: str = Field(
        default="",
        description="Optional supplied event cluster id used as evidence support",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Optional supplied evidence ids supporting this signal",
    )


class LLMAngle(BaseModel):
    """A recommended content angle."""

    vertical: str = Field(description="Which vertical this angle belongs to")
    angle: str = Field(description="Concrete angle description in Chinese, no placeholders")
    why: str = Field(description="Why this angle would trigger discussion, 1-2 sentences in Chinese")
    hook_mechanism: str = Field(
        default="",
        description="Which cognitive mechanism this angle leverages to hook readers (from lens 1)",
    )
    cluster_id: str = Field(
        default="",
        description="Required when known: one supplied event cluster id supporting the angle",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Optional supplied evidence ids; they must belong to the selected cluster",
    )


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
    cluster_ids: list[str] = Field(
        default_factory=list,
        description="Optional supplied event cluster ids represented by this vertical",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Optional supplied evidence ids represented by this vertical",
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
