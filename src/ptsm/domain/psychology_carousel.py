"""Strict, text-only carousel contracts for modern psychology posts."""

from __future__ import annotations

import re
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PSYCHOLOGY_CAROUSEL_STYLE = "psychology_text_card_v1"
PSYCHOLOGY_CAROUSEL_MIN_SLIDES = 4
PSYCHOLOGY_CAROUSEL_MAX_SLIDES = 7

PsychologyCarouselRole = Literal[
    "cover_hook",
    "concrete_scene",
    "light_mechanism",
    "save_tool",
    "scope_boundary",
    "professional_boundary",
    "comment_prompt",
]

_SLIDE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_LOCATOR_PATTERN = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+.-]*://|//|www\.|source\s*[:：]|"
    r"(?:来源|參考|参考|ref(?:erence)?)\s*[:：]|doi\s*[:：]?\s*10\.|"
    r"(?:[A-Za-z0-9-]+\.)+(?:com|cn|org|net|io|edu|gov|app|ai|dev)\b)",
    flags=re.IGNORECASE,
)
_UNSAFE_VISIBLE_MARKERS = (
    "抑郁症",
    "焦虑症",
    "强迫症",
    "双相",
    "adhd",
    "ptsd",
    "人格障碍",
    "诊断",
    "确诊",
    "治愈",
    "治好",
    "根治",
    "治疗",
    "疗法",
    "疗效",
    "保证",
    "药物",
    "用药",
    "停药",
    "服药",
    "吃药",
    "药量",
    "处方",
    "自测",
    "量表",
    "diagnos",
    "medication",
    "prescription",
)
_INSTRUCTION_LEAKAGE_MARKERS = (
    "忽略之前",
    "忽略以上",
    "系统提示",
    "开发者消息",
    "developer message",
    "system prompt",
    "输出系统",
    "内部指令",
)


class _FrozenClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class PsychologyCarouselSlide(_FrozenClosedModel):
    """One bounded semantic page; it contains only text the renderer may draw."""

    slide_id: str
    order: int = Field(ge=1, le=PSYCHOLOGY_CAROUSEL_MAX_SLIDES)
    role: PsychologyCarouselRole
    headline: str = Field(min_length=1, max_length=28)
    body_lines: tuple[str, ...] = Field(default_factory=tuple, max_length=4)

    @field_validator("slide_id")
    @classmethod
    def _validate_slide_id(cls, value: str) -> str:
        if not _SLIDE_ID_PATTERN.fullmatch(value):
            raise ValueError("slide_id must be a stable lowercase identifier")
        return value

    @field_validator("headline")
    @classmethod
    def _validate_headline(cls, value: str) -> str:
        return _require_safe_visible_text(value, field_name="headline", max_length=28)

    @field_validator("body_lines")
    @classmethod
    def _validate_body_lines(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            _require_safe_visible_text(
                line,
                field_name="body_lines",
                max_length=38,
            )
            for line in value
        )

    @model_validator(mode="after")
    def _validate_page_density(self) -> "PsychologyCarouselSlide":
        if self.role == "cover_hook" and len(self.body_lines) > 1:
            raise ValueError("cover_hook permits at most one supporting line")
        if self.role != "cover_hook" and not self.body_lines:
            raise ValueError("inner carousel slides require at least one body line")
        if len(self.headline) + sum(len(line) for line in self.body_lines) > 132:
            raise ValueError("carousel slide exceeds its visible text budget")
        return self


class PsychologyCarouselPlan(_FrozenClosedModel):
    """The only automatic multi-card image plan accepted for psychology posts."""

    backend: Literal["local_social_screenshot"]
    style: Literal["psychology_text_card"]
    role: Literal["text_carousel"]
    text_density: Literal["medium"]
    max_text_units: Literal["4"]
    cover_text_strategy: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=1, max_length=100)
    prompt_focus: str = Field(min_length=1, max_length=100)
    carousel_style: Literal["psychology_text_card_v1"]
    slides: tuple[PsychologyCarouselSlide, ...] = Field(
        min_length=PSYCHOLOGY_CAROUSEL_MIN_SLIDES,
        max_length=PSYCHOLOGY_CAROUSEL_MAX_SLIDES,
    )

    @field_validator("cover_text_strategy", "reason", "prompt_focus")
    @classmethod
    def _validate_internal_copy(cls, value: str, info: Any) -> str:
        text = value.strip()
        if not text:
            raise ValueError(f"{info.field_name} must not be empty")
        if _LOCATOR_PATTERN.search(text):
            raise ValueError(f"{info.field_name} must not contain a locator")
        lowered = text.lower()
        if any(marker in lowered for marker in _INSTRUCTION_LEAKAGE_MARKERS):
            raise ValueError(f"{info.field_name} contains instruction leakage")
        return text

    @model_validator(mode="after")
    def _validate_ordered_set(self) -> "PsychologyCarouselPlan":
        if tuple(slide.order for slide in self.slides) != tuple(
            range(1, len(self.slides) + 1)
        ):
            raise ValueError("carousel slide order must be contiguous and one-based")
        slide_ids = tuple(slide.slide_id for slide in self.slides)
        if len(set(slide_ids)) != len(slide_ids):
            raise ValueError("carousel slide_id values must be unique")
        if self.slides[0].role != "cover_hook":
            raise ValueError("the first carousel slide must be cover_hook")
        return self


def normalize_psychology_carousel_plan(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return one canonical JSON-compatible plan or raise a validation error."""
    return PsychologyCarouselPlan.model_validate(value).model_dump(mode="json")


def _require_safe_visible_text(
    value: str,
    *,
    field_name: str,
    max_length: int,
) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if len(text) > max_length:
        raise ValueError(f"{field_name} exceeds its visible text budget")
    if "\n" in text or "\r" in text:
        raise ValueError(f"{field_name} must be one visible line")
    if "#" in text:
        raise ValueError(f"{field_name} must not contain hashtags")
    if _LOCATOR_PATTERN.search(text):
        raise ValueError(f"{field_name} must not contain a source locator")
    lowered = text.lower()
    if any(marker in lowered for marker in _UNSAFE_VISIBLE_MARKERS):
        raise ValueError(f"{field_name} contains an unsafe psychology claim")
    if any(marker in lowered for marker in _INSTRUCTION_LEAKAGE_MARKERS):
        raise ValueError(f"{field_name} contains instruction leakage")
    return text
