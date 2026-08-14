from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any

DEFAULT_GENERATED_IMAGE_ASSET_LEDGER = (
    Path("outputs") / "artifacts" / "generated-image-assets" / "assets.jsonl"
)


def append_generated_image_assets(
    *,
    base_dir: Path,
    artifact_path: str,
    playbook_id: str,
    account_id: str,
    image_generation: dict[str, Any] | None,
) -> dict[str, object] | None:
    if not isinstance(image_generation, dict):
        return None
    image_paths = list(
        image_generation.get("generated_image_paths")
        or image_generation.get("image_paths")
        or []
    )
    if not image_paths:
        return None

    ledger_path = base_dir / DEFAULT_GENERATED_IMAGE_ASSET_LEDGER
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    page_evidence = _ordered_page_evidence(
        image_generation=image_generation,
        image_paths=[str(path) for path in image_paths],
    )
    entries = [
        _build_asset_entry(
            image_path=str(image_path),
            artifact_path=artifact_path,
            playbook_id=playbook_id,
            account_id=account_id,
            image_generation=image_generation,
            page=page_evidence[index],
        )
        for index, image_path in enumerate(image_paths)
    ]
    _append_entries_atomically(ledger_path=ledger_path, entries=entries)

    return {
        "status": "recorded",
        "ledger_path": str(ledger_path),
        "entry_count": len(entries),
    }


def _build_asset_entry(
    *,
    image_path: str,
    artifact_path: str,
    playbook_id: str,
    account_id: str,
    image_generation: dict[str, Any],
    page: dict[str, Any] | None,
) -> dict[str, object]:
    provenance = image_generation.get("provenance")
    provenance_source = ""
    if isinstance(provenance, dict):
        provenance_source = str(provenance.get("source") or "")
    image_plan = image_generation.get("image_plan")
    image_plan_payload = image_plan if isinstance(image_plan, dict) else {}
    prompt_material = _prompt_material(image_generation=image_generation)
    entry: dict[str, object] = {
        "created_at": _timestamp(),
        "image_path": image_path,
        "artifact_path": artifact_path,
        "playbook_id": playbook_id,
        "account_id": account_id,
        "provider": str(image_generation.get("provider") or ""),
        "style": str(image_generation.get("style") or ""),
        "model": str(image_generation.get("model") or ""),
        "provenance_source": provenance_source,
        "image_plan": image_plan_payload,
        "prompt_hash": hashlib.sha256(prompt_material.encode("utf-8")).hexdigest(),
    }
    if page is not None:
        entry.update(
            {
                "set_id": str(image_generation.get("set_id") or ""),
                "manifest_sha256": str(
                    image_generation.get("manifest_sha256") or ""
                ),
                "slide_id": str(page.get("slide_id") or ""),
                "page_order": int(page["order"]),
                "page_role": str(page.get("role") or ""),
                "page_style": str(page.get("style") or ""),
                "page_file_sha256": str(page.get("file_sha256") or ""),
            }
        )
    return entry


def _ordered_page_evidence(
    *,
    image_generation: dict[str, Any],
    image_paths: list[str],
) -> list[dict[str, Any] | None]:
    pages_value = image_generation.get("pages")
    carousel_style = str(image_generation.get("carousel_style") or "").strip()
    declared_count = image_generation.get("image_count")
    if declared_count is not None and (
        not isinstance(declared_count, int)
        or isinstance(declared_count, bool)
        or declared_count != len(image_paths)
    ):
        raise ValueError("generated image count does not match image paths")
    if not carousel_style and pages_value is None:
        return [None] * len(image_paths)
    if not isinstance(pages_value, list) or len(pages_value) != len(image_paths):
        raise ValueError("carousel page evidence does not match image paths")

    pages: list[dict[str, Any] | None] = []
    for expected_order, (image_path, page_value) in enumerate(
        zip(image_paths, pages_value, strict=True),
        start=1,
    ):
        if not isinstance(page_value, dict):
            raise ValueError("carousel page evidence must contain objects")
        try:
            page_order = int(page_value["order"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("carousel page evidence has an invalid order") from exc
        if page_order != expected_order or str(page_value.get("path") or "") != image_path:
            raise ValueError("carousel page evidence does not match manifest order")
        pages.append(page_value)
    return pages


def _append_entries_atomically(
    *,
    ledger_path: Path,
    entries: list[dict[str, object]],
) -> None:
    existing = ledger_path.read_bytes() if ledger_path.exists() else b""
    if existing and not existing.endswith(b"\n"):
        existing += b"\n"
    encoded_entries = "".join(
        json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        for entry in entries
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{ledger_path.name}.",
        suffix=".tmp",
        dir=ledger_path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(existing)
            handle.write(encoded_entries)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, ledger_path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _prompt_material(*, image_generation: dict[str, Any]) -> str:
    prompt = image_generation.get("prompt")
    if prompt:
        return str(prompt)
    return json.dumps(
        {
            "provider": image_generation.get("provider"),
            "style": image_generation.get("style"),
            "model": image_generation.get("model"),
            "image_plan": image_generation.get("image_plan"),
            "runtime_context_summary": image_generation.get("runtime_context_summary"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
