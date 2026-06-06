from __future__ import annotations

NO_WATERMARK_NEGATIVE_TERMS = ("水印", "logo", "品牌标识")


def merge_no_watermark_negative_prompt(base: str) -> str:
    """Preserve caller negative prompt while enforcing generated-image watermark bans."""
    normalized = base.lower()
    parts = [base.strip()] if base.strip() else []
    for term in NO_WATERMARK_NEGATIVE_TERMS:
        if term.lower() not in normalized:
            parts.append(term)
    return "，".join(parts)


def generated_no_watermark_policy(
    provider: str,
    provider_controls: dict[str, object],
) -> dict[str, object]:
    """Return artifact-safe metadata proving generated images request no provider watermark."""
    return {
        "source": "ptsm_generated_image",
        "requested": "no_provider_watermark",
        "provider": provider,
        "provider_controls": provider_controls,
    }


def local_renderer_provenance(renderer: str) -> dict[str, object]:
    """Return provenance metadata for trusted local PTSM-rendered images."""
    return {
        "source": "ptsm_local_renderer",
        "renderer": renderer,
        "watermark_removal": "skip",
    }
