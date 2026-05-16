from __future__ import annotations

import json
from pathlib import Path

import cv2

from ptsm.infrastructure.images.note_card_backend import NoteCardImageBackend


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
