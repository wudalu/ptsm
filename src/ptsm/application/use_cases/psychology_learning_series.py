"""Pure planning entry point for custom psychology learning-series proposals."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from ptsm.domain.psychology_learning import (
    PsychologyLearningOutlineItem,
    PsychologyLearningSeriesPlanIntent,
    PsychologyLearningSeriesProposal,
    build_psychology_learning_series_proposal,
)


def plan_psychology_learning_series(
    *,
    topic: str,
    outline: list[Mapping[str, Any] | PsychologyLearningOutlineItem]
    | tuple[Mapping[str, Any] | PsychologyLearningOutlineItem, ...]
    | None = None,
) -> PsychologyLearningSeriesProposal:
    """Return a safe review proposal without writing or resolving a catalog.

    This is intentionally a planning-only use case.  It does not persist a
    proposal, create a curriculum revision, select a lesson, or construct
    reader-visible runtime input.
    """
    if outline is not None:
        if type(outline) not in (list, tuple):
            raise TypeError("outline must be a concrete list or tuple")
        if not 2 <= len(outline) <= 6:
            raise ValueError("outline must contain between 2 and 6 lessons")
    return build_psychology_learning_series_proposal(
        PsychologyLearningSeriesPlanIntent(
            topic=topic,
            outline=tuple(outline) if outline is not None else None,
        )
    )
