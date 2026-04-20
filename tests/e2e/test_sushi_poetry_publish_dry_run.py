from __future__ import annotations

import json

from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_sushi_poetry_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析",
            "--account-id",
            "acct-sushi-local",
            "--playbook-id",
            "sushi_poetry_daily_post",
            "--thread-id",
            "thread-sushi-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "sushi_poetry_daily_post"
    assert payload["account"]["account_id"] == "acct-sushi-local"
    assert payload["publish_result"]["status"] == "dry_run"
    assert "#苏轼" in payload["final_content"]["hashtags"]
