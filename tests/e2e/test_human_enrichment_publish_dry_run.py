from __future__ import annotations

import json

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_human_enrichment_mechanics(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "把下班后的书桌从堆满快递盒改成一个十分钟手作角",
            "--account-id",
            "acct-enrichment-local",
            "--playbook-id",
            "human_enrichment_daily_post",
            "--thread-id",
            "thread-human-enrichment-cli",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "human_enrichment_daily_post"
    assert payload["account"]["account_id"] == "acct-enrichment-local"
    assert "#人类丰容计划" in content["hashtags"]
    assert any(term in combined for term in ("变量", "微调", "三步", "清单"))
    assert "评论区" in content["body"]
    assert not any(term in combined for term in ("治好", "诊断", "用药"))

    get_settings.cache_clear()
