from __future__ import annotations

import json

from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_classic_poetry_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "读到李白长风破浪会有时，想写给低谷里的自己",
            "--account-id",
            "acct-classic-poetry-local",
            "--playbook-id",
            "classic_poetry_quote_post",
            "--thread-id",
            "thread-classic-poetry-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "classic_poetry_quote_post"
    assert payload["account"]["account_id"] == "acct-classic-poetry-local"
    assert payload["publish_result"]["status"] == "dry_run"
    assert "#古诗词" in payload["final_content"]["hashtags"]
    assert any(
        cue in payload["final_content"]["body"]
        for cue in ("长风破浪会有时", "李白", "古诗词", "金句")
    )
    assert "#苏轼" not in payload["final_content"]["hashtags"]
    assert "评论区" in payload["final_content"]["body"]
    assert any(
        cue in payload["final_content"]["body"]
        for cue in ("存", "记下来", "可收藏", "这一句")
    )
