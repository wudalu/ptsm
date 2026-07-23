from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
    contains_psychology_learning_raw_provenance,
    resolve_psychology_learning_selection,
    validate_psychology_learning_draft_contract,
)


DEFAULT_POST_METRICS_PATH = Path("outputs/artifacts/xhs-post-metrics/metrics.jsonl")
VALID_CHECKPOINTS = {"2h", "24h", "72h"}
VALID_GROUP_BY = {
    "topic_direction_id",
    "image_style",
    "checkpoint",
    "account_id",
    "playbook_id",
    "psychology_learning_series_id",
    "psychology_learning_curriculum_version",
    "psychology_learning_lesson_id",
}
_LEARNING_GROUP_BY = frozenset(
    {
        "psychology_learning_series_id",
        "psychology_learning_curriculum_version",
        "psychology_learning_lesson_id",
    }
)
_PSYCHOLOGY_LEARNING_RECEIPT_FIELDS = frozenset(
    {
        "psychology_learning_mode",
        "psychology_learning_series_id",
        "psychology_learning_curriculum_version",
        "psychology_learning_lesson_id",
        "psychology_learning_lesson_number",
        "psychology_learning_evidence_manifest",
        "psychology_learning_gate",
    }
)


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
    if not isinstance(payload, dict):
        return {"status": "error", "reason": "artifact must contain a JSON object"}
    learning_identity, learning_receipt_error = _learning_metric_identity(payload)
    if learning_receipt_error:
        return {"status": "error", "reason": learning_receipt_error}
    base_record = _record_from_artifact(
        payload,
        artifact_path=artifact,
        learning_identity=learning_identity,
    )
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
    record["metric_identity"] = _metric_identity(record)

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        write_action = _upsert_metric_record(destination, record)
    except (OSError, json.JSONDecodeError):
        return {"status": "error", "reason": "could not update local metrics store"}

    return {
        "status": "recorded",
        "output_path": str(destination),
        "record": record,
        "write_action": write_action,
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

    records = _deduplicate_metric_records(
        _read_jsonl(source)
    )
    records = [
        record
        for record in records
        if _matches_filters(
            record,
            playbook_id=playbook_id,
            account_id=account_id,
            checkpoint=checkpoint,
        )
    ]
    if group_by in _LEARNING_GROUP_BY:
        records = [record for record in records if _is_learning_metric_record(record)]
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
        "content_scope": (
            "learning_series" if group_by in _LEARNING_GROUP_BY else "all"
        ),
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


def _record_from_artifact(
    payload: dict[str, Any],
    *,
    artifact_path: Path,
    learning_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        "topic_direction_id": (
            str(learning_identity["topic_direction_id"])
            if learning_identity is not None
            else str(topic_selection.get("topic_direction_id") or "")
        ),
        "psychology_learning_mode": (
            PSYCHOLOGY_LEARNING_MODE if learning_identity is not None else ""
        ),
        "psychology_learning_series_id": (
            str(learning_identity["series_id"]) if learning_identity is not None else ""
        ),
        "psychology_learning_curriculum_version": (
            str(learning_identity["curriculum_version"])
            if learning_identity is not None
            else ""
        ),
        "psychology_learning_lesson_id": (
            str(learning_identity["lesson_id"]) if learning_identity is not None else ""
        ),
        "psychology_learning_lesson_number": (
            int(learning_identity["lesson_number"])
            if learning_identity is not None
            else None
        ),
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


def _learning_metric_identity(
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    """Return verified learning identity, or a safe metrics-recording error.

    Learning dimensions must come from the same closed receipt that gates
    drafting and evaluation.  A partial marker must never manufacture a
    metrics cohort because that could make a future lesson/version comparison
    look evidence-backed when it is not.
    """
    has_learning_receipt = any(
        field_name in payload for field_name in _PSYCHOLOGY_LEARNING_RECEIPT_FIELDS
    )
    topic_selection = payload.get("topic_selection")
    has_learning_marker = bool(
        isinstance(topic_selection, Mapping)
        and topic_selection.get("source") == "psychology-learning-series"
    )
    if not has_learning_receipt and not has_learning_marker:
        return None, ""
    if payload.get("playbook_id") != "modern_psychology_post":
        return None, "invalid psychology learning receipt"
    if payload.get("psychology_learning_mode") != PSYCHOLOGY_LEARNING_MODE:
        return None, "invalid psychology learning receipt"
    try:
        bundle = resolve_psychology_learning_selection(
            series_id=str(payload["psychology_learning_series_id"]),
            lesson_id=str(payload["psychology_learning_lesson_id"]),
            curriculum_version=str(payload["psychology_learning_curriculum_version"]),
        )
    except (KeyError, ValueError):
        return None, "invalid psychology learning receipt"

    expected_gate = {
        "status": "passed",
        "series_id": bundle.series_id,
        "lesson_id": bundle.lesson_id,
        "validator": "psychology_learning_draft_contract",
        "validator_version": "1",
        "errors": [],
    }
    expected_identity = {
        "psychology_learning_series_id": bundle.series_id,
        "psychology_learning_curriculum_version": bundle.runtime_contract[
            "curriculum_version"
        ],
        "psychology_learning_lesson_id": bundle.lesson_id,
        "psychology_learning_lesson_number": bundle.lesson_number,
    }
    final_content = payload.get("final_content")
    if (
        any(payload.get(field_name) != expected for field_name, expected in expected_identity.items())
        or payload.get("psychology_learning_evidence_manifest") != bundle.manifest
        or payload.get("psychology_learning_gate") != expected_gate
        or not isinstance(final_content, Mapping)
        or validate_psychology_learning_draft_contract(
            bundle.runtime_contract,
            final_content,
        )
        or contains_psychology_learning_raw_provenance(payload)
    ):
        return None, "invalid psychology learning receipt"
    return {
        "series_id": bundle.series_id,
        "curriculum_version": bundle.runtime_contract["curriculum_version"],
        "lesson_id": bundle.lesson_id,
        "lesson_number": bundle.lesson_number,
        "topic_direction_id": bundle.direction_id,
    }, ""


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


def _metric_identity(record: Mapping[str, Any]) -> str:
    checkpoint = str(record.get("checkpoint") or "")
    post_id = str(record.get("post_id") or "").strip()
    if post_id:
        return ":".join(
            (
                "post",
                str(record.get("platform") or ""),
                str(record.get("account_id") or ""),
                post_id,
                checkpoint,
            )
        )
    artifact_path = str(record.get("artifact_path") or "").strip()
    if not artifact_path:
        # Hand-authored legacy rows without a post or artifact identity cannot
        # be safely collapsed; preserve them as distinct observations.
        return ""
    try:
        artifact_path = str(Path(artifact_path).resolve())
    except OSError:
        pass
    return f"artifact:{artifact_path}:{checkpoint}"


def _upsert_metric_record(destination: Path, record: dict[str, Any]) -> str:
    existing = _read_jsonl(destination) if destination.exists() else []
    identity = _metric_identity(record)
    retained = [item for item in existing if _metric_identity(item) != identity]
    write_action = "updated" if len(retained) != len(existing) else "appended"
    retained.append(record)
    destination.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in retained) + "\n",
        encoding="utf-8",
    )
    return write_action


def _deduplicate_metric_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the final local correction for each post/artifact checkpoint."""
    latest: dict[str, dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in records:
        identity = _metric_identity(record)
        if not identity:
            unkeyed.append(record)
            continue
        latest[identity] = record
    return [*unkeyed, *latest.values()]


def _is_learning_metric_record(record: Mapping[str, Any]) -> bool:
    if record.get("psychology_learning_mode") == PSYCHOLOGY_LEARNING_MODE:
        return True
    # Support rows written before the explicit mode field existed, without
    # putting ordinary psychology records into an `unknown` learning cohort.
    return bool(
        record.get("psychology_learning_series_id")
        and record.get("psychology_learning_curriculum_version")
        and record.get("psychology_learning_lesson_id")
    )


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


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
