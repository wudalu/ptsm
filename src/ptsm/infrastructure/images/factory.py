from __future__ import annotations

from ptsm.config.settings import Settings
from ptsm.infrastructure.images.bailian_backend import BailianImageBackend
from ptsm.infrastructure.images.contracts import ImageBackend
from ptsm.infrastructure.images.jimeng_backend import JimengImageBackend


def build_image_backend(settings: Settings) -> ImageBackend | None:
    """Return an image backend when image generation is configured."""
    if settings.jimeng_api_key:
        if not settings.jimeng_secret_key:
            raise ValueError("JIMENG_SECRET_KEY is required when JIMENG_API_KEY is configured")
        return JimengImageBackend(
            api_key=settings.jimeng_api_key,
            secret_key=settings.jimeng_secret_key,
            base_url=settings.jimeng_base_url,
            model=settings.jimeng_model,
            width=settings.jimeng_width,
            height=settings.jimeng_height,
            poll_interval_seconds=settings.jimeng_poll_interval_seconds,
            max_poll_attempts=settings.jimeng_max_poll_attempts,
        )

    if not settings.pic_model_api_key:
        return None

    return BailianImageBackend(
        api_key=settings.pic_model_api_key,
        base_url=settings.pic_model_base_url,
        model=settings.pic_model_model,
        size=settings.pic_model_size,
        negative_prompt=settings.pic_model_negative_prompt,
    )
