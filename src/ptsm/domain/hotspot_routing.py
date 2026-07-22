"""Conservative post-discovery routing for evidence-backed hotspots.

This module knows nothing about Topic Radar collection.  It only compares an
already-discovered operator headline with explicit playbook coverage profiles.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable
import unicodedata


@dataclass(frozen=True)
class HotspotRoutingProfile:
    """A playbook's explicit coverage after hotspot discovery has completed."""

    playbook_id: str
    domain: str
    include_any: tuple[str, ...] = ()
    require_all: tuple[tuple[str, ...], ...] = ()
    exclude_any: tuple[str, ...] = ()


@dataclass(frozen=True)
class HotspotRouteCandidate:
    """A safe, existing playbook fit without source-derived drafting text."""

    playbook_id: str
    domain: str
    matched_terms: tuple[str, ...]
    confidence: float
    rationale: str
    generation_seed: str


@dataclass(frozen=True)
class HotspotRoute:
    """The explicit result of mapping one discovered hotspot."""

    status: str
    candidates: tuple[HotspotRouteCandidate, ...]
    next_action: str


def route_hotspot(
    operator_headline: str,
    *,
    profiles: Iterable[HotspotRoutingProfile],
) -> HotspotRoute:
    """Map one discovered headline only when explicit coverage terms match.

    Several matches intentionally stay ambiguous: choosing a content account is
    an operator decision, not an automatic routing side effect.
    """
    normalized_headline = _normalize(operator_headline)
    candidates = tuple(
        candidate
        for profile in sorted(profiles, key=lambda item: item.playbook_id)
        if (
            candidate := _candidate_for_profile(
                normalized_headline=normalized_headline,
                profile=profile,
            )
        )
        is not None
    )
    if not candidates:
        return HotspotRoute(
            status="unmapped",
            candidates=(),
            next_action="monitor_or_new_domain_review",
        )
    if len(candidates) == 1:
        return HotspotRoute(
            status="existing_playbook_fit",
            candidates=candidates,
            next_action="select_playbook_and_account",
        )
    return HotspotRoute(
        status="ambiguous",
        candidates=candidates,
        next_action="ask_operator_to_choose_playbook",
    )


def _candidate_for_profile(
    *,
    normalized_headline: str,
    profile: HotspotRoutingProfile,
) -> HotspotRouteCandidate | None:
    if not normalized_headline:
        return None
    if any(_contains(normalized_headline, term) for term in profile.exclude_any):
        return None

    matched = [
        term for term in profile.include_any if _contains(normalized_headline, term)
    ]
    for terms in profile.require_all:
        if terms and all(_contains(normalized_headline, term) for term in terms):
            matched.extend(term for term in terms if term not in matched)

    if not matched:
        return None
    matched_terms = tuple(matched)
    return HotspotRouteCandidate(
        playbook_id=profile.playbook_id,
        domain=profile.domain,
        matched_terms=matched_terms,
        confidence=1.0,
        rationale="命中明确覆盖词：" + "、".join(matched_terms),
        generation_seed=(
            f"以{profile.domain}的内容视角提炼可写切口；"
            "不得复述来源标题、作者或链接。"
        ),
    )


def _contains(normalized_headline: str, term: str) -> bool:
    normalized_term = _normalize(term)
    return bool(normalized_term and normalized_term in normalized_headline)


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\s\W_]+", "", normalized, flags=re.UNICODE)
