from __future__ import annotations

import json

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_modern_psychology_publish_receipt(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "下班后还在反复复盘白天一句话",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--thread-id",
            "thread-modern-psychology-cli",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "modern_psychology_post"
    assert "反刍思维" in payload["final_content"]["body"]
    assert "专业帮助" in payload["final_content"]["body"]
    assert "#心理学" in payload["final_content"]["hashtags"]
    assert "治好焦虑" not in payload["final_content"]["body"]

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_modern_psychology_mechanics(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "下班路上还在反复复盘会议里一句话，越想越尴尬",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--thread-id",
            "thread-modern-psychology-quality",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert content["title"] != "下班后还在复盘那句话"
    assert content["image_text"] != "脑子还没下班"
    assert "下班路上还在反复复盘会议里一句话" in content["body"]
    assert content["body"].index("下班路上还在反复复盘会议里一句话") < content[
        "body"
    ].index("反刍思维")
    assert any(term in combined for term in ("不是你太敏感", "不是你想太多"))
    assert any(tool in content["body"] for tool in ("事实 / 猜测 / 下一步", "三栏"))
    assert "评论区" in content["body"]
    assert any(prompt in content["body"] for prompt in ("你最容易", "哪类瞬间"))
    assert "专业帮助" in content["body"]
    assert any(tag in content["hashtags"] for tag in ("#心理学", "#情绪管理"))
    assert not any(term in combined for term in ("诊断", "治好焦虑", "治愈抑郁", "用药"))
    assert not any(term in combined for term in ("首先", "其次", "最后", "综上", "本文", "作为AI"))

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_sandwich_refusal_boundary_tool(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "同事临时让我帮忙收尾，我想用三明治拒绝法拒绝但又怕显得冷漠",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--thread-id",
            "thread-modern-psychology-sandwich",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert "三明治拒绝法" in combined
    assert "边界句" in content["body"]
    assert "专业帮助" in content["body"]
    assert "评论区" in content["body"]
    assert "#心理学" in content["hashtags"]
    assert not any(term in combined for term in ("诊断", "治好焦虑", "用药"))

    get_settings.cache_clear()
