from __future__ import annotations

import json
from pathlib import Path
import re
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
        style = _normalize_style(payload.get("style"))
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{output_stem}.png"

        image = self._render(payload, style=style)
        image.save(output_path)

        return {
            "status": "generated",
            "provider": self.provider_name,
            "style": style,
            "model": "local-pillow-note-card",
            "generated_image_paths": [str(output_path)],
            "output_dir": str(output_dir),
            "output_stem": output_stem,
        }

    def _render(self, payload: dict[str, Any], *, style: str) -> Image.Image:
        if style == "iphone_notes_v1":
            return self._render_iphone_notes(payload)
        if style == "wechat_chat_v1":
            return self._render_wechat_chat(payload)
        return self._render_note_card(payload)

    def _render_note_card(self, payload: dict[str, Any]) -> Image.Image:
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
        body = _select_display_body(payload)

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
            summary = body if "\n" in body else " ".join(body.split())
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

    def _render_iphone_notes(self, payload: dict[str, Any]) -> Image.Image:
        image = Image.new("RGB", (self.width, self.height), (255, 254, 248))
        draw = ImageDraw.Draw(image)
        scale = self.width / 1080

        margin = int(72 * scale)
        content_width = self.width - (2 * margin)
        status_font = _load_font(int(25 * scale), bold=True)
        nav_font = _load_font(int(30 * scale), bold=False)
        title_font = _load_font(int(55 * scale), bold=True)
        date_font = _load_font(int(26 * scale), bold=False)
        quote_font = _load_font(int(38 * scale), bold=True)
        body_font = _load_font(int(34 * scale), bold=False)

        _draw_phone_status_bar(
            draw,
            width=self.width,
            y=int(28 * scale),
            margin=margin,
            scale=scale,
            font=status_font,
            fill=(27, 27, 27),
        )

        nav_y = int(88 * scale)
        accent = (204, 147, 0)
        draw.text((margin, nav_y), "< 文件夹", fill=accent, font=nav_font)
        draw.text(
            (self.width - margin - int(72 * scale), nav_y),
            "完成",
            fill=accent,
            font=nav_font,
        )
        y = int(172 * scale)
        draw.line(
            (margin, y, self.width - margin, y),
            fill=(238, 234, 219),
            width=max(1, int(scale)),
        )
        y += int(54 * scale)

        title = str(payload.get("title") or "小红书笔记").strip()
        image_text = str(payload.get("image_text") or "").strip()
        body = _select_display_body(payload)

        y = _draw_wrapped(
            draw,
            text=title,
            xy=(margin, y),
            font=title_font,
            fill=(23, 23, 23),
            max_width=content_width,
            line_spacing=int(18 * scale),
            max_lines=3,
        )
        y += int(18 * scale)
        draw.text((margin, y), "今天 9:41", fill=(142, 142, 147), font=date_font)
        y += int(64 * scale)

        if image_text:
            quote_top = y
            quote_left = margin
            quote_right = self.width - margin
            quote_bottom = quote_top + int(174 * scale)
            draw.rounded_rectangle(
                (quote_left, quote_top, quote_right, quote_bottom),
                radius=int(24 * scale),
                fill=(255, 243, 188),
                outline=(244, 211, 92),
                width=max(1, int(scale)),
            )
            draw.rectangle(
                (quote_left, quote_top, quote_left + int(10 * scale), quote_bottom),
                fill=(244, 190, 36),
            )
            y = _draw_wrapped(
                draw,
                text=image_text,
                xy=(quote_left + int(32 * scale), quote_top + int(30 * scale)),
                font=quote_font,
                fill=(42, 38, 26),
                max_width=content_width - int(64 * scale),
                line_spacing=int(12 * scale),
                max_lines=2,
            )
            y = max(y + int(36 * scale), quote_bottom + int(44 * scale))

        if body:
            summary = body if "\n" in body else " ".join(body.split())
            _draw_wrapped(
                draw,
                text=summary,
                xy=(margin, y),
                font=body_font,
                fill=(45, 45, 45),
                max_width=content_width,
                line_spacing=int(18 * scale),
                max_lines=12,
            )
        return image

    def _render_wechat_chat(self, payload: dict[str, Any]) -> Image.Image:
        palette = _wechat_palette(payload)
        image = Image.new("RGB", (self.width, self.height), palette["chat_background"])
        draw = ImageDraw.Draw(image)
        scale = self.width / 1080

        margin = int(48 * scale)
        body_font = _load_font(int(32 * scale), bold=False)
        label_font = _load_font(int(24 * scale), bold=False)
        small_font = _load_font(int(24 * scale), bold=False)
        show_avatars = False

        chat_margin = margin if show_avatars else int(58 * scale)
        y = int(58 * scale)
        messages = _chat_messages_from_payload(payload)
        time_labels = _wechat_time_labels_from_payload(payload)
        time_index = 0
        if time_labels:
            draw.text(
                (self.width // 2, y),
                time_labels[time_index],
                fill=palette["secondary_text"],
                font=small_font,
                anchor="mm",
            )
            time_index += 1
            y += int(58 * scale)
        for index, (speaker, message) in enumerate(messages[:8]):
            outgoing = speaker in {"me", "我"}
            y = self._draw_chat_bubble(
                draw,
                y=y,
                text=message,
                speaker_name=_wechat_speaker_label(speaker, payload),
                outgoing=outgoing,
                body_font=body_font,
                label_font=label_font,
                scale=scale,
                margin=chat_margin,
                palette=palette,
                show_avatar=show_avatars,
            )
            if time_labels and index in {1, 4} and time_index < len(time_labels):
                draw.text(
                    (self.width // 2, y + int(14 * scale)),
                    time_labels[time_index],
                    fill=palette["secondary_text"],
                    font=small_font,
                    anchor="mm",
                )
                time_index += 1
                y += int(54 * scale)
            elif not time_labels and index == 1:
                draw.text(
                    (self.width // 2, y + int(14 * scale)),
                    "9:41 AM",
                    fill=palette["secondary_text"],
                    font=small_font,
                    anchor="mm",
                )
                y += int(54 * scale)
        return image

    def _draw_chat_bubble(
        self,
        draw: ImageDraw.ImageDraw,
        *,
        y: int,
        text: str,
        speaker_name: str,
        outgoing: bool,
        body_font: ImageFont.ImageFont,
        label_font: ImageFont.ImageFont,
        scale: float,
        margin: int,
        palette: dict[str, tuple[int, int, int]],
        show_avatar: bool = True,
    ) -> int:
        avatar_size = int(54 * scale)
        bubble_max_width = int(660 * scale)
        horizontal_padding = int(28 * scale)
        vertical_padding = int(22 * scale)
        line_spacing = int(10 * scale)
        if show_avatar:
            avatar_x = self.width - margin - avatar_size if outgoing else margin
            bubble_right = (
                avatar_x - int(18 * scale) if outgoing else self.width - margin
            )
            bubble_left_limit = (
                margin if outgoing else avatar_x + avatar_size + int(18 * scale)
            )
        else:
            avatar_x = 0
            bubble_right = self.width - margin
            bubble_left_limit = margin

        speaker_label = _truncate_for_canvas(speaker_name.strip(), 10)
        label_gap = int(8 * scale) if speaker_label else 0
        if speaker_label:
            label_bbox = draw.textbbox((0, 0), speaker_label, font=label_font)
            label_height = label_bbox[3] - label_bbox[1]
            label_width = label_bbox[2] - label_bbox[0]
        else:
            label_height = 0
            label_width = 0
        bubble_y = y + label_height + label_gap

        lines = _wrap_text(draw, text=text, font=body_font, max_width=bubble_max_width)
        lines = lines[:4]
        line_heights = [
            draw.textbbox((0, 0), line, font=body_font)[3]
            - draw.textbbox((0, 0), line, font=body_font)[1]
            for line in lines
        ]
        text_height = sum(line_heights) + max(0, len(lines) - 1) * line_spacing
        text_width = (
            max(
                draw.textbbox((0, 0), line, font=body_font)[2]
                - draw.textbbox((0, 0), line, font=body_font)[0]
                for line in lines
            )
            if lines
            else 0
        )
        bubble_width = min(
            bubble_max_width + horizontal_padding * 2,
            text_width + horizontal_padding * 2,
        )
        bubble_height = text_height + vertical_padding * 2
        if outgoing:
            bubble_box = (
                bubble_right - bubble_width,
                bubble_y,
                bubble_right,
                bubble_y + bubble_height,
            )
            avatar_fill = palette["outgoing_avatar"]
            bubble_fill = palette["outgoing_bubble"]
            text_fill = palette["outgoing_text"]
        else:
            bubble_box = (
                bubble_left_limit,
                bubble_y,
                bubble_left_limit + bubble_width,
                bubble_y + bubble_height,
            )
            avatar_fill = palette["incoming_avatar"]
            bubble_fill = palette["incoming_bubble"]
            text_fill = palette["incoming_text"]
        if speaker_label:
            label_x = (
                bubble_box[2] - label_width if outgoing else bubble_box[0]
            )
            draw.text(
                (label_x, y),
                speaker_label,
                fill=palette["secondary_text"],
                font=label_font,
            )
        draw.rounded_rectangle(
            bubble_box,
            radius=int(18 * scale),
            fill=bubble_fill,
        )
        tail_y = bubble_y + int(30 * scale)
        if outgoing:
            tail_points = [
                (bubble_box[2] - int(2 * scale), tail_y - int(10 * scale)),
                (bubble_box[2] + int(15 * scale), tail_y),
                (bubble_box[2] - int(2 * scale), tail_y + int(12 * scale)),
            ]
        else:
            tail_points = [
                (bubble_box[0] + int(2 * scale), tail_y - int(10 * scale)),
                (bubble_box[0] - int(14 * scale), tail_y),
                (bubble_box[0] + int(2 * scale), tail_y + int(12 * scale)),
            ]
        draw.polygon(tail_points, fill=bubble_fill)
        if show_avatar:
            draw.rounded_rectangle(
                (avatar_x, y, avatar_x + avatar_size, y + avatar_size),
                radius=int(10 * scale),
                fill=avatar_fill,
            )
        text_x = bubble_box[0] + horizontal_padding
        text_y = bubble_y + vertical_padding
        for line in lines:
            draw.text((text_x, text_y), line, fill=text_fill, font=body_font)
            bbox = draw.textbbox((text_x, text_y), line, font=body_font)
            text_y += (bbox[3] - bbox[1]) + line_spacing
        return bubble_y + bubble_height + int(30 * scale)


def _parse_prompt_payload(prompt: str) -> dict[str, Any]:
    try:
        payload = json.loads(prompt)
    except json.JSONDecodeError:
        return {"prompt": prompt}
    if not isinstance(payload, dict):
        return {"prompt": prompt}
    return payload


def _normalize_style(value: object) -> str:
    style = str(value or "").strip().lower()
    aliases = {
        "": NoteCardImageBackend.style,
        "note_card": NoteCardImageBackend.style,
        "xhs_note_card": NoteCardImageBackend.style,
        "xhs_note_card_v1": NoteCardImageBackend.style,
        "iphone_notes": "iphone_notes_v1",
        "iphone_notes_v1": "iphone_notes_v1",
        "wechat_chat": "wechat_chat_v1",
        "wechat_chat_v1": "wechat_chat_v1",
    }
    return aliases.get(style, NoteCardImageBackend.style)


_LOW_DENSITY_IMAGE_ROLES = {
    "cover_hook",
    "save_tool",
    "comment_prompt",
    "evidence_or_scene",
    "shareable_line",
}


def _select_display_body(payload: dict[str, Any]) -> str:
    body = str(payload.get("body") or payload.get("prompt") or "").strip()
    image_plan = payload.get("image_plan")
    if not isinstance(image_plan, dict) or not _uses_low_density_display(image_plan):
        return body

    max_units = _display_max_text_units(image_plan, default=2)
    short_lines = _extract_short_display_lines(body, max_units=max_units)
    if short_lines:
        return "\n".join(short_lines[:max_units])
    return ""


def _uses_low_density_display(image_plan: dict[str, Any]) -> bool:
    role = str(image_plan.get("role") or "").strip().lower()
    text_density = str(image_plan.get("text_density") or "").strip().lower()
    return text_density == "low" or role in _LOW_DENSITY_IMAGE_ROLES


def _display_max_text_units(image_plan: dict[str, Any], *, default: int) -> int:
    raw_value = str(image_plan.get("max_text_units") or "").strip()
    try:
        value = int(raw_value)
    except ValueError:
        value = default
    return max(1, min(value, 4))


def _extract_short_display_lines(body: str, *, max_units: int) -> list[str]:
    lines: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        inline_tool_lines = _extract_inline_tool_lines(line, max_units=max_units)
        if inline_tool_lines:
            lines.extend(inline_tool_lines)
            if len(lines) >= max_units:
                return lines[:max_units]
            continue
        list_match = re.match(r"^(?:[-*•]|\d+[.)、．])\s*(.+)$", line)
        if list_match is not None:
            candidate = list_match.group(1).strip()
        elif len(line) <= 24:
            candidate = line
        else:
            continue
        if candidate:
            lines.append(_truncate_for_canvas(candidate, 32))
        if len(lines) >= max_units:
            return lines

    if lines:
        return lines

    compact = " ".join(body.split())
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[。！？!?]\s*", compact)
        if sentence.strip()
    ]
    return [
        _truncate_for_canvas(sentence, 32)
        for sentence in sentences[:max_units]
        if len(sentence) <= 36
    ]


def _extract_inline_tool_lines(line: str, *, max_units: int) -> list[str]:
    marker_match = re.search(r"(?:三栏|清单|步骤|工具)[:：]", line)
    if marker_match is None:
        return []
    tail = line[marker_match.end() :].strip()
    parts = [part.strip(" 。") for part in re.split(r"[;；]\s*", tail) if part.strip()]
    lines: list[str] = []
    for part in parts:
        if not part:
            continue
        if not any(separator in part for separator in ("=", "＝", ":", "：")) and len(part) > 24:
            continue
        lines.append(_truncate_for_canvas(part, 32))
        if len(lines) >= max_units:
            break
    return lines


def _draw_phone_status_bar(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    y: int,
    margin: int,
    scale: float,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
    time_text: str = "9:41",
) -> None:
    draw.text((margin, y), time_text, fill=fill, font=font)

    signal_x = width - margin - int(170 * scale)
    signal_base_y = y + int(27 * scale)
    for index, bar_height in enumerate((7, 11, 15, 19)):
        x = signal_x + index * int(11 * scale)
        draw.rounded_rectangle(
            (
                x,
                signal_base_y - int(bar_height * scale),
                x + int(6 * scale),
                signal_base_y,
            ),
            radius=max(1, int(2 * scale)),
            fill=fill,
        )

    wifi_center_x = width - margin - int(92 * scale)
    wifi_center_y = y + int(17 * scale)
    for radius in (22, 14):
        draw.arc(
            (
                wifi_center_x - int(radius * scale),
                wifi_center_y - int(radius * scale),
                wifi_center_x + int(radius * scale),
                wifi_center_y + int(radius * scale),
            ),
            215,
            325,
            fill=fill,
            width=max(1, int(4 * scale)),
        )
    dot_radius = max(1, int(3 * scale))
    draw.ellipse(
        (
            wifi_center_x - dot_radius,
            wifi_center_y + int(13 * scale) - dot_radius,
            wifi_center_x + dot_radius,
            wifi_center_y + int(13 * scale) + dot_radius,
        ),
        fill=fill,
    )

    battery_w = int(48 * scale)
    battery_h = int(22 * scale)
    battery_x = width - margin - battery_w
    battery_y = y + int(4 * scale)
    draw.rounded_rectangle(
        (battery_x, battery_y, battery_x + battery_w, battery_y + battery_h),
        radius=int(5 * scale),
        outline=fill,
        width=max(1, int(2 * scale)),
    )
    draw.rectangle(
        (
            battery_x + int(5 * scale),
            battery_y + int(5 * scale),
            battery_x + battery_w - int(8 * scale),
            battery_y + battery_h - int(5 * scale),
        ),
        fill=fill,
    )
    draw.rounded_rectangle(
        (
            battery_x + battery_w + int(3 * scale),
            battery_y + int(7 * scale),
            battery_x + battery_w + int(7 * scale),
            battery_y + battery_h - int(7 * scale),
        ),
        radius=int(2 * scale),
        fill=fill,
    )


def _draw_wechat_header_controls(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    scale: float,
    fill: tuple[int, int, int] = (30, 30, 30),
    unread_count: str = "",
) -> None:
    chevron_points = [
        (int(68 * scale), int(100 * scale)),
        (int(50 * scale), int(122 * scale)),
        (int(68 * scale), int(144 * scale)),
    ]
    draw.line(
        chevron_points,
        fill=fill,
        width=max(2, int(5 * scale)),
        joint="curve",
    )
    if unread_count:
        badge_center_x = int(115 * scale)
        badge_center_y = int(121 * scale)
        badge_radius = int(25 * scale)
        draw.ellipse(
            (
                badge_center_x - badge_radius,
                badge_center_y - badge_radius,
                badge_center_x + badge_radius,
                badge_center_y + badge_radius,
            ),
            fill=(42, 42, 45),
        )
        badge_font = _load_font(int(24 * scale), bold=True)
        draw.text(
            (badge_center_x, badge_center_y),
            _truncate_for_canvas(unread_count, 2),
            fill=fill,
            font=badge_font,
            anchor="mm",
        )
    dot_y = int(121 * scale)
    dot_radius = max(2, int(4 * scale))
    for dot_x in (
        width - int(92 * scale),
        width - int(72 * scale),
        width - int(52 * scale),
    ):
        draw.ellipse(
            (
                dot_x - dot_radius,
                dot_y - dot_radius,
                dot_x + dot_radius,
                dot_y + dot_radius,
            ),
            fill=fill,
        )


def _draw_wechat_input_bar(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    height: int,
    scale: float,
    palette: dict[str, tuple[int, int, int]] | None = None,
) -> None:
    if palette is None:
        palette = _wechat_light_palette()
    bar_y = height - int(180 * scale)
    draw.line(
        (0, bar_y, width, bar_y),
        fill=palette["divider"],
        width=max(1, int(scale)),
    )
    draw.rectangle((0, bar_y + 1, width, height), fill=palette["input_bar_background"])

    center_y = bar_y + int(88 * scale)
    icon_fill = palette["input_icon"]
    voice_x = int(58 * scale)
    icon_radius = int(32 * scale)
    draw.ellipse(
        (
            voice_x - icon_radius,
            center_y - icon_radius,
            voice_x + icon_radius,
            center_y + icon_radius,
        ),
        outline=icon_fill,
        width=max(1, int(3 * scale)),
    )
    _draw_voice_toggle_mark(draw, center=(voice_x, center_y), scale=scale, fill=icon_fill)

    input_left = int(130 * scale)
    input_top = bar_y + int(41 * scale)
    input_right = int(835 * scale)
    input_bottom = bar_y + int(128 * scale)
    draw.rounded_rectangle(
        (input_left, input_top, input_right, input_bottom),
        radius=int(7 * scale),
        fill=palette["input_field_background"],
    )
    _draw_wechat_microphone_icon(
        draw,
        center=(input_right - int(58 * scale), center_y),
        scale=scale,
        fill=palette["input_field_icon"],
    )

    right_icon_radius = int(31 * scale)
    for icon_x in (width - int(185 * scale), width - int(80 * scale)):
        draw.ellipse(
            (
                icon_x - right_icon_radius,
                center_y - right_icon_radius,
                icon_x + right_icon_radius,
                center_y + right_icon_radius,
            ),
            outline=icon_fill,
            width=max(1, int(4 * scale)),
        )

    emoji_x = width - int(185 * scale)
    draw.arc(
        (
            emoji_x - int(13 * scale),
            center_y - int(6 * scale),
            emoji_x + int(13 * scale),
            center_y + int(16 * scale),
        ),
        20,
        160,
        fill=icon_fill,
        width=max(1, int(4 * scale)),
    )
    for eye_x in (emoji_x - int(6 * scale), emoji_x + int(6 * scale)):
        eye_radius = max(1, int(2 * scale))
        draw.ellipse(
            (
                eye_x - eye_radius,
                center_y - int(8 * scale) - eye_radius,
                eye_x + eye_radius,
                center_y - int(8 * scale) + eye_radius,
            ),
            fill=icon_fill,
        )

    plus_x = width - int(80 * scale)
    draw.line(
        (
            plus_x - int(14 * scale),
            center_y,
            plus_x + int(14 * scale),
            center_y,
        ),
        fill=icon_fill,
        width=max(1, int(4 * scale)),
    )
    draw.line(
        (
            plus_x,
            center_y - int(14 * scale),
            plus_x,
            center_y + int(14 * scale),
        ),
        fill=icon_fill,
        width=max(1, int(4 * scale)),
    )
    home_indicator_width = int(380 * scale)
    home_indicator_height = max(4, int(9 * scale))
    home_indicator_x = (width - home_indicator_width) // 2
    home_indicator_y = height - int(30 * scale)
    draw.rounded_rectangle(
        (
            home_indicator_x,
            home_indicator_y,
            home_indicator_x + home_indicator_width,
            home_indicator_y + home_indicator_height,
        ),
        radius=home_indicator_height // 2,
        fill=palette["home_indicator"],
    )


def _draw_voice_toggle_mark(
    draw: ImageDraw.ImageDraw,
    *,
    center: tuple[int, int],
    scale: float,
    fill: tuple[int, int, int],
) -> None:
    center_x, center_y = center
    line_width = max(2, int(3 * scale))
    draw.line(
        (
            center_x - int(12 * scale),
            center_y - int(13 * scale),
            center_x - int(12 * scale),
            center_y + int(13 * scale),
        ),
        fill=fill,
        width=line_width,
    )
    for left, radius_x, radius_y in (
        (-23, 34, 23),
        (-32, 52, 31),
    ):
        draw.arc(
            (
                center_x + int(left * scale),
                center_y - int(radius_y * scale),
                center_x + int((left + radius_x) * scale),
                center_y + int(radius_y * scale),
            ),
            -50,
            50,
            fill=fill,
            width=line_width,
        )


def _draw_wechat_microphone_icon(
    draw: ImageDraw.ImageDraw,
    *,
    center: tuple[int, int],
    scale: float,
    fill: tuple[int, int, int],
) -> None:
    center_x, center_y = center
    line_width = max(2, int(4 * scale))
    draw.rounded_rectangle(
        (
            center_x - int(8 * scale),
            center_y - int(23 * scale),
            center_x + int(8 * scale),
            center_y + int(9 * scale),
        ),
        radius=int(8 * scale),
        outline=fill,
        width=line_width,
    )
    draw.arc(
        (
            center_x - int(22 * scale),
            center_y - int(8 * scale),
            center_x + int(22 * scale),
            center_y + int(28 * scale),
        ),
        25,
        155,
        fill=fill,
        width=line_width,
    )
    draw.line(
        (
            center_x,
            center_y + int(28 * scale),
            center_x,
            center_y + int(40 * scale),
        ),
        fill=fill,
        width=line_width,
    )
    draw.line(
        (
            center_x - int(14 * scale),
            center_y + int(40 * scale),
            center_x + int(14 * scale),
            center_y + int(40 * scale),
        ),
        fill=fill,
        width=line_width,
    )


def _wechat_palette(payload: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    if _wechat_uses_dark_theme(payload):
        return {
            "chat_background": (18, 18, 18),
            "header_background": (25, 25, 26),
            "input_bar_background": (28, 28, 30),
            "input_field_background": (42, 42, 44),
            "divider": (47, 47, 49),
            "primary_text": (248, 248, 248),
            "secondary_text": (126, 126, 126),
            "input_icon": (216, 216, 216),
            "input_field_icon": (150, 150, 154),
            "home_indicator": (246, 246, 246),
            "incoming_bubble": (43, 43, 45),
            "outgoing_bubble": (32, 190, 104),
            "incoming_text": (238, 238, 238),
            "outgoing_text": (20, 20, 20),
            "incoming_avatar": (80, 80, 82),
            "outgoing_avatar": (72, 151, 82),
        }
    return _wechat_light_palette()


def _wechat_light_palette() -> dict[str, tuple[int, int, int]]:
    return {
        "chat_background": (237, 237, 237),
        "header_background": (246, 246, 246),
        "input_bar_background": (246, 246, 246),
        "input_field_background": (255, 255, 255),
        "divider": (218, 218, 218),
        "primary_text": (22, 22, 22),
        "secondary_text": (150, 150, 150),
        "input_icon": (56, 56, 56),
        "input_field_icon": (120, 120, 120),
        "home_indicator": (40, 40, 40),
        "incoming_bubble": (255, 255, 255),
        "outgoing_bubble": (149, 236, 105),
        "incoming_text": (25, 25, 25),
        "outgoing_text": (25, 25, 25),
        "incoming_avatar": (190, 190, 190),
        "outgoing_avatar": (87, 173, 102),
    }


def _wechat_uses_dark_theme(payload: dict[str, Any]) -> bool:
    image_plan = payload.get("image_plan")
    raw_value: object = payload.get("theme")
    if isinstance(image_plan, dict) and raw_value is None:
        raw_value = image_plan.get("theme")
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {"dark", "black", "night", "true", "1"}
    return False


def _chat_messages_from_payload(payload: dict[str, Any]) -> list[tuple[str, str]]:
    scene = str(payload.get("scene") or "").strip()
    image_text = str(payload.get("image_text") or "").strip()
    body = str(payload.get("body") or payload.get("prompt") or "").strip()
    messages: list[tuple[str, str]] = []
    image_plan = payload.get("image_plan")
    low_density = isinstance(image_plan, dict) and _uses_low_density_display(
        image_plan
    )

    if image_text:
        image_text_lines = [
            line.strip() for line in image_text.splitlines() if line.strip()
        ]
        if len(image_text_lines) > 1 or low_density:
            for index, line in enumerate(image_text_lines):
                speaker = "other" if index % 2 == 0 else "me"
                normalized_line = _normalize_chat_message_line(
                    line, is_final=index == len(image_text_lines) - 1
                )
                messages.append((speaker, _truncate_for_canvas(normalized_line, 32)))
        else:
            messages.append(("other", image_text))
    explicit_body_messages: list[tuple[str, str]] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        speaker = _chat_speaker_from_line(line)
        if speaker is None:
            continue
        if "：" in line:
            line = line.split("：", 1)[1].strip()
        elif ":" in line:
            line = line.split(":", 1)[1].strip()
        explicit_body_messages.append((speaker, line))

    if explicit_body_messages:
        messages.extend(explicit_body_messages)
        return messages
    if messages and low_density:
        return messages

    synthetic_messages: list[tuple[str, str]] = []
    opening = _chat_opening_from_scene(scene)
    if opening:
        synthetic_messages.append(("other", opening))
    if image_text:
        synthetic_messages.append(("me", image_text))
    summary = _chat_body_summary(body)
    if summary:
        synthetic_messages.append(("other", summary))
    reply = _chat_copyable_reply(body)
    if reply and reply not in {message for _, message in synthetic_messages}:
        synthetic_messages.append(("me", reply))

    return (
        synthetic_messages
        or messages
        or [("other", "今天这条消息真的很适合截图保存。")]
    )


def _wechat_header_title_from_payload(payload: dict[str, Any]) -> str:
    image_plan = payload.get("image_plan")
    candidates: list[object] = [
        payload.get("chat_title"),
        payload.get("conversation_title"),
    ]
    if isinstance(image_plan, dict):
        candidates.extend(
            [
                image_plan.get("chat_title"),
                image_plan.get("conversation_title"),
            ]
        )
    for candidate in candidates:
        title = str(candidate or "").strip()
        if title:
            return _truncate_for_canvas(title, 12)

    title = str(payload.get("title") or "").strip()
    if title and len(title) <= 6:
        return title
    return "朋友"


def _wechat_status_time_from_payload(payload: dict[str, Any]) -> str:
    image_plan = payload.get("image_plan")
    candidates: list[object] = [payload.get("status_time")]
    if isinstance(image_plan, dict):
        candidates.append(image_plan.get("status_time"))
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return _truncate_for_canvas(value, 5)
    return "9:41"


def _wechat_unread_count_from_payload(payload: dict[str, Any]) -> str:
    image_plan = payload.get("image_plan")
    candidates: list[object] = [payload.get("unread_count")]
    if isinstance(image_plan, dict):
        candidates.append(image_plan.get("unread_count"))
    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return _truncate_for_canvas(value, 2)
    return ""


def _wechat_time_labels_from_payload(payload: dict[str, Any]) -> list[str]:
    image_plan = payload.get("image_plan")
    raw_value: object = payload.get("chat_times")
    if isinstance(image_plan, dict) and raw_value is None:
        raw_value = image_plan.get("chat_times")
    if isinstance(raw_value, str):
        return [
            _truncate_for_canvas(part.strip(), 5)
            for part in raw_value.split(",")
            if part.strip()
        ][:3]
    if isinstance(raw_value, list):
        return [
            _truncate_for_canvas(str(part).strip(), 5)
            for part in raw_value
            if str(part).strip()
        ][:3]
    return []


def _wechat_show_avatars(payload: dict[str, Any]) -> bool:
    image_plan = payload.get("image_plan")
    raw_value: object = payload.get("show_avatars")
    if isinstance(image_plan, dict) and raw_value is None:
        raw_value = image_plan.get("show_avatars")
    if isinstance(raw_value, bool):
        return raw_value
    if isinstance(raw_value, str):
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _normalize_chat_message_line(line: str, *, is_final: bool) -> str:
    text = line.strip()
    if is_final and text.endswith(("，", ",")):
        return text[:-1].rstrip() + "。"
    return text


def _wechat_speaker_label(speaker: str, payload: dict[str, Any]) -> str:
    normalized = speaker.strip()
    if normalized in {"me", "我"}:
        return "我"
    if normalized == "other":
        return _wechat_header_title_from_payload(payload)
    return normalized or _wechat_header_title_from_payload(payload)


def _chat_speaker_from_line(line: str) -> str | None:
    if "：" in line:
        speaker = line.split("：", 1)[0].strip()
    elif ":" in line:
        speaker = line.split(":", 1)[0].strip()
    else:
        return None
    if speaker in {"我", "本人"}:
        return "我"
    lowered = speaker.lower()
    if lowered in {"me", "self"}:
        return "我"
    if lowered in {"other", "friend", "peer"}:
        return "对方"
    if len(speaker) <= 12:
        return speaker
    return None


def _chat_opening_from_scene(scene: str) -> str:
    if not scene:
        return ""
    if "在吗" in scene:
        return "在吗？"
    if "领导" in scene:
        return "现在方便吗？"
    if "群" in scene:
        return "群里又来消息了"
    return ""


def _chat_body_summary(body: str) -> str:
    if not body:
        return ""
    summary = " ".join(body.split())
    for marker in ("可复制疯话：", "可复制疯话:", "群聊草稿：", "群聊草稿:"):
        if marker in summary:
            summary = summary.split(marker, 1)[0].strip()
            break
    return _truncate_for_canvas(summary, 46)


def _chat_copyable_reply(body: str) -> str:
    if not body:
        return ""
    compact = " ".join(body.split())
    for marker in ("可复制疯话：", "可复制疯话:", "群聊草稿：", "群聊草稿:"):
        if marker not in compact:
            continue
        reply = compact.split(marker, 1)[1].strip()
        for stop in ("。", "！", "？", ".", "!", "?"):
            if stop in reply:
                reply = reply.split(stop, 1)[0].strip() + stop
                break
        return _truncate_for_canvas(reply, 30)
    return ""


def _truncate_for_canvas(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


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
