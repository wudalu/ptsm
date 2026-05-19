from __future__ import annotations

import json

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_world_cup_mechanics(capsys, monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点",
            "--account-id",
            "acct-world-cup-local",
            "--playbook-id",
            "world_cup_daily_post",
            "--thread-id",
            "thread-world-cup-cli",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "world_cup_daily_post"
    assert payload["account"]["account_id"] == "acct-world-cup-local"
    assert "#世界杯" in content["hashtags"]
    assert "普通球迷" in content["body"]
    assert any(term in combined for term in ("赛前", "看点", "看球"))
    assert any(term in content["body"] for term in ("看球清单", "清单", "收藏"))
    assert "评论区" in content["body"]
    assert not any(
        term in combined
        for term in ("稳赚", "下注", "盘口", "预测比分", "内部消息", "官方消息")
    )

    get_settings.cache_clear()
