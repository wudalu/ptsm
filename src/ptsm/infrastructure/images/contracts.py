from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ImageBackend(Protocol):
    """Contract for provider-backed image generation."""

    provider_name: str

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        """Generate one or more images and persist them locally."""

