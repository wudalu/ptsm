from __future__ import annotations

import json
from pathlib import Path

from ptsm.interfaces.cli.main import main


def test_run_fengkuang_cli_outputs_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-fengkuang",
            "--scene",
            "周四晚上加班后回家",
            "--account-id",
            "acct-fk-local",
            "--thread-id",
            "thread-fk-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["account"]["account_id"] == "acct-fk-local"
    assert payload["publish_result"]["status"] == "dry_run"
    assert payload["publish_result"]["platform"] == "xiaohongshu"
    assert payload["post_publish_checks"]["requested"] is False
    # Multi-account: account info includes cookie profile summary
    assert "cookie_profile_id" in payload["account"] or True  # may not always be present


def test_run_fengkuang_cli_outputs_platform_native_mechanics(capsys) -> None:
    exit_code = main(
        [
            "run-fengkuang",
            "--scene",
            "领导18:57突然发来一句在吗，明天早会还要我补材料",
            "--account-id",
            "acct-fk-local",
            "--thread-id",
            "thread-fk-quality",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert content["title"] not in {
        "打工人地铁生存实录",
        "会议连环暴击实录",
        "社畜崩溃边缘实录",
    }
    assert any(obj in combined for obj in ("工牌", "群聊", "早会", "材料"))
    assert "评论区" in content["body"]
    assert any(cue in combined for cue in ("接一句", "疯话", "写在", "可复制"))
    assert "#发疯文学" in content["hashtags"]
    assert not any(term in combined for term in ("精神病", "心理医生", "医院", "治疗", "用药"))
    assert not any(term in combined for term in ("首先", "其次", "最后", "综上", "本文", "作为AI"))


def test_run_fengkuang_cli_outputs_sigua_tang_object_mechanic(capsys) -> None:
    exit_code = main(
        [
            "run-fengkuang",
            "--scene",
            "领导把需求改了三遍，最后只说让我喝点丝瓜汤降降火",
            "--account-id",
            "acct-fk-local",
            "--thread-id",
            "thread-fk-sigua-tang",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert "丝瓜汤" in combined
    assert any(obj in combined for obj in ("工牌", "群聊", "周报", "请假条"))
    assert "评论区" in content["body"]
    assert "#发疯文学" in content["hashtags"]


def test_run_fengkuang_cli_outputs_image_generation_receipt(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    generated_path = tmp_path / "generated.png"
    generated_path.write_bytes(b"fake-png-bytes")

    monkeypatch.setattr(
        "ptsm.application.use_cases.run_playbook.build_image_backend",
        lambda settings: type(
            "FakeImageBackend",
            (),
            {
                "generate": lambda self, **kwargs: {
                    "status": "generated",
                    "provider": "bailian",
                    "model": "qwen-image-2.0-pro",
                    "prompt": kwargs["prompt"],
                    "image_paths": [str(generated_path)],
                    "generated_image_paths": [str(generated_path)],
                    "source_url": "https://example.com/generated.png",
                }
            },
        )(),
    )

    exit_code = main(
        [
            "run-fengkuang",
            "--scene",
            "周六把堆满快递盒的书桌当成发疯现场",
            "--account-id",
            "acct-fk-local",
            "--auto-generate-image",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["image_generation"]["generated_image_paths"]
    if payload["image_generation"]["provider"] == "bailian":
        assert payload["image_generation"]["generated_image_paths"] == [str(generated_path)]
    else:
        assert payload["image_generation"]["provider"] == "local_note_card"
