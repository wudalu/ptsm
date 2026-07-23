from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
    plan_psychology_learning_series,
)
from ptsm.application.use_cases.xhs_post_metrics import (
    record_xhs_post_metrics,
    summarize_xhs_post_metrics,
)
from ptsm.domain.psychology_learning import (
    build_psychology_learning_catalog_receipt,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
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


def _write_learning_artifact(
    path: Path,
    *,
    lesson_id: str = "notice_the_loop",
    bundle=None,
) -> None:
    if bundle is None:
        bundle = resolve_psychology_learning_selection(
            series_id="after_work_rumination",
            lesson_id=lesson_id,
        )
    contract = bundle.runtime_contract
    payload = {
        "playbook_id": "modern_psychology_post",
        "account": {
            "account_id": "acct-psychology-local",
            "platform": "xiaohongshu",
        },
        "platform": "xiaohongshu",
        "scene": f"心理学学习专题：{contract['series_badge']}｜{contract['lesson_title']}",
        "publish_mode": "dry-run",
        "activated_skills": [],
        "activated_skill_details": [],
        "final_content": render_psychology_learning_draft(contract),
        "format_patterns_used": {"status": "not_used"},
        "publish_result": {"status": "dry_run"},
        "topic_selection": {
            "source": "psychology-learning-series",
            "psychology_learning": {
                "series_id": bundle.series_id,
                "curriculum_version": contract["curriculum_version"],
                "lesson_id": bundle.lesson_id,
                "lesson_number": bundle.lesson_number,
            },
        },
        "psychology_learning_mode": "learning_series",
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": contract["curriculum_version"],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
        "psychology_learning_evidence_manifest": bundle.manifest,
        "psychology_learning_gate": {
            "status": "passed",
            "series_id": bundle.series_id,
            "lesson_id": bundle.lesson_id,
            "validator": "psychology_learning_draft_contract",
            "validator_version": "1",
            "errors": [],
        },
    }
    catalog_receipt = build_psychology_learning_catalog_receipt(bundle)
    if catalog_receipt is not None:
        payload["psychology_learning_catalog_receipt"] = catalog_receipt
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


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


def test_record_xhs_post_metrics_captures_and_groups_learning_series_fields(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "learning-artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    _write_learning_artifact(artifact_path)

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=4,
        comments=2,
        shares=1,
        output_path=metrics_path,
    )

    record = result["record"]
    assert record["psychology_learning_series_id"] == "after_work_rumination"
    assert record["psychology_learning_curriculum_version"] == "1"
    assert record["psychology_learning_lesson_id"] == "notice_the_loop"
    assert record["psychology_learning_lesson_number"] == 1
    assert record["psychology_learning_mode"] == "learning_series"
    assert record["topic_direction_id"] == (
        "psychology_learning_after_work_rumination_notice_the_loop"
    )
    summary = summarize_xhs_post_metrics(
        input_path=metrics_path,
        group_by="psychology_learning_series_id",
    )
    assert summary["groups"][0]["group"] == "after_work_rumination"


def test_record_xhs_post_metrics_rejects_an_unverified_learning_receipt(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "unverified-learning-artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    artifact_path.write_text(
        json.dumps(
            {
                "playbook_id": "modern_psychology_post",
                "psychology_learning_mode": "learning_series",
                "psychology_learning_series_id": "after_work_rumination",
                "psychology_learning_lesson_id": "notice_the_loop",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=4,
        comments=2,
        shares=1,
        output_path=metrics_path,
    )

    assert result["status"] == "error"
    assert "learning receipt" in result["reason"]
    assert not metrics_path.exists()


def test_record_xhs_post_metrics_accepts_confirmed_custom_catalog_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifact_path = tmp_path / "custom-learning-artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻"},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore()
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id=catalog.lessons[0].lesson_id,
        curriculum_version=catalog.curriculum_version,
    )
    _write_learning_artifact(artifact_path, bundle=bundle)

    assert bundle.catalog is not None
    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=4,
        comments=2,
        shares=1,
        output_path=metrics_path,
    )

    assert result["status"] == "recorded"
    assert result["record"]["psychology_learning_series_id"] == catalog.series_id
    assert metrics_path.exists()


def test_record_xhs_post_metrics_rejects_a_tampered_custom_catalog_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    private_goal = "确认前私有目标，绝不应进入指标记录"
    artifact_path = tmp_path / "custom-learning-artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    proposal = plan_psychology_learning_series(
        topic="下班后的脑内回放",
        outline=(
            {"id": "notice", "title": "先识别重复时刻", "goal": private_goal},
            {"id": "practice", "title": "练习一个小步骤"},
        ),
    )
    store = PsychologyLearningSeriesStore()
    store.persist_proposal(proposal)
    catalog = store.confirm(
        proposal_id=proposal.proposal_id,
        proposal_fingerprint=proposal.proposal_fingerprint,
    )
    bundle = resolve_psychology_learning_selection(
        series_id=catalog.series_id,
        lesson_id="notice",
        curriculum_version=catalog.curriculum_version,
    )
    _write_learning_artifact(artifact_path, bundle=bundle)
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    artifact["psychology_learning_catalog_receipt"]["catalog_digest"] = (
        "catalog:tampered"
    )
    artifact_path.write_text(json.dumps(artifact, ensure_ascii=False), encoding="utf-8")

    result = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=4,
        comments=2,
        shares=1,
        output_path=metrics_path,
    )

    assert result == {"status": "error", "reason": "invalid psychology learning receipt"}
    assert private_goal not in json.dumps(result, ensure_ascii=False)
    assert not metrics_path.exists()


def test_learning_metric_groups_exclude_ordinary_psychology_rows(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    records = [
        {
            "artifact_path": "ordinary.json",
            "playbook_id": "modern_psychology_post",
            "checkpoint": "24h",
            "psychology_learning_mode": "",
            "psychology_learning_series_id": "",
            "interaction_score": 12,
            "interaction_rate": 0.12,
            "like_rate": 0.1,
            "views": 100,
        },
        {
            "artifact_path": "lesson.json",
            "playbook_id": "modern_psychology_post",
            "checkpoint": "24h",
            "psychology_learning_mode": "learning_series",
            "psychology_learning_series_id": "after_work_rumination",
            "psychology_learning_curriculum_version": "1",
            "psychology_learning_lesson_id": "notice_the_loop",
            "interaction_score": 24,
            "interaction_rate": 0.24,
            "like_rate": 0.2,
            "views": 100,
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
        group_by="psychology_learning_series_id",
    )

    assert result["records_count"] == 1
    assert [group["group"] for group in result["groups"]] == [
        "after_work_rumination"
    ]


def test_record_xhs_post_metrics_upserts_a_checkpoint_for_the_same_artifact(
    tmp_path: Path,
) -> None:
    artifact_path = tmp_path / "learning-artifact.json"
    metrics_path = tmp_path / "metrics.jsonl"
    _write_learning_artifact(artifact_path)

    first = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=100,
        likes=10,
        collects=4,
        comments=2,
        shares=1,
        output_path=metrics_path,
    )
    second = record_xhs_post_metrics(
        artifact_path=artifact_path,
        checkpoint="24h",
        views=200,
        likes=20,
        collects=8,
        comments=4,
        shares=2,
        output_path=metrics_path,
    )

    assert first["status"] == "recorded"
    assert second["status"] == "recorded"
    [record] = _read_jsonl(metrics_path)
    assert record["views"] == 200
    summary = summarize_xhs_post_metrics(
        input_path=metrics_path,
        group_by="psychology_learning_lesson_id",
    )
    assert summary["records_count"] == 1
    assert summary["groups"][0]["posts"] == 1


def test_summarize_xhs_post_metrics_can_group_learning_rows_by_curriculum_version(
    tmp_path: Path,
) -> None:
    metrics_path = tmp_path / "metrics.jsonl"
    metrics_path.write_text(
        json.dumps(
            {
                "artifact_path": "lesson.json",
                "playbook_id": "modern_psychology_post",
                "checkpoint": "24h",
                "psychology_learning_mode": "learning_series",
                "psychology_learning_series_id": "after_work_rumination",
                "psychology_learning_curriculum_version": "1",
                "psychology_learning_lesson_id": "notice_the_loop",
                "views": 100,
                "interaction_score": 24,
                "interaction_rate": 0.24,
                "like_rate": 0.2,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = summarize_xhs_post_metrics(
        input_path=metrics_path,
        group_by="psychology_learning_curriculum_version",
    )

    assert result["groups"][0]["group"] == "1"


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
