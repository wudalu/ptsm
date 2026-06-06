from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
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
    entries = [
        _build_asset_entry(
            image_path=str(image_path),
            artifact_path=artifact_path,
            playbook_id=playbook_id,
            account_id=account_id,
            image_generation=image_generation,
        )
        for image_path in image_paths
    ]
    with ledger_path.open("a", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

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
) -> dict[str, object]:
    provenance = image_generation.get("provenance")
    provenance_source = ""
    if isinstance(provenance, dict):
        provenance_source = str(provenance.get("source") or "")
    image_plan = image_generation.get("image_plan")
    image_plan_payload = image_plan if isinstance(image_plan, dict) else {}
    prompt_material = _prompt_material(image_generation=image_generation)
    return {
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
