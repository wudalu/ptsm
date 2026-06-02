from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


DEFAULT_POST_METRICS_PATH = Path("outputs/artifacts/xhs-post-metrics/metrics.jsonl")
VALID_CHECKPOINTS = {"2h", "24h", "72h"}
VALID_GROUP_BY = {
    "topic_direction_id",
    "image_style",
    "checkpoint",
    "account_id",
    "playbook_id",
}


def record_xhs_post_metrics(
    *,
    artifact_path: Path | str,
    checkpoint: str,
    views: int,
    likes: int,
    collects: int,
    comments: int,
    shares: int,
    output_path: Path | str = DEFAULT_POST_METRICS_PATH,
    decision: str = "",
    notes: str = "",
    recorded_at: str | None = None,
) -> dict[str, Any]:
    artifact = Path(artifact_path)
    destination = Path(output_path)
    if not artifact.exists():
        return {"status": "error", "reason": f"artifact not found: {artifact}"}

    validation_error = _validate_metrics(
        checkpoint=checkpoint,
        views=views,
        likes=likes,
        collects=collects,
        comments=comments,
        shares=shares,
    )
    if validation_error:
        return {"status": "error", "reason": validation_error}

    payload = json.loads(artifact.read_text(encoding="utf-8"))
    base_record = _record_from_artifact(payload, artifact_path=artifact)
    interaction_score = likes + (collects * 2) + (comments * 4) + (shares * 6)
    record = {
        **base_record,
        "recorded_at": recorded_at or datetime.now(timezone.utc).isoformat(),
        "checkpoint": checkpoint,
        "views": int(views),
        "likes": int(likes),
        "collects": int(collects),
        "comments": int(comments),
        "shares": int(shares),
        "interaction_score": interaction_score,
        "interaction_rate": _rate(interaction_score, views),
        "like_rate": _rate(likes, views),
        "decision": decision,
        "notes": notes,
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "status": "recorded",
        "output_path": str(destination),
        "record": record,
    }


def summarize_xhs_post_metrics(
    *,
    input_path: Path | str = DEFAULT_POST_METRICS_PATH,
    playbook_id: str | None = None,
    account_id: str | None = None,
    checkpoint: str | None = None,
    group_by: str = "topic_direction_id",
) -> dict[str, Any]:
    source = Path(input_path)
    if group_by not in VALID_GROUP_BY:
        return {"status": "error", "reason": f"unsupported group_by: {group_by}"}
    if not source.exists():
        return {
            "status": "ok",
            "input_path": str(source),
            "records_count": 0,
            "group_by": group_by,
            "groups": [],
        }

    records = [
        record
        for record in _read_jsonl(source)
        if _matches_filters(
            record,
            playbook_id=playbook_id,
            account_id=account_id,
            checkpoint=checkpoint,
        )
    ]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        key = str(record.get(group_by) or "unknown")
        grouped.setdefault(key, []).append(record)

    groups = [_summarize_group(key, items) for key, items in grouped.items()]
    groups.sort(
        key=lambda group: (
            float(group["avg_interaction_rate"]),
            float(group["avg_views"]),
        ),
        reverse=True,
    )
    return {
        "status": "ok",
        "input_path": str(source),
        "filters": {
            "playbook_id": playbook_id,
            "account_id": account_id,
            "checkpoint": checkpoint,
        },
        "records_count": len(records),
        "group_by": group_by,
        "groups": groups,
    }


def _validate_metrics(
    *,
    checkpoint: str,
    views: int,
    likes: int,
    collects: int,
    comments: int,
    shares: int,
) -> str:
    if checkpoint not in VALID_CHECKPOINTS:
        return f"unsupported checkpoint: {checkpoint}"
    values = {
        "views": views,
        "likes": likes,
        "collects": collects,
        "comments": comments,
        "shares": shares,
    }
    for field, value in values.items():
        if int(value) < 0:
            return f"{field} must be non-negative"
    return ""


def _record_from_artifact(payload: dict[str, Any], *, artifact_path: Path) -> dict[str, Any]:
    account = payload.get("account") if isinstance(payload.get("account"), dict) else {}
    final_content = (
        payload.get("final_content") if isinstance(payload.get("final_content"), dict) else {}
    )
    topic_selection = (
        payload.get("topic_selection")
        if isinstance(payload.get("topic_selection"), dict)
        else {}
    )
    publish_result = (
        payload.get("publish_result")
        if isinstance(payload.get("publish_result"), dict)
        else {}
    )
    image_plan = _extract_image_plan(payload)
    return {
        "artifact_path": str(artifact_path),
        "playbook_id": str(payload.get("playbook_id") or ""),
        "account_id": str(account.get("account_id") or ""),
        "platform": str(account.get("platform") or payload.get("platform") or ""),
        "scene": str(payload.get("scene") or ""),
        "topic_direction_id": str(topic_selection.get("topic_direction_id") or ""),
        "title": str(final_content.get("title") or ""),
        "image_text": str(final_content.get("image_text") or ""),
        "hashtags": list(final_content.get("hashtags") or []),
        "image_style": str(
            image_plan.get("style")
            or image_plan.get("local_style")
            or image_plan.get("selected_style")
            or ""
        ),
        "image_role": str(image_plan.get("role") or ""),
        "publish_mode": str(payload.get("publish_mode") or ""),
        "publish_status": str(publish_result.get("status") or ""),
        "post_id": str(publish_result.get("post_id") or ""),
        "post_url": str(publish_result.get("post_url") or ""),
    }


def _extract_image_plan(payload: dict[str, Any]) -> dict[str, Any]:
    content_review = (
        payload.get("content_review") if isinstance(payload.get("content_review"), dict) else {}
    )
    image_plan = content_review.get("image_plan")
    if isinstance(image_plan, dict):
        return image_plan
    image_generation = (
        payload.get("image_generation")
        if isinstance(payload.get("image_generation"), dict)
        else {}
    )
    image_plan = image_generation.get("image_plan")
    if isinstance(image_plan, dict):
        return image_plan
    final_content = (
        payload.get("final_content") if isinstance(payload.get("final_content"), dict) else {}
    )
    image_plan = final_content.get("image_plan")
    return image_plan if isinstance(image_plan, dict) else {}


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def _matches_filters(
    record: dict[str, Any],
    *,
    playbook_id: str | None,
    account_id: str | None,
    checkpoint: str | None,
) -> bool:
    if playbook_id is not None and record.get("playbook_id") != playbook_id:
        return False
    if account_id is not None and record.get("account_id") != account_id:
        return False
    if checkpoint is not None and record.get("checkpoint") != checkpoint:
        return False
    return True


def _summarize_group(key: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    posts = len(records)
    totals = {
        "views": sum(_to_int(record.get("views")) for record in records),
        "likes": sum(_to_int(record.get("likes")) for record in records),
        "collects": sum(_to_int(record.get("collects")) for record in records),
        "comments": sum(_to_int(record.get("comments")) for record in records),
        "shares": sum(_to_int(record.get("shares")) for record in records),
        "interaction_score": sum(
            _to_int(record.get("interaction_score")) for record in records
        ),
    }
    return {
        "group": key,
        "posts": posts,
        "sample_status": "ok" if posts >= 3 else "needs_more_data",
        "total_views": totals["views"],
        "total_likes": totals["likes"],
        "total_collects": totals["collects"],
        "total_comments": totals["comments"],
        "total_shares": totals["shares"],
        "total_interaction_score": totals["interaction_score"],
        "avg_views": _average(totals["views"], posts),
        "avg_likes": _average(totals["likes"], posts),
        "avg_collects": _average(totals["collects"], posts),
        "avg_comments": _average(totals["comments"], posts),
        "avg_shares": _average(totals["shares"], posts),
        "avg_interaction_score": _average(totals["interaction_score"], posts),
        "avg_interaction_rate": _average(
            sum(float(record.get("interaction_rate") or 0.0) for record in records),
            posts,
        ),
        "avg_like_rate": _average(
            sum(float(record.get("like_rate") or 0.0) for record in records),
            posts,
        ),
    }


def _average(total: int | float, count: int) -> float:
    if count <= 0:
        return 0.0
    return total / count


def _to_int(value: Any) -> int:
    if value in {None, ""}:
        return 0
    return int(value)
