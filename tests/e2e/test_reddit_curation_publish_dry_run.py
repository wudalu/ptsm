from __future__ import annotations

import json

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


def test_run_playbook_cli_outputs_reddit_curation_publish_receipt(
    capsys, monkeypatch
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
    monkeypatch.delenv("REDDIT_PUBLIC_JSON_FALLBACK", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度",
            "--account-id",
            "acct-reddit-curation-local",
            "--playbook-id",
            "reddit_curation_daily_post",
            "--thread-id",
            "thread-reddit-curation-cli",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["playbook_id"] == "reddit_curation_daily_post"
    assert payload["account"]["account_id"] == "acct-reddit-curation-local"
    assert payload["publish_result"]["status"] == "dry_run"
    assert "#Reddit" in content["hashtags"]
    assert "Reddit" in content["body"]
    assert "英文讨论" in content["body"]
    assert "中文" in content["body"] or "翻成中文" in content["body"]
    assert "收藏" in content["body"]
    assert "评论区" in content["body"]
    assert any(
        detail["skill_name"] == "reddit_discussion_scan"
        for detail in payload["runtime_skill_details"]
    )

    get_settings.cache_clear()
