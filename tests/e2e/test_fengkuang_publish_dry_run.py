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
            "周六社畜躺平",
            "--account-id",
            "acct-fk-local",
            "--auto-generate-image",
        ]
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["image_generation"]["provider"] == "bailian"
    assert payload["image_generation"]["generated_image_paths"] == [str(generated_path)]
