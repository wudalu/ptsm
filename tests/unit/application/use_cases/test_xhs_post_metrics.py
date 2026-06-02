from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.use_cases.xhs_post_metrics import (
    record_xhs_post_metrics,
    summarize_xhs_post_metrics,
)


def _write_psychology_artifact(path: Path) -> None:
    payload = {
        "playbook_id": "modern_psychology_post",
        "scene": "办公室下班后还是很紧绷",
        "account": {
            "account_id": "acct-psychology-local",
            "platform": "xiaohongshu",
        },
        "topic_selection": {
            "topic_direction_id": "sleep_recovery_shutdown_card",
        },
        "final_content": {
            "title": "下班后身体被拖回工位",
            "image_text": "5分钟给身体下班信号",
            "hashtags": ["#心理学", "#睡眠恢复"],
        },
        "content_review": {
            "image_plan": {"style": "iphone_notes", "role": "save_tool"},
        },
        "publish_result": {"status": "published", "post_id": "xhs-1"},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_record_xhs_post_metrics_writes_artifact_linked_score_row(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    _write_psychology_artifact(artifact_path)

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=1000,
        likes=80,
        collects=60,
        comments=8,
        shares=2,
        output_path=metrics_path,
        decision="keep",
        notes="collects close to likes",
    )

    assert result["status"] == "recorded"
    assert result["output_path"] == str(metrics_path)
    assert metrics_path.exists()

    [record] = _read_jsonl(metrics_path)
    assert record["artifact_path"] == str(artifact_path)
    assert record["playbook_id"] == "modern_psychology_post"
    assert record["account_id"] == "acct-psychology-local"
    assert record["platform"] == "xiaohongshu"
    assert record["topic_direction_id"] == "sleep_recovery_shutdown_card"
    assert record["title"] == "下班后身体被拖回工位"
    assert record["image_text"] == "5分钟给身体下班信号"
    assert record["image_style"] == "iphone_notes"
    assert record["image_role"] == "save_tool"
    assert record["post_id"] == "xhs-1"
    assert record["checkpoint"] == "24h"
    assert record["views"] == 1000
    assert record["likes"] == 80
    assert record["collects"] == 60
    assert record["comments"] == 8
    assert record["shares"] == 2
    assert record["interaction_score"] == 244
    assert record["interaction_rate"] == pytest.approx(0.244)
    assert record["like_rate"] == pytest.approx(0.08)
    assert record["decision"] == "keep"
    assert record["notes"] == "collects close to likes"
    assert result["record"]["interaction_score"] == 244


def test_record_xhs_post_metrics_reads_local_style_image_plan(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    payload = {
        "playbook_id": "modern_psychology_post",
        "account": {"account_id": "acct-psychology-local"},
        "topic_selection": {"topic_direction_id": "sleep_recovery_shutdown_card"},
        "final_content": {"title": "下班后身体被拖回工位"},
        "content_review": {
            "image_plan": {"local_style": "iphone_notes", "role": "save_tool"},
        },
    }
    artifact_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=5,
        comments=1,
        shares=0,
        output_path=metrics_path,
    )

    assert result["status"] == "recorded"
    [record] = _read_jsonl(metrics_path)
    assert record["image_style"] == "iphone_notes"


def test_record_xhs_post_metrics_rejects_missing_artifact(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.jsonl"

    result = record_xhs_post_metrics(
        artifact_path=tmp_path / "missing.json",
        checkpoint="24h",
        views=100,
        likes=10,
        collects=2,
        comments=1,
        shares=0,
        output_path=metrics_path,
    )

    assert result["status"] == "error"
    assert "artifact not found" in result["reason"]
    assert not metrics_path.exists()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("views", -1),
        ("likes", -1),
        ("collects", -1),
        ("comments", -1),
        ("shares", -1),
    ],
)
def test_record_xhs_post_metrics_rejects_negative_metrics(
    tmp_path: Path,
    field: str,
    value: int,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    _write_psychology_artifact(artifact_path)
    kwargs = {
        "artifact_path": artifact_path,
        "checkpoint": "24h",
        "views": 100,
        "likes": 10,
        "collects": 2,
        "comments": 1,
        "shares": 0,
        "output_path": tmp_path / "metrics.jsonl",
    }
    kwargs[field] = value

    result = record_xhs_post_metrics(**kwargs)

    assert result["status"] == "error"
    assert field in result["reason"]


def test_record_xhs_post_metrics_rejects_unsupported_checkpoint(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "artifact.json"
    _write_psychology_artifact(artifact_path)

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="7d",
        views=100,
        likes=10,
        collects=2,
        comments=1,
        shares=0,
        output_path=tmp_path / "metrics.jsonl",
    )

    assert result["status"] == "error"
    assert "checkpoint" in result["reason"]


def test_summarize_xhs_post_metrics_groups_psychology_direction_performance(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    records = [
        {
            "playbook_id": "modern_psychology_post",
            "account_id": "acct-psychology-local",
            "checkpoint": "24h",
            "topic_direction_id": "sleep_recovery_shutdown_card",
            "image_style": "iphone_notes",
            "views": 1000,
            "likes": 80,
            "collects": 60,
            "comments": 8,
            "shares": 2,
            "interaction_score": 244,
            "interaction_rate": 0.244,
            "like_rate": 0.08,
        },
        {
            "playbook_id": "modern_psychology_post",
            "account_id": "acct-psychology-local",
            "checkpoint": "24h",
            "topic_direction_id": "sleep_recovery_shutdown_card",
            "image_style": "iphone_notes",
            "views": 800,
            "likes": 64,
            "collects": 56,
            "comments": 6,
            "shares": 1,
            "interaction_score": 206,
            "interaction_rate": 0.2575,
            "like_rate": 0.08,
        },
        {
            "playbook_id": "modern_psychology_post",
            "account_id": "acct-psychology-local",
            "checkpoint": "24h",
            "topic_direction_id": "boundary_sandwich_refusal",
            "image_style": "wechat_chat",
            "views": 900,
            "likes": 45,
            "collects": 20,
            "comments": 3,
            "shares": 0,
            "interaction_score": 97,
            "interaction_rate": 0.1077777778,
            "like_rate": 0.05,
        },
        {
            "playbook_id": "fengkuang_daily_post",
            "account_id": "acct-fk-local",
            "checkpoint": "24h",
            "topic_direction_id": "fk_demo",
            "image_style": "note_card",
            "views": 2000,
            "likes": 200,
            "collects": 10,
            "comments": 5,
            "shares": 1,
            "interaction_score": 246,
            "interaction_rate": 0.123,
            "like_rate": 0.1,
        },
    ]
    metrics_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    result = summarize_xhs_post_metrics(
        input_path=metrics_path,
        playbook_id="modern_psychology_post",
        checkpoint="24h",
        group_by="topic_direction_id",
    )

    assert result["status"] == "ok"
    assert result["records_count"] == 3
    assert result["group_by"] == "topic_direction_id"
    groups = result["groups"]
    assert [group["group"] for group in groups] == [
        "sleep_recovery_shutdown_card",
        "boundary_sandwich_refusal",
    ]

    sleep_group = groups[0]
    assert sleep_group["posts"] == 2
    assert sleep_group["sample_status"] == "needs_more_data"
    assert sleep_group["total_views"] == 1800
    assert sleep_group["total_likes"] == 144
    assert sleep_group["total_collects"] == 116
    assert sleep_group["total_comments"] == 14
    assert sleep_group["total_shares"] == 3
    assert sleep_group["avg_views"] == pytest.approx(900)
    assert sleep_group["avg_likes"] == pytest.approx(72)
    assert sleep_group["avg_interaction_score"] == pytest.approx(225)
    assert sleep_group["avg_interaction_rate"] == pytest.approx(0.25075)
    assert sleep_group["avg_like_rate"] == pytest.approx(0.08)


def test_summarize_xhs_post_metrics_can_group_by_image_style(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    records = [
        {
            "playbook_id": "modern_psychology_post",
            "account_id": "acct-psychology-local",
            "checkpoint": "24h",
            "topic_direction_id": "sleep_recovery_shutdown_card",
            "image_style": "iphone_notes",
            "views": 1000,
            "likes": 80,
            "collects": 60,
            "comments": 8,
            "shares": 2,
            "interaction_score": 244,
            "interaction_rate": 0.244,
            "like_rate": 0.08,
        },
        {
            "playbook_id": "modern_psychology_post",
            "account_id": "acct-psychology-local",
            "checkpoint": "24h",
            "topic_direction_id": "boundary_sandwich_refusal",
            "image_style": "wechat_chat",
            "views": 900,
            "likes": 45,
            "collects": 20,
            "comments": 3,
            "shares": 0,
            "interaction_score": 97,
            "interaction_rate": 0.1077777778,
            "like_rate": 0.05,
        },
    ]
    metrics_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n",
        encoding="utf-8",
    )

    result = summarize_xhs_post_metrics(
        input_path=metrics_path,
        playbook_id="modern_psychology_post",
        checkpoint="24h",
        group_by="image_style",
    )

    assert result["status"] == "ok"
    assert [group["group"] for group in result["groups"]] == [
        "iphone_notes",
        "wechat_chat",
    ]
