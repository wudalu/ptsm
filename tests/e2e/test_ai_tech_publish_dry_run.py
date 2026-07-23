from __future__ import annotations

import json
from pathlib import Path

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


FIXTURES_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ai_tech_evidence"


def test_run_playbook_cli_outputs_ai_tech_publish_receipt(capsys, monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
            "--ai-content-mode",
            "news_brief",
            "--ai-evidence-file",
            str(FIXTURES_ROOT / "news_brief.json"),
            "--topic-direction-id",
            "ai_news_three_updates_brief",
            "--publish-mode",
            "dry-run",
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
    assert "模型发布｜产品新增了长文本处理能力。" in body
    assert "开发工具｜开发者控制台加入批量任务入口。" in body
    assert "团队功能｜团队空间开放了共享项目设置。" in body
    assert payload["ai_tech_content_mode"] == "news_brief"
    assert payload["ai_tech_evidence_gate"]["status"] == "passed"
    assert "source:" not in body

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_prompt_builder_ai_tech_receipt(capsys, monkeypatch) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-ai-tech-local",
            "--playbook-id",
            "ai_tech_daily_post",
            "--ai-content-mode",
            "hands_on",
            "--ai-evidence-file",
            str(FIXTURES_ROOT / "hands_on.json"),
            "--topic-direction-id",
            "ai_prompt_clarifying_questions",
            "--publish-mode",
            "dry-run",
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
    assert "主题：提示词追问实测" in body
    assert "产品与版本：示例助手 2026.07" in body
    assert "测试日期：2026-07-22" in body
    assert "任务：把三条会议记录整理成周报" in body
    assert "输入：三条含项目进度的匿名会议记录" in body
    assert "观察：先追问缺失负责人，再给出三段式周报。" in body
    assert "局限：没有负责人信息时，输出仍需人工核对。" in body
    assert payload["ai_tech_content_mode"] == "hands_on"
    assert payload["ai_tech_evidence_gate"]["status"] == "passed"
    assert not any(
        leaked in body
        for leaked in ("save_tool", "comment_chain", "模板要求", "直接复制")
    )

    get_settings.cache_clear()
