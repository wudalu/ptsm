from __future__ import annotations

import json

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
