from __future__ import annotations

import json

from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_wuxia_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
            "--account-id",
            "acct-wuxia-local",
            "--playbook-id",
            "wuxia_character_post",
            "--thread-id",
            "thread-wuxia-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "wuxia_character_post"
    assert "令狐冲" in payload["final_content"]["body"]
    assert "原文" in payload["final_content"]["body"]
    assert "截图" in payload["final_content"]["body"]
    assert "评论区" in payload["final_content"]["body"]
    assert "#金庸" in payload["final_content"]["hashtags"]
    assert len(payload["final_content"]["body"]) >= 800
