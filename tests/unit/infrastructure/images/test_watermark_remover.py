from __future__ import annotations

from pathlib import Path
import tempfile

import cv2
import numpy as np
import pytest

from ptsm.infrastructure.images.watermark_remover import WatermarkRemover


def _make_test_image(width: int = 200, height: int = 300) -> np.ndarray:
    img = np.full((height, width, 3), (128, 160, 200), dtype=np.uint8)
    return img


def _make_image_with_text_corner(
    width: int = 400,
    height: int = 600,
    text: str = "WM",
) -> np.ndarray:
    img = _make_test_image(width, height)
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5
    thickness = 2
    text_size, _ = cv2.getTextSize(text, font, font_scale, thickness)
    x = width - text_size[0] - 8
    y = height - 10
    cv2.putText(img, text, (x, y), font, font_scale, (255, 255, 255), thickness)
    return img


class TestWatermarkRemover:
    def test_import(self) -> None:
        assert WatermarkRemover.provider_name == "opencv-inpaint"

    def test_remove_clean_image_returns_skipped(self) -> None:
        remover = WatermarkRemover()
        img = _make_test_image()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "clean.png"
            cv2.imwrite(str(src), img)
            result = remover.remove(image_path=src)
            assert result["status"] == "skipped"
            assert result["reason"] == "no_watermark_detected"

    def test_remove_image_with_text_corner_returns_removed(self) -> None:
        remover = WatermarkRemover()
        img = _make_image_with_text_corner()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "watermarked.png"
            cv2.imwrite(str(src), img)
            result = remover.remove(image_path=src)
            assert result["status"] == "removed"
            assert result["provider"] == "opencv-inpaint"
            output_path = Path(str(result["output_path"]))
            assert output_path.exists()
            out_img = cv2.imread(str(output_path))
            assert out_img is not None
            assert out_img.shape == img.shape

    def test_remove_respects_output_dir_and_stem(self) -> None:
        remover = WatermarkRemover()
        img = _make_image_with_text_corner()
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / "source.png"
            cv2.imwrite(str(src), img)
            out_dir = Path(tmpdir) / "custom_out"
            result = remover.remove(
                image_path=src,
                output_dir=out_dir,
                output_stem="my_clean",
            )
            output_path = Path(str(result["output_path"]))
            assert output_path.parent == out_dir
            assert output_path.stem == "my_clean"

    def test_remove_unreadable_path_raises(self) -> None:
        remover = WatermarkRemover()
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = Path(tmpdir) / "does_not_exist.png"
            with pytest.raises(ValueError, match="Failed to read image"):
                remover.remove(image_path=nonexistent)

    def test_detect_watermark_mask_empty_on_plain_region(self) -> None:
        remover = WatermarkRemover()
        plain = _make_test_image(100, 100)
        mask = remover._detect_watermark_mask(plain)
        assert mask is None

    def test_detect_watermark_mask_finds_text_like_pattern(self) -> None:
        remover = WatermarkRemover()
        img = _make_image_with_text_corner(400, 600, "LOGO")
        mask = remover._detect_watermark_mask(img)
        assert mask is not None
        assert np.count_nonzero(mask) > 0

    def test_constructor_defaults(self) -> None:
        remover = WatermarkRemover()
        assert remover._corner_search_ratio == 0.25
        assert remover._inpaint_radius == 8.0

    def test_constructor_custom_params(self) -> None:
        remover = WatermarkRemover(
            corner_search_ratio=0.3,
            inpaint_radius=3.0,
        )
        assert remover._corner_search_ratio == 0.3
        assert remover._inpaint_radius == 3.0
