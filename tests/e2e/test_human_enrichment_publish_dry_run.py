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
    assert not any(term in combined for term in ("首先", "其次", "最后", "综上", "本文", "作为AI"))

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_solo_living_handcraft_enrichment(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "一个人住以后想按适我主义改床头角落，把旧材料做成十分钟手作心流",
            "--account-id",
            "acct-enrichment-local",
            "--playbook-id",
            "human_enrichment_daily_post",
            "--thread-id",
            "thread-human-enrichment-solo-handcraft",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert any(term in combined for term in ("适我主义", "新独居", "手作心流"))
    assert any(term in combined for term in ("旧材料", "床头", "角落"))
    assert any(term in combined for term in ("三步", "清单", "十分钟"))
    assert "评论区" in content["body"]
    assert "#人类丰容计划" in content["hashtags"]

    get_settings.cache_clear()
