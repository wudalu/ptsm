"""Proposal, confirmation, and local persistence for psychology learning series."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from ptsm.domain.psychology_learning import (
    PsychologyLearningCatalog,
    PsychologyLearningCatalogRevisionRecord,
    PsychologyLearningOutlineItem,
    PsychologyLearningProductionProgress,
    PsychologyLearningSeriesPlanIntent,
    PsychologyLearningSeriesProposal,
    _build_confirmed_psychology_learning_catalog,
    _build_psychology_learning_catalog_revision_record,
    _confirmed_catalog_snapshot_versions,
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
        catalog = _build_confirmed_psychology_learning_catalog(
            proposal,
            curriculum_version=pending.curriculum_version,
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
                catalog.approval != record.approval
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
    staging_directory.mkdir(parents=True, exist_ok=True)
    temp_path = staging_directory / f"{path.name}.{uuid4().hex}.tmp"
    try:
        temp_path.write_text(_canonical_json(payload), encoding="utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        os.link(temp_path, path)
    except OSError:
        if not path.exists():
            try:
                path.parent.rmdir()
            except OSError:
                pass
        raise
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass


def _replace_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temp_path.write_text(_canonical_json(payload), encoding="utf-8")
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


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
