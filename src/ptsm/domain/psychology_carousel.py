"""Strict, text-only carousel contracts for modern psychology posts."""

from __future__ import annotations

import re
import unicodedata
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
_ASCII_DOMAIN_LABEL_PATTERN = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_ASCII_DOMAIN_TLD_PATTERN = (
    r"(?:[a-z]{2,63}|xn--[a-z0-9](?:[a-z0-9-]{0,57}[a-z0-9])?)"
)
_HAN_DOMAIN_LABEL_PATTERN = r"[\u3400-\u9fff]{1,63}"
_IDN_LEADING_LABEL_PATTERN = (
    rf"(?:[a-z0-9][a-z0-9-]{{0,61}}[a-z0-9]|{_HAN_DOMAIN_LABEL_PATTERN})"
)
_LOCATOR_PATTERN = re.compile(
    rf"(?:[a-z][a-z0-9+.-]*\s*:\s*/\s*/|//|www\s*\.|"
    rf"(?:source|来源|來源|參考|参考|ref(?:erence)?|author|link|doi|arxiv|pmid|isbn|issn)\s*[:：]|"
    rf"doi\s*[:：]?\s*10\.)",
    flags=re.IGNORECASE,
)
_RAW_DOMAIN_PATTERN = re.compile(
    rf"(?<![a-z0-9_\-\u3400-\u9fff])(?:"
    rf"(?:(?:{_ASCII_DOMAIN_LABEL_PATTERN}|{_HAN_DOMAIN_LABEL_PATTERN})\.)+"
    rf"{_ASCII_DOMAIN_TLD_PATTERN}|"
    rf"(?:{_IDN_LEADING_LABEL_PATTERN}\.)+{_HAN_DOMAIN_LABEL_PATTERN}"
    rf")(?![a-z0-9_\-\u3400-\u9fff])",
    flags=re.IGNORECASE,
)
_OBFUSCATED_DOT_DOMAIN_PATTERN = re.compile(
    rf"(?<![a-z0-9_\-\u3400-\u9fff]){_ASCII_DOMAIN_LABEL_PATTERN}\s*"
    rf"(?:\[\s*dot\s*\]|\bdot\b)\s*{_ASCII_DOMAIN_TLD_PATTERN}"
    rf"(?![a-z0-9_\-\u3400-\u9fff])",
    flags=re.IGNORECASE,
)
_UNSAFE_HAN_MARKERS = (
    "抑郁症",
    "抑鬱症",
    "憂鬱症",
    "焦虑症",
    "焦慮症",
    "强迫症",
    "強迫症",
    "双相",
    "雙相",
    "人格障碍",
    "人格障礙",
    "诊断",
    "診斷",
    "确诊",
    "確診",
    "治愈",
    "治癒",
    "治好",
    "根治",
    "治疗",
    "治療",
    "疗法",
    "療法",
    "疗效",
    "療效",
    "保证",
    "保證",
    "药物",
    "藥物",
    "用药",
    "用藥",
    "停药",
    "停藥",
    "服药",
    "服藥",
    "吃药",
    "吃藥",
    "药量",
    "藥量",
    "处方",
    "處方",
    "自测",
    "自測",
    "量表",
)
_UNSAFE_ASCII_MARKERS = (
    "adhd",
    "ptsd",
    "diagnos",
    "treat",
    "therapy",
    "therapist",
    "psychotherapy",
    "cure",
    "guarantee",
    "medication",
    "medicine",
    "meds",
    "prescription",
    "dosage",
)
_INSTRUCTION_LEAKAGE_HAN_MARKERS = (
    "忽略之前",
    "忽略以上",
    "系统提示",
    "系統提示",
    "开发者消息",
    "開發者消息",
    "输出系统",
    "輸出系統",
    "内部指令",
    "內部指令",
    "隐藏提示",
    "隱藏提示",
)
_INSTRUCTION_LEAKAGE_ASCII_MARKERS = (
    "ignoreprior",
    "ignoreprevious",
    "ignoreabove",
    "developermessage",
    "developerinstruction",
    "systemprompt",
    "hiddenprompt",
    "revealprompt",
    "internalinstruction",
)
_SECURITY_CONFUSABLE_TRANSLATION = str.maketrans(
    {
        "А": "A",
        "а": "a",
        "В": "B",
        "Е": "E",
        "е": "e",
        "І": "I",
        "і": "i",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "о": "o",
        "Р": "P",
        "р": "p",
        "С": "C",
        "с": "c",
        "Т": "T",
        "Х": "X",
        "х": "x",
        "Υ": "Y",
        "у": "y",
        "Α": "A",
        "Β": "B",
        "Ε": "E",
        "Ι": "I",
        "Κ": "K",
        "Μ": "M",
        "Ν": "N",
        "Ο": "O",
        "Ρ": "P",
        "Τ": "T",
        "Χ": "X",
        "α": "a",
        "β": "b",
        "ε": "e",
        "ι": "i",
        "κ": "k",
        "ο": "o",
        "ρ": "p",
        "τ": "t",
        "χ": "x",
    }
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
        security_text = _security_text(text, field_name=info.field_name)
        if _contains_locator(security_text):
            raise ValueError(f"{info.field_name} must not contain a locator")
        if _contains_instruction_leakage(security_text):
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
    security_text = _security_text(text, field_name=field_name)
    if re.search(r"(?<!#)#[^#\s]", security_text):
        raise ValueError(f"{field_name} must not contain hashtags")
    if _contains_locator(security_text):
        raise ValueError(f"{field_name} must not contain a source locator")
    if _contains_unsafe_psychology_marker(security_text):
        raise ValueError(f"{field_name} contains an unsafe psychology claim")
    if _contains_instruction_leakage(security_text):
        raise ValueError(f"{field_name} contains instruction leakage")
    return text


def _security_text(value: str, *, field_name: str) -> str:
    """Normalize only for safety matching while preserving accepted display copy."""
    normalized = unicodedata.normalize("NFKD", value).translate(
        _SECURITY_CONFUSABLE_TRANSLATION
    )
    if any(
        unicodedata.category(character).startswith("C")
        or unicodedata.category(character) in {"Zl", "Zp"}
        for character in normalized
    ):
        raise ValueError(f"{field_name} contains unsupported control characters")
    return "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("M")
    ).casefold()


def _contains_locator(security_text: str) -> bool:
    return (
        _LOCATOR_PATTERN.search(security_text) is not None
        or _RAW_DOMAIN_PATTERN.search(security_text) is not None
        or _OBFUSCATED_DOT_DOMAIN_PATTERN.search(security_text) is not None
    )


def _contains_unsafe_psychology_marker(security_text: str) -> bool:
    han_text, ascii_text = _marker_skeletons(security_text)
    return any(marker in han_text for marker in _UNSAFE_HAN_MARKERS) or any(
        marker in ascii_text for marker in _UNSAFE_ASCII_MARKERS
    )


def _contains_instruction_leakage(security_text: str) -> bool:
    han_text, ascii_text = _marker_skeletons(security_text)
    return any(
        marker in han_text for marker in _INSTRUCTION_LEAKAGE_HAN_MARKERS
    ) or any(
        marker in ascii_text for marker in _INSTRUCTION_LEAKAGE_ASCII_MARKERS
    ) or bool(
        re.search(
            r"(?:ignore|disregard)[a-z0-9]{0,12}(?:prior|previous|above)"
            r"[a-z0-9]{0,12}(?:rule|instruction)",
            ascii_text,
        )
        or re.search(
            r"(?:print|output|reveal|show)[a-z0-9]{0,12}"
            r"(?:developer|system|hidden|internal)[a-z0-9]{0,12}"
            r"(?:prompt|instruction|message)",
            ascii_text,
        )
    )


def _marker_skeletons(value: str) -> tuple[str, str]:
    return (
        "".join(character for character in value if _is_cjk_han(character)),
        "".join(
            character
            for character in value
            if character.isascii() and character.isalnum()
        ),
    )


def _is_cjk_han(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0x20000 <= codepoint <= 0x2EBEF
        or 0x30000 <= codepoint <= 0x323AF
    )
