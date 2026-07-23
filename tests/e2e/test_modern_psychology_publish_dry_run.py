from __future__ import annotations

import json

from ptsm.config.settings import get_settings
from ptsm.domain.psychology_learning import (
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
)
from ptsm.interfaces.cli.main import main


PSYCHOLOGY_TITLE_FORBIDDEN = (
    "不是你",
    "反刍思维",
    "低控制感",
    "边界压力",
    "灾难化思维",
    "心理机制",
)
DRAMATIC_TITLE_CUES = (
    "那一秒",
    "不是",
    "别",
    "却",
    "反而",
    "突然",
    "原来",
    "被",
    "最累",
    "先别",
    "救",
    "拖回",
)


def test_run_playbook_cli_outputs_modern_psychology_publish_receipt(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
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
    content = payload["final_content"]
    assert 200 <= len(content["body"]) <= 380
    assert not any(term in content["title"] for term in PSYCHOLOGY_TITLE_FORBIDDEN)
    assert "专业帮助" in content["body"]
    assert "#心理学" in payload["final_content"]["hashtags"]
    assert "治好焦虑" not in payload["final_content"]["body"]

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_psychology_learning_series_lesson(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--psychology-content-mode",
            "learning_series",
            "--psychology-series-id",
            "after_work_rumination",
            "--psychology-lesson-id",
            "notice_the_loop",
            "--psychology-curriculum-version",
            "1",
            "--topic-direction-id",
            "psychology_learning_after_work_rumination_notice_the_loop",
            "--publish-mode",
            "dry-run",
            "--thread-id",
            "thread-modern-psychology-learning-series",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    bundle = resolve_psychology_learning_selection(
        series_id="after_work_rumination",
        lesson_id="notice_the_loop",
        curriculum_version="1",
    )

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert validate_psychology_learning_draft_contract(
        bundle.runtime_contract, content
    ) == []
    assert 200 <= len(content["body"]) <= 380
    assert payload["psychology_learning_series_id"] == "after_work_rumination"
    assert payload["psychology_learning_lesson_id"] == "notice_the_loop"
    assert payload["psychology_learning_gate"]["status"] == "passed"
    assert payload["psychology_learning_evidence_manifest"] == bundle.manifest
    assert "source:" not in json.dumps(content, ensure_ascii=False)
    assert "https://" not in json.dumps(payload, ensure_ascii=False)

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_modern_psychology_mechanics(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
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
    assert 200 <= len(content["body"]) <= 380
    assert not any(term in content["title"] for term in PSYCHOLOGY_TITLE_FORBIDDEN)
    assert "下班路上还在反复复盘会议里一句话" in content["body"]
    assert content["body"].index("下班路上还在反复复盘会议里一句话") < content[
        "body"
    ].index("反刍思维")
    assert content["body"].index("反刍思维") >= 120
    assert content["body"].count("反刍思维") <= 1
    assert "不是你" not in combined
    assert "这不是" not in combined
    assert any(tool in content["body"] for tool in ("写下来", "备忘录", "存"))
    assert any(prompt in content["body"] for prompt in ("哪派", "A.", "B.", "____"))
    assert "专业帮助" in content["body"]
    assert any(tag in content["hashtags"] for tag in ("#心理学", "#情绪管理"))
    assert not any(term in combined for term in ("诊断", "治好焦虑", "治愈抑郁", "用药"))
    assert not any(term in combined for term in ("首先", "其次", "最后", "综上", "本文", "作为AI"))

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_sandwich_refusal_boundary_tool(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
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
    assert "三明治拒绝法" in content["body"]
    assert "三明治拒绝法" not in content["title"]
    assert "边界句" in content["body"]
    assert "专业帮助" in content["body"]
    assert any(prompt in content["body"] for prompt in ("哪派", "A.", "B.", "____"))
    assert "#心理学" in content["hashtags"]
    assert not any(term in combined for term in ("诊断", "治好焦虑", "用药"))

    get_settings.cache_clear()


def test_run_playbook_cli_outputs_sleep_recovery_growth_sublane(
    capsys, monkeypatch, tmp_path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            "办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号",
            "--account-id",
            "acct-psychology-local",
            "--playbook-id",
            "modern_psychology_post",
            "--thread-id",
            "thread-modern-psychology-sleep-recovery",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]
    combined = f"{content['title']}\n{content['image_text']}\n{content['body']}"

    assert exit_code == 0
    assert len(content["title"]) <= 22
    assert any(cue in content["title"] for cue in DRAMATIC_TITLE_CUES)
    assert 200 <= len(content["body"]) <= 380
    assert any(signal in content["body"] for signal in ("睡眠恢复", "轻养生", "下班信号"))
    assert any(tool in content["body"] for tool in ("5分钟", "5 分钟", "下班信号"))
    assert any(prompt in content["body"] for prompt in ("哪派", "A.", "B.", "____"))
    assert "专业帮助" in content["body"]
    assert any(tag in content["hashtags"] for tag in ("#心理学", "#情绪管理"))
    assert not any(term in content["title"] for term in PSYCHOLOGY_TITLE_FORBIDDEN)
    assert not any(term in combined for term in ("诊断", "治好焦虑", "治愈抑郁", "用药"))
    assert not any(term in content["body"] for term in ("原话", "脑补", "审判", "扣分"))
    assert not any(term in content["body"] for term in ("保证立刻", "改善睡眠", "治疗睡眠"))

    get_settings.cache_clear()
