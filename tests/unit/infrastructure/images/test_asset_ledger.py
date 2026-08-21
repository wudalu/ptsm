from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import threading

import pytest

import ptsm.infrastructure.images.asset_ledger as asset_ledger_module
from ptsm.infrastructure.images.asset_ledger import (
    append_generated_image_assets,
    verify_generated_image_asset_receipt_intent,
)


def test_append_generated_image_assets_writes_jsonl_entries(tmp_path: Path) -> None:
    image_path = tmp_path / "outputs" / "generated_images" / "cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"png")

    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="fengkuang_daily_post",
        account_id="acct-fk-local",
        image_generation={
            "provider": "local_note_card",
            "style": "wechat_chat_v1",
            "model": "local-pillow-note-card",
            "generated_image_paths": [str(image_path)],
            "provenance": {"source": "ptsm_local_renderer"},
            "image_plan": {"role": "comment_prompt", "requested_style": "wechat_chat"},
        },
    )

    ledger_path = Path(result["ledger_path"])
    entries = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
    ]

    assert result["status"] == "recorded"
    assert ledger_path == tmp_path / "outputs" / "artifacts" / "generated-image-assets" / "assets.jsonl"
    assert len(entries) == 1
    assert entries[0]["image_path"] == str(image_path)
    assert entries[0]["provider"] == "local_note_card"
    assert entries[0]["style"] == "wechat_chat_v1"
    assert entries[0]["model"] == "local-pillow-note-card"
    assert entries[0]["provenance_source"] == "ptsm_local_renderer"
    assert entries[0]["image_plan"]["role"] == "comment_prompt"
    assert entries[0]["artifact_path"] == str(tmp_path / "artifact.json")
    assert entries[0]["playbook_id"] == "fengkuang_daily_post"
    assert entries[0]["account_id"] == "acct-fk-local"
    assert entries[0]["prompt_hash"]
    assert entries[0]["created_at"]


def test_append_generated_image_assets_skips_when_no_generated_paths(tmp_path: Path) -> None:
    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="fengkuang_daily_post",
        account_id="acct-fk-local",
        image_generation=None,
    )

    assert result is None
    assert not (
        tmp_path / "outputs" / "artifacts" / "generated-image-assets" / "assets.jsonl"
    ).exists()


def test_append_generated_image_assets_records_carousel_pages_in_manifest_order(
    tmp_path: Path,
) -> None:
    image_dir = tmp_path / "outputs" / "generated_images" / "set-1"
    image_dir.mkdir(parents=True)
    image_paths = [image_dir / f"lesson-{order:02d}.png" for order in range(1, 5)]
    for path in image_paths:
        path.write_bytes(b"png")
    pages = [
        {
            "slide_id": f"slide-{order}",
            "order": order,
            "role": role,
            "style": "psychology_text_card_v1",
            "path": str(path),
            "filename": path.name,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for order, role, path in zip(
            range(1, 5),
            ("cover_hook", "concrete_scene", "light_mechanism", "save_tool"),
            image_paths,
            strict=True,
        )
    ]

    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="modern_psychology_post",
        account_id="acct-psychology-local",
        image_generation={
            "provider": "local_note_card",
            "style": "psychology_text_card_v1",
            "carousel_style": "psychology_text_card_v1",
            "image_count": 4,
            "set_id": "set-1",
            "manifest_sha256": "manifest-hash",
            "generated_image_paths": [str(path) for path in image_paths],
            "pages": pages,
            "provenance": {"source": "ptsm_local_renderer"},
        },
    )

    assert result is not None
    assert result["entry_count"] == 4
    entries = _read_jsonl(Path(result["ledger_path"]))
    assert [entry["page_order"] for entry in entries] == [1, 2, 3, 4]
    assert [entry["slide_id"] for entry in entries] == [
        "slide-1",
        "slide-2",
        "slide-3",
        "slide-4",
    ]
    assert entries[0]["page_role"] == "cover_hook"
    assert entries[-1]["page_role"] == "save_tool"
    assert all(entry["set_id"] == "set-1" for entry in entries)
    assert all(entry["manifest_sha256"] == "manifest-hash" for entry in entries)
    assert [entry["page_file_sha256"] for entry in entries] == [
        hashlib.sha256(path.read_bytes()).hexdigest() for path in image_paths
    ]


def test_asset_ledger_verifies_the_complete_receipt_intent_projection(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "outputs" / "generated_images" / "carousel-01-cover.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"carousel page")
    fingerprint = "a" * 64
    page_sha256 = "b" * 64
    file_sha256 = hashlib.sha256(image_path.read_bytes()).hexdigest()
    intent = {
        "account_id": "acct-psychology-local",
        "playbook_id": "modern_psychology_post",
        "artifact_path": "outputs/artifacts/carousel.json",
        "carousel_plan_fingerprint": fingerprint,
        "set_id": "c" * 64,
        "manifest_sha256": "d" * 64,
        "pages": [
            {
                "order": 1,
                "slide_id": "cover",
                "path": str(image_path),
                "page_sha256": page_sha256,
                "file_sha256": file_sha256,
            }
        ],
    }

    result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=intent["artifact_path"],
        playbook_id=intent["playbook_id"],
        account_id=intent["account_id"],
        image_generation={
            "provider": "local_note_card",
            "style": "psychology_text_card_v1",
            "carousel_style": "psychology_text_card_v1",
            "carousel_plan_fingerprint": fingerprint,
            "image_count": 1,
            "set_id": intent["set_id"],
            "manifest_sha256": intent["manifest_sha256"],
            "generated_image_paths": [str(image_path)],
            "pages": [
                {
                    "slide_id": "cover",
                    "order": 1,
                    "role": "cover_hook",
                    "style": "psychology_text_card_v1",
                    "path": str(image_path),
                    "file_sha256": file_sha256,
                    "page_sha256": page_sha256,
                }
            ],
        },
    )

    assert result is not None
    assert verify_generated_image_asset_receipt_intent(
        base_dir=tmp_path,
        receipt_intent=intent,
    )

    ledger_path = Path(result["ledger_path"])
    entries = _read_jsonl(ledger_path)
    entries[0]["page_sha256"] = "0" * 64
    ledger_path.write_text(
        "".join(json.dumps(entry, ensure_ascii=False) + "\n" for entry in entries),
        encoding="utf-8",
    )

    assert not verify_generated_image_asset_receipt_intent(
        base_dir=tmp_path,
        receipt_intent=intent,
    )


def test_append_generated_image_assets_hash_mismatch_leaves_no_ledger(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    with pytest.raises(ValueError, match="image_file_hash_mismatch"):
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={
                "generated_image_paths": [str(image_path)],
                "carousel_style": "psychology_text_card_v1",
                "image_count": 1,
                "pages": [
                    {
                        "order": 1,
                        "path": str(image_path),
                        "file_sha256": "0" * 64,
                    }
                ],
            },
        )

    assert not (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    ).exists()


def test_append_generated_image_assets_rejects_misaligned_carousel_page_evidence(
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    with pytest.raises(ValueError, match="does not match"):
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={
                "generated_image_paths": [str(image_path)],
                "carousel_style": "psychology_text_card_v1",
                "image_count": 2,
                "pages": [],
            },
        )


@pytest.mark.parametrize(
    ("symlink_name", "safe_prefix", "escaped_suffix"),
    [
        ("outputs", (), ("artifacts", "generated-image-assets")),
        ("artifacts", ("outputs",), ("generated-image-assets",)),
    ],
    ids=("outputs", "artifacts"),
)
def test_append_generated_image_assets_rejects_intermediate_directory_symlink(
    tmp_path: Path,
    symlink_name: str,
    safe_prefix: tuple[str, ...],
    escaped_suffix: tuple[str, ...],
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    link_parent = base_dir.joinpath(*safe_prefix)
    link_parent.mkdir(parents=True, exist_ok=True)
    attacker_dir = tmp_path / "attacker-output"
    attacker_dir.mkdir()
    (link_parent / symlink_name).symlink_to(
        attacker_dir,
        target_is_directory=True,
    )
    escaped_ledger = attacker_dir.joinpath(*escaped_suffix, "assets.jsonl")
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    with pytest.raises(
        OSError,
        match="generated image asset ledger directory is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=base_dir,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert not escaped_ledger.exists()
    assert (link_parent / symlink_name).is_symlink()


def test_append_generated_image_assets_rejects_concurrent_ancestor_rebind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    ledger_parent = (
        base_dir / "outputs" / "artifacts" / "generated-image-assets"
    )
    displaced_outputs = tmp_path / "displaced-outputs"
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    original_open = os.open
    ancestor_rebound = False

    def rebind_ancestor_during_directory_open(
        path: object,
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal ancestor_rebound
        path_value = os.fspath(path)
        opening_current_parent = (
            isinstance(path_value, str) and Path(path_value) == ledger_parent
        )
        opening_pinned_artifacts = path_value == "artifacts" and dir_fd is not None
        if not ancestor_rebound and (
            opening_current_parent or opening_pinned_artifacts
        ):
            (base_dir / "outputs").rename(displaced_outputs)
            ledger_parent.mkdir(parents=True)
            ancestor_rebound = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(
        "ptsm.infrastructure.images.asset_ledger.os.open",
        rebind_ancestor_during_directory_open,
    )

    with pytest.raises(
        OSError,
        match="generated image asset ledger directory is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=base_dir,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert ancestor_rebound
    assert str(tmp_path) not in str(exc_info.value)
    assert not (ledger_parent / "assets.jsonl").exists()
    assert not (
        displaced_outputs
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    ).exists()


def test_append_generated_image_assets_keeps_existing_ledger_on_batch_write_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    original = '{"existing": true}\n'
    ledger_path.write_text(original, encoding="utf-8")
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    def fail_replace(
        source: object,
        destination: object,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("ptsm.infrastructure.images.asset_ledger.os.replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert ledger_path.read_text(encoding="utf-8") == original


def test_append_generated_image_assets_rejects_symlink_lock_without_path_disclosure(
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    attacker_lock = tmp_path / "attacker.lock"
    attacker_lock.write_bytes(b"")
    ledger_path.with_name(f".{ledger_path.name}.lock").symlink_to(attacker_lock)
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")

    with pytest.raises(
        OSError,
        match="generated image asset ledger lock is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert not ledger_path.exists()


def test_append_generated_image_assets_rejects_replaced_parent_after_lock_open(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    displaced_parent = tmp_path / "displaced-generated-image-assets"
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    original_flock = fcntl.flock
    parent_replaced = False

    def replace_parent_after_lock_open(descriptor: int, operation: int) -> None:
        nonlocal parent_replaced
        if operation == fcntl.LOCK_EX and not parent_replaced:
            ledger_path.parent.rename(displaced_parent)
            ledger_path.parent.mkdir()
            parent_replaced = True
        original_flock(descriptor, operation)

    monkeypatch.setattr(
        "ptsm.infrastructure.images.asset_ledger.fcntl.flock",
        replace_parent_after_lock_open,
    )

    with pytest.raises(
        OSError,
        match="generated image asset ledger directory is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert parent_replaced
    assert str(tmp_path) not in str(exc_info.value)
    assert not ledger_path.exists()
    assert not (displaced_parent / ledger_path.name).exists()


def test_append_generated_image_assets_rejects_parent_replacement_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    displaced_parent = tmp_path / "displaced-after-commit"
    original_replace = os.replace
    parent_replaced = False

    def replace_then_move_parent(
        source: object,
        destination: object,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal parent_replaced
        original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        ledger_path.parent.rename(displaced_parent)
        ledger_path.parent.mkdir()
        parent_replaced = True

    monkeypatch.setattr(
        "ptsm.infrastructure.images.asset_ledger.os.replace",
        replace_then_move_parent,
    )

    with pytest.raises(
        OSError,
        match="generated image asset ledger directory is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert parent_replaced
    assert str(tmp_path) not in str(exc_info.value)
    assert not ledger_path.exists()
    assert (displaced_parent / ledger_path.name).is_file()


def test_append_generated_image_assets_rejects_existing_ledger_symlink_without_reading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    attacker_ledger = tmp_path / "attacker-ledger.jsonl"
    attacker_payload = b'{"attacker": true}\n'
    attacker_ledger.write_bytes(attacker_payload)
    ledger_path.symlink_to(attacker_ledger)
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    original_read_bytes = Path.read_bytes
    read_paths: list[Path] = []

    def observe_path_reads(path: Path) -> bytes:
        read_paths.append(path)
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", observe_path_reads)

    with pytest.raises(
        OSError,
        match="generated image asset ledger is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert ledger_path not in read_paths
    assert ledger_path.is_symlink()
    assert attacker_ledger.read_bytes() == attacker_payload


def test_append_generated_image_assets_rejects_existing_ledger_hardlink_without_reading(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ledger_path = (
        tmp_path
        / "outputs"
        / "artifacts"
        / "generated-image-assets"
        / "assets.jsonl"
    )
    ledger_path.parent.mkdir(parents=True)
    attacker_ledger = tmp_path / "attacker-ledger.jsonl"
    attacker_payload = b'{"attacker": true}\n'
    attacker_ledger.write_bytes(attacker_payload)
    os.link(attacker_ledger, ledger_path)
    original_identity = attacker_ledger.stat()
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    original_read_bytes = Path.read_bytes
    read_paths: list[Path] = []

    def observe_path_reads(path: Path) -> bytes:
        read_paths.append(path)
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", observe_path_reads)

    with pytest.raises(
        OSError,
        match="generated image asset ledger is invalid",
    ) as exc_info:
        append_generated_image_assets(
            base_dir=tmp_path,
            artifact_path=str(tmp_path / "artifact.json"),
            playbook_id="modern_psychology_post",
            account_id="acct-psychology-local",
            image_generation={"generated_image_paths": [str(image_path)]},
        )

    assert str(tmp_path) not in str(exc_info.value)
    assert ledger_path not in read_paths
    assert attacker_ledger.read_bytes() == attacker_payload
    assert os.path.samestat(ledger_path.stat(), original_identity)


def test_append_generated_image_assets_fsyncs_parent_after_replace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    image_path = tmp_path / "page.png"
    image_path.write_bytes(b"png")
    original_replace = os.replace
    original_fsync = os.fsync
    replaced = False
    directory_synced_after_replace = False

    def record_replace(
        source: object,
        destination: object,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        nonlocal replaced
        original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        replaced = True

    def record_fsync(descriptor: int) -> None:
        nonlocal directory_synced_after_replace
        if replaced and stat.S_ISDIR(os.fstat(descriptor).st_mode):
            directory_synced_after_replace = True
        original_fsync(descriptor)

    monkeypatch.setattr("ptsm.infrastructure.images.asset_ledger.os.replace", record_replace)
    monkeypatch.setattr("ptsm.infrastructure.images.asset_ledger.os.fsync", record_fsync)

    append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(tmp_path / "artifact.json"),
        playbook_id="modern_psychology_post",
        account_id="acct-psychology-local",
        image_generation={"generated_image_paths": [str(image_path)]},
    )

    assert directory_synced_after_replace


def test_append_generated_image_assets_serializes_concurrent_batches(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seed_path = tmp_path / "seed.png"
    seed_path.write_bytes(b"seed")
    seed_artifact = tmp_path / "seed.json"
    seed_result = append_generated_image_assets(
        base_dir=tmp_path,
        artifact_path=str(seed_artifact),
        playbook_id="modern_psychology_post",
        account_id="acct-psychology-local",
        image_generation={"generated_image_paths": [str(seed_path)]},
    )
    assert seed_result is not None
    ledger_path = Path(seed_result["ledger_path"])

    batch_paths = {
        label: [tmp_path / f"{label}-{order}.png" for order in range(1, 3)]
        for label in ("alpha", "beta")
    }
    for paths in batch_paths.values():
        for path in paths:
            path.write_bytes(path.name.encode("utf-8"))

    original_read_existing_ledger = asset_ledger_module._read_existing_ledger
    read_count = 0
    read_count_lock = threading.Lock()
    second_snapshot_read = threading.Event()

    def synchronize_first_two_ledger_reads(
        *,
        parent_fd: int,
        ledger_name: str,
    ) -> tuple[bytes, os.stat_result | None]:
        nonlocal read_count
        snapshot = original_read_existing_ledger(
            parent_fd=parent_fd,
            ledger_name=ledger_name,
        )
        with read_count_lock:
            read_count += 1
            position = read_count
        if position == 1:
            # Without a lock, the second writer reaches this read and both
            # continue from the same snapshot. With the lock, this bounded
            # wait expires and the second writer reads the first commit.
            second_snapshot_read.wait(timeout=0.2)
        elif position == 2:
            second_snapshot_read.set()
        return snapshot

    monkeypatch.setattr(
        asset_ledger_module,
        "_read_existing_ledger",
        synchronize_first_two_ledger_reads,
    )
    start = threading.Barrier(2)
    failures: list[BaseException] = []
    results: list[dict[str, object] | None] = []

    def append_batch(label: str) -> None:
        try:
            start.wait(timeout=5)
            results.append(
                append_generated_image_assets(
                    base_dir=tmp_path,
                    artifact_path=str(tmp_path / f"{label}.json"),
                    playbook_id="modern_psychology_post",
                    account_id="acct-psychology-local",
                    image_generation={
                        "generated_image_paths": [
                            str(path) for path in batch_paths[label]
                        ]
                    },
                )
            )
        except BaseException as exc:  # pragma: no cover - asserted below
            failures.append(exc)

    threads = [
        threading.Thread(target=append_batch, args=(label,))
        for label in ("alpha", "beta")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not failures
    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert all(result is not None and result["entry_count"] == 2 for result in results)

    entries = _read_jsonl(ledger_path)
    observed = [
        (Path(str(entry["artifact_path"])).stem, Path(str(entry["image_path"])).stem)
        for entry in entries
    ]
    assert observed[0] == ("seed", "seed")
    assert observed[1:] in (
        [
            ("alpha", "alpha-1"),
            ("alpha", "alpha-2"),
            ("beta", "beta-1"),
            ("beta", "beta-2"),
        ],
        [
            ("beta", "beta-1"),
            ("beta", "beta-2"),
            ("alpha", "alpha-1"),
            ("alpha", "alpha-2"),
        ],
    )
    lock_identity = ledger_path.with_name(f".{ledger_path.name}.lock").lstat()
    assert stat.S_ISREG(lock_identity.st_mode)
    assert not stat.S_ISLNK(lock_identity.st_mode)
    assert lock_identity.st_nlink == 1


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
