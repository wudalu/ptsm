"""Proposal, confirmation, and local persistence for psychology learning series."""

from __future__ import annotations

import json
import os
from pathlib import Path
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
    _build_confirmed_psychology_learning_catalog,
    _build_confirmed_psychology_learning_catalog_for_template,
    _build_psychology_learning_catalog_revision_record,
    _confirmed_catalog_snapshot_versions,
    _load_confirmed_psychology_learning_catalog_snapshot,
    _read_psychology_learning_catalog_revision_records,
    _sync_existing_directory,
    _sync_existing_json,
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


class PsychologyLearningSeriesStore:
    """Local immutable proposal/catalog store with a separate progress sidecar.

    The store is intentionally application-owned: it controls filesystem writes,
    while the domain resolver independently revalidates every stored catalog
    before it can become a selected lesson.  Proposal and catalog paths are
    append-only; only production progress is replaceable.
    """

    def __init__(self, *, catalog_root: Path | str | None = None) -> None:
        self.catalog_root = psychology_learning_series_catalog_root(catalog_root)

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
        if path.exists():
            existing = read_psychology_learning_series_proposal_snapshot(
                proposal_id=normalized.proposal_id,
                catalog_root=self.catalog_root,
            )
            if existing != normalized:
                raise ValueError("psychology learning proposal snapshot is immutable")
            return existing
        payload = normalized.model_dump(mode="json")
        try:
            _write_new_json(path, payload)
        except FileExistsError:
            existing = read_psychology_learning_series_proposal_snapshot(
                proposal_id=normalized.proposal_id,
                catalog_root=self.catalog_root,
            )
            if existing != normalized:
                raise ValueError("psychology learning proposal snapshot is immutable")
            return existing
        return normalized

    def read_proposal(self, *, proposal_id: str) -> PsychologyLearningSeriesProposal:
        return read_psychology_learning_series_proposal_snapshot(
            proposal_id=proposal_id,
            catalog_root=self.catalog_root,
        )

    def confirm(
        self,
        *,
        proposal_id: str,
        proposal_fingerprint: str,
    ) -> PsychologyLearningCatalog:
        """Confirm one exact stored proposal as an append-only catalog revision."""
        proposal = self.read_proposal(proposal_id=proposal_id)
        if proposal.proposal_fingerprint != proposal_fingerprint:
            raise ValueError("psychology learning proposal fingerprint does not match")
        self._sync_existing_catalog_history(series_id=proposal.series_id_candidate)
        records = _read_psychology_learning_catalog_revision_records(
            series_id=proposal.series_id_candidate,
            catalog_root=self.catalog_root,
        )
        try:
            revisions = list_confirmed_psychology_learning_catalog_revisions(
                series_id=proposal.series_id_candidate,
                catalog_root=self.catalog_root,
            )
        except ValueError:
            return self._recover_pending_catalog_snapshot(
                proposal=proposal,
                records=records,
            )
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
            return existing
        next_version = str(
            max((int(catalog.curriculum_version) for catalog in revisions), default=0) + 1
        )
        catalog = _build_confirmed_psychology_learning_catalog(
            proposal,
            curriculum_version=next_version,
        )
        self._persist_confirmation_record(catalog)
        return self._persist_catalog_snapshot(catalog)

    def _sync_existing_catalog_history(self, *, series_id: str) -> None:
        """Complete a prior durable commit barrier before accepting existing history."""
        for directory in (
            self.catalog_root / "confirmations" / series_id,
            self.catalog_root / "catalogs" / series_id,
        ):
            if directory.exists():
                _sync_existing_directory(directory)

    def _recover_pending_catalog_snapshot(
        self,
        *,
        proposal: PsychologyLearningSeriesProposal,
        records: tuple[PsychologyLearningCatalogRevisionRecord, ...],
    ) -> PsychologyLearningCatalog:
        """Complete only the single pending snapshot bound to this proposal."""
        pending_records = tuple(
            record
            for record in records
            if not psychology_learning_series_catalog_snapshot_path(
                series_id=record.series_id,
                curriculum_version=record.curriculum_version,
                catalog_root=self.catalog_root,
            ).exists()
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
        return self._persist_catalog_snapshot(catalog)

    def _validate_recoverable_catalog_history(
        self,
        *,
        records: tuple[PsychologyLearningCatalogRevisionRecord, ...],
        pending: PsychologyLearningCatalogRevisionRecord,
    ) -> None:
        """Reject corruption before completing one ledger-backed snapshot."""
        catalog_directory = self.catalog_root / "catalogs" / pending.series_id
        expected_existing_versions = [
            int(record.curriculum_version)
            for record in records
            if record.curriculum_version != pending.curriculum_version
        ]
        if catalog_directory.exists():
            try:
                versions = _confirmed_catalog_snapshot_versions(catalog_directory)
            except ValueError as exc:
                raise ValueError("invalid psychology learning catalog revision history") from exc
        else:
            versions = []
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

    def _persist_catalog_snapshot(
        self,
        catalog: PsychologyLearningCatalog,
    ) -> PsychologyLearningCatalog:
        path = psychology_learning_series_catalog_snapshot_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        try:
            _write_new_json(path, catalog.model_dump(mode="json"))
        except FileExistsError:
            existing = load_confirmed_psychology_learning_catalog(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                catalog_root=self.catalog_root,
            )
            if existing != catalog:
                raise ValueError("psychology learning catalog revision is immutable")
            return existing
        return catalog

    def _persist_confirmation_record(self, catalog: PsychologyLearningCatalog) -> None:
        record = _build_psychology_learning_catalog_revision_record(catalog)
        path = psychology_learning_series_catalog_confirmation_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        try:
            _write_new_json(path, record.model_dump(mode="json"))
        except FileExistsError:
            records = _read_psychology_learning_catalog_revision_records(
                series_id=catalog.series_id,
                catalog_root=self.catalog_root,
            )
            existing = next(
                (
                    existing_record
                    for existing_record in records
                    if existing_record.curriculum_version == catalog.curriculum_version
                ),
                None,
            )
            if existing != record:
                raise ValueError("psychology learning catalog revision is immutable")

    def read_production_progress(
        self,
        *,
        series_id: str,
        curriculum_version: str,
    ) -> PsychologyLearningProductionProgress:
        """Read one safe progress sidecar, returning empty progress if absent."""
        catalog = load_confirmed_psychology_learning_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
            catalog_root=self.catalog_root,
        )
        path = psychology_learning_series_progress_sidecar_path(
            series_id=series_id,
            curriculum_version=curriculum_version,
            catalog_root=self.catalog_root,
        )
        if not path.exists():
            return PsychologyLearningProductionProgress(
                series_id=catalog.series_id,
                curriculum_version=catalog.curriculum_version,
                catalog_digest=catalog.catalog_digest,
            )
        _sync_existing_json(path)
        payload = _read_progress_json(path)
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
        return progress

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
        catalog = load_confirmed_psychology_learning_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
            catalog_root=self.catalog_root,
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
        path = psychology_learning_series_progress_sidecar_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        _replace_json(path, progress.model_dump(mode="json"))
        return progress

    def mark_production_lesson_completed(
        self,
        *,
        series_id: str,
        curriculum_version: str,
        lesson_id: str,
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
        catalog = load_confirmed_psychology_learning_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
            catalog_root=self.catalog_root,
        )
        if lesson_id not in {lesson.lesson_id for lesson in catalog.lessons}:
            raise ValueError("unknown psychology learning lesson_id for production progress")
        path = psychology_learning_series_progress_sidecar_path(
            series_id=catalog.series_id,
            curriculum_version=catalog.curriculum_version,
            catalog_root=self.catalog_root,
        )
        _ensure_durable_directory(path.parent)
        lock_path = path.with_name(f"{path.name}.lock")
        with lock_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                current = self.read_production_progress(
                    series_id=catalog.series_id,
                    curriculum_version=catalog.curriculum_version,
                )
                if lesson_id in current.completed_lesson_ids:
                    return current
                return self.write_production_progress(
                    series_id=catalog.series_id,
                    curriculum_version=catalog.curriculum_version,
                    completed_lesson_ids=(
                        *current.completed_lesson_ids,
                        lesson_id,
                    ),
                )
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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


def _write_new_json(path: Path, payload: dict[str, Any]) -> None:
    staging_directory = path.parent.parent / ".staging"
    _ensure_durable_directory(staging_directory)
    created_target_directories = _ensure_durable_directory(path.parent)
    temp_path = staging_directory / f"{path.name}.{uuid4().hex}.tmp"
    try:
        _write_and_sync_json(temp_path, payload)
        try:
            os.link(temp_path, path)
        except FileExistsError:
            _sync_existing_json(path)
            raise
        _sync_existing_directory(path.parent)
    except OSError:
        if not path.exists():
            _remove_empty_directories(created_target_directories)
        raise
    finally:
        _best_effort_unlink(temp_path)


def _replace_json(path: Path, payload: dict[str, Any]) -> None:
    created_target_directories = _ensure_durable_directory(path.parent)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        _write_and_sync_json(temp_path, payload)
        temp_path.replace(path)
        _sync_existing_directory(path.parent)
    except OSError:
        if not path.exists():
            _remove_empty_directories(created_target_directories)
        raise
    finally:
        _best_effort_unlink(temp_path)


def _write_and_sync_json(path: Path, payload: dict[str, Any]) -> None:
    """Create one staged JSON file and make its content durable before commit."""
    with path.open("x", encoding="utf-8") as handle:
        handle.write(_canonical_json(payload))
        handle.flush()
        os.fsync(handle.fileno())


def _ensure_durable_directory(path: Path) -> tuple[Path, ...]:
    """Create missing directory ancestors and sync each new entry before use."""
    missing: list[Path] = []
    current = path
    while not current.exists():
        missing.append(current)
        parent = current.parent
        if parent == current:
            raise OSError(f"cannot create durable directory {path}")
        current = parent
    if not current.is_dir():
        raise NotADirectoryError(current)
    created: list[Path] = []
    try:
        _sync_existing_directory(current)
        for directory in reversed(missing):
            try:
                directory.mkdir()
            except FileExistsError:
                # Another progress marker can create this parent between the
                # existence scan above and our mkdir.  Accept only the exact
                # directory shape, then synchronize the winner's entry before
                # continuing to its child.
                if not directory.is_dir():
                    raise NotADirectoryError(directory)
            else:
                created.append(directory)
            _sync_existing_directory(directory)
    except OSError:
        _remove_empty_directories(tuple(created))
        raise
    return tuple(created)


def _remove_empty_directories(directories: tuple[Path, ...]) -> None:
    """Best-effort cleanup for directories created by an unsuccessful write."""
    for directory in reversed(directories):
        try:
            directory.rmdir()
            _sync_existing_directory(directory.parent)
        except OSError:
            pass


def _best_effort_unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass


def _read_progress_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid psychology learning production progress") from exc
    if type(payload) is not dict:
        raise ValueError("invalid psychology learning production progress")
    return payload


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
