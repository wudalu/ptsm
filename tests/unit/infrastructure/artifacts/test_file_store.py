from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from ptsm.infrastructure.artifacts.file_store import FileArtifactStore


def test_file_artifact_store_merge_updates_existing_artifact(tmp_path: Path) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = store.write(
        {
            "playbook_id": "fengkuang_daily_post",
            "final_content": {"title": "打工人地铁生存实录"},
        },
        run_key="artifact-demo",
    )

    updated_path = store.merge(
        artifact_path,
        {
            "publish_result": {"status": "published"},
            "account": {"account_id": "acct-fk-local"},
            "publish_mode": "mcp-real",
        },
    )

    artifact = json.loads(updated_path.read_text(encoding="utf-8"))

    assert updated_path == artifact_path
    assert artifact["playbook_id"] == "fengkuang_daily_post"
    assert artifact["final_content"]["title"] == "打工人地铁生存实录"
    assert artifact["publish_result"]["status"] == "published"
    assert artifact["account"]["account_id"] == "acct-fk-local"
    assert artifact["publish_mode"] == "mcp-real"


def test_file_artifact_store_preserves_existing_run_key_writes(tmp_path: Path) -> None:
    store = FileArtifactStore(base_dir=tmp_path)

    first_path = store.write({"title": "first"}, run_key="acct-fk-local-demo-1")
    second_path = store.write({"title": "second"}, run_key="acct-fk-local-demo-1")

    assert first_path != second_path
    assert json.loads(first_path.read_text(encoding="utf-8"))["title"] == "first"
    assert json.loads(second_path.read_text(encoding="utf-8"))["title"] == "second"


@pytest.mark.parametrize("run_key", ("../escaped", "/tmp/escaped"))
def test_file_artifact_store_write_rejects_run_keys_that_escape_the_base_directory(
    tmp_path: Path,
    run_key: str,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path / "artifacts")

    with pytest.raises(ValueError, match="run_key"):
        store.write({"title": "unsafe"}, run_key=run_key)

    assert not (tmp_path / "escaped.json").exists()


def test_file_artifact_store_write_rejects_a_rebound_base_directory_before_writing(
    tmp_path: Path,
) -> None:
    base_dir = tmp_path / "artifacts"
    base_dir.mkdir()
    expected_identity = base_dir.stat()
    former_base_dir = tmp_path / "former-artifacts"
    base_dir.rename(former_base_dir)
    base_dir.mkdir()
    store = FileArtifactStore(base_dir=base_dir)

    with pytest.raises(OSError, match="artifact parent changed"):
        store.write(
            {"title": "must not reach the replacement root"},
            run_key="rebound",
            expected_base_identity=expected_identity,
        )

    assert not (base_dir / "rebound.json").exists()
    assert not (former_base_dir / "rebound.json").exists()


def test_file_artifact_store_read_rejects_terminal_symlink(tmp_path: Path) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_path.write_text(
        json.dumps({"private_goal": "不得读取这个确认前目标"}, ensure_ascii=False),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "artifact.json"
    artifact_path.symlink_to(snapshot_path)

    with pytest.raises(OSError):
        store.read(artifact_path)

    assert artifact_path.is_symlink()
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {
        "private_goal": "不得读取这个确认前目标"
    }


def test_file_artifact_store_merge_rejects_terminal_symlink_without_mutating_target(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_before = json.dumps(
        {"private_goal": "不得写入这个确认前目标"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.symlink_to(snapshot_path)

    with pytest.raises(OSError):
        store.merge(artifact_path, {"publish_result": {"status": "published"}})

    assert artifact_path.is_symlink()
    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_replace_replaces_terminal_symlink_without_mutating_target(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_before = json.dumps(
        {"private_goal": "符号链接目标必须保持原样"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.symlink_to(snapshot_path)

    updated_path = store.replace(artifact_path, {"status": "sealed"})

    assert updated_path == artifact_path
    assert not artifact_path.is_symlink()
    assert store.read(artifact_path) == {"status": "sealed"}
    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_replace_replaces_terminal_hard_link_without_mutating_peer(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_before = json.dumps(
        {"private_goal": "硬链接目标必须保持原样"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    artifact_path = tmp_path / "artifact.json"
    os.link(snapshot_path, artifact_path)

    store.replace(artifact_path, {"status": "sealed"})

    assert not os.path.samestat(artifact_path.stat(), snapshot_path.stat())
    assert store.read(artifact_path) == {"status": "sealed"}
    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_merge_replaces_terminal_hard_link_without_mutating_peer(
    tmp_path: Path,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_before = json.dumps(
        {"status": "snapshot", "private_goal": "硬链接合并不能污染快照"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    artifact_path = tmp_path / "artifact.json"
    os.link(snapshot_path, artifact_path)

    store.merge(artifact_path, {"publish_result": {"status": "published"}})

    assert not os.path.samestat(artifact_path.stat(), snapshot_path.stat())
    assert store.read(artifact_path) == {
        "status": "snapshot",
        "private_goal": "硬链接合并不能污染快照",
        "publish_result": {"status": "published"},
    }
    assert snapshot_path.read_bytes() == snapshot_before


@pytest.mark.parametrize("replacement_kind", ("symlink", "hardlink"))
def test_file_artifact_store_replace_rejects_temporary_source_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    replacement_kind: str,
) -> None:
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "old"}), encoding="utf-8")
    snapshot_path = tmp_path / "catalog-snapshot.json"
    snapshot_before = json.dumps(
        {"private_goal": "临时源换链不得暴露 catalog 快照"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    original_replace = os.replace

    def replace_after_temp_swap(source: object, destination: object, **kwargs: object) -> None:
        source_name = str(source)
        source_parent_fd = kwargs.get("src_dir_fd")
        if isinstance(source_parent_fd, int):
            os.unlink(source_name, dir_fd=source_parent_fd)
            if replacement_kind == "symlink":
                os.symlink(snapshot_path, source_name, dir_fd=source_parent_fd)
            else:
                os.link(snapshot_path, source_name, dst_dir_fd=source_parent_fd)
        else:
            source_path = Path(source_name)
            source_path.unlink()
            if replacement_kind == "symlink":
                source_path.symlink_to(snapshot_path)
            else:
                os.link(snapshot_path, source_path)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", replace_after_temp_swap)

    with pytest.raises(OSError):
        store.replace(artifact_path, {"status": "sealed"})

    if replacement_kind == "symlink":
        assert artifact_path.is_symlink()
    else:
        assert artifact_path.exists()
        assert os.path.samestat(artifact_path.stat(), snapshot_path.stat())
    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_replace_rejects_mutated_hardlink_to_its_own_temp(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A peer hardlink must not mutate the still-named replacement inode."""
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "old"}), encoding="utf-8")
    peer_name = "attacker-peer.json"
    original_replace = os.replace

    def replace_after_mutating_temp(
        source: object,
        destination: object,
        **kwargs: object,
    ) -> None:
        source_name = str(source)
        source_parent_fd = kwargs.get("src_dir_fd")
        destination_parent_fd = kwargs.get("dst_dir_fd")
        assert isinstance(source_parent_fd, int)
        assert isinstance(destination_parent_fd, int)
        os.link(
            source_name,
            peer_name,
            src_dir_fd=source_parent_fd,
            dst_dir_fd=destination_parent_fd,
        )
        peer_fd = os.open(
            peer_name,
            os.O_WRONLY | os.O_TRUNC,
            dir_fd=destination_parent_fd,
        )
        try:
            os.write(peer_fd, b'{"status":"attacker"}')
            os.fsync(peer_fd)
        finally:
            os.close(peer_fd)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", replace_after_mutating_temp)

    with pytest.raises(OSError, match="artifact replacement source changed"):
        store.replace(artifact_path, {"status": "sealed"})

    assert artifact_path.exists()
    peer_path = tmp_path / peer_name
    assert os.path.samestat(artifact_path.stat(), peer_path.stat())
    assert json.loads(peer_path.read_text(encoding="utf-8")) == {
        "status": "attacker"
    }


def test_file_artifact_store_replace_rejects_a_mutated_temp_after_peer_is_unlinked(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A same-UID writer cannot hide a source-content mutation by unlinking its peer."""
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = tmp_path / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "old"}), encoding="utf-8")
    peer_name = "attacker-peer.json"
    attacker_bytes = b'{"status":"attacker"}'
    original_replace = os.replace

    def replace_after_hidden_temp_mutation(
        source: object,
        destination: object,
        **kwargs: object,
    ) -> None:
        source_name = str(source)
        source_parent_fd = kwargs.get("src_dir_fd")
        destination_parent_fd = kwargs.get("dst_dir_fd")
        assert isinstance(source_parent_fd, int)
        assert isinstance(destination_parent_fd, int)
        os.link(
            source_name,
            peer_name,
            src_dir_fd=source_parent_fd,
            dst_dir_fd=destination_parent_fd,
        )
        peer_fd = os.open(
            peer_name,
            os.O_WRONLY | os.O_TRUNC,
            dir_fd=destination_parent_fd,
        )
        try:
            os.write(peer_fd, attacker_bytes)
            os.fsync(peer_fd)
        finally:
            os.close(peer_fd)
        os.unlink(peer_name, dir_fd=destination_parent_fd)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", replace_after_hidden_temp_mutation)

    with pytest.raises(OSError, match="artifact replacement payload changed"):
        store.replace(artifact_path, {"status": "sealed"})

    assert artifact_path.read_bytes() == attacker_bytes
    assert not (tmp_path / peer_name).exists()


def test_file_artifact_store_write_rejects_a_hidden_content_mutation_after_create(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A direct O_EXCL write verifies the opened inode's final payload."""
    store = FileArtifactStore(base_dir=tmp_path)
    artifact_path = tmp_path / "created.json"
    peer_path = tmp_path / "attacker-peer.json"
    attacker_bytes = b'{"status":"attacker"}'
    original_fsync = os.fsync
    mutated = False

    def fsync_after_hidden_content_mutation(fd: int) -> None:
        nonlocal mutated
        original_fsync(fd)
        if (
            not mutated
            and artifact_path.exists()
            and stat.S_ISREG(os.fstat(fd).st_mode)
        ):
            mutated = True
            os.link(artifact_path, peer_path)
            peer_fd = os.open(peer_path, os.O_WRONLY | os.O_TRUNC)
            try:
                os.write(peer_fd, attacker_bytes)
                original_fsync(peer_fd)
            finally:
                os.close(peer_fd)
            peer_path.unlink()

    monkeypatch.setattr(os, "fsync", fsync_after_hidden_content_mutation)

    with pytest.raises(OSError, match="artifact creation payload changed"):
        store.write({"status": "sealed"}, run_key="created")

    assert mutated
    assert artifact_path.read_bytes() == attacker_bytes


def test_file_artifact_store_replace_rejects_parent_directory_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A parent symlink swap cannot redirect a controlled replacement."""
    trusted_parent = tmp_path / "artifacts"
    trusted_parent.mkdir()
    artifact_path = trusted_parent / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "old"}), encoding="utf-8")
    catalog_parent = tmp_path / "catalogs"
    catalog_parent.mkdir()
    snapshot_path = catalog_parent / artifact_path.name
    snapshot_before = json.dumps(
        {"private_goal": "父目录换链不得覆盖 catalog snapshot"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    rebound_parent = tmp_path / "former-artifacts"
    original_replace = os.replace

    def replace_after_parent_swap(
        source: object,
        destination: object,
        **kwargs: object,
    ) -> None:
        source_path = Path(str(source))
        destination_path = Path(str(destination))
        trusted_parent.rename(rebound_parent)
        trusted_parent.symlink_to(catalog_parent, target_is_directory=True)
        if "src_dir_fd" not in kwargs:
            assert source_path.parent == trusted_parent
            assert destination_path == artifact_path
            os.link(rebound_parent / source_path.name, catalog_parent / source_path.name)
        original_replace(source, destination, **kwargs)

    monkeypatch.setattr(os, "replace", replace_after_parent_swap)

    with pytest.raises(OSError):
        FileArtifactStore(base_dir=trusted_parent).replace(
            artifact_path,
            {"status": "sealed"},
        )

    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_read_rejects_parent_directory_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A read pinned to an owned parent cannot be redirected before open."""
    trusted_parent = tmp_path / "artifacts"
    trusted_parent.mkdir()
    artifact_path = trusted_parent / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "safe"}), encoding="utf-8")
    snapshot_parent = tmp_path / "catalogs"
    snapshot_parent.mkdir()
    snapshot_path = snapshot_parent / artifact_path.name
    snapshot_before = json.dumps(
        {"private_goal": "读取前父目录换链不得访问 catalog snapshot"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    rebound_parent = tmp_path / "former-artifacts"
    original_open_parent = FileArtifactStore._open_parent_directory

    def open_after_parent_swap(
        parent_path: Path,
        *,
        expected_parent_identity: os.stat_result | None = None,
    ) -> tuple[int, os.stat_result]:
        trusted_parent.rename(rebound_parent)
        trusted_parent.symlink_to(snapshot_parent, target_is_directory=True)
        return original_open_parent(
            parent_path,
            expected_parent_identity=expected_parent_identity,
        )

    monkeypatch.setattr(
        FileArtifactStore,
        "_open_parent_directory",
        staticmethod(open_after_parent_swap),
    )

    with pytest.raises(OSError):
        FileArtifactStore(base_dir=trusted_parent).read_with_identity(
            artifact_path,
            expected_parent_identity=trusted_parent.stat(),
        )

    assert snapshot_path.read_bytes() == snapshot_before


def test_file_artifact_store_remove_entry_rejects_parent_directory_swap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Cleanup cannot unlink a snapshot after its parent path is rebound."""
    trusted_parent = tmp_path / "artifacts"
    trusted_parent.mkdir()
    artifact_path = trusted_parent / "artifact.json"
    artifact_path.write_text(json.dumps({"status": "unsafe"}), encoding="utf-8")
    snapshot_parent = tmp_path / "catalogs"
    snapshot_parent.mkdir()
    snapshot_path = snapshot_parent / artifact_path.name
    snapshot_before = json.dumps(
        {"private_goal": "清理时父目录换链不得删除 catalog snapshot"},
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_path.write_bytes(snapshot_before)
    rebound_parent = tmp_path / "former-artifacts"
    original_open_parent = FileArtifactStore._open_parent_directory

    def open_after_parent_swap(
        parent_path: Path,
        *,
        expected_parent_identity: os.stat_result | None = None,
    ) -> tuple[int, os.stat_result]:
        trusted_parent.rename(rebound_parent)
        trusted_parent.symlink_to(snapshot_parent, target_is_directory=True)
        return original_open_parent(
            parent_path,
            expected_parent_identity=expected_parent_identity,
        )

    monkeypatch.setattr(
        FileArtifactStore,
        "_open_parent_directory",
        staticmethod(open_after_parent_swap),
    )

    with pytest.raises(OSError):
        FileArtifactStore(base_dir=trusted_parent).remove_entry(
            artifact_path,
            expected_parent_identity=trusted_parent.stat(),
        )

    assert snapshot_path.read_bytes() == snapshot_before
