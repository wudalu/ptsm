from __future__ import annotations

import json
from pathlib import Path

import cv2

from ptsm.infrastructure.images.note_card_backend import (
    NoteCardImageBackend,
    _select_display_body,
)


def _count_wechat_green_pixels(image) -> int:
    channels = image.astype("int16")
    green_pixels = (
        (channels[:, :, 1] > channels[:, :, 0] + 50)
        & (channels[:, :, 1] > channels[:, :, 2] + 50)
    )
    return int(green_pixels.sum())


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
    assert output_path.exists()
    assert output_path.suffix == ".png"

    image = cv2.imread(str(output_path), cv2.IMREAD_GRAYSCALE)
    assert image is not None
    assert image.shape == (1440, 1080)
    assert int(image.min()) < int(image.max())


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
