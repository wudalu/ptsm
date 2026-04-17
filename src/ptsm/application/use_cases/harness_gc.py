from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import re
import shutil
from typing import Any

import yaml


FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
DEFAULT_DOC_STALE_DAYS = 90
DEFAULT_RUNS_RETENTION_DAYS = 30
DEFAULT_PLAN_RUNS_RETENTION_DAYS = 30


def inspect_harness_state(
    *,
    project_root: Path | str = ".",
    now: datetime | None = None,
    doc_stale_days: int = DEFAULT_DOC_STALE_DAYS,
    runs_retention_days: int = DEFAULT_RUNS_RETENTION_DAYS,
    plan_runs_retention_days: int = DEFAULT_PLAN_RUNS_RETENTION_DAYS,
) -> dict[str, object]:
    root = Path(project_root)
    current_time = now or datetime.now(timezone.utc)

    docs_check = _inspect_docs_freshness(
        docs_root=root / "docs",
        current_time=current_time,
        stale_days=doc_stale_days,
        root=root,
    )
    run_store_check, run_candidates = _inspect_run_store(
        runs_dir=root / ".ptsm" / "runs",
        current_time=current_time,
        retention_days=runs_retention_days,
        root=root,
    )
    plan_runs_check, plan_run_candidates = _inspect_plan_runs(
        plan_runs_dir=root / ".ptsm" / "plan_runs",
        current_time=current_time,
        retention_days=plan_runs_retention_days,
        root=root,
    )

    checks = [docs_check, run_store_check, plan_runs_check]
    status = "warning" if any(check["status"] == "warning" for check in checks) else "ok"
    return {
        "status": status,
        "checks": checks,
        "candidates": [*run_candidates, *plan_run_candidates],
    }


def run_harness_gc(
    *,
    project_root: Path | str = ".",
    now: datetime | None = None,
    runs_retention_days: int = DEFAULT_RUNS_RETENTION_DAYS,
    plan_runs_retention_days: int = DEFAULT_PLAN_RUNS_RETENTION_DAYS,
    apply: bool = False,
) -> dict[str, object]:
    inspection = inspect_harness_state(
        project_root=project_root,
        now=now,
        runs_retention_days=runs_retention_days,
        plan_runs_retention_days=plan_runs_retention_days,
    )
    candidates = list(inspection["candidates"])
    removed: list[dict[str, object]] = []

    if apply:
        for candidate in candidates:
            for raw_path in candidate["paths"]:
                path = Path(project_root) / str(raw_path)
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=False)
                elif path.exists():
                    path.unlink()
            removed.append(candidate)

    return {
        "status": "applied" if apply else "dry-run",
        "candidate_count": len(candidates),
        "removed_count": len(removed),
        "candidates": candidates,
        "removed": removed,
    }


def _inspect_docs_freshness(
    *,
    docs_root: Path,
    current_time: datetime,
    stale_days: int,
    root: Path,
) -> dict[str, object]:
    stale_cutoff = current_time.date() - timedelta(days=stale_days)
    stale_docs: list[str] = []

    if docs_root.exists():
        for path in docs_root.rglob("*.md"):
            metadata = _load_front_matter(path)
            if not metadata:
                continue
            if metadata.get("status") != "active":
                continue
            if metadata.get("source_of_truth") is not True:
                continue
            last_verified = metadata.get("last_verified")
            if last_verified is None:
                continue
            if date.fromisoformat(str(last_verified)) < stale_cutoff:
                stale_docs.append(_rel(path, root))

    return {
        "name": "harness_docs_freshness",
        "status": "warning" if stale_docs else "ok",
        "details": {
            "stale_docs": sorted(stale_docs),
            "stale_cutoff": stale_cutoff.isoformat(),
        },
    }


def _inspect_run_store(
    *,
    runs_dir: Path,
    current_time: datetime,
    retention_days: int,
    root: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    malformed_run_dirs: list[str] = []
    candidates: list[dict[str, object]] = []
    stale_cutoff = current_time - timedelta(days=retention_days)

    if runs_dir.exists():
        for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
            summary_path = run_dir / "summary.json"
            if not summary_path.exists():
                malformed_run_dirs.append(_rel(run_dir, root))
                continue
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            status = str(summary.get("status", "unknown"))
            finished_at = summary.get("finished_at") or summary.get("started_at")
            if status == "running" or finished_at is None:
                continue
            finished_at_dt = datetime.fromisoformat(str(finished_at))
            if finished_at_dt <= stale_cutoff:
                candidates.append(
                    {
                        "kind": "run_dir",
                        "reason": "stale_completed_run",
                        "paths": [_rel(run_dir, root)],
                    }
                )

    check_status = "warning" if malformed_run_dirs or candidates else "ok"
    return (
        {
            "name": "harness_run_store",
            "status": check_status,
            "details": {
                "malformed_run_dirs": malformed_run_dirs,
                "stale_completed_run_dirs": [
                    candidate["paths"][0]
                    for candidate in candidates
                    if candidate["reason"] == "stale_completed_run"
                ],
            },
        },
        candidates,
    )


def _inspect_plan_runs(
    *,
    plan_runs_dir: Path,
    current_time: datetime,
    retention_days: int,
    root: Path,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    orphan_evidence_paths: list[str] = []
    candidates: list[dict[str, object]] = []
    stale_cutoff = current_time - timedelta(days=retention_days)

    if plan_runs_dir.exists():
        for evidence_path in sorted(plan_runs_dir.glob("*.evidence.json")):
            state_path = _state_path_for_evidence(evidence_path)
            if state_path.exists():
                continue
            orphan_evidence_paths.append(_rel(evidence_path, root))
            if _file_mtime(evidence_path) <= stale_cutoff:
                candidates.append(
                    {
                        "kind": "plan_run_evidence",
                        "reason": "orphan_plan_run_evidence",
                        "paths": [_rel(evidence_path, root)],
                    }
                )

        for state_path in sorted(plan_runs_dir.glob("*.json")):
            if state_path.name.endswith(".evidence.json"):
                continue
            payload = json.loads(state_path.read_text(encoding="utf-8"))
            status = str(payload.get("status", "unknown"))
            if status in {"running", "in_progress"}:
                continue
            if _file_mtime(state_path) > stale_cutoff:
                continue
            evidence_path = _evidence_path_for_state(state_path)
            paths = [_rel(state_path, root)]
            if evidence_path.exists():
                paths.append(_rel(evidence_path, root))
            candidates.append(
                {
                    "kind": "plan_run_pair",
                    "reason": "stale_completed_plan_run",
                    "paths": paths,
                }
            )

    check_status = "warning" if orphan_evidence_paths or candidates else "ok"
    return (
        {
            "name": "harness_plan_runs",
            "status": check_status,
            "details": {
                "orphan_evidence_paths": orphan_evidence_paths,
                "stale_completed_plan_runs": [
                    candidate["paths"][0]
                    for candidate in candidates
                    if candidate["reason"] == "stale_completed_plan_run"
                ],
            },
        },
        candidates,
    )


def _load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1)) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def _state_path_for_evidence(evidence_path: Path) -> Path:
    return evidence_path.with_name(
        evidence_path.name.removesuffix(".evidence.json") + ".json"
    )


def _evidence_path_for_state(state_path: Path) -> Path:
    return state_path.with_name(state_path.stem + ".evidence.json")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
