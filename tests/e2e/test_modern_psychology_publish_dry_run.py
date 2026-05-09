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
