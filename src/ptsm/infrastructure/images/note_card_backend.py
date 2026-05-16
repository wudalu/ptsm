from __future__ import annotations

import json
from pathlib import Path
import textwrap
from typing import Any

from PIL import Image, ImageDraw, ImageFont


class NoteCardImageBackend:
    """Render a local Xiaohongshu notes-style cover image."""

    provider_name = "local_note_card"
    style = "xhs_note_card_v1"

    def __init__(self, *, width: int = 1080, height: int = 1440) -> None:
        self.width = width
        self.height = height

    def generate(
        self,
        *,
        prompt: str,
        output_dir: Path,
        output_stem: str,
    ) -> dict[str, object]:
        payload = _parse_prompt_payload(prompt)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{output_stem}.png"

        image = self._render(payload)
        image.save(output_path)

        return {
            "status": "generated",
            "provider": self.provider_name,
            "style": self.style,
            "model": "local-pillow-note-card",
            "generated_image_paths": [str(output_path)],
            "output_dir": str(output_dir),
            "output_stem": output_stem,
        }

    def _render(self, payload: dict[str, Any]) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height), (250, 248, 240))
        draw = ImageDraw.Draw(image)
        scale = self.width / 1080

        margin = int(72 * scale)
        top = int(72 * scale)
        card_radius = int(34 * scale)
        card_box = (
            margin,
            top,
            self.width - margin,
            self.height - margin,
        )
        draw.rounded_rectangle(
            card_box,
            radius=card_radius,
            fill=(255, 253, 247),
            outline=(232, 226, 214),
            width=max(1, int(2 * scale)),
        )

        x = margin + int(56 * scale)
        y = top + int(48 * scale)
        content_width = self.width - (2 * x)

        nav_font = _load_font(int(30 * scale), bold=False)
        title_font = _load_font(int(58 * scale), bold=True)
        subtitle_font = _load_font(int(42 * scale), bold=True)
        body_font = _load_font(int(32 * scale), bold=False)
        meta_font = _load_font(int(26 * scale), bold=False)

        draw.text((x, y), "Notes", fill=(193, 143, 58), font=nav_font)
        draw.text(
            (self.width - x - int(90 * scale), y),
            "Done",
            fill=(193, 143, 58),
            font=nav_font,
        )
        y += int(82 * scale)
        draw.line(
            (x, y, self.width - x, y),
            fill=(238, 232, 220),
            width=max(1, int(scale)),
        )
        y += int(62 * scale)

        title = str(payload.get("title") or "小红书笔记").strip()
        image_text = str(payload.get("image_text") or "").strip()
        body = str(payload.get("body") or payload.get("prompt") or "").strip()

        y = _draw_wrapped(
            draw,
            text=title,
            xy=(x, y),
            font=title_font,
            fill=(38, 37, 34),
            max_width=content_width,
            line_spacing=int(18 * scale),
            max_lines=3,
        )
        y += int(48 * scale)

        if image_text:
            quote_box_top = y
            quote_box_bottom = y + int(190 * scale)
            draw.rounded_rectangle(
                (x, quote_box_top, self.width - x, quote_box_bottom),
                radius=int(22 * scale),
                fill=(255, 247, 224),
                outline=(245, 224, 176),
                width=max(1, int(scale)),
            )
            y = _draw_wrapped(
                draw,
                text=image_text,
                xy=(x + int(30 * scale), y + int(34 * scale)),
                font=subtitle_font,
                fill=(64, 54, 42),
                max_width=content_width - int(60 * scale),
                line_spacing=int(14 * scale),
                max_lines=2,
            )
            y = max(y + int(34 * scale), quote_box_bottom + int(42 * scale))

        if body:
            summary = " ".join(body.split())
            y = _draw_wrapped(
                draw,
                text=summary,
                xy=(x, y),
                font=body_font,
                fill=(78, 75, 68),
                max_width=content_width,
                line_spacing=int(16 * scale),
                max_lines=10,
            )

        footer = "Generated locally by PTSM"
        draw.text(
            (x, self.height - margin - int(48 * scale)),
            footer,
            fill=(170, 163, 150),
            font=meta_font,
        )
        return image


def _parse_prompt_payload(prompt: str) -> dict[str, Any]:
    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        return {"prompt": prompt}
    if not isinstance(payload, dict):
        return {"prompt": prompt}
    return payload


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    xy: tuple[int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    max_width: int,
    line_spacing: int,
    max_lines: int,
) -> int:
    x, y = xy
    lines = _wrap_text(draw, text=text, font=font, max_width=max_width)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .，。") + "..."
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    *,
    text: str,
    font: ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    for raw_line in text.splitlines():
        current = ""
        for char in raw_line:
            candidate = current + char
            bbox = draw.textbbox((0, 0), candidate, font=font)
            if bbox[2] - bbox[0] <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
    return lines or textwrap.wrap(text, width=18)


def _load_font(size: int, *, bold: bool) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                continue
    return ImageFont.load_default()
