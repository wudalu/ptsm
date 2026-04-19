from __future__ import annotations

from ptsm.config.settings import Settings
from ptsm.infrastructure.images.bailian_backend import BailianImageBackend
from ptsm.infrastructure.images.contracts import ImageBackend


def build_image_backend(settings: Settings) -> ImageBackend | None:
    """Return an image backend when image generation is configured."""
    if not settings.pic_model_api_key:
        return None

    return BailianImageBackend(
        api_key=settings.pic_model_api_key,
        base_url=settings.pic_model_base_url,
        model=settings.pic_model_model,
        size=settings.pic_model_size,
        negative_prompt=settings.pic_model_negative_prompt,
    )
