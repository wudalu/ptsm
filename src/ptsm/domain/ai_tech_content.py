"""Evidence-gated domain contract for AI technology content.

The contract deliberately separates operator-authored facts that may enter a
drafting prompt from opaque provenance references retained only for audit.  It
does not collect sources, call agents, or depend on Topic Radar.
"""

from __future__ import annotations

from datetime import date
import re
import unicodedata
from typing import Any, Iterable, Literal, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)


AiTechContentMode = Literal["news_brief", "hands_on", "fact_translation"]

_AI_TECH_CONTENT_MODES = frozenset(("news_brief", "hands_on", "fact_translation"))
_FIRST_PERSON_TEST_MARKERS = (
    "我实测",
    "我试了",
    "我测了",
    "我用了",
    "亲测",
    "实测",
    "跑了一遍",
)
_NON_HANDS_ON_EXPERIENCE_MARKERS = (
    "我",
    "本人",
    "亲自",
    "亲测",
    "实测",
    "试了",
    "试过",
    "测了",
    "跑了",
    "跑过",
    "上手",
    "用过",
    "体验",
    "观察到",
    "昨晚",
    "刚刚",
    "结果很",
    "效果很",
    "很稳",
)
_PERFORMANCE_CLAIM_MARKERS = (
    "速度提升明显",
    "性能提升",
    "性能更强",
    "明显提速",
    "提速",
    "更快",
)

_OPAQUE_REFERENCE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:-]{0,127}$")
_HIERARCHICAL_URI_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])[A-Za-z][A-Za-z0-9+.-]*://[^\s]+",
    flags=re.IGNORECASE,
)
_PROTOCOL_RELATIVE_URI_PATTERN = re.compile(r"(?<![A-Za-z0-9_])//[^\s]+")
_UNC_PATH_PATTERN = re.compile(r"(?<!\\)\\\\[^\s]+")
_NON_HIERARCHICAL_URI_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])"
    r"(?:about|blob|data|javascript|mailto|tel|urn):[^\s]+",
    flags=re.IGNORECASE,
)
# Bare dotted text is ambiguous with APIs such as ``torch.compile``.  Treat
# common public suffixes as domains, and require a URL suffix for every other
# dotted identifier so normal AI technical vocabulary remains usable.
_COMMON_BARE_DOMAIN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+"
    r"(?:ai|app|biz|blog|cc|cloud|cn|co|com|dev|edu|gov|info|io|me|mil|net|"
    r"online|org|pro|site|store|tech|top|tv|uk|us|xyz)"
    r"(?![A-Za-z0-9-])",
    flags=re.IGNORECASE,
)
_DOMAIN_WITH_URL_SUFFIX_PATTERN = re.compile(
    r"(?<![\w-])(?:[\w-]+\.)+(?:[^\W\d_][\w-]{1,62})(?=[/:?#])",
    flags=re.UNICODE,
)
_ASCII_DOMAIN_WITH_UNICODE_SEPARATOR_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?[\u3002\uff61])+"
    r"[A-Za-z]{2,63}(?![A-Za-z0-9-])",
    flags=re.IGNORECASE,
)
_UNICODE_DOMAIN_WITH_UNICODE_SEPARATOR_AND_PATH_PATTERN = re.compile(
    r"(?<![\w-])(?:[\w-]+[\u3002\uff61])+"
    # A natural Chinese sentence such as ``模型发布。开发者工具：`` must
    # not look like a unicode host followed by a URL delimiter.  Preserve
    # detection for an actual path/query/fragment or numeric port instead.
    r"(?:[^\W\d_][\w-]{1,62})(?=(?:/[^\s]*|:\d+(?:/[^\s]*)?|[?#][^\s]*))",
    flags=re.UNICODE,
)
_LOCAL_HOST_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_-])(?:localhost|(?:\d{1,3}\.){3}\d{1,3})(?![A-Za-z0-9_-])",
    flags=re.IGNORECASE,
)
_BRACKETED_IP_LITERAL_PATTERN = re.compile(r"\[[0-9A-Fa-f:.]+\](?::\d+)?(?:/[^\s]*)?")
_ALLOWED_REFERENCE_FIELDS = {
    "sourcerefs",
    "testevidencerefs",
    "evidenceids",
}


class _FrozenDomainModel(BaseModel):
    """A strict, immutable Pydantic boundary for domain evidence."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
        str_strip_whitespace=True,
    )


class AiTechTrendSupport(_FrozenDomainModel):
    """Opaque trend metadata that can justify selection but not a fact claim."""

    cluster_id: str | None = Field(default=None, min_length=1, max_length=128)
    evidence_ids: tuple[str, ...] = ()

    @field_validator("cluster_id")
    @classmethod
    def _validate_cluster_id(cls, value: str | None) -> str | None:
        if value is not None:
            _require_opaque_reference(value, field_name="cluster_id")
        return value

    @field_validator("evidence_ids")
    @classmethod
    def _validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_opaque_references(value, field_name="evidence_ids")

    @model_validator(mode="after")
    def _require_any_reference(self) -> "AiTechTrendSupport":
        if self.cluster_id is None and not self.evidence_ids:
            raise ValueError("trend_support requires at least one opaque reference")
        return self


class AiTechNewsItem(_FrozenDomainModel):
    """One source-backed, operator-authored item for a news brief."""

    label: str = Field(min_length=1, max_length=120)
    event_fingerprint: str = Field(min_length=1, max_length=128)
    facts: tuple[str, ...] = Field(min_length=1, max_length=6)
    source_refs: tuple[str, ...] = Field(min_length=1, max_length=8)
    trend_support: AiTechTrendSupport | None = None

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="label")

    @field_validator("event_fingerprint")
    @classmethod
    def _validate_event_fingerprint(cls, value: str) -> str:
        _require_opaque_reference(value, field_name="event_fingerprint")
        return value

    @field_validator("facts")
    @classmethod
    def _validate_facts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_non_empty_texts(value, field_name="facts")

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_opaque_references(value, field_name="source_refs")


class AiTechFact(_FrozenDomainModel):
    """A claim eligible for fact translation, with opaque support references."""

    statement: str = Field(min_length=1, max_length=500)
    source_refs: tuple[str, ...] = Field(min_length=1, max_length=8)

    @field_validator("statement")
    @classmethod
    def _validate_statement(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="statement")

    @field_validator("source_refs")
    @classmethod
    def _validate_source_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_opaque_references(value, field_name="source_refs")


class AiTechTopic(_FrozenDomainModel):
    """A safe operator-authored topic label and optional opaque trend context."""

    label: str = Field(min_length=1, max_length=160)
    trend_support: AiTechTrendSupport | None = None

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="topic label")


class AiTechHandsOnRecord(_FrozenDomainModel):
    """The minimum reproducible record required before drafting a hands-on post."""

    product: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    tested_at: date
    task: str = Field(min_length=1, max_length=500)
    input_summary: str = Field(min_length=1, max_length=1_000)
    observed_output: str = Field(min_length=1, max_length=2_000)
    limitation: str = Field(min_length=1, max_length=1_000)
    test_evidence_refs: tuple[str, ...] = Field(min_length=1, max_length=12)

    @field_validator(
        "product",
        "version",
        "task",
        "input_summary",
        "observed_output",
        "limitation",
    )
    @classmethod
    def _validate_drafting_text(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="hands_on text")

    @field_validator("test_evidence_refs")
    @classmethod
    def _validate_test_evidence_refs(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_opaque_references(value, field_name="test_evidence_refs")


class AiTechAudience(_FrozenDomainModel):
    """The decision boundary required for a fact-translation post."""

    who_should_care: str = Field(min_length=1, max_length=500)
    who_can_wait: str = Field(min_length=1, max_length=500)

    @field_validator("who_should_care", "who_can_wait")
    @classmethod
    def _validate_drafting_text(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="audience text")


class AiTechEvidenceManifest(_FrozenDomainModel):
    """Opaque provenance retained for audit and intentionally excluded from prompts."""

    source_refs: tuple[str, ...] = ()
    test_evidence_refs: tuple[str, ...] = ()
    event_fingerprints: tuple[str, ...] = ()
    trend_support: tuple[AiTechTrendSupport, ...] = ()

    @field_validator("source_refs", "test_evidence_refs", "event_fingerprints")
    @classmethod
    def _validate_opaque_manifest_references(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _validate_opaque_references(value, field_name="opaque reference")

    @field_validator("trend_support")
    @classmethod
    def _validate_opaque_trend_support(
        cls,
        value: tuple[AiTechTrendSupport, ...],
    ) -> tuple[AiTechTrendSupport, ...]:
        for trend_support in value:
            _validate_trend_support(trend_support)
        return value


class AiTechModeRequirements(_FrozenDomainModel):
    """Stable mode policy exposed to planners and deterministic validators."""

    mode: AiTechContentMode
    required_sections: tuple[str, ...]
    allowed_claim_kinds: tuple[str, ...]
    forbidden_claim_kinds: tuple[str, ...]
    requires_test_evidence: bool


class _AiTechRuntimeNewsItem(_FrozenDomainModel):
    """Provenance-free news item permitted in runtime state."""

    label: str = Field(min_length=1, max_length=120)
    facts: tuple[str, ...] = Field(min_length=1, max_length=6)

    @field_validator("label")
    @classmethod
    def _validate_label(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="label")

    @field_validator("facts")
    @classmethod
    def _validate_facts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_non_empty_texts(value, field_name="facts")


class _AiTechRuntimeNewsPayload(_FrozenDomainModel):
    mode: Literal["news_brief"]
    news_items: tuple[_AiTechRuntimeNewsItem, ...] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def _require_distinct_labels(self) -> "_AiTechRuntimeNewsPayload":
        labels = {_normalize_news_label(item.label) for item in self.news_items}
        if len(labels) != len(self.news_items):
            raise ValueError("news_brief requires distinct news item labels")
        return self


class _AiTechRuntimeHandsOnRecord(_FrozenDomainModel):
    product: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    tested_at: date
    task: str = Field(min_length=1, max_length=500)
    input_summary: str = Field(min_length=1, max_length=1_000)
    observed_output: str = Field(min_length=1, max_length=2_000)
    limitation: str = Field(min_length=1, max_length=1_000)

    @field_validator(
        "product",
        "version",
        "task",
        "input_summary",
        "observed_output",
        "limitation",
    )
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="hands_on runtime text")


class _AiTechRuntimeHandsOnPayload(_FrozenDomainModel):
    mode: Literal["hands_on"]
    topic: str = Field(min_length=1, max_length=160)
    hands_on: _AiTechRuntimeHandsOnRecord

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="topic label")


class _AiTechRuntimeAudience(_FrozenDomainModel):
    who_should_care: str = Field(min_length=1, max_length=500)
    who_can_wait: str = Field(min_length=1, max_length=500)

    @field_validator("who_should_care", "who_can_wait")
    @classmethod
    def _validate_text(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="audience text")


class _AiTechRuntimeFactTranslationPayload(_FrozenDomainModel):
    mode: Literal["fact_translation"]
    topic: str = Field(min_length=1, max_length=160)
    facts: tuple[str, ...] = Field(min_length=2, max_length=12)
    audience: _AiTechRuntimeAudience

    @field_validator("topic")
    @classmethod
    def _validate_topic(cls, value: str) -> str:
        return _require_drafting_safe_text(value, field_name="topic label")

    @field_validator("facts")
    @classmethod
    def _validate_facts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validate_non_empty_texts(value, field_name="facts")


class _AiTechRuntimeContract(_FrozenDomainModel):
    """Strict, provenance-free state boundary for AI evidence."""

    mode: AiTechContentMode
    drafting_payload: dict[str, Any]
    requirements: AiTechModeRequirements

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_provenance(cls, value: Any) -> Any:
        _assert_no_raw_source_provenance(value)
        return value

    @model_validator(mode="after")
    def _validate_mode_payload_and_policy(self) -> "_AiTechRuntimeContract":
        payload_model = _parse_runtime_payload(self.mode, self.drafting_payload)
        if payload_model.mode != self.mode:
            raise ValueError("runtime drafting payload mode does not match contract mode")
        expected = _mode_requirements_for(self.mode)
        if self.requirements.model_dump(mode="json") != expected.model_dump(mode="json"):
            raise ValueError("runtime AI tech requirements do not match the mode policy")
        return self

    @property
    def normalized(self) -> dict[str, Any]:
        payload = _parse_runtime_payload(self.mode, self.drafting_payload)
        return {
            "mode": self.mode,
            "drafting_payload": payload.model_dump(mode="json"),
            "requirements": _mode_requirements_for(self.mode).model_dump(mode="json"),
        }


class AiTechEvidenceBundle(_FrozenDomainModel):
    """Validated evidence that determines which AI-tech drafting mode is legal."""

    mode: AiTechContentMode
    news_items: tuple[AiTechNewsItem, ...] = ()
    topic: AiTechTopic | None = None
    hands_on: AiTechHandsOnRecord | None = None
    facts: tuple[AiTechFact, ...] = ()
    audience: AiTechAudience | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_raw_source_provenance(cls, value: Any) -> Any:
        _assert_no_raw_source_provenance(value)
        return value

    @model_validator(mode="after")
    def _enforce_mode_shape(self) -> "AiTechEvidenceBundle":
        self._assert_drafting_texts_are_safe()
        if self.mode == "news_brief":
            if not 3 <= len(self.news_items) <= 5:
                raise ValueError("news_brief requires at least 3 and at most 5 news items")
            normalized_labels = {
                _normalize_news_label(item.label) for item in self.news_items
            }
            if len(normalized_labels) != len(self.news_items):
                raise ValueError("news_brief requires distinct news item labels")
            event_fingerprints = {
                item.event_fingerprint for item in self.news_items
            }
            if len(event_fingerprints) != len(self.news_items):
                raise ValueError("news_brief requires distinct event fingerprints")
            if (
                self.topic is not None
                or self.hands_on is not None
                or self.facts
                or self.audience is not None
            ):
                raise ValueError("news_brief only accepts news_items")
            return self

        if self.mode == "hands_on":
            if self.topic is None or self.hands_on is None:
                raise ValueError("hands_on requires topic and hands_on evidence")
            if self.news_items or self.facts or self.audience is not None:
                raise ValueError("hands_on only accepts topic and hands_on evidence")
            return self

        if self.topic is None or self.audience is None:
            raise ValueError("fact_translation requires topic and audience")
        if len(self.facts) < 2:
            raise ValueError(
                "fact_translation requires at least 2 facts; trend support alone "
                "is not publishable fact evidence"
            )
        if self.news_items or self.hands_on is not None:
            raise ValueError("fact_translation only accepts topic, facts, and audience")
        return self

    def _assert_drafting_texts_are_safe(self) -> None:
        """Defend the prompt boundary even against unvalidated nested instances."""
        for item in self.news_items:
            _require_drafting_safe_text(item.label, field_name="label")
            _validate_non_empty_texts(item.facts, field_name="facts")

        if self.topic is not None:
            _require_drafting_safe_text(self.topic.label, field_name="topic label")

        if self.hands_on is not None:
            for value in (
                self.hands_on.product,
                self.hands_on.version,
                self.hands_on.task,
                self.hands_on.input_summary,
                self.hands_on.observed_output,
                self.hands_on.limitation,
            ):
                _require_drafting_safe_text(value, field_name="hands_on text")

        for fact in self.facts:
            _require_drafting_safe_text(fact.statement, field_name="statement")

        if self.audience is not None:
            _require_drafting_safe_text(
                self.audience.who_should_care,
                field_name="audience text",
            )
            _require_drafting_safe_text(
                self.audience.who_can_wait,
                field_name="audience text",
            )

    @property
    def drafting_payload(self) -> dict[str, Any]:
        """Return fresh safe data for a prompt, excluding all provenance IDs."""
        return self._revalidated_for_drafting()._build_drafting_payload()

    def _revalidated_for_drafting(self) -> "AiTechEvidenceBundle":
        """Refuse a whole bundle that was created with Pydantic model_construct()."""
        return AiTechEvidenceBundle.model_validate(self.model_dump(mode="python"))

    def _build_drafting_payload(self) -> dict[str, Any]:
        """Build a prompt payload only from a fully validated contract."""
        self._assert_drafting_texts_are_safe()
        if self.mode == "news_brief":
            return {
                "mode": self.mode,
                "news_items": tuple(
                    {
                        "label": item.label,
                        "facts": item.facts,
                    }
                    for item in self.news_items
                ),
            }

        if self.mode == "hands_on":
            assert self.topic is not None
            assert self.hands_on is not None
            return {
                "mode": self.mode,
                "topic": self.topic.label,
                "hands_on": {
                    "product": self.hands_on.product,
                    "version": self.hands_on.version,
                    "tested_at": self.hands_on.tested_at.isoformat(),
                    "task": self.hands_on.task,
                    "input_summary": self.hands_on.input_summary,
                    "observed_output": self.hands_on.observed_output,
                    "limitation": self.hands_on.limitation,
                },
            }

        assert self.topic is not None
        assert self.audience is not None
        return {
            "mode": self.mode,
            "topic": self.topic.label,
            "facts": tuple(fact.statement for fact in self.facts),
            "audience": {
                "who_should_care": self.audience.who_should_care,
                "who_can_wait": self.audience.who_can_wait,
            },
        }

    @property
    def manifest(self) -> AiTechEvidenceManifest:
        """Return opaque IDs only; never raw URLs, authors, feeds, or headlines."""
        if self.mode == "news_brief":
            return AiTechEvidenceManifest(
                source_refs=_unique_references(
                    ref for item in self.news_items for ref in item.source_refs
                ),
                event_fingerprints=tuple(
                    item.event_fingerprint for item in self.news_items
                ),
                trend_support=tuple(
                    item.trend_support
                    for item in self.news_items
                    if item.trend_support is not None
                ),
            )

        if self.mode == "hands_on":
            assert self.topic is not None
            assert self.hands_on is not None
            return AiTechEvidenceManifest(
                test_evidence_refs=self.hands_on.test_evidence_refs,
                trend_support=(self.topic.trend_support,)
                if self.topic.trend_support is not None
                else (),
            )

        assert self.topic is not None
        return AiTechEvidenceManifest(
            source_refs=_unique_references(
                ref for fact in self.facts for ref in fact.source_refs
            ),
            trend_support=(self.topic.trend_support,)
            if self.topic.trend_support is not None
            else (),
        )

    @property
    def mode_requirements(self) -> AiTechModeRequirements:
        """Return deterministic policy that downstream drafting must honor."""
        return _mode_requirements_for(self.mode)

    @property
    def runtime_contract(self) -> dict[str, Any]:
        """Return the complete provenance-safe contract allowed into the runtime."""
        return parse_ai_tech_runtime_contract(
            {
                "mode": self.mode,
                "drafting_payload": self.drafting_payload,
                "requirements": self.mode_requirements.model_dump(mode="json"),
            }
        )


def parse_ai_tech_evidence_bundle(
    value: Mapping[str, Any],
) -> AiTechEvidenceBundle:
    """Parse a user-supplied AI-tech evidence bundle at the domain boundary."""
    return AiTechEvidenceBundle.model_validate(value)


def parse_ai_tech_runtime_contract(value: Mapping[str, Any]) -> dict[str, Any]:
    """Reparse and normalize the exact AI-tech state contract.

    This representation deliberately contains no provenance references.  It
    remains strict so arbitrary dictionaries, raw source data, stale policy,
    and incomplete mode shapes cannot become runtime model context.
    """
    return _AiTechRuntimeContract.model_validate(value).normalized


def _parse_runtime_payload(
    mode: AiTechContentMode,
    value: Mapping[str, Any] | dict[str, Any],
) -> (
    _AiTechRuntimeNewsPayload
    | _AiTechRuntimeHandsOnPayload
    | _AiTechRuntimeFactTranslationPayload
):
    if mode == "news_brief":
        return _AiTechRuntimeNewsPayload.model_validate(value)
    if mode == "hands_on":
        return _AiTechRuntimeHandsOnPayload.model_validate(value)
    return _AiTechRuntimeFactTranslationPayload.model_validate(value)


def _mode_requirements_for(mode: AiTechContentMode) -> AiTechModeRequirements:
    if mode == "news_brief":
        return AiTechModeRequirements(
            mode=mode,
            required_sections=(
                "news_items",
                "event_fingerprint",
                "facts",
                "source_refs",
            ),
            allowed_claim_kinds=("事实", "影响判断"),
            forbidden_claim_kinds=("实测体验", "无证据性能结论"),
            requires_test_evidence=False,
        )
    if mode == "hands_on":
        return AiTechModeRequirements(
            mode=mode,
            required_sections=(
                "topic",
                "product",
                "version",
                "tested_at",
                "task",
                "input_summary",
                "observed_output",
                "limitation",
                "test_evidence_refs",
            ),
            allowed_claim_kinds=("事实", "体验", "观察结果", "局限说明"),
            forbidden_claim_kinds=("未记录的性能数字",),
            requires_test_evidence=True,
        )
    return AiTechModeRequirements(
        mode=mode,
        required_sections=("topic", "facts", "who_should_care", "who_can_wait"),
        allowed_claim_kinds=("事实", "人群判断"),
        forbidden_claim_kinds=("实测体验", "无证据性能结论"),
        requires_test_evidence=False,
    )


def validate_ai_tech_draft(
    evidence: AiTechEvidenceBundle | Mapping[str, Any],
    draft: Mapping[str, Any],
) -> list[str]:
    """Return deterministic violations for a completed AI-tech draft.

    ``AiTechEvidenceBundle`` is used at the application boundary; the runtime
    receives only its ``runtime_contract``.  Supporting both inputs keeps the
    same pure validator on both sides of the workflow boundary without ever
    putting opaque provenance into the graph state.
    """
    if isinstance(evidence, AiTechEvidenceBundle):
        contract = evidence.runtime_contract
    else:
        # Public callers often hold the just-loaded operator bundle, while the
        # runtime holds the normalized prompt-safe contract.  Accept either
        # shape, but always reparse it before evaluating a draft.
        try:
            contract = parse_ai_tech_runtime_contract(evidence)
        except (TypeError, ValidationError):
            try:
                contract = parse_ai_tech_evidence_bundle(evidence).runtime_contract
            except (TypeError, ValidationError):
                return ["invalid AI tech evidence contract"]
    return validate_ai_tech_draft_contract(contract, draft)


def validate_ai_tech_draft_contract(
    contract: Mapping[str, Any],
    draft: Mapping[str, Any],
) -> list[str]:
    """Validate a draft against an already-normalized, safe runtime contract."""
    try:
        normalized_contract = parse_ai_tech_runtime_contract(contract)
    except (TypeError, ValidationError):
        return ["invalid AI tech evidence contract"]
    mode = normalized_contract["mode"]
    payload = normalized_contract["drafting_payload"]
    if mode not in _AI_TECH_CONTENT_MODES or not isinstance(payload, Mapping):
        return ["invalid AI tech evidence contract"]

    body = _safe_text(draft.get("body"))
    text = _draft_text(draft)
    errors: list[str] = []
    if _contains_raw_source_locator(text):
        errors.append("raw source locator")

    if mode == "news_brief":
        _validate_news_brief_draft(payload=payload, text=text, errors=errors)
        _append_non_hands_on_claim_errors(
            body=body,
            text=text,
            approved_statements=_news_facts(payload),
            errors=errors,
        )
        _append_unsupported_test_claim_errors(text=text, errors=errors)
        _append_unsupported_performance_claim_errors(
            text=text,
            approved_statements=_news_facts(payload),
            errors=errors,
        )
    elif mode == "hands_on":
        _validate_hands_on_draft(payload=payload, text=text, errors=errors)
        _append_unsupported_performance_claim_errors(
            text=text,
            approved_statements=_hands_on_observations(payload),
            errors=errors,
        )
    else:
        _validate_fact_translation_draft(payload=payload, text=text, errors=errors)
        _append_non_hands_on_claim_errors(
            body=body,
            text=text,
            approved_statements=(
                *_string_values(payload.get("facts")),
                *_audience_statements(payload),
                _safe_text(payload.get("topic")),
            ),
            errors=errors,
        )
        _append_unsupported_test_claim_errors(text=text, errors=errors)
        _append_unsupported_performance_claim_errors(
            text=text,
            approved_statements=_string_values(payload.get("facts")),
            errors=errors,
        )

    return list(dict.fromkeys(errors))


def is_ai_tech_drafting_safe_text(value: object) -> bool:
    """Whether a string is safe to render in the AI runtime context."""
    return isinstance(value, str) and bool(value.strip()) and not _contains_raw_source_locator(value)


def _validate_news_brief_draft(
    *,
    payload: Mapping[str, Any],
    text: str,
    errors: list[str],
) -> None:
    items = payload.get("news_items")
    if not isinstance(items, (list, tuple)) or not 3 <= len(items) <= 5:
        errors.append("news brief requires 3 to 5 items")
        return

    for item in items:
        if not isinstance(item, Mapping):
            errors.append("news brief item is invalid")
            continue
        label = _safe_text(item.get("label"))
        facts = _string_values(item.get("facts"))
        if not label:
            errors.append("news brief item label is missing")
        elif label not in text:
            errors.append(f"missing news item label: {label}")
        if not facts:
            errors.append("news brief item fact is missing")
        for fact in facts:
            if fact not in text:
                errors.append(f"missing approved fact: {fact}")


def _validate_hands_on_draft(
    *,
    payload: Mapping[str, Any],
    text: str,
    errors: list[str],
) -> None:
    topic = _safe_text(payload.get("topic"))
    if not topic or topic not in text:
        errors.append("recorded topic")

    record = payload.get("hands_on")
    if not isinstance(record, Mapping):
        errors.extend(("recorded task", "recorded observed output", "recorded limitation"))
        return

    for field_name, error in (
        ("product", "recorded product"),
        ("version", "recorded version"),
        ("tested_at", "recorded test date"),
        ("task", "recorded task"),
        ("input_summary", "recorded input summary"),
        ("observed_output", "recorded observed output"),
        ("limitation", "recorded limitation"),
    ):
        value = _safe_text(record.get(field_name))
        if not value or value not in text:
            errors.append(error)


def _validate_fact_translation_draft(
    *,
    payload: Mapping[str, Any],
    text: str,
    errors: list[str],
) -> None:
    topic = _safe_text(payload.get("topic"))
    if not topic:
        errors.append("fact translation topic is missing")
    elif topic not in text:
        errors.append("recorded topic")

    facts = _string_values(payload.get("facts"))
    if len(facts) < 2:
        errors.append("fact translation requires 2 approved facts")
    for fact in facts:
        if fact not in text:
            errors.append(f"missing approved fact: {fact}")

    audience = payload.get("audience")
    if not isinstance(audience, Mapping):
        errors.extend(("who_should_care", "who_can_wait"))
        return
    for field_name in ("who_should_care", "who_can_wait"):
        value = _safe_text(audience.get(field_name))
        if not value or value not in text:
            errors.append(field_name)


def _append_unsupported_test_claim_errors(*, text: str, errors: list[str]) -> None:
    for marker in _FIRST_PERSON_TEST_MARKERS:
        if marker in text:
            errors.append(marker)


def _append_non_hands_on_claim_errors(
    *,
    body: str,
    text: str,
    approved_statements: tuple[str, ...],
    errors: list[str],
) -> None:
    """Fail closed when news/fact drafts add claims beyond approved statements."""
    if any(marker in text for marker in _NON_HANDS_ON_EXPERIENCE_MARKERS):
        errors.append("non-hands-on experience language")

    allowed = tuple(statement for statement in approved_statements if statement)
    for sentence in _draft_sentences(body):
        if not any(statement in sentence for statement in allowed):
            errors.append("unapproved non-hands-on claim")
            break


def _append_unsupported_performance_claim_errors(
    *,
    text: str,
    approved_statements: tuple[str, ...],
    errors: list[str],
) -> None:
    for marker in _PERFORMANCE_CLAIM_MARKERS:
        if marker not in text:
            continue
        if any(marker in statement and statement in text for statement in approved_statements):
            continue
        errors.append(marker)


def _news_facts(payload: Mapping[str, Any]) -> tuple[str, ...]:
    items = payload.get("news_items")
    if not isinstance(items, (list, tuple)):
        return ()
    return tuple(
        fact
        for item in items
        if isinstance(item, Mapping)
        for fact in _string_values(item.get("facts"))
    )


def _hands_on_observations(payload: Mapping[str, Any]) -> tuple[str, ...]:
    record = payload.get("hands_on")
    if not isinstance(record, Mapping):
        return ()
    observed_output = _safe_text(record.get("observed_output"))
    return (observed_output,) if observed_output else ()


def _audience_statements(payload: Mapping[str, Any]) -> tuple[str, ...]:
    audience = payload.get("audience")
    if not isinstance(audience, Mapping):
        return ()
    return tuple(
        statement
        for field_name in ("who_should_care", "who_can_wait")
        if (statement := _safe_text(audience.get(field_name)))
    )


def _draft_sentences(body: str) -> tuple[str, ...]:
    if not body:
        return ()
    return tuple(
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?])|\n+", body)
        if sentence.strip()
    )


def _draft_text(draft: Mapping[str, Any]) -> str:
    parts = [
        _safe_text(draft.get("title")),
        _safe_text(draft.get("image_text")),
        _safe_text(draft.get("body")),
        *_string_values(draft.get("hashtags")),
    ]
    return "\n".join(part for part in parts if part)


def _safe_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _string_values(value: object) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(text for item in value if (text := _safe_text(item)))


def _validate_non_empty_texts(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    for value in values:
        if not value:
            raise ValueError(f"{field_name} cannot contain empty text")
        _require_drafting_safe_text(value, field_name=field_name)
    return values


def _require_drafting_safe_text(value: str, *, field_name: str) -> str:
    if _contains_raw_source_locator(value):
        raise ValueError(f"{field_name} cannot contain a raw URL or domain")
    return value


def _contains_raw_source_locator(value: str) -> bool:
    normalized = _normalize_locator_text(value)
    return any(
        pattern.search(normalized) is not None
        for pattern in (
            _HIERARCHICAL_URI_PATTERN,
            _PROTOCOL_RELATIVE_URI_PATTERN,
            _UNC_PATH_PATTERN,
            _NON_HIERARCHICAL_URI_PATTERN,
            _COMMON_BARE_DOMAIN_PATTERN,
            _DOMAIN_WITH_URL_SUFFIX_PATTERN,
            _ASCII_DOMAIN_WITH_UNICODE_SEPARATOR_PATTERN,
            _UNICODE_DOMAIN_WITH_UNICODE_SEPARATOR_AND_PATH_PATTERN,
            _LOCAL_HOST_PATTERN,
            _BRACKETED_IP_LITERAL_PATTERN,
        )
    )


def _normalize_locator_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _validate_opaque_references(
    values: tuple[str, ...],
    *,
    field_name: str,
) -> tuple[str, ...]:
    for value in values:
        _require_opaque_reference(value, field_name=field_name)
    return values


def _require_opaque_reference(value: str, *, field_name: str) -> None:
    if not _OPAQUE_REFERENCE_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must contain an opaque reference ID, not a URL, domain, or path"
        )


def _unique_references(references: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(references))


def _validate_trend_support(value: AiTechTrendSupport) -> None:
    if value.cluster_id is None and not value.evidence_ids:
        raise ValueError("trend_support requires at least one opaque reference")
    if value.cluster_id is not None:
        _require_opaque_reference(value.cluster_id, field_name="cluster_id")
    _validate_opaque_references(value.evidence_ids, field_name="evidence_ids")


def _assert_no_raw_source_provenance(value: Any, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            normalized_key = _normalize_field_name(str(key))
            current_path = (*path, str(key))
            if _is_raw_provenance_key(normalized_key):
                raise ValueError(
                    "Raw source provenance is not accepted "
                    f"(field: {'.'.join(current_path)})"
                )
            _assert_no_raw_source_provenance(nested_value, current_path)
        return

    if isinstance(value, (list, tuple)):
        for index, nested_value in enumerate(value):
            _assert_no_raw_source_provenance(nested_value, (*path, str(index)))
        return

    if isinstance(value, str) and _contains_raw_source_locator(value):
        parent_field = _normalize_field_name(path[-2]) if len(path) >= 2 else ""
        if parent_field not in _ALLOWED_REFERENCE_FIELDS:
            location = ".".join(path) or "root"
            raise ValueError(
                "Raw source provenance cannot contain a raw URL or domain "
                f"(at: {location})"
            )


def _is_raw_provenance_key(normalized_key: str) -> bool:
    if normalized_key in _ALLOWED_REFERENCE_FIELDS:
        return False
    if normalized_key in {"url", "uri", "href", "link", "author", "byline", "title"}:
        return True
    if "author" in normalized_key or "byline" in normalized_key:
        return True
    if "feed" in normalized_key:
        return True
    if "url" in normalized_key or "uri" in normalized_key or "href" in normalized_key:
        return True
    return "source" in normalized_key


def _normalize_field_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def _normalize_news_label(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"\s+", "", normalized)


__all__ = [
    "AiTechAudience",
    "AiTechContentMode",
    "AiTechEvidenceBundle",
    "AiTechEvidenceManifest",
    "AiTechFact",
    "AiTechHandsOnRecord",
    "AiTechModeRequirements",
    "AiTechNewsItem",
    "AiTechTopic",
    "AiTechTrendSupport",
    "is_ai_tech_drafting_safe_text",
    "parse_ai_tech_evidence_bundle",
    "parse_ai_tech_runtime_contract",
    "validate_ai_tech_draft",
    "validate_ai_tech_draft_contract",
]
