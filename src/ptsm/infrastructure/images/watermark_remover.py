from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


class WatermarkRemover:
    """Post-process AI-generated images to remove residual watermarks using OpenCV inpainting."""

    provider_name = "opencv-inpaint"

    def __init__(
        self,
        *,
        corner_search_ratio: float = 0.25,
        inpaint_radius: float = 8.0,
    ) -> None:
        self._corner_search_ratio = corner_search_ratio
        self._inpaint_radius = inpaint_radius

    def remove(
        self,
        *,
        image_path: Path,
        output_dir: Path | None = None,
        output_stem: str | None = None,
    ) -> dict[str, object]:
        """Remove detected watermark from a single image and persist the result."""
        img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"Failed to read image: {image_path}")

        output_dir = output_dir or image_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = output_stem or f"{image_path.stem}-nowm"
        suffix = image_path.suffix or ".png"
        output_path = output_dir / f"{stem}{suffix}"

        mask = self._detect_watermark_mask(img)
        if mask is None:
            cv2.imwrite(str(output_path), img)
            return {
                "status": "skipped",
                "reason": "no_watermark_detected",
                "provider": self.provider_name,
                "source_path": str(image_path),
                "output_path": str(output_path),
            }

        result = cv2.inpaint(img, mask, self._inpaint_radius, cv2.INPAINT_TELEA)
        cv2.imwrite(str(output_path), result)
        return {
            "status": "removed",
            "provider": self.provider_name,
            "source_path": str(image_path),
            "output_path": str(output_path),
        }

    def _detect_watermark_mask(self, img: np.ndarray) -> np.ndarray | None:
        """Build a binary mask covering candidate watermark regions in image corners."""
        h, w = img.shape[:2]
        search_size = int(min(h, w) * self._corner_search_ratio)
        if search_size < 20:
            return None

        mask = np.zeros((h, w), dtype=np.uint8)
        corners = [
            ("bottom_right", img[h - search_size : h, w - search_size : w]),
            ("bottom_left", img[h - search_size : h, 0:search_size]),
            ("top_right", img[0:search_size, w - search_size : w]),
        ]

        for name, roi in corners:
            if roi.size == 0:
                continue
            roi_mask = self._detect_text_like_region(roi)
            if roi_mask is not None:
                if name == "bottom_right":
                    mask[h - search_size : h, w - search_size : w] = roi_mask
                elif name == "bottom_left":
                    mask[h - search_size : h, 0:search_size] = roi_mask
                else:
                    mask[0:search_size, w - search_size : w] = roi_mask

        if np.count_nonzero(mask) == 0:
            return None
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        mask = cv2.dilate(mask, kernel, iterations=2)
        return mask

    @staticmethod
    def _detect_text_like_region(roi: np.ndarray) -> np.ndarray | None:
        """Detect text-like patterns using Canny edges + contour filling for solid masks."""
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(gray, 40, 140)
        kernel_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, kernel_small, iterations=1)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel_small, iterations=2)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        roi_area = roi.shape[0] * roi.shape[1]
        valid = [c for c in contours if 10 < cv2.contourArea(c) < roi_area * 0.25]
        if not valid:
            return None

        filled = np.zeros(roi.shape[:2], dtype=np.uint8)
        cv2.drawContours(filled, valid, -1, 255, -1)

        kernel_med = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        filled = cv2.dilate(filled, kernel_med, iterations=2)
        filled = cv2.morphologyEx(filled, cv2.MORPH_CLOSE, kernel_med, iterations=1)

        text_ratio = np.count_nonzero(filled) / filled.size
        if text_ratio < 0.005 or text_ratio > 0.35:
            return None
        return filled
