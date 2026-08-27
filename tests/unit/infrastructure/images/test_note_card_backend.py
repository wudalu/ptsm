from __future__ import annotations

import json
from pathlib import Path

import cv2
from PIL import Image, ImageChops, ImageDraw

from ptsm.infrastructure.images.note_card_backend import (
    NoteCardImageBackend,
    _chat_messages_from_payload,
    _select_display_body,
    _wechat_header_title_from_payload,
    _wechat_speaker_label,
    _wechat_time_labels_from_payload,
)


def _count_wechat_green_pixels(image) -> int:
    channels = image.astype("int16")
    green_pixels = (
        (channels[:, :, 1] > channels[:, :, 0] + 50)
        & (channels[:, :, 1] > channels[:, :, 2] + 50)
    )
    return int(green_pixels.sum())


def _count_dark_pixels(image, *, x1: int, y1: int, x2: int, y2: int) -> int:
    region = image[y1:y2, x1:x2].astype("int16")
    dark_pixels = (
        (region[:, :, 0] < 70)
        & (region[:, :, 1] < 70)
        & (region[:, :, 2] < 70)
    )
    return int(dark_pixels.sum())


def _count_bright_pixels(image, *, x1: int, y1: int, x2: int, y2: int) -> int:
    region = image[y1:y2, x1:x2].astype("int16")
    bright_pixels = (
        (region[:, :, 0] > 245)
        & (region[:, :, 1] > 245)
        & (region[:, :, 2] > 245)
    )
    return int(bright_pixels.sum())


def _count_near_color_pixels(
    image,
    *,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: tuple[int, int, int],
    tolerance: int,
) -> int:
    # cv2 reads BGR, but all grayscale-ish colors used here have equal channels.
    region = image[y1:y2, x1:x2].astype("int16")
    target = color[::-1]
    near_pixels = (
        (abs(region[:, :, 0] - target[0]) <= tolerance)
        & (abs(region[:, :, 1] - target[1]) <= tolerance)
        & (abs(region[:, :, 2] - target[2]) <= tolerance)
    )
    return int(near_pixels.sum())


def test_note_card_backend_renders_nonblank_png(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "title": "周日晚上怕周一消息，不是你没用",
                "image_text": "脑子提前打卡上班",
                "body": "可以先存一个 5分钟落地练习：写下最担心的1件事、能做的1个动作。",
                "hashtags": ["#心理学", "#情绪管理"],
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="cover",
    )

    output_path = Path(result["generated_image_paths"][0])
    assert result["status"] == "generated"
    assert result["provider"] == "local_note_card"
    assert result["style"] == "xhs_note_card_v1"
    assert result["provenance"] == {
        "source": "ptsm_local_renderer",
        "renderer": "NoteCardImageBackend",
        "watermark_removal": "skip",
    }
    assert output_path.exists()
    assert output_path.suffix == ".png"

    image = cv2.imread(str(output_path), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    assert image.shape == (1440, 1080)
    assert int(image.min()) < int(image.max())


def test_note_card_backend_does_not_draw_local_branding_footer(
    monkeypatch,
    tmp_path: Path,
) -> None:
    drawn_texts: list[str] = []
    original_text = ImageDraw.ImageDraw.text

    def capture_text(self, xy, text, *args, **kwargs):
        drawn_texts.append(str(text))
        return original_text(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture_text)

    NoteCardImageBackend(width=540, height=720).generate(
        prompt=json.dumps(
            {
                "title": "周日晚上怕周一消息，不是你没用",
                "image_text": "脑子提前打卡上班",
                "body": "可以先存一个 5分钟落地练习。",
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="cover",
    )

    assert "Generated locally by PTSM" not in drawn_texts


def test_note_card_backend_falls_back_to_prompt_text_when_json_is_invalid(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend(width=540, height=720)

    result = backend.generate(
        prompt="一张小红书笔记风封面，主题是普通人看懂AI更新",
        output_dir=tmp_path,
        output_stem="plain",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    assert image.shape == (720, 540)
    assert result["provider"] == "local_note_card"


def test_note_card_backend_renders_iphone_notes_style(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "iphone_notes_v1",
                "title": "领导连发三个在吗，我刚打开咖啡",
                "image_text": "在吗？在的，但灵魂已进入飞行模式",
                "body": "周一早上刚坐下，手机震了三下。可以先存一句：有事请@我的咖啡杯。",
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="iphone",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape == (1440, 1080, 3)
    assert result["style"] == "iphone_notes_v1"
    assert int(image.min()) < int(image.max())
    sampled_pixels = image[80:1320:160, 80:1000:160].reshape(-1, 3)
    assert len({tuple(pixel) for pixel in sampled_pixels}) >= 5


def test_iphone_notes_default_timestamp_varies_by_payload(
    monkeypatch,
    tmp_path: Path,
) -> None:
    drawn_texts: list[str] = []
    original_text = ImageDraw.ImageDraw.text

    def capture_text(self, xy, text, *args, **kwargs):
        drawn_texts.append(str(text))
        return original_text(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture_text)
    backend = NoteCardImageBackend(width=540, height=720)

    for stem, scene in (
        ("first", "领导18:57发来一句在吗"),
        ("second", "周日23点想起明天晨会"),
    ):
        backend.generate(
            prompt=json.dumps(
                {
                    "style": "iphone_notes_v1",
                    "scene": scene,
                    "title": scene,
                    "image_plan": {
                        "role": "save_tool",
                        "text_density": "low",
                    },
                },
                ensure_ascii=False,
            ),
            output_dir=tmp_path,
            output_stem=stem,
        )

    timestamps = [text for text in drawn_texts if text.startswith("今天 ")]

    assert len(timestamps) == 2
    assert "今天 9:41" not in timestamps
    assert timestamps[0] != timestamps[1]


def test_wechat_default_time_labels_vary_by_payload() -> None:
    workplace_labels = _wechat_time_labels_from_payload(
        {
            "style": "wechat_chat_v1",
            "scene": "领导18:57发来一句在吗",
            "body": "领导：在吗\n我：收到，但灵魂已下班。",
        }
    )
    late_night_labels = _wechat_time_labels_from_payload(
        {
            "style": "wechat_chat_v1",
            "scene": "朋友23点发来一大段消息",
            "body": "朋友：你睡了吗\n我：刚准备关机。",
        }
    )

    assert workplace_labels
    assert late_night_labels
    assert workplace_labels != late_night_labels
    assert "9:41 AM" not in workplace_labels
    assert "9:41" not in workplace_labels


def test_wechat_generic_other_label_uses_simulated_nickname() -> None:
    assert (
        _wechat_speaker_label(
            "other",
            {
                "scene": "领导18:57发来一句在吗",
                "title": "领导18:57发来一句在吗",
            },
        )
        == "林主管"
    )
    assert (
        _wechat_speaker_label(
            "other",
            {
                "scene": "朋友23点发来一大段消息",
                "title": "朋友半夜发来一大段消息",
            },
        )
        == "阿晴"
    )


def test_select_display_body_clamps_low_density_iphone_notes_copy() -> None:
    display_body = _select_display_body(
        {
            "style": "iphone_notes_v1",
            "title": "会议后反复复盘，不是你太玻璃心",
            "image_text": "先把脑内回放按暂停",
            "body": (
                "下班地铁里，我又一次点开公司群聊，反复确认自己在会议上说错的"
                "那句话有没有被所有人记住。越想越觉得脸发烫，甚至开始脑补明天"
                "大家看我的眼神。\n"
                "1. 给这件事起名：复盘漩涡\n"
                "2. 分开事实和脑补\n"
                "3. 给明天留一句可执行动作"
            ),
            "image_plan": {
                "role": "save_tool",
                "text_density": "low",
                "max_text_units": "3",
            },
        }
    )

    assert "下班地铁里" not in display_body
    assert "复盘漩涡" in display_body
    assert len([line for line in display_body.splitlines() if line.strip()]) <= 3


def test_select_display_body_prefers_image_plan_golden_line() -> None:
    display_body = _select_display_body(
        {
            "style": "iphone_notes_v1",
            "body": (
                "下班以后同事说要工作留痕，我第一反应是又要截图又要解释。"
                "后来才发现，留痕不是为了吵架，是为了让事情别反复消耗。"
            ),
            "image_plan": {
                "role": "cover_hook",
                "text_density": "low",
                "max_text_units": "1",
                "golden_line": "事要留痕，但心别留疤。",
            },
        }
    )

    assert display_body == "事要留痕，但心别留疤。"


def test_select_display_body_extracts_inline_tool_lines_without_prompt_focus() -> None:
    display_body = _select_display_body(
        {
            "style": "iphone_notes_v1",
            "body": (
                "下班路上反复复盘会议上说错的那句话，脑子还在把会议那一秒拖回进度条。\n"
                "可以先存一个事实 / 猜测 / 下一步三栏：事实=对方实际说了什么；"
                "猜测=我补出的评价；下一步=明天是否用一句轻确认收尾。"
            ),
            "image_plan": {
                "role": "save_tool",
                "text_density": "low",
                "max_text_units": "3",
                "prompt_focus": "做成低密度工具卡，保留标题、封面语和最多三条短句。",
            },
        }
    )

    assert "事实=对方实际说了什么" in display_body
    assert "猜测=我补出的评价" in display_body
    assert "下一步=明天是否用一句轻确认收尾" in display_body
    assert "低密度工具卡" not in display_body
    assert len([line for line in display_body.splitlines() if line.strip()]) == 3


def test_note_card_backend_renders_wechat_chat_style(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "title": "领导",
                "image_text": "在吗？",
                "body": "领导：在吗\n我：在的，但灵魂已进入飞行模式\n领导：下班前把PPT重做一遍",
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert image.shape == (1440, 1080, 3)
    assert result["style"] == "wechat_chat_v1"
    assert int(image.min()) < int(image.max())
    assert _count_wechat_green_pixels(image) > 5000


def test_note_card_backend_wechat_style_synthesizes_outgoing_bubble(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "scene": "周一早上刚坐到工位，领导连发三个在吗",
                "title": "领导连发三个在吗",
                "image_text": "我的工牌先替我发疯",
                "body": (
                    "周一早上刚坐到工位，领导连发三个在吗，群聊弹出来那一秒，"
                    "我的工牌已经在桌上替我原地离职。"
                    "可复制疯话：收到，但灵魂已下班。"
                ),
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-synthetic",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert result["style"] == "wechat_chat_v1"
    assert _count_wechat_green_pixels(image) > 5000


def test_note_card_backend_wechat_style_omits_phone_header_chrome(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "title": "520后劲最大的文案，我选苏轼这句",
                "image_text": "520别只发我爱你\n但愿人长久。",
                "image_plan": {
                    "role": "cover_hook",
                    "text_density": "low",
                    "max_text_units": "2",
                },
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-header-controls",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert _count_near_color_pixels(
        image,
        x1=0,
        y1=78,
        x2=1080,
        y2=154,
        color=(237, 237, 237),
        tolerance=4,
    ) > 50000
    assert _count_dark_pixels(image, x1=34, y1=90, x2=90, y2=150) < 80
    assert _count_dark_pixels(image, x1=965, y1=100, x2=1045, y2=135) < 80


def test_note_card_backend_wechat_style_omits_input_bar(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "title": "520后劲最大的文案，我选苏轼这句",
                "image_text": "520别只发我爱你\n但愿人长久。",
                "image_plan": {
                    "role": "cover_hook",
                    "text_density": "low",
                    "max_text_units": "2",
                },
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-input-bar",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert _count_bright_pixels(image, x1=100, y1=1320, x2=825, y2=1405) < 1000
    assert _count_dark_pixels(image, x1=25, y1=1335, x2=80, y2=1400) < 80
    assert _count_dark_pixels(image, x1=865, y1=1335, x2=1015, y2=1400) < 120


def test_note_card_backend_wechat_style_omits_voice_button(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "title": "520后劲最大的文案，我选苏轼这句",
                "image_text": "520别只发我爱你\n但愿人长久。",
                "image_plan": {
                    "role": "cover_hook",
                    "text_density": "low",
                    "max_text_units": "2",
                },
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-voice-button",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert _count_dark_pixels(image, x1=25, y1=1315, x2=100, y2=1385) < 80
    assert _count_dark_pixels(image, x1=42, y1=1332, x2=78, y2=1368) < 60


def test_note_card_backend_wechat_style_renders_dark_theme(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "theme": "dark",
                "title": "520后劲最大的文案，我选苏轼这句",
                "image_text": "520别只发我爱你\n但愿人长久。",
                "image_plan": {
                    "role": "cover_hook",
                    "text_density": "low",
                    "max_text_units": "2",
                },
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-dark-theme",
    )

    output_path = Path(result["generated_image_paths"][0])
    image = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert image is not None
    assert _count_dark_pixels(image, x1=0, y1=155, x2=1080, y2=1280) > 900000
    assert _count_dark_pixels(image, x1=0, y1=72, x2=1080, y2=154) > 70000
    assert _count_dark_pixels(image, x1=0, y1=1285, x2=1080, y2=1440) > 120000
    assert _count_bright_pixels(image, x1=490, y1=90, x2=590, y2=135) < 100


def test_wechat_dark_no_avatar_reference_style_is_content_only_transcript(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend(width=1080, height=1440)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "wechat_chat_v1",
                "theme": "dark",
                "status_time": "23:22",
                "chat_title": "sy",
                "show_avatars": False,
                "chat_times": ["10:11", "10:27", "10:34"],
                "body": "\n".join(
                    [
                        "同事：刚看见热搜",
                        "同事：工作留痕的重要性",
                        "我：我现在啥事都发文字确认",
                        "同事：我也是，口头说完还要补一句收到",
                        "我：事要留痕，但心别留疤",
                    ]
                ),
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="wechat-reference-style",
    )

    image = cv2.imread(str(Path(result["generated_image_paths"][0])), cv2.IMREAD_COLOR)
    assert image is not None
    # The simplified transcript removes phone header/footer chrome.
    assert _count_near_color_pixels(
        image,
        x1=0,
        y1=0,
        x2=1080,
        y2=120,
        color=(18, 18, 18),
        tolerance=4,
    ) > 110000
    assert _count_near_color_pixels(
        image,
        x1=745,
        y1=1320,
        x2=815,
        y2=1395,
        color=(42, 42, 44),
        tolerance=8,
    ) < 300
    # No avatar squares should be painted in the left gutter.
    assert _count_bright_pixels(image, x1=24, y1=220, x2=126, y2=1120) < 1200


def test_wechat_header_title_avoids_long_post_title() -> None:
    assert (
        _wechat_header_title_from_payload(
            {
                "title": "520后劲最大的文案，我选苏轼这句",
                "image_text": "520别只发我爱你\n但愿人长久。",
            }
        )
        == "朋友"
    )
    assert (
        _wechat_header_title_from_payload(
            {
                "title": "520后劲最大的文案，我选苏轼这句",
                "chat_title": "阿晚",
            }
        )
        == "阿晚"
    )


def test_wechat_explicit_body_messages_preserve_speaker_names() -> None:
    messages = _chat_messages_from_payload(
        {
            "style": "wechat_chat_v1",
            "body": "\n".join(
                [
                    "同事：刚看见热搜",
                    "同事：工作留痕的重要性",
                    "我：我现在啥事都发文字确认",
                ]
            ),
        }
    )

    assert messages == [
        ("同事", "刚看见热搜"),
        ("同事", "工作留痕的重要性"),
        ("我", "我现在啥事都发文字确认"),
    ]


def test_wechat_low_density_image_text_does_not_pull_body_summary() -> None:
    messages = _chat_messages_from_payload(
        {
            "style": "wechat_chat_v1",
            "title": "520后劲最大的文案，我选苏轼这句",
            "image_text": "520别只发我爱你\n但愿人长久。",
            "body": (
                "刷到满屏520文案，礼物、转账、玫瑰花，翻到第10条就开始"
                "审美疲劳。然后我想起苏轼那句。"
            ),
            "image_plan": {
                "role": "cover_hook",
                "text_density": "low",
                "max_text_units": "2",
            },
        }
    )

    assert messages == [
        ("other", "520别只发我爱你"),
        ("me", "但愿人长久。"),
    ]


def test_wechat_low_density_final_comma_is_closed_as_sentence() -> None:
    messages = _chat_messages_from_payload(
        {
            "style": "wechat_chat_v1",
            "image_text": "520别只发我爱你\n但愿人长久，",
            "image_plan": {
                "role": "cover_hook",
                "text_density": "low",
                "max_text_units": "2",
            },
        }
    )

    assert messages == [
        ("other", "520别只发我爱你"),
        ("me", "但愿人长久。"),
    ]


def test_note_card_backend_unknown_style_falls_back_to_note_card(tmp_path: Path) -> None:
    backend = NoteCardImageBackend(width=540, height=720)

    result = backend.generate(
        prompt=json.dumps(
            {
                "style": "unknown-phone-style",
                "title": "普通人看懂AI更新",
                "body": "这是一张本地兜底封面。",
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="fallback",
    )

    assert result["style"] == "xhs_note_card_v1"


def test_psychology_text_card_renders_role_aware_1080x1440_variants(
    tmp_path: Path,
) -> None:
    backend = NoteCardImageBackend()
    common = {
        "style": "psychology_text_card_v1",
        "headline": "消息没回，不等于关系结束",
        "body_lines": ["先分开事实、猜测和需要"],
        "page_count": 6,
    }

    cover_result = backend.generate(
        prompt=json.dumps(
            {**common, "slide_id": "cover", "order": 1, "role": "cover_hook"},
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="cover",
    )
    tool_result = backend.generate(
        prompt=json.dumps(
            {**common, "slide_id": "tool", "order": 4, "role": "save_tool"},
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="tool",
    )

    cover = Image.open(Path(cover_result["generated_image_paths"][0])).convert("RGB")
    tool = Image.open(Path(tool_result["generated_image_paths"][0])).convert("RGB")
    assert cover_result["style"] == "psychology_text_card_v1"
    assert tool_result["style"] == "psychology_text_card_v1"
    assert cover.size == (1080, 1440)
    assert tool.size == (1080, 1440)
    assert cover.getextrema() != ((255, 255), (255, 255), (255, 255))
    assert tool.getextrema() != ((255, 255), (255, 255), (255, 255))
    assert ImageChops.difference(cover, tool).getbbox() is not None


def test_psychology_text_card_wraps_maximum_legal_copy_without_drawing_post_fields(
    monkeypatch,
    tmp_path: Path,
) -> None:
    drawn: list[tuple[tuple[float, float], str, object]] = []
    original_text = ImageDraw.ImageDraw.text

    def capture_text(self, xy, text, *args, **kwargs):
        drawn.append((xy, str(text), kwargs.get("font")))
        return original_text(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture_text)
    headline = "关系里的不确定感先放回事实这一边看看再慢慢决定下一步再看"
    body_lines = [
        "事实是消息暂时没有回复并不等于关系已经结束先停一下再看眼前能确认的部分再看看",
        "猜测是我把沉默自动翻译成对方准备离开先把这个故事放在纸上而不是当成答案再看看",
        "需要是我想确认彼此现在如何理解这段关系也想知道自己真正需要怎样的回应再慢慢看",
        "先写下事实猜测需要再决定要不要发出询问给身体一点时间从警报里慢慢回来再慢慢看",
    ]
    assert len(headline) == 28
    assert all(len(line) == 38 for line in body_lines)

    result = NoteCardImageBackend().generate(
        prompt=json.dumps(
            {
                "style": "psychology_text_card_v1",
                "slide_id": "tool",
                "order": 4,
                "role": "save_tool",
                "headline": headline,
                "body_lines": body_lines,
                "page_count": 6,
                "title": "绝不能进入图片的帖子标题",
                "image_text": "绝不能进入图片的旧封面字",
                "body": "绝不能进入图片的整段正文",
                "hashtags": ["#心理学", "#关系边界"],
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="bounded",
    )

    rendered_text = "".join(text for _, text, _ in drawn)
    assert headline in rendered_text
    assert all(line in rendered_text for line in body_lines)
    assert "今晚试试" in rendered_text
    assert "04 / 06" in rendered_text
    assert "绝不能进入图片" not in rendered_text
    assert "#" not in rendered_text
    for (x, y), text, font in drawn:
        assert x >= 0
        assert y >= 0
        bbox = ImageDraw.Draw(Image.new("RGB", (1080, 1440))).textbbox(
            (x, y), text, font=font
        )
        assert bbox[2] <= 1010
        assert bbox[3] <= 1360


def test_psychology_text_card_uses_warm_editorial_type_hierarchy(
    monkeypatch,
    tmp_path: Path,
) -> None:
    drawn: list[tuple[tuple[float, float], str, object]] = []
    original_text = ImageDraw.ImageDraw.text

    def capture_text(self, xy, text, *args, **kwargs):
        drawn.append((xy, str(text), kwargs.get("font")))
        return original_text(self, xy, text, *args, **kwargs)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture_text)

    NoteCardImageBackend().generate(
        prompt=json.dumps(
            {
                "style": "psychology_text_card_v1",
                "slide_id": "tool",
                "order": 4,
                "role": "save_tool",
                "headline": "今晚，只做一个小动作",
                "body_lines": ["写下事实", "写下猜测", "留一个下一步"],
                "page_count": 7,
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="editorial",
    )

    by_text = {text: (xy, font) for xy, text, font in drawn}
    assert "今晚试试" in by_text
    assert "04 / 07" in by_text
    headline_xy, headline_font = by_text["今晚，只做一个小动作"]
    body_xy, body_font = by_text["写下事实"]
    assert headline_xy == (140, 310)
    assert body_xy[0] == 178
    assert body_xy[1] > headline_xy[1] + 100
    assert headline_font.size == 58
    assert body_font.size == 36


def test_psychology_text_card_alias_selects_dedicated_style(tmp_path: Path) -> None:
    result = NoteCardImageBackend(width=540, height=720).generate(
        prompt=json.dumps(
            {
                "style": "psychology_text_card",
                "slide_id": "cover",
                "order": 1,
                "role": "cover_hook",
                "headline": "先别急着给沉默下结论",
                "body_lines": ["从事实开始看"],
                "page_count": 4,
            },
            ensure_ascii=False,
        ),
        output_dir=tmp_path,
        output_stem="alias",
    )

    assert result["style"] == "psychology_text_card_v1"
