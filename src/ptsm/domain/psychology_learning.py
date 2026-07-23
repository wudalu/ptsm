"""Closed runtime curriculum and proposal-only planning contracts.

Unlike time-sensitive AI facts, psychology learning claims must not be supplied
by an operator for each run.  The builtin catalog remains the only runnable
curriculum here.  Custom operator intent can only become a safe, deterministic
proposal; it has no runtime contract, manifest, persistence, or resolver path.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any, Literal, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


PSYCHOLOGY_LEARNING_MODE = "learning_series"
PSYCHOLOGY_LEARNING_CURRICULUM_VERSION = "1"
STARTER_SERIES_ID = "after_work_rumination"
PSYCHOLOGY_LEARNING_PROPOSAL_SCHEMA_VERSION = "1"

_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
_OPAQUE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:-]{0,127}$")
_RAW_LOCATOR_PATTERN = re.compile(
    r"(?:[A-Za-z][A-Za-z0-9+.-]*://|//|www\.|(?:[A-Za-z0-9-]+\.)+(?:com|cn|org|net|io|edu|gov|app|ai|dev|co)(?:[/?#:]|\b))",
    flags=re.IGNORECASE,
)
_UNSAFE_CLAIM_MARKERS = (
    "你就是抑郁症",
    "你就是双相",
    "你就是adhd",
    "人格障碍",
    "治好",
    "治愈",
    "药物",
    "用药",
    "停药",
    "自测",
    "量表",
    "保证",
)
_PROPOSAL_UNSAFE_CLINICAL_MARKERS = (
    "诊断",
    "診斷",
    "确诊",
    "確診",
    "抑郁症",
    "憂鬱症",
    "焦虑症",
    "焦慮症",
    "强迫症",
    "強迫症",
    "双相",
    "雙相",
    "创伤后应激障碍",
    "創傷後應激障礙",
    "創傷後壓力障礙",
    "adhd",
    "人格障碍",
    "人格障礙",
    "精神分裂",
    "治疗",
    "治療",
    "诊疗",
    "診療",
    "医疗",
    "醫療",
    "疗法",
    "療法",
    "诊治",
    "診治",
    "医治",
    "醫治",
    "治好",
    "治愈",
    "治癒",
    "药物",
    "藥物",
    "用药",
    "用藥",
    "停药",
    "停藥",
    "处方",
    "處方",
    "服药",
    "服藥",
    "吃药",
    "吃藥",
    "断药",
    "斷藥",
    "开药",
    "開藥",
    "开方",
    "開方",
    "药方",
    "藥方",
    "配药",
    "配藥",
    "药剂",
    "藥劑",
    "药品",
    "藥品",
    "自测",
    "自測",
    "量表",
    "自杀",
    "自殺",
    "自伤",
    "自傷",
    "轻生",
    "輕生",
    "割腕",
    "伤害自己",
    "傷害自己",
    "自我伤害",
    "自我傷害",
    "自残",
    "自殘",
    "自我残害",
    "自我殘害",
    "伤害自身",
    "傷害自身",
    "自尽",
    "自盡",
    "寻死",
    "尋死",
    "寻短见",
    "尋短見",
    "结束生命",
    "結束生命",
    "了结生命",
    "了結生命",
    "危机",
    "危機",
    "crisis",
    "selfharm",
    "suicide",
    "ptsd",
    "ocd",
    "anxiety disorder",
    "bipolar disorder",
    "schizophrenia",
    "diagnos",
    "treat",
    "therapy",
    "therapist",
    "psychotherapy",
    "counseling",
    "counselling",
    "medication",
    "self-test",
)
_PROPOSAL_HAN_UNSAFE_CLINICAL_MARKERS = tuple(
    marker
    for marker in _PROPOSAL_UNSAFE_CLINICAL_MARKERS
    if not marker.isascii()
)
_PROPOSAL_ASCII_UNSAFE_CLINICAL_MARKERS = tuple(
    re.sub(r"[^a-z0-9]", "", marker)
    for marker in _PROPOSAL_UNSAFE_CLINICAL_MARKERS
    if marker.isascii()
)
_PROPOSAL_ENGLISH_RISK_LEET_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "@": "a",
        "$": "s",
    }
)
_PROPOSAL_OBFUSCATED_PTSD_MARKER = "ptsd"
_PROPOSAL_SOURCE_REFERENCE_PATTERN = re.compile(
    r"(?:source|来源|來源|参考|參考|ref(?:erence)?|author|link|doi)\s*[:：]"
    r"|(?<![a-z])doi[:：]?10\.\d{4,9}/\S+"
    r"|(?:(?:参考|參考)(?:文献|文獻|资料|資料))"
    r"|(?:\bcitation\b|\bbibliograph\w*)",
    flags=re.IGNORECASE,
)
_PROPOSAL_DOMAIN_LABEL_PATTERN = (
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?|[\u3400-\u9fff]{1,63})"
)
_PROPOSAL_DOMAIN_TLD_PATTERN = (
    r"(?:[a-z]{2,63}|xn--[a-z0-9](?:[a-z0-9-]{0,57}[a-z0-9])?|[\u3400-\u9fff]{2,63})"
)
_PROPOSAL_RAW_DOMAIN_PATTERN = re.compile(
    rf"(?<![a-z0-9_\-\u3400-\u9fff])"
    rf"(?:{_PROPOSAL_DOMAIN_LABEL_PATTERN}\.)+"
    rf"{_PROPOSAL_DOMAIN_TLD_PATTERN}"
    rf"(?![a-z0-9_\-\u3400-\u9fff])",
    flags=re.IGNORECASE,
)
_PROPOSAL_OBFUSCATED_DOT_DOMAIN_PATTERN = re.compile(
    rf"(?<![a-z0-9_\-\u3400-\u9fff])"
    rf"{_PROPOSAL_DOMAIN_LABEL_PATTERN}\s*"
    rf"(?:\[\s*dot\s*\]|\bdot\b)\s*"
    rf"{_PROPOSAL_DOMAIN_TLD_PATTERN}"
    rf"(?![a-z0-9_\-\u3400-\u9fff])",
    flags=re.IGNORECASE,
)
_PROPOSAL_SOURCE_STRUCTURAL_ASCII = frozenset(":/?&=#._-@%")
_OBFUSCATED_URL_SCHEME_PATTERN = re.compile(
    r"(?<![a-z0-9])(?P<scheme>https?)(?P<separator>[^a-z0-9]+)",
    flags=re.IGNORECASE,
)
_PROPOSAL_SECURITY_CONFUSABLE_TRANSLATION = str.maketrans(
    {
        # Common Cyrillic/Greek lookalikes for the ASCII letters used by source
        # markers and clinical-risk tokens.  This is only a security skeleton;
        # accepted proposal text keeps its original reader-visible spelling.
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
_INSTRUCTIONAL_STAGE_ORDER: tuple[str, ...] = (
    "notice",
    "understand",
    "practice",
    "apply",
    "review",
    "support",
)
_INSTRUCTIONAL_STAGE_MARKERS: dict[str, tuple[str, ...]] = {
    "notice": ("识别", "觉察", "看见", "观察", "notice", "observe"),
    "understand": ("理解", "区分", "事实", "感受", "understand"),
    "practice": ("练习", "练一练", "尝试", "practice"),
    "apply": ("应用", "行动", "下一步", "apply"),
    "review": ("回顾", "复盘", "总结", "review"),
    "support": ("支持", "求助", "资源", "support"),
}
_INSTRUCTIONAL_STAGE_RATIONALES: dict[str, str] = {
    "notice": "先从识别一个具体时刻开始，降低进入门槛。",
    "understand": "在识别之后补充理解，避免把感受直接当结论。",
    "practice": "再安排一个小练习，方便读者保存后尝试。",
    "apply": "把前面的理解放回一个可完成的行动场景。",
    "review": "在有了前面练习后再回顾，便于看见可保留的线索。",
    "support": "把支持和边界放在后面，避免把系列写成临床判断。",
}
_RAW_PROVENANCE_KEYS = {
    "author",
    "authorname",
    "source",
    "sourceref",
    "sourcerefs",
    "sourcetitle",
    "sourceurl",
    "url",
    "lessonfingerprint",
}
_XHS_POST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_ARTIFACT_RAW_PROVENANCE_KEYS = _RAW_PROVENANCE_KEYS | {
    "author",
    "authorname",
    "headline",
    "rawheadline",
    "rawresponse",
    "rawsourcetitle",
    "rawsourceurl",
    "preflight",
    "platformpayload",
    "posturl",
    "publisherserverurl",
    "serverurl",
    "source",
    "sourceauthor",
    "sourceartifactpath",
    "sourcepath",
    "sourcetitle",
    "sourceurl",
    "sourcerefs",
    "xsectoken",
    "lessonfingerprint",
}
_PSYCHOLOGY_LEARNING_ARTIFACT_ROOT_KEYS = frozenset(
    {
        "account",
        "activated_skill_details",
        "activated_skills",
        "final_content",
        "format_patterns_used",
        "image_generation",
        "playbook_id",
        "platform",
        "post_publish_checks",
        "publish_mode",
        "publish_result",
        "psychology_learning_curriculum_version",
        "psychology_learning_evidence_manifest",
        "psychology_learning_gate",
        "psychology_learning_lesson_id",
        "psychology_learning_lesson_number",
        "psychology_learning_mode",
        "psychology_learning_series_id",
        "run",
        "scene",
        "topic_selection",
        "watermark_removal",
    }
)
_PSYCHOLOGY_LEARNING_ARTIFACT_ALLOWED_FIELDS_BY_PATH = {
    ("account",): frozenset({"account_id", "platform"}),
    ("final_content",): frozenset(
        {"title", "image_text", "body", "hashtags", "image_plan"}
    ),
    ("final_content", "image_plan"): frozenset(
        {
            "backend",
            "style",
            "role",
            "text_density",
            "max_text_units",
            "cover_text_strategy",
            "reason",
            "prompt_focus",
        }
    ),
    ("format_patterns_used",): frozenset({"status"}),
    ("image_generation",): frozenset({"status", "renderer"}),
    ("post_publish_checks",): frozenset(
        {"requested", "browser_opened", "publish_status", "status_result"}
    ),
    ("post_publish_checks", "status_result"): frozenset({"status", "source"}),
    ("publish_result",): frozenset({"status"}),
    ("psychology_learning_gate",): frozenset(
        {"status", "series_id", "lesson_id", "validator", "validator_version", "errors"}
    ),
    ("run",): frozenset({"run_id"}),
    ("watermark_removal",): frozenset({"status"}),
}
_PSYCHOLOGY_LEARNING_ARTIFACT_EMPTY_LIST_FIELDS = frozenset(
    {"activated_skills", "activated_skill_details"}
)
_PSYCHOLOGY_LEARNING_ACCOUNT_ID_PATTERN = re.compile(
    r"^acct-[a-z0-9]+(?:-[a-z0-9]+)*$"
)
_PSYCHOLOGY_LEARNING_RUN_ID_PATTERN = re.compile(
    r"^\d{8}T\d{6}Z-[0-9a-f]{8}$"
)
_PSYCHOLOGY_LEARNING_PUBLISH_STATUSES = frozenset(
    {"dry_run", "published", "login_required", "error", "unknown"}
)
_PSYCHOLOGY_LEARNING_POST_PUBLISH_STATUSES = frozenset(
    {
        "skipped",
        "unknown",
        "published",
        "published_visible",
        "published_search_verified",
        "manual_check_required",
        "login_required",
        "unsupported",
        "error",
        "failed",
    }
)


class _FrozenDomainModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        str_strip_whitespace=True,
    )


def _require_identifier(value: str, *, field_name: str) -> str:
    if not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be a stable lowercase identifier")
    return value


def _require_opaque_reference(value: str, *, field_name: str) -> str:
    if not _OPAQUE_REFERENCE_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} must be an opaque reference")
    if _RAW_LOCATOR_PATTERN.search(value):
        raise ValueError(f"{field_name} must not contain a locator")
    return value


def _require_drafting_safe_text(value: str, *, field_name: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    if _RAW_LOCATOR_PATTERN.search(text) or "source:" in text.lower():
        raise ValueError(f"{field_name} must not contain a source locator or reference")
    return text


def _string_list(value: object) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


class PsychologyLearningLesson(_FrozenDomainModel):
    """One human-reviewed lesson; this type is only populated by the catalog."""

    series_id: str
    series_title: str
    curriculum_version: str
    lesson_id: str
    lesson_number: int = Field(ge=1, le=99)
    lesson_title: str
    post_title: str
    cover_text: str
    scene_anchor: str
    concept_label: str
    learning_goal: str
    approved_explanation: str
    applicability: str
    micro_exercise: str
    scope_limit: str
    professional_boundary: str
    comment_prompt: str
    source_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    lesson_fingerprint: str

    @field_validator("series_id", "lesson_id")
    @classmethod
    def _validate_identifiers(cls, value: str, info: Any) -> str:
        return _require_identifier(value, field_name=info.field_name)

    @field_validator("curriculum_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]{0,3}", value):
            raise ValueError("curriculum_version must be a positive integer string")
        return value

    @field_validator(
        "series_title",
        "lesson_title",
        "post_title",
        "cover_text",
        "scene_anchor",
        "concept_label",
        "learning_goal",
        "approved_explanation",
        "applicability",
        "micro_exercise",
        "scope_limit",
        "professional_boundary",
        "comment_prompt",
    )
    @classmethod
    def _validate_safe_lesson_text(cls, value: str, info: Any) -> str:
        return _require_drafting_safe_text(value, field_name=info.field_name)

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            _require_opaque_reference(item, field_name="source_refs") for item in value
        )

    @field_validator("lesson_fingerprint")
    @classmethod
    def _validate_lesson_fingerprint(cls, value: str) -> str:
        return _require_opaque_reference(value, field_name="lesson_fingerprint")

    @property
    def direction_id(self) -> str:
        return f"psychology_learning_{self.series_id}_{self.lesson_id}"

    @property
    def series_badge(self) -> str:
        return f"《{self.series_title}》第{self.lesson_number}课"

    @property
    def runtime_contract(self) -> dict[str, Any]:
        return parse_psychology_learning_runtime_contract(
            {
                "mode": PSYCHOLOGY_LEARNING_MODE,
                "series_id": self.series_id,
                "series_title": self.series_title,
                "curriculum_version": self.curriculum_version,
                "lesson_id": self.lesson_id,
                "lesson_number": self.lesson_number,
                "direction_id": self.direction_id,
                "series_badge": self.series_badge,
                "lesson_title": self.lesson_title,
                "post_title": self.post_title,
                "cover_text": self.cover_text,
                "scene_anchor": self.scene_anchor,
                "concept_label": self.concept_label,
                "learning_goal": self.learning_goal,
                "approved_explanation": self.approved_explanation,
                "applicability": self.applicability,
                "micro_exercise": self.micro_exercise,
                "scope_limit": self.scope_limit,
                "professional_boundary": self.professional_boundary,
                "comment_prompt": self.comment_prompt,
            }
        )

    @property
    def manifest(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "curriculum_version": self.curriculum_version,
            "lesson_id": self.lesson_id,
            "lesson_number": self.lesson_number,
            "source_refs": list(self.source_refs),
            "lesson_fingerprint": self.lesson_fingerprint,
        }

    @property
    def public_direction(self) -> dict[str, Any]:
        return {
            "id": self.direction_id,
            "name": f"{self.series_badge}：{self.lesson_title}",
            "direction_type": "learning_series_lesson",
            "scene_fit": "catalog_lesson",
            "trend_signal": "心理学学习专题 / 生活化概念练习",
            "viral_hook": "一个具体下班瞬间 + 一张可保存的小练习",
            "why_it_may_work": "课次固定，读者能从具体场景里学一个概念，也能收藏后续接着学。",
            "best_scenes": [self.scene_anchor],
            "content_angle": self.learning_goal,
            "saveable_tool": self.micro_exercise,
            "comment_prompt": self.comment_prompt,
            "avoid": self.scope_limit,
            "format_recommendation": {
                "format_archetype": "note_card",
                "cover_role": "save_tool",
                "body_shape": "micro scene / one approved concept / bounded micro-exercise / natural A-B handoff",
                "visual_evidence_need": "low",
                "avoid_format": ["dense_text_poster", "clinical_self_test"],
            },
            "series_id": self.series_id,
            "curriculum_version": self.curriculum_version,
            "lesson_id": self.lesson_id,
            "lesson_number": self.lesson_number,
        }

    @property
    def roadmap_item(self) -> dict[str, Any]:
        return {
            "series_id": self.series_id,
            "curriculum_version": self.curriculum_version,
            "lesson_id": self.lesson_id,
            "lesson_number": self.lesson_number,
            "lesson_title": self.lesson_title,
            "learning_goal": self.learning_goal,
            "direction_id": self.direction_id,
            "direction_type": "learning_series_lesson",
        }


class _PsychologyLearningRuntimeContract(_FrozenDomainModel):
    mode: Literal["learning_series"]
    series_id: str
    series_title: str
    curriculum_version: str
    lesson_id: str
    lesson_number: int = Field(ge=1, le=99)
    direction_id: str
    series_badge: str
    lesson_title: str
    post_title: str
    cover_text: str
    scene_anchor: str
    concept_label: str
    learning_goal: str
    approved_explanation: str
    applicability: str
    micro_exercise: str
    scope_limit: str
    professional_boundary: str
    comment_prompt: str

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("series_id", "lesson_id")
    @classmethod
    def _validate_identifiers(cls, value: str, info: Any) -> str:
        return _require_identifier(value, field_name=info.field_name)

    @field_validator("curriculum_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]{0,3}", value):
            raise ValueError("curriculum_version must be a positive integer string")
        return value

    @field_validator("direction_id")
    @classmethod
    def _validate_direction_id(cls, value: str) -> str:
        if not value.startswith("psychology_learning_"):
            raise ValueError("direction_id must be a psychology learning direction")
        return _require_drafting_safe_text(value, field_name="direction_id")

    @field_validator(
        "series_title",
        "series_badge",
        "lesson_title",
        "post_title",
        "cover_text",
        "scene_anchor",
        "concept_label",
        "learning_goal",
        "approved_explanation",
        "applicability",
        "micro_exercise",
        "scope_limit",
        "professional_boundary",
        "comment_prompt",
    )
    @classmethod
    def _validate_safe_text(cls, value: str, info: Any) -> str:
        return _require_drafting_safe_text(value, field_name=info.field_name)

    @field_validator("post_title")
    @classmethod
    def _validate_post_title_length(cls, value: str) -> str:
        if len(value) > 22:
            raise ValueError("post_title must not exceed 22 characters")
        return value

    @model_validator(mode="after")
    def _validate_identity(self) -> "_PsychologyLearningRuntimeContract":
        expected_direction = f"psychology_learning_{self.series_id}_{self.lesson_id}"
        if self.direction_id != expected_direction:
            raise ValueError("direction_id does not match series_id and lesson_id")
        expected_badge = f"《{self.series_title}》第{self.lesson_number}课"
        if self.series_badge != expected_badge:
            raise ValueError("series_badge does not match series title and lesson number")
        return self

    @property
    def normalized(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PsychologyLearningEvidenceManifest(_FrozenDomainModel):
    """Opaque audit receipt for one catalog lesson, never drafting context."""

    series_id: str
    curriculum_version: str
    lesson_id: str
    lesson_number: int = Field(ge=1, le=99)
    source_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    lesson_fingerprint: str

    @field_validator("series_id", "lesson_id")
    @classmethod
    def _validate_identifiers(cls, value: str, info: Any) -> str:
        return _require_identifier(value, field_name=info.field_name)

    @field_validator("curriculum_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if not re.fullmatch(r"[1-9][0-9]{0,3}", value):
            raise ValueError("curriculum_version must be a positive integer string")
        return value

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            _require_opaque_reference(item, field_name="source_refs") for item in value
        )

    @field_validator("lesson_fingerprint")
    @classmethod
    def _validate_lesson_fingerprint(cls, value: str) -> str:
        return _require_opaque_reference(value, field_name="lesson_fingerprint")


class PsychologyLearningBundle(_FrozenDomainModel):
    """A selected catalog lesson and the parent series roadmap."""

    lesson: PsychologyLearningLesson
    lessons: tuple[PsychologyLearningLesson, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_series(self) -> "PsychologyLearningBundle":
        identities = {(item.lesson_number, item.lesson_id) for item in self.lessons}
        if len(identities) != len(self.lessons):
            raise ValueError("learning series lessons must be unique")
        if any(item.series_id != self.lesson.series_id for item in self.lessons):
            raise ValueError("all lessons must belong to the selected series")
        if self.lesson not in self.lessons:
            raise ValueError("selected lesson must exist in the series roadmap")
        return self

    @property
    def mode(self) -> str:
        return PSYCHOLOGY_LEARNING_MODE

    @property
    def series_id(self) -> str:
        return self.lesson.series_id

    @property
    def lesson_id(self) -> str:
        return self.lesson.lesson_id

    @property
    def lesson_number(self) -> int:
        return self.lesson.lesson_number

    @property
    def direction_id(self) -> str:
        return self.lesson.direction_id

    @property
    def runtime_contract(self) -> dict[str, Any]:
        return self.lesson.runtime_contract

    @property
    def manifest(self) -> dict[str, Any]:
        return self.lesson.manifest

    @property
    def public_direction(self) -> dict[str, Any]:
        return self.lesson.public_direction

    @property
    def roadmap(self) -> tuple[dict[str, Any], ...]:
        return tuple(item.roadmap_item for item in self.lessons)


class PsychologyLearningOutlineItem(_FrozenDomainModel):
    """Safe operator intent for one proposed lesson, not lesson content."""

    id: str | None = None
    title: str
    goal: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("id")
    @classmethod
    def _validate_optional_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_identifier(value, field_name="outline id")

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="outline title",
            min_length=2,
            max_length=60,
        )

    @field_validator("goal")
    @classmethod
    def _validate_optional_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_safe_proposal_text(
            value,
            field_name="outline goal",
            min_length=2,
            max_length=120,
        )


class PsychologyLearningSeriesPlanIntent(_FrozenDomainModel):
    """Only the safe operator input accepted by proposal planning."""

    topic: str
    outline: tuple[PsychologyLearningOutlineItem, ...] | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="topic",
            min_length=2,
            max_length=60,
        )

    @model_validator(mode="after")
    def _validate_outline(self) -> "PsychologyLearningSeriesPlanIntent":
        if self.outline is None:
            return self
        if not 2 <= len(self.outline) <= 6:
            raise ValueError("outline must contain between 2 and 6 lessons")
        lesson_ids = tuple(_outline_lesson_id(item) for item in self.outline)
        if len(set(lesson_ids)) != len(lesson_ids):
            raise ValueError("outline lesson ids must be unique")
        return self


class PsychologyLearningProposedLesson(_FrozenDomainModel):
    """Canonical identity for a proposed lesson, deliberately not runnable."""

    lesson_id: str
    lesson_number: int = Field(ge=1, le=6)
    title: str
    goal: str | None = None
    instructional_stage: Literal[
        "notice", "understand", "practice", "apply", "review", "support"
    ]

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("lesson_id")
    @classmethod
    def _validate_lesson_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="lesson_id")

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="proposed lesson title",
            min_length=2,
            max_length=60,
        )

    @field_validator("goal")
    @classmethod
    def _validate_optional_goal(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_safe_proposal_text(
            value,
            field_name="proposed lesson goal",
            min_length=2,
            max_length=120,
        )


class PsychologyLearningProposedCatalog(_FrozenDomainModel):
    """A reviewable custom catalog candidate with no resolver/runtime path."""

    catalog_kind: Literal["proposal_only"] = "proposal_only"
    runnable: Literal[False] = False
    series_id: str
    series_title: str
    lessons: tuple[PsychologyLearningProposedLesson, ...] = Field(
        min_length=2,
        max_length=6,
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("series_id")
    @classmethod
    def _validate_series_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="series_id")

    @field_validator("series_title")
    @classmethod
    def _validate_series_title(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="series_title",
            min_length=2,
            max_length=64,
        )

    @model_validator(mode="after")
    def _validate_canonical_identities(self) -> "PsychologyLearningProposedCatalog":
        lesson_ids = tuple(lesson.lesson_id for lesson in self.lessons)
        if len(set(lesson_ids)) != len(lesson_ids):
            raise ValueError("proposed catalog lesson ids must be unique")
        lesson_numbers = tuple(lesson.lesson_number for lesson in self.lessons)
        if lesson_numbers != tuple(range(1, len(self.lessons) + 1)):
            raise ValueError("proposed catalog lesson numbers must be canonical and contiguous")
        return self


class PsychologyLearningPublicationPlanItem(_FrozenDomainModel):
    """One recommended posting slot; never changes canonical lesson identity."""

    publication_order: int = Field(ge=1, le=6)
    lesson_id: str
    canonical_lesson_number: int = Field(ge=1, le=6)
    instructional_stage: Literal[
        "notice", "understand", "practice", "apply", "review", "support"
    ]
    rationale: str

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("lesson_id")
    @classmethod
    def _validate_lesson_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="publication plan lesson_id")

    @field_validator("rationale")
    @classmethod
    def _validate_rationale(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="publication plan rationale",
            min_length=2,
            max_length=120,
        )


class PsychologyLearningPublicationPlan(_FrozenDomainModel):
    """Deterministic recommendation separate from the catalog lesson order."""

    plan_version: Literal["1"] = "1"
    items: tuple[PsychologyLearningPublicationPlanItem, ...] = Field(
        min_length=2,
        max_length=6,
    )

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @model_validator(mode="after")
    def _validate_plan_shape(self) -> "PsychologyLearningPublicationPlan":
        if len({item.lesson_id for item in self.items}) != len(self.items):
            raise ValueError("publication plan lesson ids must be unique")
        if len({item.canonical_lesson_number for item in self.items}) != len(self.items):
            raise ValueError("publication plan canonical lesson numbers must be unique")
        orders = tuple(item.publication_order for item in self.items)
        if orders != tuple(range(1, len(self.items) + 1)):
            raise ValueError("publication plan orders must be contiguous")
        return self


class PsychologyLearningProposalReview(_FrozenDomainModel):
    """Fixed review receipt for a safe proposal awaiting explicit confirmation."""

    status: Literal["safe_for_confirmation_review"] = "safe_for_confirmation_review"
    structural_checks: tuple[str, ...] = Field(min_length=3, max_length=3)
    safety_checks: tuple[str, ...] = Field(min_length=3, max_length=3)

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @model_validator(mode="after")
    def _validate_fixed_checks(self) -> "PsychologyLearningProposalReview":
        expected_structural = (
            "lesson-count-within-bounds",
            "lesson-ids-unique",
            "canonical-identity-separate-from-publication-order",
        )
        expected_safety = (
            "no-raw-provenance",
            "no-clinical-or-crisis-content",
            "proposal-only",
        )
        if self.structural_checks != expected_structural:
            raise ValueError("proposal structural checks must use the safe fixed receipt")
        if self.safety_checks != expected_safety:
            raise ValueError("proposal safety checks must use the safe fixed receipt")
        return self


class PsychologyLearningSeriesProposal(_FrozenDomainModel):
    """Immutable, deterministic proposal that cannot be selected for a run."""

    proposal_schema_version: Literal["1"] = PSYCHOLOGY_LEARNING_PROPOSAL_SCHEMA_VERSION
    proposal_id: str
    proposal_fingerprint: str
    topic: str
    catalog: PsychologyLearningProposedCatalog
    review: PsychologyLearningProposalReview
    publication_plan: PsychologyLearningPublicationPlan

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_provenance(value)
        return value

    @field_validator("proposal_id")
    @classmethod
    def _validate_proposal_id(cls, value: str) -> str:
        return _require_identifier(value, field_name="proposal_id")

    @field_validator("proposal_fingerprint")
    @classmethod
    def _validate_proposal_fingerprint(cls, value: str) -> str:
        return _require_opaque_reference(value, field_name="proposal_fingerprint")

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        return _require_safe_proposal_text(
            value,
            field_name="proposal topic",
            min_length=2,
            max_length=60,
        )

    @model_validator(mode="after")
    def _validate_catalog_and_plan(self) -> "PsychologyLearningSeriesProposal":
        catalog_lessons = {lesson.lesson_id: lesson for lesson in self.catalog.lessons}
        if set(catalog_lessons) != {
            item.lesson_id for item in self.publication_plan.items
        }:
            raise ValueError("publication plan must cover every proposed lesson exactly once")
        for item in self.publication_plan.items:
            lesson = catalog_lessons[item.lesson_id]
            if item.canonical_lesson_number != lesson.lesson_number:
                raise ValueError("publication plan must preserve canonical lesson numbers")
            if item.instructional_stage != lesson.instructional_stage:
                raise ValueError("publication plan stage must match the proposed lesson")
        if self.catalog.series_id != _series_id_candidate(self.topic):
            raise ValueError("proposal series_id candidate does not match the topic")
        if self.catalog.series_title != f"{self.topic}学习系列":
            raise ValueError("proposal series_title candidate does not match the topic")
        digest = _stable_proposal_digest(
            _proposal_material(
                topic=self.topic,
                catalog=self.catalog,
                publication_plan=self.publication_plan,
            )
        )
        if self.proposal_id != f"proposal_{digest[:24]}":
            raise ValueError("proposal_id does not match the proposal payload")
        if self.proposal_fingerprint != f"proposal:{digest}":
            raise ValueError("proposal_fingerprint does not match the proposal payload")
        return self

    @property
    def series_id_candidate(self) -> str:
        """Return the candidate identifier without exposing a runnable resolver."""
        return self.catalog.series_id

    @property
    def series_title_candidate(self) -> str:
        return self.catalog.series_title

    @property
    def lesson_proposals(self) -> tuple[PsychologyLearningProposedLesson, ...]:
        return self.catalog.lessons


def build_psychology_learning_series_proposal(
    intent: PsychologyLearningSeriesPlanIntent | Mapping[str, Any],
) -> PsychologyLearningSeriesProposal:
    """Build a pure, deterministic proposal from sanitized operator intent.

    The return value intentionally has no conversion to ``PsychologyLearningLesson``
    and no reader-visible runtime contract.  Later confirmation can choose how to
    create an immutable catalog revision; this function only offers a reviewable
    plan.
    """
    normalized_intent = PsychologyLearningSeriesPlanIntent.model_validate(intent)
    outline = normalized_intent.outline or _synthesized_outline(normalized_intent.topic)
    proposed_lessons = tuple(
        PsychologyLearningProposedLesson(
            lesson_id=_outline_lesson_id(item),
            lesson_number=index,
            title=item.title,
            goal=item.goal,
            instructional_stage=_infer_instructional_stage(item),
        )
        for index, item in enumerate(outline, start=1)
    )
    catalog = PsychologyLearningProposedCatalog(
        series_id=_series_id_candidate(normalized_intent.topic),
        series_title=f"{normalized_intent.topic}学习系列",
        lessons=proposed_lessons,
    )
    ordered_lessons = tuple(
        sorted(
            catalog.lessons,
            key=lambda lesson: (
                _INSTRUCTIONAL_STAGE_ORDER.index(lesson.instructional_stage),
                lesson.lesson_number,
            ),
        )
    )
    publication_plan = PsychologyLearningPublicationPlan(
        items=tuple(
            PsychologyLearningPublicationPlanItem(
                publication_order=index,
                lesson_id=lesson.lesson_id,
                canonical_lesson_number=lesson.lesson_number,
                instructional_stage=lesson.instructional_stage,
                rationale=_INSTRUCTIONAL_STAGE_RATIONALES[lesson.instructional_stage],
            )
            for index, lesson in enumerate(ordered_lessons, start=1)
        )
    )
    material = _proposal_material(
        topic=normalized_intent.topic,
        catalog=catalog,
        publication_plan=publication_plan,
    )
    digest = _stable_proposal_digest(material)
    return PsychologyLearningSeriesProposal(
        proposal_id=f"proposal_{digest[:24]}",
        proposal_fingerprint=f"proposal:{digest}",
        topic=normalized_intent.topic,
        catalog=catalog,
        review=PsychologyLearningProposalReview(
            structural_checks=(
                "lesson-count-within-bounds",
                "lesson-ids-unique",
                "canonical-identity-separate-from-publication-order",
            ),
            safety_checks=(
                "no-raw-provenance",
                "no-clinical-or-crisis-content",
                "proposal-only",
            ),
        ),
        publication_plan=publication_plan,
    )


def _require_safe_proposal_text(
    value: str,
    *,
    field_name: str,
    min_length: int,
    max_length: int,
) -> str:
    text = value.strip()
    if not min_length <= len(text) <= max_length:
        raise ValueError(
            f"{field_name} must contain between {min_length} and {max_length} characters"
        )
    security_text = _proposal_security_text(text)
    if not security_text:
        raise ValueError(
            f"{field_name} must contain between {min_length} and {max_length} characters"
        )
    if _contains_unsafe_proposal_clinical_marker(
        text,
        security_text,
        max_length=max_length,
    ):
        raise ValueError(f"{field_name} must not contain unsafe clinical or crisis content")
    if _contains_proposal_source_shape(text):
        raise ValueError(f"{field_name} must not contain a source locator or reference")
    if _contains_unexpected_proposal_alphabetic_script(text):
        raise ValueError(f"{field_name} must not contain unsupported alphabetic script")
    return text


def _proposal_security_text(value: str) -> str:
    """Return a security-only text skeleton without changing display text.

    NFKC closes full-width bypasses; a bounded confusable map covers common
    cross-script lookalikes; and category-C/category-Z characters are removed
    before matching.  This catches invisible and Unicode-space separators such
    as ``自\\u200b伤`` and ``self\\u00a0harm`` without rewriting accepted proposal
    text that later appears in a review surface.
    """
    normalized = _proposal_security_unicode_text(value)
    return "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith(("C", "Z"))
    ).casefold()


def _proposal_source_security_text(value: str) -> str:
    """Normalize source/reference forms while preserving ASCII URL structure."""
    normalized = _normalize_obfuscated_url_schemes(value)
    return "".join(
        character
        for character in normalized
        if _is_cjk_han(character)
        or (
            character.isascii()
            and (character.isalnum() or character in _PROPOSAL_SOURCE_STRUCTURAL_ASCII)
        )
    )


def _proposal_source_label_text(value: str) -> str:
    """Collapse Unicode separators around source/ref labels while keeping colons."""
    normalized = _proposal_security_unicode_text(value)
    return "".join(
        character
        for character in normalized
        if _is_cjk_han(character)
        or character == ":"
        or (character.isascii() and character.isalnum())
    )


def _proposal_source_shape_text(value: str) -> str:
    """Keep visible source-shape separators while removing invisible controls."""
    normalized = _proposal_security_unicode_text(value)
    return "".join(
        character
        for character in normalized
        if not unicodedata.category(character).startswith("C")
    )


def _proposal_security_unicode_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).translate(
        _PROPOSAL_SECURITY_CONFUSABLE_TRANSLATION
    ).casefold()


def _normalize_obfuscated_url_schemes(value: str) -> str:
    """Restore non-whitespace Unicode punctuation used to hide ``http(s)://``."""
    normalized = _proposal_security_unicode_text(value)

    def _replace(match: re.Match[str]) -> str:
        separator = match.group("separator")
        if _is_split_source_domain_separator(separator):
            return f"{match.group('scheme')}://"
        return match.group(0)

    return _OBFUSCATED_URL_SCHEME_PATTERN.sub(_replace, normalized)


def _contains_split_source_domain_shape(value: str) -> bool:
    """Detect an obfuscated domain boundary without a suffix allowlist.

    A gap with a Unicode punctuation, symbol, mark, or ignorable character
    between ASCII label tokens is treated as a hidden domain boundary, even
    when ordinary whitespace surrounds it. This deliberately rejects values
    such as ``note · card`` as a safe proposal-input tradeoff; pure ASCII-space
    prose is not treated as a source locator.
    """
    normalized = _normalize_obfuscated_url_schemes(value)
    runs = tuple(re.finditer(r"[a-z0-9]+", normalized))
    for host, suffix in zip(runs, runs[1:]):
        gap = normalized[host.end() : suffix.start()]
        if not _is_split_source_domain_separator(gap):
            continue
        if not re.fullmatch(r"[a-z]{2,63}", suffix.group()):
            continue
        if _is_source_domain_label(host.group()):
            return True
    return False


def _contains_proposal_source_shape(value: str) -> bool:
    """Detect direct and obfuscated source shapes in proposal-only text.

    This detector intentionally treats bare Unicode/IDNA domains and explicit
    ``dot``/``[dot]`` spellings as provenance.  Proposal display text remains
    unchanged; the normalized values below are used only for the safety gate.
    """
    source_security_text = _proposal_source_security_text(value)
    source_label_text = _proposal_source_label_text(value)
    source_shape_text = _proposal_source_shape_text(value)
    return bool(
        _contains_source_reference(source_security_text)
        or _PROPOSAL_SOURCE_REFERENCE_PATTERN.search(source_security_text)
        or _PROPOSAL_SOURCE_REFERENCE_PATTERN.search(source_label_text)
        or _PROPOSAL_RAW_DOMAIN_PATTERN.search(source_security_text)
        or _PROPOSAL_OBFUSCATED_DOT_DOMAIN_PATTERN.search(source_shape_text)
        or _contains_split_source_domain_shape(value)
    )


def _is_split_source_domain_separator(value: str) -> bool:
    non_whitespace_characters = tuple(
        character for character in value if not character.isspace()
    )
    if not non_whitespace_characters or not any(
        not character.isascii() for character in non_whitespace_characters
    ):
        return False
    return all(
        character in ":/"
        or (
            not character.isascii()
            and unicodedata.category(character).startswith(("C", "M", "S", "P"))
        )
        for character in non_whitespace_characters
    )


def _is_source_domain_label(value: str) -> bool:
    return bool(
        re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", value)
    )


def _contains_unsafe_proposal_clinical_marker(
    text: str,
    security_text: str,
    *,
    max_length: int,
) -> bool:
    """Check proposal-only clinical and crisis markers without rewriting text.

    Han markers use a separate Han-only skeleton, so punctuation, ASCII, and
    format characters cannot split a Chinese danger marker. English
    ``self...harm`` and obfuscated ``PTSD`` use ordered risk-only checks that
    cannot bridge beyond the proposal field's display-length limit.
    """
    han_marker_text = _proposal_han_marker_skeleton(text)
    ascii_marker_text = _proposal_ascii_marker_skeleton(security_text)
    english_marker_text = _proposal_security_unicode_text(text)
    return (
        any(
            marker in han_marker_text
            for marker in _PROPOSAL_HAN_UNSAFE_CLINICAL_MARKERS
        )
        or any(
            marker in ascii_marker_text
            for marker in _PROPOSAL_ASCII_UNSAFE_CLINICAL_MARKERS
        )
        or _contains_ordered_english_marker(
            english_marker_text,
            prefix="self",
            suffix="harm",
            max_length=max_length,
        )
        or _contains_obfuscated_ptsd_marker(
            english_marker_text,
            max_length=max_length,
        )
    )


def _proposal_han_marker_skeleton(value: str) -> str:
    """Return only Han characters for Chinese danger-marker detection."""
    return "".join(
        character
        for character in _proposal_security_unicode_text(value)
        if _is_cjk_han(character)
    )


def _proposal_ascii_marker_skeleton(security_text: str) -> str:
    """Return ASCII alphanumerics for non-Han marker checks."""
    return "".join(
        character
        for character in security_text
        if character.isascii() and character.isalnum()
    )


def _contains_ordered_english_marker(
    value: str,
    *,
    prefix: str,
    suffix: str,
    max_length: int,
) -> bool:
    """Match an ordered English risk marker within one bounded proposal field."""
    max_bridge_length = max(0, max_length - len(prefix) - len(suffix))
    pattern = re.compile(
        rf"(?<![a-z0-9]){re.escape(prefix)}"
        rf"(?s:.{{0,{max_bridge_length}}}?){re.escape(suffix)}(?![a-z0-9])"
    )
    risk_text = value.translate(_PROPOSAL_ENGLISH_RISK_LEET_TRANSLATION)
    return bool(pattern.search(risk_text))


def _contains_obfuscated_ptsd_marker(value: str, *, max_length: int) -> bool:
    """Detect a leet or letter-inserted PTSD token without spanning prose."""
    risk_text = value.translate(_PROPOSAL_ENGLISH_RISK_LEET_TRANSLATION)
    return any(
        len(token) <= max_length
        and token.startswith(_PROPOSAL_OBFUSCATED_PTSD_MARKER[0])
        and token.endswith(_PROPOSAL_OBFUSCATED_PTSD_MARKER[-1])
        and _is_ordered_subsequence(_PROPOSAL_OBFUSCATED_PTSD_MARKER, token)
        for token in re.findall(r"[a-z0-9]+", risk_text)
    )


def _is_ordered_subsequence(marker: str, value: str) -> bool:
    marker_index = 0
    for character in value:
        if character == marker[marker_index]:
            marker_index += 1
            if marker_index == len(marker):
                return True
    return False


def _contains_unexpected_proposal_alphabetic_script(value: str) -> bool:
    """Reject alphabetic scripts outside the product's Chinese/ASCII boundary."""
    normalized = unicodedata.normalize("NFKC", value)
    return any(
        character.isalpha()
        and not (character.isascii() or _is_cjk_han(character))
        for character in normalized
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


def _normalized_security_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", _proposal_security_text(str(value)))


def _outline_lesson_id(item: PsychologyLearningOutlineItem) -> str:
    if item.id is not None:
        return item.id
    digest = hashlib.sha256(item.title.casefold().encode("utf-8")).hexdigest()[:16]
    return f"lesson_{digest}"


def _series_id_candidate(topic: str) -> str:
    digest = hashlib.sha256(topic.casefold().encode("utf-8")).hexdigest()[:16]
    return f"custom_psychology_{digest}"


def _infer_instructional_stage(item: PsychologyLearningOutlineItem) -> Literal[
    "notice", "understand", "practice", "apply", "review", "support"
]:
    text = " ".join(part for part in (item.title, item.goal) if part).casefold()
    for stage in _INSTRUCTIONAL_STAGE_ORDER:
        if any(marker in text for marker in _INSTRUCTIONAL_STAGE_MARKERS[stage]):
            return stage  # type: ignore[return-value]
    return "apply"


def _synthesized_outline(topic: str) -> tuple[PsychologyLearningOutlineItem, ...]:
    return (
        PsychologyLearningOutlineItem(
            id="notice_pattern",
            title="先识别出现的时刻",
            goal=f"记录{topic}最容易出现的一个具体时刻。",
        ),
        PsychologyLearningOutlineItem(
            id="understand_context",
            title="理解感受和事实",
            goal="把可确认的信息和自己的感受分开写下来。",
        ),
        PsychologyLearningOutlineItem(
            id="practice_next_step",
            title="练习一个小步骤",
            goal="选一个十分钟内可以完成的小动作。",
        ),
        PsychologyLearningOutlineItem(
            id="review_support",
            title="回顾并安排支持",
            goal="回顾有效的小动作，并为需要支持的时刻留出选择。",
        ),
    )


def _stable_proposal_digest(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _proposal_material(
    *,
    topic: str,
    catalog: PsychologyLearningProposedCatalog,
    publication_plan: PsychologyLearningPublicationPlan,
) -> dict[str, Any]:
    return {
        "proposal_schema_version": PSYCHOLOGY_LEARNING_PROPOSAL_SCHEMA_VERSION,
        "topic": topic,
        "catalog": catalog.model_dump(mode="json"),
        "publication_plan": publication_plan.model_dump(mode="json"),
    }


def _lesson(
    *,
    lesson_id: str,
    lesson_number: int,
    lesson_title: str,
    post_title: str,
    cover_text: str,
    scene_anchor: str,
    concept_label: str,
    learning_goal: str,
    approved_explanation: str,
    applicability: str,
    micro_exercise: str,
    scope_limit: str,
    comment_prompt: str,
    source_refs: tuple[str, ...],
) -> PsychologyLearningLesson:
    return PsychologyLearningLesson(
        series_id=STARTER_SERIES_ID,
        series_title="下班后脑子停不下来",
        curriculum_version=PSYCHOLOGY_LEARNING_CURRICULUM_VERSION,
        lesson_id=lesson_id,
        lesson_number=lesson_number,
        lesson_title=lesson_title,
        post_title=post_title,
        cover_text=cover_text,
        scene_anchor=scene_anchor,
        concept_label=concept_label,
        learning_goal=learning_goal,
        approved_explanation=approved_explanation,
        applicability=applicability,
        micro_exercise=micro_exercise,
        scope_limit=scope_limit,
        professional_boundary="如果这种状态持续影响睡眠、工作或生活，专业帮助比继续硬扛更重要。",
        comment_prompt=comment_prompt,
        source_refs=source_refs,
        lesson_fingerprint=f"lesson:{STARTER_SERIES_ID}:{lesson_id}:v1",
    )


_STARTER_SERIES: tuple[PsychologyLearningLesson, ...] = (
    _lesson(
        lesson_id="notice_the_loop",
        lesson_number=1,
        lesson_title="先认出重复回放",
        post_title="下班路上又在回放那句话",
        cover_text="先别急着替自己判错",
        scene_anchor="下班路上又把会议里那句话重播了一遍",
        concept_label="反刍思维",
        learning_goal="今天只学会一件事：分辨自己是在复盘，还是在重复回放。",
        approved_explanation="反刍思维会让同一段不舒服的画面反复回来，却不一定把你带到下一步。",
        applicability="它适合用在下班后、睡前或消息发出后那种停不下来的脑内回放。",
        micro_exercise="打开备忘录写三栏：发生了什么、我脑中补了什么、下一步只做哪一句。",
        scope_limit="它不是给自己下结论的工具，只是把一段反复回放先放到桌面上。",
        comment_prompt="你是哪派：A.回家路上继续想 B.洗澡时又想起来？",
        source_refs=("source:apa-rumination-2023", "source:cci-rumination-plan-2026"),
    ),
    _lesson(
        lesson_id="facts_and_stories",
        lesson_number=2,
        lesson_title="把事实和脑补分开",
        post_title="“收到”之后，我又开始猜了",
        cover_text="先分事实，再分脑补",
        scene_anchor="同事只回了一个“收到”，我已经在猜他是不是不高兴",
        concept_label="事实与脑补",
        learning_goal="今天练的不是压住想法，而是先把可核对的事和脑中补全的故事分开。",
        approved_explanation="事实通常能被复述，脑补常常是在替沉默补一个最坏的解释。",
        applicability="它适合用在消息没回、语气变短、会议后反复猜别人意思的时刻。",
        micro_exercise="在备忘录写两行：事实是____；我补的故事是____；先不急着把第二行当结论。",
        scope_limit="它不负责判断谁对谁错，只帮你把不确定感从事实里拆出来。",
        comment_prompt="你最常补哪一种故事：A.他生气了 B.我做错了？",
        source_refs=("source:apa-rumination-2023", "source:cci-rumination-plan-2026"),
    ),
    _lesson(
        lesson_id="control_and_next_step",
        lesson_number=3,
        lesson_title="只留一个可控下一步",
        post_title="会前脑补十种翻车怎么办",
        cover_text="只留一个可控下一步",
        scene_anchor="明天的会还没开始，我已经在脑内排练了十种翻车",
        concept_label="可控与不可控",
        learning_goal="今天试着把大脑里的整面墙，缩成一件自己现在能做的小事。",
        approved_explanation="不确定的部分不一定能靠多想解决，但下一步可以写得更小、更具体。",
        applicability="它适合用在周日晚、会前、等回复时那种越想越想把一切控制住的时刻。",
        micro_exercise="写两列：我现在控制不了什么；我能在十分钟内做的一步是什么。",
        scope_limit="它不是让你忽略现实难题，只是不把所有结果都扛在今晚的脑子里。",
        comment_prompt="你今晚最想缩小的一件事是____。",
        source_refs=("source:cci-rumination-plan-2026",),
    ),
    _lesson(
        lesson_id="leave_work_signal",
        lesson_number=4,
        lesson_title="给身体一个下班信号",
        post_title="18:57 的“在吗”又来了",
        cover_text="先给身体一个下班信号",
        scene_anchor="领导18:57发来一句“在吗”，身体先被拉回了工位",
        concept_label="状态切换",
        learning_goal="今天不追求立刻放松，只练习给身体一个从工作回到生活的信号。",
        approved_explanation="一条工作消息会把注意力拉回待命状态，先认出这个切换，比逼自己马上平静更实际。",
        applicability="它适合用在下班后收到工作消息、回家还像坐在工位上的时刻。",
        micro_exercise="做一个三步收口：判断紧急度、写下回复时间、慢慢松开肩颈十秒。",
        scope_limit="它不替代必要沟通，也不鼓励消失；重点是把回应和待命分开。",
        comment_prompt="你是哪派：A.秒回 B.先写明天再回 C.先看紧急度？",
        source_refs=("source:cci-rumination-plan-2026",),
    ),
    _lesson(
        lesson_id="close_the_replay",
        lesson_number=5,
        lesson_title="给回放一个收尾动作",
        post_title="洗完澡还在复盘那句话",
        cover_text="给回放一个收尾动作",
        scene_anchor="洗完澡躺下，那句说错的话又在脑子里开始第二轮",
        concept_label="行动收口",
        learning_goal="今天练习把“我还要再想想”换成一个小到能完成的收尾动作。",
        approved_explanation="当脑内回放没有出口时，给它一件可完成的小事，比继续追问原因更容易停在当下。",
        applicability="它适合用在睡前、洗澡后或已经想了很久却没有新信息的时候。",
        micro_exercise="写一句收尾：这件事我明天先做____；今晚不再替它开第二场会。",
        scope_limit="它不要求你强行停止想法，只给反复回放留一个暂时的出口。",
        comment_prompt="今晚你想给哪件事写一句“先到这里”？",
        source_refs=("source:cci-rumination-plan-2026",),
    ),
    _lesson(
        lesson_id="support_boundary",
        lesson_number=6,
        lesson_title="知道什么时候别只靠一张卡",
        post_title="反复回放拖了好多天时",
        cover_text="一张卡不该扛全部",
        scene_anchor="不是今天一件事，而是很多天都被同一种回放拖住",
        concept_label="求助边界",
        learning_goal="最后一课只记住一条：自我练习有边界，持续受影响时可以找人一起处理。",
        approved_explanation="一张卡片适合帮你停一下，但它不该承担持续痛苦、功能受损或危机时的全部支持。",
        applicability="它适合用在反复回放已经影响睡眠、工作、学习或日常关系的时候。",
        micro_exercise="写下一个支持名单：可以聊的人、可以预约的专业资源、今晚先做的一步。",
        scope_limit="它不替你判断任何诊断，也不把求助写成失败。",
        comment_prompt="你愿意先把哪一种支持写进名单：A.朋友 B.专业资源 C.休息安排？",
        source_refs=("source:cci-rumination-plan-2026",),
    ),
)


def resolve_psychology_learning_selection(
    *,
    series_id: str,
    lesson_id: str,
    curriculum_version: str | None = None,
) -> PsychologyLearningBundle:
    """Resolve explicit identifiers to one approved catalog lesson."""
    _require_identifier(series_id, field_name="series_id")
    _require_identifier(lesson_id, field_name="lesson_id")
    lessons = _series_lessons(series_id)
    if curriculum_version is not None and curriculum_version != PSYCHOLOGY_LEARNING_CURRICULUM_VERSION:
        raise ValueError("unsupported psychology learning curriculum version")
    for lesson in lessons:
        if lesson.lesson_id == lesson_id:
            return PsychologyLearningBundle(lesson=lesson, lessons=lessons)
    raise ValueError("unknown psychology learning lesson_id for the selected series")


def list_psychology_learning_series(*, series_id: str) -> tuple[PsychologyLearningLesson, ...]:
    """Return a catalog series for safe guide-post roadmap rendering."""
    _require_identifier(series_id, field_name="series_id")
    return _series_lessons(series_id)


def parse_psychology_learning_runtime_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    """Reparse and normalize the only lesson data allowed into runtime state."""
    return _PsychologyLearningRuntimeContract.model_validate(value).normalized


def validate_psychology_learning_draft_contract(
    contract: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> list[str]:
    """Return deterministic violations for a reader-visible lesson draft.

    Learning-series copy is deliberately rendered from a reviewed catalog
    template.  Requiring exact approved slots—not merely their presence—keeps
    an otherwise plausible extra psychological assertion from becoming reader
    visible through a custom or hosted drafting backend.
    """
    try:
        normalized = parse_psychology_learning_runtime_contract(contract)
    except (TypeError, ValidationError):
        return ["invalid psychology learning contract"]

    expected = render_psychology_learning_draft(normalized)
    title = str(draft.get("title") or "").strip()
    image_text = str(draft.get("image_text") or "").strip()
    body = str(draft.get("body") or "").strip()
    hashtags = _string_list(draft.get("hashtags"))
    errors: list[str] = []
    if not title or not image_text or not body:
        errors.append("draft must include title, image_text, and body")
        return errors
    if len(title) > 22:
        errors.append("title exceeds 22 characters")
    if not 200 <= len(body) <= 380:
        errors.append("body must stay within 200-380 characters for learning_series")
    if normalized["concept_label"] in title:
        errors.append("title must not reveal the lesson concept")
    for field_name in (
        "series_badge",
        "concept_label",
        "learning_goal",
        "approved_explanation",
        "applicability",
        "micro_exercise",
        "scope_limit",
        "professional_boundary",
        "comment_prompt",
    ):
        if normalized[field_name] not in body:
            errors.append(f"missing approved {field_name}")
    if "#心理学" not in hashtags or "#心理学学习" not in hashtags:
        errors.append("learning_series hashtags must include #心理学 and #心理学学习")
    visible_text = "\n".join([title, image_text, body, " ".join(hashtags)])
    if _contains_source_reference(visible_text):
        errors.append("source reference leakage in reader-visible draft")
    unsafe = [marker for marker in _UNSAFE_CLAIM_MARKERS if marker in visible_text.lower()]
    if unsafe:
        errors.append("unsafe psychology claim: " + ", ".join(unsafe))
    if dict(draft) != expected:
        errors.append("draft must match the controlled lesson template")
    return errors


def render_psychology_learning_draft(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Render the only reader-visible draft shape approved for a lesson.

    This is intentionally a catalog-derived renderer rather than a prompt
    suggestion.  It gives every backend the same compact, four-beat Xiaohongshu
    post while leaving no free-form space for new psychology claims.
    """
    normalized = parse_psychology_learning_runtime_contract(contract)
    body = "\n".join(
        (
            f"{normalized['scene_anchor']}，我发现自己又想把那一段想出个完美答案。",
            (
                f"{normalized['series_badge']}｜{normalized['lesson_title']}。"
                f"先记住：{normalized['concept_label']}。"
                f"{normalized['learning_goal']}{normalized['approved_explanation']}"
            ),
            (
                f"{normalized['applicability']}\n"
                f"今晚试试：{normalized['micro_exercise']}{normalized['scope_limit']}"
            ),
            f"{normalized['professional_boundary']}\n{normalized['comment_prompt']}",
        )
    )
    return {
        "title": normalized["post_title"],
        "image_text": normalized["cover_text"],
        "body": body,
        "hashtags": ["#心理学", "#心理学学习", "#下班后脑子停不下来"],
        "image_plan": {
            "backend": "local_social_screenshot",
            "style": "iphone_notes",
            "role": "save_tool",
            "text_density": "low",
            "max_text_units": "3",
            "cover_text_strategy": (
                f"封面只放{normalized['cover_text']}和一条已批准的微练习。"
            ),
            "reason": "固定学习卡用低密度记事本截图，方便读者保存。",
            "prompt_focus": "低密度学习卡，不添加任何课程外结论。",
        },
    }


def is_psychology_learning_drafting_safe_text(value: object) -> bool:
    """Return whether a reader-visible string avoids source/provenance leakage."""
    if not isinstance(value, str) or not value.strip():
        return False
    return not _contains_source_reference(value)


def contains_psychology_learning_raw_provenance(
    value: object,
    *,
    _path: tuple[str, ...] = (),
    _artifact_root: Mapping[object, object] | None = None,
    strict_artifact_shape: bool = True,
) -> bool:
    """Detect raw provenance anywhere except the validated opaque manifest.

    Artifacts retain only an opaque catalog manifest for audit.  This scanner is
    shared by the publish backstop and offline evaluator so a custom workflow
    cannot leave a raw URL, author, headline, or source reference in a field
    the reader-visible draft gate does not inspect.
    """
    if isinstance(value, Mapping):
        if _path == ():
            _artifact_root = value
        if strict_artifact_shape:
            allowed_fields = (
                _PSYCHOLOGY_LEARNING_ARTIFACT_ROOT_KEYS
                if _path == ()
                else _PSYCHOLOGY_LEARNING_ARTIFACT_ALLOWED_FIELDS_BY_PATH.get(_path)
            )
            if allowed_fields is not None and any(
                not isinstance(key, str) or key not in allowed_fields for key in value
            ):
                return True
        for key, nested in value.items():
            child_path = (*_path, str(key))
            if (
                strict_artifact_shape
                and _path == ()
                and key in _PSYCHOLOGY_LEARNING_ARTIFACT_EMPTY_LIST_FIELDS
                and nested != []
            ):
                return True
            if key == "topic_selection" and strict_artifact_shape:
                if not _is_valid_psychology_learning_topic_selection_marker(
                    nested,
                    artifact=_artifact_root,
                ):
                    return True
                continue
            if key == "psychology_learning_evidence_manifest":
                try:
                    PsychologyLearningEvidenceManifest.model_validate(nested)
                except ValidationError:
                    return True
                continue
            if strict_artifact_shape and not _is_valid_psychology_learning_artifact_value(
                path=child_path,
                value=nested,
                artifact=_artifact_root,
            ):
                return True
            normalized_key = _normalized_security_key(key)
            if normalized_key in _ARTIFACT_RAW_PROVENANCE_KEYS:
                # Before the application replaces a standard workflow artifact
                # with the closed learning envelope, runtime-context details
                # legitimately declare `source_path: None`: they are generated
                # in memory and have no source file.  A null cannot carry
                # provenance, while a non-empty runtime source path remains
                # rejected below and strict persisted artifacts never retain
                # this field at all.
                if (
                    not strict_artifact_shape
                    and normalized_key == "sourcepath"
                    and nested is None
                ):
                    continue
                if not _is_allowed_artifact_metadata_field(
                    path=child_path,
                    normalized_key=normalized_key,
                    value=nested,
                    container=value,
                ):
                    return True
                continue
            if contains_psychology_learning_raw_provenance(
                nested,
                _path=child_path,
                _artifact_root=_artifact_root,
                strict_artifact_shape=strict_artifact_shape,
            ):
                return True
        return False
    if isinstance(value, (list, tuple)):
        return any(
            contains_psychology_learning_raw_provenance(
                item,
                _path=(*_path, str(index)),
                _artifact_root=_artifact_root,
                strict_artifact_shape=strict_artifact_shape,
            )
            for index, item in enumerate(value)
        )
    return (
        isinstance(value, str)
        and bool(value.strip())
        and not is_psychology_learning_drafting_safe_text(value)
    )


def _is_valid_psychology_learning_artifact_value(
    *,
    path: tuple[str, ...],
    value: object,
    artifact: Mapping[object, object] | None,
) -> bool:
    """Validate the closed operational receipt rather than trusting text tokens.

    A learning artifact may carry a small amount of operational state, but
    publisher, image, and status backends are not catalog authorities.  Every
    retained value is therefore either an application-derived constant, a
    finite status vocabulary, or a local opaque identifier with its own shape.
    """
    if path == ("playbook_id",):
        return value == "modern_psychology_post"
    if path == ("scene",):
        expected_scene = _expected_psychology_learning_artifact_scene(artifact)
        return expected_scene is not None and value == expected_scene
    if path == ("platform",):
        return value == "xiaohongshu"
    if path == ("publish_mode",):
        return value in {"dry-run", "mcp-real"}
    if path == ("account",):
        return isinstance(value, Mapping) and set(value) == {"account_id", "platform"}
    if path == ("account", "account_id"):
        return isinstance(value, str) and bool(
            _PSYCHOLOGY_LEARNING_ACCOUNT_ID_PATTERN.fullmatch(value)
        )
    if path == ("account", "platform"):
        return value == "xiaohongshu"
    if path == ("format_patterns_used",):
        return isinstance(value, Mapping) and value == {"status": "not_used"}
    if path == ("format_patterns_used", "status"):
        return value == "not_used"
    if path == ("publish_result",):
        return value is None or (
            isinstance(value, Mapping) and set(value) == {"status"}
        )
    if path == ("publish_result", "status"):
        return value in _PSYCHOLOGY_LEARNING_PUBLISH_STATUSES
    if path == ("image_generation",):
        return value is None or (
            isinstance(value, Mapping) and set(value) == {"status", "renderer"}
        )
    if path == ("image_generation", "status"):
        return value == "generated"
    if path == ("image_generation", "renderer"):
        return value == "ptsm_local_renderer"
    if path == ("watermark_removal",):
        return value is None or (
            isinstance(value, Mapping) and set(value) == {"status"}
        )
    if path == ("watermark_removal", "status"):
        return value == "skipped"
    if path == ("post_publish_checks",):
        if not isinstance(value, Mapping):
            return False
        required = {"requested", "browser_opened", "publish_status"}
        return required.issubset(value) and set(value).issubset(
            {"requested", "browser_opened", "publish_status", "status_result"}
        )
    if path in {
        ("post_publish_checks", "requested"),
        ("post_publish_checks", "browser_opened"),
    }:
        return isinstance(value, bool)
    if path == ("post_publish_checks", "publish_status"):
        return value in _PSYCHOLOGY_LEARNING_POST_PUBLISH_STATUSES
    if path == ("post_publish_checks", "status_result"):
        return value is None or (
            isinstance(value, Mapping)
            and "status" in value
            and set(value).issubset({"status", "source"})
        )
    if path == ("post_publish_checks", "status_result", "status"):
        return value in _PSYCHOLOGY_LEARNING_POST_PUBLISH_STATUSES
    if path == ("post_publish_checks", "status_result", "source"):
        return value in {"mcp", "mcp_search"}
    if path == ("run",):
        return isinstance(value, Mapping) and set(value) == {"run_id"}
    if path == ("run", "run_id"):
        return isinstance(value, str) and bool(
            _PSYCHOLOGY_LEARNING_RUN_ID_PATTERN.fullmatch(value)
        )
    return True


def _expected_psychology_learning_artifact_scene(
    artifact: Mapping[object, object] | None,
) -> str | None:
    if not isinstance(artifact, Mapping):
        return None
    try:
        bundle = resolve_psychology_learning_selection(
            series_id=str(artifact["psychology_learning_series_id"]),
            lesson_id=str(artifact["psychology_learning_lesson_id"]),
            curriculum_version=str(artifact["psychology_learning_curriculum_version"]),
        )
    except (KeyError, ValueError):
        return None
    return f"心理学学习专题：{bundle.lesson.series_badge}｜{bundle.lesson.lesson_title}"


def _is_allowed_artifact_metadata_field(
    *,
    path: tuple[str, ...],
    normalized_key: str,
    value: object,
    container: Mapping[object, object],
) -> bool:
    """Allow only framework-owned, non-research source metadata fields."""
    if normalized_key == "source":
        if path == ("topic_selection", "source"):
            return value == "psychology-learning-series"
        if path in {
            ("image_generation", "provenance", "source"),
            ("image_generation", "watermark_policy", "source"),
            ("image_generation", "image_plan", "source"),
        }:
            return value in {
                "default",
                "llm_image_plan",
                "manual_override",
                "ptsm_generated_image",
                "ptsm_local_renderer",
            }
        if path == ("post_publish_checks", "status_result", "source"):
            return value in {"mcp", "mcp_search"}
        return False
    if normalized_key == "posturl":
        return _is_canonical_xhs_post_url(
            path=path,
            value=value,
            post_id=container.get("post_id"),
        )
    if normalized_key == "sourcepath":
        return (
            "activated_skill_details" in path
            and _is_safe_local_artifact_path(value, suffix=".md")
        )
    if normalized_key == "sourceartifactpath":
        return (
            path == ("format_patterns_used", "source_artifact_path")
            and _is_safe_local_artifact_path(value, suffix=".json")
        )
    return False


def _is_canonical_xhs_post_url(
    *,
    path: tuple[str, ...],
    value: object,
    post_id: object,
) -> bool:
    if path not in {
        ("publish_result", "post_url"),
        ("post_publish_checks", "status_result", "post_url"),
    }:
        return False
    if not isinstance(post_id, str) or not _XHS_POST_ID_PATTERN.fullmatch(post_id):
        return False
    return value == f"https://www.xiaohongshu.com/explore/{post_id}"


def _is_valid_psychology_learning_topic_selection_marker(
    value: object,
    *,
    artifact: Mapping[object, object] | None = None,
) -> bool:
    if not isinstance(value, Mapping):
        return False
    if set(value) != {"source", "psychology_learning"}:
        return False
    if value.get("source") != "psychology-learning-series":
        return False
    selection = value.get("psychology_learning")
    if not isinstance(selection, Mapping):
        return False
    if set(selection) != {
        "series_id",
        "curriculum_version",
        "lesson_id",
        "lesson_number",
    }:
        return False
    try:
        bundle = resolve_psychology_learning_selection(
            series_id=str(selection["series_id"]),
            lesson_id=str(selection["lesson_id"]),
            curriculum_version=str(selection["curriculum_version"]),
        )
    except (KeyError, ValueError):
        return False
    if selection.get("lesson_number") != bundle.lesson_number:
        return False
    if artifact is None:
        return True
    expected = {
        "series_id": artifact.get("psychology_learning_series_id"),
        "curriculum_version": artifact.get("psychology_learning_curriculum_version"),
        "lesson_id": artifact.get("psychology_learning_lesson_id"),
        "lesson_number": artifact.get("psychology_learning_lesson_number"),
    }
    return selection == expected


def _is_safe_local_artifact_path(value: object, *, suffix: str) -> bool:
    if value is None:
        return True
    if not isinstance(value, str) or not value.strip():
        return False
    text = value.strip()
    return (
        text.endswith(suffix)
        and "/" in text
        and not _contains_source_reference(text)
    )


def _series_lessons(series_id: str) -> tuple[PsychologyLearningLesson, ...]:
    if series_id != STARTER_SERIES_ID:
        raise ValueError("unknown psychology learning series_id")
    return _STARTER_SERIES


def _contains_source_reference(value: str) -> bool:
    normalized = value.lower()
    return bool(_RAW_LOCATOR_PATTERN.search(value) or "source:" in normalized)


def _assert_no_raw_provenance(value: Any) -> None:
    if isinstance(value, Mapping):
        for raw_key, nested in value.items():
            normalized_key = _normalized_security_key(raw_key)
            if normalized_key in _RAW_PROVENANCE_KEYS:
                raise ValueError("runtime psychology learning contract cannot contain provenance")
            _assert_no_raw_provenance(nested)
        return
    if isinstance(value, (list, tuple)):
        for nested in value:
            _assert_no_raw_provenance(nested)
        return
    if isinstance(value, str):
        _require_drafting_safe_text(value, field_name="runtime psychology learning text")
