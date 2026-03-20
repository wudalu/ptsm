from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillSpec:
    """Parsed metadata for a local skill."""

    skill_name: str
    display_name: str
    short_description: str
    display_order: int
    source_path: Path
    metadata: dict[str, str] = field(default_factory=dict)

