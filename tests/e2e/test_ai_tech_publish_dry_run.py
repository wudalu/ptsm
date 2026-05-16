from __future__ import annotations

import json

from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_ai_tech_publish_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "OpenAI 发布一项新的多模态助手更新，普通用户想知道到底值不值得试",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
            "--thread-id",
            "thread-ai-tech-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    body = payload["final_content"]["body"]

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "ai_tech_daily_post"
    assert payload["publish_result"]["status"] == "dry_run"
    assert "#AI资讯" in payload["final_content"]["hashtags"]
    assert "是什么" in body
    assert "为什么重要" in body
    assert "普通人" in body
    assert "收藏" in body
    assert "评论区" in body
