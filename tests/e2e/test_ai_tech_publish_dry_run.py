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


def test_run_playbook_cli_outputs_prompt_builder_ai_tech_receipt(capsys) -> None:
    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "想模拟一条教普通人写好 prompt 的小红书帖子，重点是让 AI 先问清楚再输出",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
            "--thread-id",
            "thread-ai-tech-prompt-builder-cli",
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
    assert "任务" in body
    assert "背景" in body
    assert "输出格式" in body
    assert "反例" in body or "失败样例" in body
    assert "直接复制" in body
    assert "你是一个" in body
    assert "如果信息不够" in body
    assert "请先问我" in body
    assert "不要编造" in body
    assert "评论区" in body
    assert not any(
        leaked in body
        for leaked in ("save_tool", "comment_chain", "模板要求")
    )
