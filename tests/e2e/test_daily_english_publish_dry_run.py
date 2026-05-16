from __future__ import annotations

import json

from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_daily_english_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "想学一个开会和私聊都能用的英语表达",
            "--account-id",
            "acct-daily-english-local",
            "--playbook-id",
            "daily_english_post",
            "--thread-id",
            "thread-daily-english-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    body = payload["final_content"]["body"]

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "daily_english_post"
    assert payload["publish_result"]["status"] == "dry_run"
    assert "#每日英语" in payload["final_content"]["hashtags"]
    for term in ["音标", "词性", "例句", "翻译", "造句"]:
        assert term in body
    assert "评论区" in body
