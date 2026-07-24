"""Proposal, confirmation, and local persistence for psychology learning series."""

from __future__ import annotations

import errno
import json
import os
from pathlib import Path
import stat
from typing import Any
from uuid import uuid4

try:  # ``fcntl`` is the cross-process lock primitive on supported local runtimes.
    import fcntl
except ImportError:  # pragma: no cover - fail closed on unsupported platforms.
    fcntl = None  # type: ignore[assignment]

from ptsm.domain.psychology_learning import (
    PsychologyLearningCatalog,
    PsychologyLearningCatalogRevisionRecord,
    PsychologyLearningOutlineItem,
    PsychologyLearningProductionProgress,
    PsychologyLearningSeriesPlanIntent,
    PsychologyLearningSeriesProposal,
    _PinnedPsychologyLearningCatalogReader,
    _build_confirmed_psychology_learning_catalog,
    _build_confirmed_psychology_learning_catalog_for_template,
    _build_psychology_learning_catalog_revision_record,
    _confirmed_catalog_snapshot_versions_from_reader,
    _load_confirmed_psychology_learning_catalog_snapshot,
    _read_psychology_learning_catalog_revision_records,
    build_psychology_learning_series_proposal,
    list_confirmed_psychology_learning_catalog_revisions,
    load_confirmed_psychology_learning_catalog,
    psychology_learning_series_catalog_root,
    psychology_learning_series_catalog_confirmation_path,
    psychology_learning_series_catalog_snapshot_path,
    psychology_learning_series_progress_sidecar_path,
    psychology_learning_series_proposal_snapshot_path,
    read_psychology_learning_series_proposal_snapshot,
)


def plan_psychology_learning_series(
    *,
    topic: str,
    outline: list[dict[str, Any] | PsychologyLearningOutlineItem]
    | tuple[dict[str, Any] | PsychologyLearningOutlineItem, ...]
    | None = None,
) -> PsychologyLearningSeriesProposal:
    """Return a safe review proposal without writing or resolving a catalog.

    This is intentionally a planning-only use case.  It does not persist a
    proposal, create a curriculum revision, select a lesson, or construct
    reader-visible runtime input.
    """
    if outline is not None:
        if type(outline) not in (list, tuple):
            raise TypeError("outline must be a concrete list or tuple")
        if not 2 <= len(outline) <= 6:
            raise ValueError("outline must contain between 2 and 6 lessons")
    return build_psychology_learning_series_proposal(
        PsychologyLearningSeriesPlanIntent(
            topic=topic,
            outline=tuple(outline) if outline is not None else None,
        )
    )


_PINNED_CATALOG_STORAGE_DIRECTORIES = (
    "proposals",
    "confirmations",
    "catalogs",
    "progress",
)


def provision_psychology_learning_series_storage(
    *,
    catalog_root: Path | str | None = None,
) -> Path:
    """Create the fixed custom-series storage tree during trusted setup only.

    Darwin/POSIX ``mkdir`` does not return a child descriptor, so no ordinary
    mutation can prove it owns a directory that was absent at operation start.
    Provisioning is therefore deliberately separate from proposal confirmation
    and progress mutation.  Invoke it only while the operator has exclusive
    control of the storage parent; later operations open this fixed tree with
    ``create=False`` and fail closed if any entry is missing or rebound.
    """
    root_path = psychology_learning_series_catalog_root(catalog_root).resolve(
        strict=False
    )
    root_fd = _open_or_create_no_follow_directory_path(root_path)
    try:
        _assert_trusted_provisioned_directory(
            fd=root_fd,
            label="psychology learning storage root",
        )
        for directory_name in _PINNED_CATALOG_STORAGE_DIRECTORIES:
            directory_fd = _open_or_create_pinned_directory(
                parent_fd=root_fd,
                name=directory_name,
            )
            try:
                _assert_trusted_provisioned_directory(
                    fd=directory_fd,
                    label=f"psychology learning storage directory {directory_name}",
                )
                _assert_pinned_directory_entry_matches(
                    parent_fd=root_fd,
                    name=directory_name,
                    expected_identity=os.fstat(directory_fd),
                )
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        os.fsync(root_fd)
    finally:
        os.close(root_fd)
    return root_path


def _assert_trusted_provisioned_directory(*, fd: int, label: str) -> None:
    _assert_trusted_provisioned_directory_identity(
        identity=os.fstat(fd),
        label=label,
    )


def _assert_trusted_provisioned_directory_identity(
    *,
    identity: os.stat_result,
    label: str,
) -> None:
    if not stat.S_ISDIR(identity.st_mode):
        raise OSError(f"{label} is not a directory")
    if identity.st_mode & 0o077:
        raise OSError(f"{label} must not grant group or other access")
    if hasattr(os, "geteuid") and identity.st_uid != os.geteuid():
        raise OSError(f"{label} must be owned by the current user")


class _PinnedCatalogMutationScope:
    """Mutate only a previously provisioned, fixed catalog directory tree."""

    def __init__(self, *, root_path: Path, root_fd: int) -> None:
        self.root_path = root_path
        self._root_fd = root_fd
        self._root_identity = os.fstat(root_fd)
        self._root_directory_version = _pinned_directory_mutation_version(
            self._root_identity
        )
        self._directory_fds: dict[str, int] = {}
        self._directory_identities: dict[str, os.stat_result] = {}
        self._closed = False

    @classmethod
    def open(cls, catalog_root: Path) -> _PinnedCatalogMutationScope:
        root_path = Path(os.path.abspath(os.fspath(catalog_root)))
        try:
            root_fd = _open_or_create_no_follow_directory_path(root_path, create=False)
        except FileNotFoundError as exc:
            raise OSError(
                "psychology learning storage is not provisioned"
            ) from exc
        scope = cls(root_path=root_path, root_fd=root_fd)
        try:
            for directory_name in _PINNED_CATALOG_STORAGE_DIRECTORIES:
                scope._bind_required_directory(directory_name)
        except Exception:
            scope.close()
            raise
        return scope

    def __enter__(self) -> _PinnedCatalogMutationScope:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        try:
            if exc_type is None:
                self.assert_current()
        finally:
            self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            for fd in self._directory_fds.values():
                os.close(fd)
        finally:
            os.close(self._root_fd)

    def relative_parts(self, path: Path) -> tuple[str, str]:
        absolute_path = Path(os.path.abspath(os.fspath(path)))
        try:
            relative_path = absolute_path.relative_to(self.root_path)
        except ValueError as exc:
            raise ValueError("psychology learning path is outside its catalog root") from exc
        parts = relative_path.parts
        if (
            len(parts) != 2
            or any(part in {"", ".", ".."} for part in parts)
            or parts[0] not in self._directory_fds
        ):
            raise ValueError("invalid psychology learning catalog path")
        return parts[0], parts[1]

    def open_directory(self, directory_name: str) -> int:
        self.assert_current()
        fd = self._directory_fds.get(directory_name)
        if fd is None:
            raise OSError("psychology learning storage directory changed")
        self._assert_directory_entry(directory_name)
        return os.dup(fd)

    def assert_current(self) -> None:
        if self._closed:
            raise OSError("psychology learning mutation scope is closed")
        reopened_fd = _open_or_create_no_follow_directory_path(self.root_path, create=False)
        try:
            current_root_identity = os.fstat(reopened_fd)
            if (
                not os.path.samestat(current_root_identity, self._root_identity)
                or _pinned_directory_mutation_version(current_root_identity)
                != self._root_directory_version
            ):
                raise OSError("psychology learning storage root changed")
        finally:
            os.close(reopened_fd)
        self._assert_root_view()
        for directory_name in self._directory_fds:
            self._assert_directory_entry(directory_name)

    def _assert_root_view(self) -> None:
        identity = os.fstat(self._root_fd)
        if (
            not os.path.samestat(identity, self._root_identity)
            or _pinned_directory_mutation_version(identity)
            != self._root_directory_version
        ):
            raise OSError("psychology learning storage root changed")
        _assert_trusted_provisioned_directory(
            fd=self._root_fd,
            label="psychology learning storage root",
        )

    def _bind_required_directory(self, directory_name: str) -> None:
        self._assert_root_view()
        try:
            fd = _open_pinned_directory_entry(
                parent_fd=self._root_fd,
                name=directory_name,
            )
        except FileNotFoundError as exc:
            raise OSError("psychology learning storage is not provisioned") from exc
        try:
            self._directory_fds[directory_name] = os.dup(fd)
            self._directory_identities[directory_name] = os.fstat(fd)
            _assert_trusted_provisioned_directory(
                fd=fd,
                label=f"psychology learning storage directory {directory_name}",
            )
        finally:
            os.close(fd)
        self._assert_root_view()
        self._assert_directory_entry(directory_name)

    def _assert_directory_entry(self, directory_name: str) -> None:
        fd = self._directory_fds.get(directory_name)
        if fd is None:
            raise OSError("psychology learning storage directory changed")
        _assert_pinned_directory_entry_matches(
            parent_fd=self._root_fd,
            name=directory_name,
            expected_identity=self._directory_identities[directory_name],
        )
        if not os.path.samestat(
            os.fstat(fd),
            self._directory_identities[directory_name],
        ):
            raise OSError("psychology learning storage directory changed")
        _assert_trusted_provisioned_directory(
            fd=fd,
            label=f"psychology learning storage directory {directory_name}",
        )


class PsychologyLearningSeriesStore:
    """Local immutable proposal/catalog store with a separate progress sidecar.

    The store is intentionally application-owned: it controls filesystem writes,
    while the domain resolver independently revalidates every stored catalog
    before it can become a selected lesson.  Proposal and catalog paths are
    append-only; only production progress is replaceable.
    """

    def __init__(
        self,
        *,
        catalog_root: Path | str | None = None,
        trusted_provision: bool = False,
    ) -> None:
        self.catalog_root = psychology_learning_series_catalog_root(catalog_root)
        if trusted_provision:
            self.catalog_root = provision_psychology_learning_series_storage(
                catalog_root=self.catalog_root,
            )

    def _assert_pinned_progress_storage(
        self,
        *,
        expected_catalog_root_identity: os.stat_result | None = None,
        expected_artifact_root_path: Path | None = None,
        expected_artifact_root_identity: os.stat_result | None = None,
    ) -> None:
        """Fail closed if a learning run's catalog/artifact root was rebound."""
        if (expected_artifact_root_path is None) != (
            expected_artifact_root_identity is None
        ):
            raise ValueError("artifact root path and identity must be supplied together")
        if expected_catalog_root_identity is not None:
            catalog_identity = self._assert_pinned_directory(
                path=self.catalog_root.absolute(),
                expected_identity=expected_catalog_root_identity,
            )
            _assert_trusted_provisioned_directory_identity(
                identity=catalog_identity,
                label="psychology learning storage root",
            )
        if expected_artifact_root_path is not None:
            assert expected_artifact_root_identity is not None
            self._assert_pinned_directory(
                path=expected_artifact_root_path,
                expected_identity=expected_artifact_root_identity,
            )

    def _capture_pinned_progress_directory_identity(
        self,
        *,
        expected_catalog_root_identity: os.stat_result,
    ) -> os.stat_result:
        """Capture the fixed progress directory before untrusted workflow code."""
        self._assert_pinned_progress_storage(
            expected_catalog_root_identity=expected_catalog_root_identity,
        )
        catalog_fd = _open_pinned_catalog_root(
            catalog_root_path=self.catalog_root.absolute(),
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_artifact_root_path=None,
            expected_artifact_root_identity=None,
        )
        try:
            progress_fd = _open_pinned_directory_entry(
                parent_fd=catalog_fd,
                name="progress",
            )
            try:
                _assert_pinned_progress_directory(
                    catalog_fd=catalog_fd,
                    progress_fd=progress_fd,
                )
                return os.fstat(progress_fd)
            finally:
                os.close(progress_fd)
        finally:
            os.close(catalog_fd)

    @staticmethod
    def _assert_pinned_directory(
        *,
        path: Path,
        expected_identity: os.stat_result,
    ) -> os.stat_result:
        try:
            actual_identity = _pinned_directory_path_identity(path)
        except OSError as exc:
            raise OSError("psychology learning storage root changed") from exc
        if (
            not stat.S_ISDIR(actual_identity.st_mode)
            or not os.path.samestat(actual_identity, expected_identity)
        ):
            raise OSError("psychology learning storage root changed")
        return actual_identity

    def _capture_catalog_root_identity(self) -> os.stat_result:
        try:
            identity = _pinned_directory_path_identity(self.catalog_root.absolute())
        except OSError as exc:
            raise OSError("psychology learning storage root changed") from exc
        _assert_trusted_provisioned_directory_identity(
            identity=identity,
            label="psychology learning storage root",
        )
        return identity

    def _assert_catalog_root_identity(self, expected_identity: os.stat_result) -> None:
        actual_identity = self._assert_pinned_directory(
            path=self.catalog_root.absolute(),
            expected_identity=expected_identity,
        )
        _assert_trusted_provisioned_directory_identity(
            identity=actual_identity,
            label="psychology learning storage root",
        )

    def _resolve_legacy_pinned_catalog(
        self,
        *,
        series_id: str,
        curriculum_version: str,
    ) -> tuple[PsychologyLearningCatalog, os.stat_result]:
        """Resolve a public store operation, then bind it to its entry root.

        Legacy APIs do not receive a run preflight identity, but they still must
        not authorize a replaceable progress path through a symlink.  Capture
        the catalog root before resolving, then reopen that exact directory
        through the same no-follow descriptor path used by guarded runs.
        """
        catalog_root_path = self.catalog_root.absolute()
        identity = self._capture_catalog_root_identity()
        catalog = load_confirmed_psychology_learning_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
            catalog_root=self.catalog_root,
        )
        self._assert_catalog_root_identity(identity)
        catalog_fd = _open_pinned_catalog_root(
            catalog_root_path=catalog_root_path,
            expected_catalog_root_identity=identity,
            expected_artifact_root_path=None,
            expected_artifact_root_identity=None,
        )
        os.close(catalog_fd)
        return catalog, identity

    def persist_proposal(
        self,
        proposal: PsychologyLearningSeriesProposal | dict[str, Any],
    ) -> PsychologyLearningSeriesProposal:
        """Persist a sanitized proposal without creating a runnable revision."""
        normalized = PsychologyLearningSeriesProposal.model_validate(proposal)
        path = psychology_learning_series_proposal_snapshot_path(
            proposal_id=normalized.proposal_id,
            catalog_root=self.catalog_root,
        )
        payload = normalized.model_dump(mode="json")
        with _PinnedCatalogMutationScope.open(
            self.catalog_root.absolute()
        ) as mutation_scope:
            proposal_directory_fd = mutation_scope.open_directory("proposals")
            os.close(proposal_directory_fd)
            try:
                _write_new_json(path, payload, mutation_scope=mutation_scope)
            except FileExistsError:
                mutation_scope.assert_current()
                existing = read_psychology_learning_series_proposal_snapshot(
                    proposal_id=normalized.proposal_id,
                    catalog_root=self.catalog_root,
                )
                mutation_scope.assert_current()
                if existing != normalized:
                    raise ValueError("psychology learning proposal snapshot is immutable")
                return existing
            mutation_scope.assert_current()
            persisted = read_psychology_learning_series_proposal_snapshot(
                proposal_id=normalized.proposal_id,
                catalog_root=self.catalog_root,
            )
            mutation_scope.assert_current()
            if persisted != normalized:
                raise ValueError("psychology learning proposal snapshot is immutable")
            return persisted

    def read_proposal(self, *, proposal_id: str) -> PsychologyLearningSeriesProposal:
        path = psychology_learning_series_proposal_snapshot_path(
            proposal_id=proposal_id,
            catalog_root=self.catalog_root,
        )
        try:
            payload = _read_pinned_immutable_json_path(path)
        except FileNotFoundError as exc:
            raise ValueError("unknown psychology learning proposal") from exc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OSError("psychology learning proposal snapshot is not private storage") from exc
        try:
            proposal = PsychologyLearningSeriesProposal.model_validate(payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid psychology learning proposal snapshot") from exc
        if proposal.proposal_id != proposal_id:
            raise ValueError("invalid psychology learning proposal snapshot")
        return proposal

    def confirm(
        self,
        *,
        proposal_id: str,
        proposal_fingerprint: str,
    ) -> PsychologyLearningCatalog:
        """Confirm one exact stored proposal as an append-only catalog revision."""
        with _PinnedCatalogMutationScope.open(
            self.catalog_root.absolute()
        ) as mutation_scope:
            mutation_scope.assert_current()
            proposal = self.read_proposal(proposal_id=proposal_id)
            mutation_scope.assert_current()
            if proposal.proposal_fingerprint != proposal_fingerprint:
                raise ValueError("psychology learning proposal fingerprint does not match")
            self._sync_existing_catalog_history(series_id=proposal.series_id_candidate)
            mutation_scope.assert_current()
            records = _read_psychology_learning_catalog_revision_records(
                series_id=proposal.series_id_candidate,
                catalog_root=self.catalog_root,
            )
            mutation_scope.assert_current()
            try:
                revisions = list_confirmed_psychology_learning_catalog_revisions(
                    series_id=proposal.series_id_candidate,
                    catalog_root=self.catalog_root,
                )
            except ValueError:
                mutation_scope.assert_current()
                recovered = self._recover_pending_catalog_snapshot(
                    proposal=proposal,
                    records=records,
                    mutation_scope=mutation_scope,
                )
                mutation_scope.assert_current()
                return self._revalidate_catalog_in_mutation_scope(
                    catalog=recovered,
                    mutation_scope=mutation_scope,
                )
            mutation_scope.assert_current()
            existing = next(
                (
                    catalog
                    for catalog in revisions
                    if catalog.approval.proposal_id == proposal.proposal_id
                    and catalog.approval.proposal_fingerprint == proposal.proposal_fingerprint
                ),
                None,
            )
            if existing is not None:
                return self._revalidate_catalog_in_mutation_scope(
                    catalog=existing,
                    mutation_scope=mutation_scope,
                )
            next_version = str(
                max((int(catalog.curriculum_version) for catalog in revisions), default=0)
                + 1
            )
            catalog = _build_confirmed_psychology_learning_catalog(
                proposal,
                curriculum_version=next_version,
            )
            self._persist_confirmation_record(catalog, mutation_scope=mutation_scope)
            mutation_scope.assert_current()
            persisted = self._persist_catalog_snapshot(
                catalog,
                mutation_scope=mutation_scope,
            )
            mutation_scope.assert_current()
            return self._revalidate_catalog_in_mutation_scope(
                catalog=persisted,
                mutation_scope=mutation_scope,
            )

    def _sync_existing_catalog_history(self, *, series_id: str) -> None:
        """Complete a prior durable commit barrier before accepting existing history."""
        with _PinnedPsychologyLearningCatalogReader.open(self.catalog_root) as reader:
            reader.directory_exists("confirmations")
            reader.directory_exists("catalogs")

    def _recover_pending_catalog_snapshot(
        self,
        *,
        proposal: PsychologyLearningSeriesProposal,
        records: tuple[PsychologyLearningCatalogRevisionRecord, ...],
        mutation_scope: _PinnedCatalogMutationScope,
    ) -> PsychologyLearningCatalog:
        """Complete only the single pending snapshot bound to this proposal."""
        pending_records = tuple(
            record
            for record in records
            if not self._pinned_catalog_snapshot_exists(
                series_id=record.series_id,
                curriculum_version=record.curriculum_version,
            )
        )
        if len(pending_records) != 1:
            raise ValueError("invalid psychology learning catalog revision history")
        pending = pending_records[0]
        if pending.curriculum_version != records[-1].curriculum_version:
            raise ValueError("invalid psychology learning catalog revision history")
        if (
            pending.approval.proposal_id != proposal.proposal_id
            or pending.approval.proposal_fingerprint != proposal.proposal_fingerprint
        ):
            raise ValueError("invalid psychology learning catalog revision history")
        catalog = _build_confirmed_psychology_learning_catalog_for_template(
            proposal,
            curriculum_version=pending.curriculum_version,
            controlled_template_version=pending.controlled_template_version,
        )
        if _build_psychology_learning_catalog_revision_record(catalog) != pending:
            raise ValueError("invalid psychology learning catalog revision history")
        self._validate_recoverable_catalog_history(records=records, pending=pending)
        mutation_scope.assert_current()
        return self._persist_catalog_snapshot(catalog, mutation_scope=mutation_scope)

    def _validate_recoverable_catalog_history(
        self,
        *,
        records: tuple[PsychologyLearningCatalogRevisionRecord, ...],
        pending: PsychologyLearningCatalogRevisionRecord,
    ) -> None:
        """Reject corruption before completing one ledger-backed snapshot."""
        expected_existing_versions = [
            int(record.curriculum_version)
            for record in records
            if record.curriculum_version != pending.curriculum_version
        ]
        try:
            with _PinnedPsychologyLearningCatalogReader.open(self.catalog_root) as reader:
                if reader.directory_exists("catalogs"):
                    versions = _confirmed_catalog_snapshot_versions_from_reader(
                        reader=reader,
                        series_id=pending.series_id,
                    )
                else:
                    versions = []
        except (OSError, ValueError) as exc:
            raise ValueError("invalid psychology learning catalog revision history") from exc
        if versions != expected_existing_versions:
            raise ValueError("invalid psychology learning catalog revision history")
        for record in records:
            if record.curriculum_version == pending.curriculum_version:
                continue
            try:
                catalog = _load_confirmed_psychology_learning_catalog_snapshot(
                    series_id=record.series_id,
                    curriculum_version=record.curriculum_version,
                    catalog_root=self.catalog_root,
                )
            except ValueError as exc:
                raise ValueError("invalid psychology learning catalog revision history") from exc
            if (
                catalog.controlled_template_version != record.controlled_template_version
                or catalog.approval != record.approval
                or catalog.catalog_digest != record.catalog_digest
            ):
                raise ValueError("invalid psychology learning catalog revision history")

    def _pinned_catalog_snapshot_exists(
        self,
        *,
        series_id: str,
        curriculum_version: str,
    ) -> bool:
        """Check a catalog entry through one no-follow pinned reader."""
        try:
            with _PinnedPsychologyLearningCatalogReader.open(self.catalog_root) as reader:
                reader.read_json_bytes(
                    "catalogs",
                    psychology_learning_series_catalog_snapshot_path(
                        series_id=series_id,
                        curriculum_version=curriculum_version,
                        catalog_root=self.catalog_root,
                    ).name,
                )
        except FileNotFoundError:
            return False
        return True

    def _persist_catalog_snapshot(
        self,
        catalog: PsychologyLearningCatalog,
        *,
        mutation_scope: _PinnedCatalogMutationScope,
    ) -> PsychologyLearningCatalog:
        path = psychology_learning_series_catalog_snapshot_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        try:
            _write_new_json(
                path,
                catalog.model_dump(mode="json"),
                mutation_scope=mutation_scope,
            )
        except FileExistsError:
            mutation_scope.assert_current()
            _read_pinned_immutable_json_path(path)
            mutation_scope.assert_current()
            existing = load_confirmed_psychology_learning_catalog(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                catalog_root=self.catalog_root,
            )
            mutation_scope.assert_current()
            if existing != catalog:
                raise ValueError("psychology learning catalog revision is immutable")
            return existing
        return catalog

    def _persist_confirmation_record(
        self,
        catalog: PsychologyLearningCatalog,
        *,
        mutation_scope: _PinnedCatalogMutationScope,
    ) -> None:
        record = _build_psychology_learning_catalog_revision_record(catalog)
        path = psychology_learning_series_catalog_confirmation_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        mutation_scope.assert_current()
        try:
            _write_new_json(
                path,
                record.model_dump(mode="json"),
                mutation_scope=mutation_scope,
            )
        except FileExistsError:
            mutation_scope.assert_current()
            try:
                existing = PsychologyLearningCatalogRevisionRecord.model_validate(
                    _read_pinned_immutable_json_path(path)
                )
            except (TypeError, ValueError) as exc:
                raise ValueError("psychology learning catalog revision is immutable") from exc
            if existing != record:
                raise ValueError("psychology learning catalog revision is immutable")
        mutation_scope.assert_current()

    def _revalidate_catalog_in_mutation_scope(
        self,
        *,
        catalog: PsychologyLearningCatalog,
        mutation_scope: _PinnedCatalogMutationScope,
    ) -> PsychologyLearningCatalog:
        """Require the current pinned tree to resolve exactly what was committed."""
        mutation_scope.assert_current()
        confirmed = load_confirmed_psychology_learning_catalog(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        mutation_scope.assert_current()
        if confirmed != catalog:
            raise ValueError("psychology learning catalog revision is immutable")
        return confirmed

    def read_production_progress(
        self,
        *,
        series_id: str,
        curriculum_version: str,
    ) -> PsychologyLearningProductionProgress:
        """Read one safe progress sidecar, returning empty progress if absent."""
        catalog, expected_catalog_root_identity = self._resolve_legacy_pinned_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
        )
        return self._read_pinned_production_progress_for_catalog(
            catalog=catalog,
            expected_catalog_root_identity=expected_catalog_root_identity,
        )

    def write_production_progress(
        self,
        *,
        series_id: str,
        curriculum_version: str,
        completed_lesson_ids: tuple[str, ...] | list[str],
    ) -> PsychologyLearningProductionProgress:
        """Replace only the progress sidecar after validating catalog lesson IDs."""
        if type(completed_lesson_ids) not in (tuple, list):
            raise TypeError("completed_lesson_ids must be a concrete tuple or list")
        catalog, expected_catalog_root_identity = self._resolve_legacy_pinned_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
        )
        requested_progress = PsychologyLearningProductionProgress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_digest=catalog.catalog_digest,
            completed_lesson_ids=tuple(completed_lesson_ids),
        )
        requested = requested_progress.completed_lesson_ids
        known_ids = {lesson.lesson_id for lesson in catalog.lessons}
        if any(lesson_id not in known_ids for lesson_id in requested):
            raise ValueError("unknown psychology learning lesson_id for production progress")
        ordered_ids = tuple(
            lesson.lesson_id for lesson in catalog.lessons if lesson.lesson_id in requested
        )
        progress = PsychologyLearningProductionProgress(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_digest=catalog.catalog_digest,
            completed_lesson_ids=ordered_ids,
        )
        return self._write_pinned_production_progress_for_catalog(
            catalog=catalog,
            progress=progress,
            expected_catalog_root_identity=expected_catalog_root_identity,
        )

    def mark_production_lesson_completed(
        self,
        *,
        series_id: str,
        curriculum_version: str,
        lesson_id: str,
        catalog: PsychologyLearningCatalog | None = None,
        expected_catalog_root_identity: os.stat_result | None = None,
        expected_progress_identity: os.stat_result | None = None,
        expected_artifact_root_path: Path | None = None,
        expected_artifact_root_identity: os.stat_result | None = None,
    ) -> PsychologyLearningProductionProgress:
        """Atomically add one completed custom lesson without losing another mark.

        The progress sidecar is replaceable, so a caller must not read its set,
        union one lesson, and write it back outside a cross-process critical
        section.  The lock sits beside the sidecar (not in a scanned immutable
        catalog directory); the existing durable replace protocol remains the
        only persistence mechanism for the actual progress JSON.
        """
        if fcntl is None:
            raise OSError("psychology learning progress locking is unsupported")
        if _pinned_progress_operation_requested(
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_progress_identity=expected_progress_identity,
            expected_artifact_root_path=expected_artifact_root_path,
            expected_artifact_root_identity=expected_artifact_root_identity,
        ):
            if (
                catalog is None
                or expected_catalog_root_identity is None
                or expected_progress_identity is None
            ):
                raise ValueError(
                    "pinned psychology learning progress requires a resolved catalog, root identity, and progress identity"
                )
            if (expected_artifact_root_path is None) != (
                expected_artifact_root_identity is None
            ):
                raise ValueError(
                    "artifact root path and identity must be supplied together"
                )
            return self._mark_pinned_production_lesson_completed(
                series_id=series_id,
                curriculum_version=curriculum_version,
                lesson_id=lesson_id,
                catalog=catalog,
                expected_catalog_root_identity=expected_catalog_root_identity,
                expected_progress_identity=expected_progress_identity,
                expected_artifact_root_path=expected_artifact_root_path,
                expected_artifact_root_identity=expected_artifact_root_identity,
            )
        if catalog is not None:
            raise ValueError("resolved psychology learning catalog requires pinned storage")
        resolved_catalog, expected_catalog_root_identity = self._resolve_legacy_pinned_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
        )
        return self._mark_pinned_production_lesson_completed(
            series_id=series_id,
            curriculum_version=curriculum_version,
            lesson_id=lesson_id,
            catalog=resolved_catalog,
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_progress_identity=self._capture_pinned_progress_directory_identity(
                expected_catalog_root_identity=expected_catalog_root_identity,
            ),
            expected_artifact_root_path=None,
            expected_artifact_root_identity=None,
        )

    def _read_pinned_production_progress_for_catalog(
        self,
        *,
        catalog: PsychologyLearningCatalog,
        expected_catalog_root_identity: os.stat_result,
    ) -> PsychologyLearningProductionProgress:
        """Read the replaceable sidecar through the catalog's pinned namespace."""
        self._assert_pinned_progress_storage(
            expected_catalog_root_identity=expected_catalog_root_identity,
        )
        catalog_fd = _open_pinned_catalog_root(
            catalog_root_path=self.catalog_root.absolute(),
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_artifact_root_path=None,
            expected_artifact_root_identity=None,
        )
        try:
            progress_fd = _open_pinned_directory_entry(
                parent_fd=catalog_fd,
                name="progress",
            )
            try:
                _assert_pinned_progress_directory(
                    catalog_fd=catalog_fd,
                    progress_fd=progress_fd,
                )
                progress, _, _ = _read_pinned_production_progress(
                    parent_fd=progress_fd,
                    name=psychology_learning_series_progress_sidecar_path(
                        series_id=catalog.series_id,
                        curriculum_version=catalog.curriculum_version,
                        catalog_root=self.catalog_root,
                    ).name,
                    catalog=catalog,
                )
                self._assert_pinned_progress_storage(
                    expected_catalog_root_identity=expected_catalog_root_identity,
                )
                _assert_pinned_progress_directory(
                    catalog_fd=catalog_fd,
                    progress_fd=progress_fd,
                )
                return progress
            finally:
                os.close(progress_fd)
        finally:
            os.close(catalog_fd)

    def _write_pinned_production_progress_for_catalog(
        self,
        *,
        catalog: PsychologyLearningCatalog,
        progress: PsychologyLearningProductionProgress,
        expected_catalog_root_identity: os.stat_result,
    ) -> PsychologyLearningProductionProgress:
        """Replace an explicit progress set through the same safe lock domain."""
        if fcntl is None:
            raise OSError("psychology learning progress locking is unsupported")
        if (
            progress.series_id != catalog.series_id
            or progress.curriculum_version != catalog.curriculum_version
            or progress.catalog_digest != catalog.catalog_digest
        ):
            raise ValueError("invalid psychology learning production progress")
        _validate_progress_lesson_ids(progress, catalog)
        self._assert_pinned_progress_storage(
            expected_catalog_root_identity=expected_catalog_root_identity,
        )
        catalog_fd = _open_pinned_catalog_root(
            catalog_root_path=self.catalog_root.absolute(),
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_artifact_root_path=None,
            expected_artifact_root_identity=None,
        )
        try:
            progress_fd = _open_pinned_directory_entry(
                parent_fd=catalog_fd,
                name="progress",
            )
            try:
                _assert_pinned_progress_directory(
                    catalog_fd=catalog_fd,
                    progress_fd=progress_fd,
                )
                progress_name = psychology_learning_series_progress_sidecar_path(
                    series_id=catalog.series_id,
                    curriculum_version=catalog.curriculum_version,
                    catalog_root=self.catalog_root,
                ).name
                lock_name = _pinned_progress_lock_name(progress_name)
                lock_fd = _open_or_create_pinned_progress_lock(
                    parent_fd=progress_fd,
                    name=lock_name,
                )
                try:
                    assert fcntl is not None
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                    try:
                        _assert_pinned_progress_directory(
                            catalog_fd=catalog_fd,
                            progress_fd=progress_fd,
                        )
                        _assert_pinned_progress_lock(
                            parent_fd=progress_fd,
                            name=lock_name,
                            fd=lock_fd,
                        )
                        self._assert_pinned_progress_storage(
                            expected_catalog_root_identity=expected_catalog_root_identity,
                        )
                        _, _, previous_identity = (
                            _read_pinned_production_progress(
                                parent_fd=progress_fd,
                                name=progress_name,
                                catalog=catalog,
                            )
                        )
                        payload_bytes = _canonical_json(
                            progress.model_dump(mode="json")
                        ).encode("utf-8")
                        try:
                            committed_identity = _replace_pinned_regular_file(
                                parent_fd=progress_fd,
                                name=progress_name,
                                payload=payload_bytes,
                                expected_identity=previous_identity,
                            )
                        except OSError:
                            # A failed replace may have left a raced entry.
                            # Never clean it up by name: a same-UID writer can
                            # substitute that name between validation and unlink.
                            raise
                        # Recheck through the final target name after the
                        # outer directory barrier closes the helper-return
                        # window. The helper keeps its own FD open through its
                        # internal barrier; this additional check narrows the
                        # remaining transaction window before returning.
                        os.fsync(progress_fd)
                        _sync_pinned_private_regular_file(
                            parent_fd=progress_fd,
                            name=progress_name,
                            expected_identity=committed_identity,
                            expected_payload_bytes=payload_bytes,
                            payload_error_message="psychology learning progress payload changed",
                        )
                        try:
                            self._assert_pinned_progress_storage(
                                expected_catalog_root_identity=expected_catalog_root_identity,
                            )
                            _assert_pinned_progress_directory(
                                catalog_fd=catalog_fd,
                                progress_fd=progress_fd,
                            )
                            _assert_pinned_progress_lock(
                                parent_fd=progress_fd,
                                name=lock_name,
                                fd=lock_fd,
                            )
                        except OSError:
                            # The replacement is at-least-once once rename has
                            # occurred.  A retry remains idempotent; no rollback
                            # may delete or overwrite a raced name.
                            raise
                        return progress
                    finally:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            finally:
                os.close(progress_fd)
        finally:
            os.close(catalog_fd)

    def _mark_pinned_production_lesson_completed(
        self,
        *,
        series_id: str,
        curriculum_version: str,
        lesson_id: str,
        catalog: PsychologyLearningCatalog,
        expected_catalog_root_identity: os.stat_result,
        expected_progress_identity: os.stat_result,
        expected_artifact_root_path: Path | None,
        expected_artifact_root_identity: os.stat_result | None,
    ) -> PsychologyLearningProductionProgress:
        """Commit one progress marker through the preflight-pinned directory.

        A learning workflow can invoke arbitrary code before it reaches this
        method, so every path below is untrusted by the time this method starts.
        The caller's resolved catalog is therefore used directly and the
        mutable progress sidecar is accessed only from a descriptor opened
        through the preflight artifact root. Once an atomic replacement has
        occurred, a later root rebind is at-least-once: this method fails
        closed and leaves recovery to idempotent retry or trusted offline
        maintenance rather than deleting or restoring a mutable name.
        """
        if (
            catalog.series_id != series_id
            or catalog.curriculum_version != curriculum_version
        ):
            raise ValueError("resolved psychology learning catalog does not match progress")
        if lesson_id not in {lesson.lesson_id for lesson in catalog.lessons}:
            raise ValueError("unknown psychology learning lesson_id for production progress")
        self._assert_pinned_progress_storage(
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_artifact_root_path=expected_artifact_root_path,
            expected_artifact_root_identity=expected_artifact_root_identity,
        )
        catalog_fd = _open_pinned_catalog_root(
            catalog_root_path=self.catalog_root.absolute(),
            expected_catalog_root_identity=expected_catalog_root_identity,
            expected_artifact_root_path=expected_artifact_root_path,
            expected_artifact_root_identity=expected_artifact_root_identity,
        )
        try:
            progress_fd = _open_pinned_directory_entry(
                parent_fd=catalog_fd,
                name="progress",
            )
            try:
                _assert_pinned_progress_directory(
                    catalog_fd=catalog_fd,
                    progress_fd=progress_fd,
                    expected_identity=expected_progress_identity,
                )
                progress_name = psychology_learning_series_progress_sidecar_path(
                    series_id=series_id,
                    curriculum_version=curriculum_version,
                    catalog_root=self.catalog_root,
                ).name
                lock_name = _pinned_progress_lock_name(progress_name)
                lock_fd = _open_or_create_pinned_progress_lock(
                    parent_fd=progress_fd,
                    name=lock_name,
                )
                try:
                    assert fcntl is not None
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                    try:
                        _assert_pinned_progress_directory(
                            catalog_fd=catalog_fd,
                            progress_fd=progress_fd,
                            expected_identity=expected_progress_identity,
                        )
                        _assert_pinned_progress_lock(
                            parent_fd=progress_fd,
                            name=lock_name,
                            fd=lock_fd,
                        )
                        self._assert_pinned_progress_storage(
                            expected_catalog_root_identity=expected_catalog_root_identity,
                            expected_artifact_root_path=expected_artifact_root_path,
                            expected_artifact_root_identity=expected_artifact_root_identity,
                        )
                        current, _, previous_identity = (
                            _read_pinned_production_progress(
                                parent_fd=progress_fd,
                                name=progress_name,
                                catalog=catalog,
                            )
                        )
                        if lesson_id in current.completed_lesson_ids:
                            self._assert_pinned_progress_storage(
                                expected_catalog_root_identity=expected_catalog_root_identity,
                                expected_artifact_root_path=expected_artifact_root_path,
                                expected_artifact_root_identity=expected_artifact_root_identity,
                            )
                            _assert_pinned_progress_directory(
                                catalog_fd=catalog_fd,
                                progress_fd=progress_fd,
                                expected_identity=expected_progress_identity,
                            )
                            _assert_pinned_progress_lock(
                                parent_fd=progress_fd,
                                name=lock_name,
                                fd=lock_fd,
                            )
                            return current
                        updated = PsychologyLearningProductionProgress(
                            series_id=catalog.series_id,
                            curriculum_version=catalog.curriculum_version,
                            catalog_digest=catalog.catalog_digest,
                            completed_lesson_ids=tuple(
                                lesson.lesson_id
                                for lesson in catalog.lessons
                                if lesson.lesson_id
                                in (*current.completed_lesson_ids, lesson_id)
                            ),
                        )
                        self._assert_pinned_progress_storage(
                            expected_catalog_root_identity=expected_catalog_root_identity,
                            expected_artifact_root_path=expected_artifact_root_path,
                            expected_artifact_root_identity=expected_artifact_root_identity,
                        )
                        _assert_pinned_progress_directory(
                            catalog_fd=catalog_fd,
                            progress_fd=progress_fd,
                            expected_identity=expected_progress_identity,
                        )
                        _assert_pinned_progress_lock(
                            parent_fd=progress_fd,
                            name=lock_name,
                            fd=lock_fd,
                        )
                        payload_bytes = _canonical_json(
                            updated.model_dump(mode="json")
                        ).encode("utf-8")
                        try:
                            committed_identity = _replace_pinned_regular_file(
                                parent_fd=progress_fd,
                                name=progress_name,
                                payload=payload_bytes,
                                expected_identity=previous_identity,
                            )
                        except OSError:
                            # Leave an untrusted raced entry in place and fail
                            # closed rather than deleting it by its mutable name.
                            raise
                        # Recheck through the final target name after the
                        # outer directory barrier closes the helper-return
                        # window. Subsequent boundary failures are
                        # at-least-once and are never rolled back by mutable
                        # name.
                        os.fsync(progress_fd)
                        _sync_pinned_private_regular_file(
                            parent_fd=progress_fd,
                            name=progress_name,
                            expected_identity=committed_identity,
                            expected_payload_bytes=payload_bytes,
                            payload_error_message="psychology learning progress payload changed",
                        )
                        try:
                            self._assert_pinned_progress_storage(
                                expected_catalog_root_identity=expected_catalog_root_identity,
                                expected_artifact_root_path=expected_artifact_root_path,
                                expected_artifact_root_identity=expected_artifact_root_identity,
                            )
                            _assert_pinned_progress_directory(
                                catalog_fd=catalog_fd,
                                progress_fd=progress_fd,
                                expected_identity=expected_progress_identity,
                            )
                            _assert_pinned_progress_lock(
                                parent_fd=progress_fd,
                                name=lock_name,
                                fd=lock_fd,
                            )
                        except OSError:
                            # Post-rename failures are at-least-once.  Do not
                            # roll back by name after untrusted workflow code.
                            raise
                        return updated
                    finally:
                        fcntl.flock(lock_fd, fcntl.LOCK_UN)
                finally:
                    os.close(lock_fd)
            finally:
                os.close(progress_fd)
        finally:
            os.close(catalog_fd)


def persist_psychology_learning_series_proposal(
    proposal: PsychologyLearningSeriesProposal | dict[str, Any],
    *,
    catalog_root: Path | str | None = None,
) -> PsychologyLearningSeriesProposal:
    """Convenience API for proposal persistence with an injectable store root."""
    return PsychologyLearningSeriesStore(catalog_root=catalog_root).persist_proposal(proposal)


def confirm_psychology_learning_series_proposal(
    *,
    proposal_id: str,
    proposal_fingerprint: str,
    catalog_root: Path | str | None = None,
) -> PsychologyLearningCatalog:
    """Convenience API for explicit confirmation of an exact proposal receipt."""
    return PsychologyLearningSeriesStore(catalog_root=catalog_root).confirm(
        proposal_id=proposal_id,
        proposal_fingerprint=proposal_fingerprint,
    )


def _write_new_json(
    path: Path,
    payload: dict[str, Any],
    *,
    mutation_scope: _PinnedCatalogMutationScope | None = None,
) -> None:
    """Create one immutable JSON entry directly through a no-follow directory FD.

    ``O_EXCL`` makes the immutable name visible exactly once without a staged
    alias that would later need a non-atomic name cleanup.  A failed write may
    therefore leave an unreadable/uncommitted entry behind; retries verify an
    exact existing snapshot or fail closed instead of deleting a name another
    same-UID writer could have replaced.
    """
    common_parent_fd: int | None = None
    target_parent_fd: int | None = None
    target_fd: int | None = None
    try:
        if mutation_scope is None:
            common_parent_fd = _open_or_create_no_follow_directory_path(
                path.parent.parent,
                create=False,
            )
            target_parent_fd = _open_pinned_directory_entry(
                parent_fd=common_parent_fd,
                name=path.parent.name,
            )
        else:
            target_directory, _ = mutation_scope.relative_parts(path)
            target_parent_fd = mutation_scope.open_directory(target_directory)
        try:
            target_fd = os.open(
                path.name,
                _pinned_file_flags(writable=True, create=True) | os.O_EXCL,
                0o600,
                dir_fd=target_parent_fd,
            )
        except FileExistsError:
            _sync_pinned_private_regular_file(
                parent_fd=target_parent_fd,
                name=path.name,
            )
            raise
        payload_bytes = _canonical_json(payload).encode("utf-8")
        _assert_pinned_private_regular_entry(
            parent_fd=target_parent_fd,
            name=path.name,
            fd=target_fd,
        )
        _write_all_to_fd(target_fd, payload_bytes)
        os.fsync(target_fd)
        _assert_pinned_private_regular_entry(
            parent_fd=target_parent_fd,
            name=path.name,
            fd=target_fd,
        )
        _assert_pinned_file_payload(
            fd=target_fd,
            expected_payload_bytes=payload_bytes,
            name=path.name,
        )
        if mutation_scope is not None:
            mutation_scope.assert_current()
        _sync_pinned_private_regular_file(
            parent_fd=target_parent_fd,
            name=path.name,
            expected_nlink=1,
            expected_identity=os.fstat(target_fd),
            expected_payload_bytes=payload_bytes,
        )
        if mutation_scope is not None:
            mutation_scope.assert_current()
    finally:
        if target_fd is not None:
            os.close(target_fd)
        if target_parent_fd is not None:
            os.close(target_parent_fd)
        if common_parent_fd is not None:
            os.close(common_parent_fd)


def _open_or_create_no_follow_directory_path(
    path: Path,
    *,
    create: bool = True,
) -> int:
    """Open a lexical absolute directory path, creating only safe components."""
    normalized = Path(os.path.abspath(os.fspath(path)))
    if not normalized.is_absolute():  # pragma: no cover - abspath guarantees this.
        raise OSError("psychology learning storage path must be absolute")
    current_fd = os.open("/", _pinned_directory_flags())
    try:
        for component in normalized.parts[1:]:
            if component in {"", ".", ".."}:
                raise OSError("invalid psychology learning storage path component")
            # Every existing ancestor is part of the durable path to the
            # eventual commit. Re-sync it on retry instead of trusting an
            # earlier interrupted directory creation.
            os.fsync(current_fd)
            next_fd = (
                _open_or_create_pinned_directory(
                    parent_fd=current_fd,
                    name=component,
                )
                if create
                else _open_pinned_directory_entry(
                    parent_fd=current_fd,
                    name=component,
                )
            )
            os.fsync(next_fd)
            os.close(current_fd)
            current_fd = next_fd
        os.fsync(current_fd)
        result = current_fd
        current_fd = -1
        return result
    finally:
        if current_fd >= 0:
            os.close(current_fd)


def _pinned_directory_path_exists(path: Path) -> bool:
    try:
        fd = _open_or_create_no_follow_directory_path(path, create=False)
    except FileNotFoundError:
        return False
    try:
        return True
    finally:
        os.close(fd)


def _pinned_directory_path_identity(path: Path) -> os.stat_result:
    fd = _open_or_create_no_follow_directory_path(path, create=False)
    try:
        identity = os.fstat(fd)
        if not stat.S_ISDIR(identity.st_mode):
            raise OSError("psychology learning storage root is not a directory")
        return identity
    finally:
        os.close(fd)


def _pinned_directory_mutation_version(identity: os.stat_result) -> tuple[int, int]:
    return identity.st_mtime_ns, identity.st_ctime_ns


def _sync_pinned_private_regular_file(
    *,
    parent_fd: int,
    name: str,
    expected_nlink: int = 1,
    expected_identity: os.stat_result | None = None,
    expected_payload_bytes: bytes | None = None,
    payload_error_message: str = "psychology learning immutable snapshot source changed",
) -> None:
    fd = os.open(name, _pinned_file_flags(writable=False), dir_fd=parent_fd)
    try:
        _assert_pinned_private_regular_entry(
            parent_fd=parent_fd,
            name=name,
            fd=fd,
            expected_nlink=expected_nlink,
        )
        if expected_identity is not None and not os.path.samestat(
            os.fstat(fd),
            expected_identity,
        ):
            raise OSError(
                errno.EPERM,
                "psychology learning immutable snapshot source changed",
                name,
            )
        if expected_payload_bytes is not None:
            _assert_pinned_file_payload(
                fd=fd,
                expected_payload_bytes=expected_payload_bytes,
                name=name,
                error_message=payload_error_message,
            )
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent_fd)


def _assert_pinned_file_payload(
    *,
    fd: int,
    expected_payload_bytes: bytes,
    name: str,
    error_message: str = "psychology learning immutable snapshot source changed",
) -> None:
    """Reject an inode whose bytes changed while its link identity looked valid."""
    os.lseek(fd, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 64 * 1024)
        if not chunk:
            break
        chunks.append(chunk)
    if b"".join(chunks) != expected_payload_bytes:
        raise OSError(
            errno.EPERM,
            error_message,
            name,
        )


def _read_pinned_immutable_json_path(path: Path) -> dict[str, Any]:
    """Read one immutable JSON snapshot through a no-follow descriptor chain."""
    parent_fd = _open_or_create_no_follow_directory_path(path.parent, create=False)
    try:
        fd = os.open(path.name, _pinned_file_flags(writable=False), dir_fd=parent_fd)
        try:
            _assert_pinned_private_regular_entry(
                parent_fd=parent_fd,
                name=path.name,
                fd=fd,
            )
            parts: list[bytes] = []
            while True:
                chunk = os.read(fd, 64 * 1024)
                if not chunk:
                    break
                parts.append(chunk)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    payload = json.loads(b"".join(parts).decode("utf-8"))
    if type(payload) is not dict:
        raise ValueError("immutable psychology learning snapshot must be a JSON object")
    return payload


def _assert_pinned_private_regular_entry(
    *,
    parent_fd: int,
    name: str,
    fd: int,
    expected_nlink: int = 1,
) -> None:
    entry = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
    identity = os.fstat(fd)
    if (
        not stat.S_ISREG(entry.st_mode)
        or not stat.S_ISREG(identity.st_mode)
        or not os.path.samestat(entry, identity)
        or entry.st_nlink != expected_nlink
        or identity.st_nlink != expected_nlink
    ):
        raise OSError(
            errno.EMLINK,
            "psychology learning immutable snapshot must be a private regular file",
            name,
        )


def _pinned_progress_operation_requested(
    *,
    expected_catalog_root_identity: os.stat_result | None,
    expected_progress_identity: os.stat_result | None,
    expected_artifact_root_path: Path | None,
    expected_artifact_root_identity: os.stat_result | None,
) -> bool:
    """Return whether a caller supplied any frozen storage boundary."""
    return any(
        value is not None
        for value in (
            expected_catalog_root_identity,
            expected_progress_identity,
            expected_artifact_root_path,
            expected_artifact_root_identity,
        )
    )


def _pinned_directory_flags() -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError(
            errno.ENOTSUP,
            "pinned psychology learning storage requires O_NOFOLLOW",
        )
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | os.O_NOFOLLOW


def _pinned_file_flags(*, writable: bool, create: bool = False) -> int:
    if not hasattr(os, "O_NOFOLLOW"):
        raise OSError(
            errno.ENOTSUP,
            "pinned psychology learning storage requires O_NOFOLLOW",
        )
    flags = os.O_RDWR if writable else os.O_RDONLY
    if create:
        flags |= os.O_CREAT
    return flags | os.O_NOFOLLOW


def _open_pinned_catalog_root(
    *,
    catalog_root_path: Path,
    expected_catalog_root_identity: os.stat_result,
    expected_artifact_root_path: Path | None,
    expected_artifact_root_identity: os.stat_result | None,
) -> int:
    """Open the catalog root from a no-follow descriptor chain.

    In production the catalog lives directly under the artifact root.  Opening
    it through that root descriptor prevents an intermediate root symlink from
    silently resolving to the old catalog inode after the lexical artifact root
    has been rebound.
    """
    if expected_artifact_root_path is None:
        return _open_pinned_directory_path(
            path=catalog_root_path,
            expected_identity=expected_catalog_root_identity,
        )
    if expected_artifact_root_identity is None:
        raise ValueError("artifact root path and identity must be supplied together")
    artifact_root_path = expected_artifact_root_path.absolute()
    try:
        relative_catalog_path = catalog_root_path.relative_to(artifact_root_path)
    except ValueError as exc:
        raise ValueError("catalog root must be inside the pinned artifact root") from exc
    artifact_fd = _open_pinned_directory_path(
        path=artifact_root_path,
        expected_identity=expected_artifact_root_identity,
    )
    catalog_fd: int | None = None
    try:
        catalog_fd = os.dup(artifact_fd)
        for part in relative_catalog_path.parts:
            if part in {"", ".", ".."}:
                raise ValueError("invalid pinned catalog root component")
            next_fd = _open_pinned_directory_entry(
                parent_fd=catalog_fd,
                name=part,
            )
            os.close(catalog_fd)
            catalog_fd = next_fd
        catalog_identity = os.fstat(catalog_fd)
        if not os.path.samestat(catalog_identity, expected_catalog_root_identity):
            raise OSError(
                errno.ELOOP,
                "psychology learning catalog root changed",
                str(catalog_root_path),
            )
        result = catalog_fd
        catalog_fd = None
        return result
    finally:
        try:
            if catalog_fd is not None:
                os.close(catalog_fd)
        finally:
            os.close(artifact_fd)


def _open_pinned_directory_path(
    *,
    path: Path,
    expected_identity: os.stat_result,
) -> int:
    fd = os.open(path, _pinned_directory_flags())
    try:
        identity = os.fstat(fd)
        if (
            not stat.S_ISDIR(identity.st_mode)
            or not os.path.samestat(identity, expected_identity)
        ):
            raise OSError(errno.ELOOP, "psychology learning storage root changed", str(path))
        return fd
    except Exception:
        os.close(fd)
        raise


def _open_pinned_directory_entry(*, parent_fd: int, name: str) -> int:
    fd = os.open(name, _pinned_directory_flags(), dir_fd=parent_fd)
    try:
        identity = os.fstat(fd)
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            not stat.S_ISDIR(identity.st_mode)
            or not stat.S_ISDIR(entry.st_mode)
            or not os.path.samestat(identity, entry)
        ):
            raise OSError(errno.ELOOP, "psychology learning directory changed", name)
        return fd
    except Exception:
        os.close(fd)
        raise


def _assert_pinned_directory_entry_matches(
    *,
    parent_fd: int,
    name: str,
    expected_identity: os.stat_result,
) -> None:
    entry = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
    if (
        not stat.S_ISDIR(entry.st_mode)
        or not os.path.samestat(entry, expected_identity)
    ):
        raise OSError("psychology learning storage directory changed")


def _open_or_create_pinned_directory(*, parent_fd: int, name: str) -> int:
    fd, _ = _open_or_create_pinned_directory_with_creation(
        parent_fd=parent_fd,
        name=name,
    )
    return fd


def _open_or_create_pinned_directory_with_creation(
    *,
    parent_fd: int,
    name: str,
) -> tuple[int, bool]:
    try:
        return _open_pinned_directory_entry(parent_fd=parent_fd, name=name), False
    except FileNotFoundError:
        try:
            os.mkdir(name, 0o700, dir_fd=parent_fd)
        except FileExistsError:
            return _open_pinned_directory_entry(parent_fd=parent_fd, name=name), False
        else:
            os.fsync(parent_fd)
        return _open_pinned_directory_entry(parent_fd=parent_fd, name=name), True


def _assert_pinned_progress_directory(
    *,
    catalog_fd: int,
    progress_fd: int,
    expected_identity: os.stat_result | None = None,
) -> None:
    """Keep flat progress entries inside the pre-provisioned namespace."""
    progress_identity = os.fstat(progress_fd)
    progress_entry = _pinned_entry_lstat(parent_fd=catalog_fd, name="progress")
    if (
        not stat.S_ISDIR(progress_identity.st_mode)
        or not stat.S_ISDIR(progress_entry.st_mode)
        or not os.path.samestat(progress_identity, progress_entry)
        or (
            expected_identity is not None
            and (
                not os.path.samestat(progress_identity, expected_identity)
                or not os.path.samestat(progress_entry, expected_identity)
            )
        )
    ):
        raise OSError(errno.ELOOP, "psychology learning progress directory changed")
    _assert_trusted_provisioned_directory_identity(
        identity=progress_identity,
        label="psychology learning storage directory progress",
    )


def _pinned_progress_lock_name(progress_name: str) -> str:
    if not progress_name.endswith(".json"):
        raise ValueError("invalid psychology learning progress entry")
    return f".{progress_name.removesuffix('.json')}.lock"


def _open_or_create_pinned_progress_lock(*, parent_fd: int, name: str) -> int:
    """Create a private lock file atomically or reopen and verify it."""
    try:
        fd = os.open(
            name,
            _pinned_file_flags(writable=True, create=True) | os.O_EXCL,
            0o600,
            dir_fd=parent_fd,
        )
    except FileExistsError:
        fd = os.open(
            name,
            _pinned_file_flags(writable=True),
            dir_fd=parent_fd,
        )
    try:
        _assert_pinned_progress_lock(parent_fd=parent_fd, name=name, fd=fd)
        os.fsync(fd)
        os.fsync(parent_fd)
        _assert_pinned_progress_lock(parent_fd=parent_fd, name=name, fd=fd)
        return fd
    except Exception:
        os.close(fd)
        raise


def _assert_pinned_progress_lock(*, parent_fd: int, name: str, fd: int) -> None:
    entry = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
    identity = os.fstat(fd)
    if (
        not _is_private_regular_entry(entry=entry, expected_identity=identity)
        or identity.st_nlink != 1
    ):
        raise OSError(errno.ELOOP, "psychology learning progress lock changed", name)


def _pinned_entry_lstat(*, parent_fd: int, name: str) -> os.stat_result:
    return os.stat(name, dir_fd=parent_fd, follow_symlinks=False)


def _is_private_regular_entry(
    *,
    entry: os.stat_result,
    expected_identity: os.stat_result | None = None,
) -> bool:
    return (
        stat.S_ISREG(entry.st_mode)
        and not stat.S_ISLNK(entry.st_mode)
        and entry.st_nlink == 1
        and (
            expected_identity is None
            or os.path.samestat(entry, expected_identity)
        )
    )


def _read_pinned_regular_file(
    *,
    parent_fd: int,
    name: str,
) -> tuple[bytes | None, os.stat_result | None]:
    # A prior successful rename whose directory barrier failed must not be
    # treated as durable by a later reader until this same namespace can sync.
    os.fsync(parent_fd)
    try:
        before_open = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
    except FileNotFoundError:
        return None, None
    if not _is_private_regular_entry(entry=before_open):
        raise OSError(errno.ELOOP, "psychology learning file changed", name)
    fd = os.open(
        name,
        _pinned_file_flags(writable=False),
        dir_fd=parent_fd,
    )
    try:
        opened_identity = os.fstat(fd)
        after_open = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
        if (
            not _is_private_regular_entry(
                entry=opened_identity,
                expected_identity=before_open,
            )
            or not _is_private_regular_entry(
                entry=after_open,
                expected_identity=opened_identity,
            )
        ):
            raise OSError(errno.ELOOP, "psychology learning file changed", name)
        os.fsync(fd)
        return _read_all_from_fd(fd), opened_identity
    finally:
        os.close(fd)


def _read_pinned_production_progress(
    *,
    parent_fd: int,
    name: str,
    catalog: PsychologyLearningCatalog,
) -> tuple[PsychologyLearningProductionProgress, bytes | None, os.stat_result | None]:
    raw, identity = _read_pinned_regular_file(parent_fd=parent_fd, name=name)
    if raw is None:
        return (
            PsychologyLearningProductionProgress(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                catalog_digest=catalog.catalog_digest,
            ),
            None,
            None,
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid psychology learning production progress") from exc
    if type(payload) is not dict:
        raise ValueError("invalid psychology learning production progress")
    try:
        progress = PsychologyLearningProductionProgress.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid psychology learning production progress") from exc
    if (
        progress.series_id != catalog.series_id
        or progress.curriculum_version != catalog.curriculum_version
        or progress.catalog_digest != catalog.catalog_digest
    ):
        raise ValueError("invalid psychology learning production progress")
    _validate_progress_lesson_ids(progress, catalog)
    return progress, raw, identity


def _replace_pinned_regular_file(
    *,
    parent_fd: int,
    name: str,
    payload: bytes,
    expected_identity: os.stat_result | None,
) -> os.stat_result:
    temporary_name = f".{name}.{uuid4().hex}.tmp"
    temporary_fd: int | None = None
    try:
        temporary_fd = os.open(
            temporary_name,
            _pinned_file_flags(writable=True, create=True) | os.O_EXCL,
            0o600,
            dir_fd=parent_fd,
        )
        _write_all_to_fd(temporary_fd, payload)
        os.fsync(temporary_fd)
        temporary_identity = os.fstat(temporary_fd)
        _assert_pinned_file_payload(
            fd=temporary_fd,
            expected_payload_bytes=payload,
            name=temporary_name,
            error_message="psychology learning progress payload changed",
        )
        _verify_pinned_temporary_source(
            parent_fd=parent_fd,
            name=temporary_name,
            expected_identity=temporary_identity,
        )
        try:
            current_identity = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
        except FileNotFoundError:
            if expected_identity is not None:
                raise OSError(errno.ELOOP, "psychology learning file changed", name)
        else:
            if (
                expected_identity is None
                or not _is_private_regular_entry(
                    entry=current_identity,
                    expected_identity=expected_identity,
                )
            ):
                raise OSError(errno.ELOOP, "psychology learning file changed", name)
        # The source name is mutable even though its descriptor remains open.
        # Recheck immediately before replacement; every post-replace mismatch
        # fails closed and leaves its name for trusted offline maintenance.
        _verify_pinned_temporary_source(
            parent_fd=parent_fd,
            name=temporary_name,
            expected_identity=temporary_identity,
        )
        _assert_pinned_file_payload(
            fd=temporary_fd,
            expected_payload_bytes=payload,
            name=temporary_name,
            error_message="psychology learning progress payload changed",
        )
        os.replace(
            temporary_name,
            name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        committed_identity = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
        if not _is_private_regular_entry(
            entry=committed_identity,
            expected_identity=temporary_identity,
        ):
            raise OSError(errno.ELOOP, "psychology learning file changed", name)
        _assert_pinned_file_payload(
            fd=temporary_fd,
            expected_payload_bytes=payload,
            name=name,
            error_message="psychology learning progress payload changed",
        )
        os.fsync(parent_fd)
        committed_identity = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
        if not _is_private_regular_entry(
            entry=committed_identity,
            expected_identity=temporary_identity,
        ):
            raise OSError(errno.ELOOP, "psychology learning file changed", name)
        _assert_pinned_file_payload(
            fd=temporary_fd,
            expected_payload_bytes=payload,
            name=name,
            error_message="psychology learning progress payload changed",
        )
        return committed_identity
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)


def _verify_pinned_temporary_source(
    *,
    parent_fd: int,
    name: str,
    expected_identity: os.stat_result,
) -> None:
    """Require the named replacement source to remain our private temp inode."""
    current_identity = _pinned_entry_lstat(parent_fd=parent_fd, name=name)
    if not _is_private_regular_entry(
        entry=current_identity,
        expected_identity=expected_identity,
    ):
        raise OSError(errno.ELOOP, "psychology learning temporary file changed", name)


def _read_all_from_fd(fd: int) -> bytes:
    chunks: list[bytes] = []
    while True:
        chunk = os.read(fd, 64 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _write_all_to_fd(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError(errno.EIO, "could not write psychology learning progress")
        view = view[written:]


def _validate_progress_lesson_ids(
    progress: PsychologyLearningProductionProgress,
    catalog: PsychologyLearningCatalog,
) -> None:
    known_ids = {lesson.lesson_id for lesson in catalog.lessons}
    if any(lesson_id not in known_ids for lesson_id in progress.completed_lesson_ids):
        raise ValueError("invalid psychology learning production progress")
    expected_order = tuple(
        lesson.lesson_id
        for lesson in catalog.lessons
        if lesson.lesson_id in progress.completed_lesson_ids
    )
    if progress.completed_lesson_ids != expected_order:
        raise ValueError("invalid psychology learning production progress")


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
