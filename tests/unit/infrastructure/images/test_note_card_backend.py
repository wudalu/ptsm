from __future__ import annotations

import json
from pathlib import Path

import cv2

from ptsm.infrastructure.images.note_card_backend import NoteCardImageBackend


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
