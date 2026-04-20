from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
from typing import Any, Sequence

import yaml


FRONT_MATTER_PATTERN = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
RELEVANT_CODE_PREFIXES = ("src/ptsm/", "shared_contracts/")


@dataclass(frozen=True)
class SourceDoc:
    path: str
    related_paths: tuple[str, ...]
    doc_surface_paths: tuple[str, ...]


def run_docs_sync(
    *,
    project_root: Path | str = ".",
    changed_paths: Sequence[str] | None = None,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
) -> dict[str, object]:
    root = Path(project_root)
    effective_changed_paths = _resolve_changed_paths(
        project_root=root,
        changed_paths=changed_paths,
        base_ref=base_ref,
        head_ref=head_ref,
    )
    changed_doc_paths = sorted(path for path in effective_changed_paths if _is_document_path(path))
    changed_doc_path_set = set(changed_doc_paths)
    relevant_code_paths = sorted(
        path for path in effective_changed_paths if _is_relevant_code_path(path)
    )

    source_docs = _load_source_docs(root)
    missing_updates: list[dict[str, object]] = []
    unmapped_changes: list[str] = []

    for changed_path in relevant_code_paths:
        candidates = _candidate_docs_for_change(changed_path, source_docs)
        if not candidates:
            unmapped_changes.append(changed_path)
            continue
        if any(set(candidate.doc_surface_paths) & changed_doc_path_set for candidate in candidates):
            continue
        missing_updates.append(
            {
                "changed_path": changed_path,
                "candidate_docs": [
                    {
                        "doc": candidate.path,
                        "doc_surface_paths": list(candidate.doc_surface_paths),
                    }
                    for candidate in candidates
                ],
            }
        )

    status = "ok" if not missing_updates and not unmapped_changes else "error"
    return {
        "status": status,
        "changed_paths": effective_changed_paths,
        "changed_doc_paths": changed_doc_paths,
        "relevant_code_paths": relevant_code_paths,
        "missing_updates": missing_updates,
        "unmapped_changes": unmapped_changes,
    }


def _resolve_changed_paths(
    *,
    project_root: Path,
    changed_paths: Sequence[str] | None,
    base_ref: str | None,
    head_ref: str,
) -> list[str]:
    if changed_paths is not None:
        return sorted({_normalize_path(path) for path in changed_paths if str(path).strip()})
    if not base_ref:
        return []

    completed = subprocess.run(
        [
            "git",
            "diff",
            "--name-only",
            "--diff-filter=ACMRD",
            f"{base_ref}...{head_ref}",
        ],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return sorted(
        {
            _normalize_path(line)
            for line in completed.stdout.splitlines()
            if line.strip()
        }
    )


def _load_source_docs(project_root: Path) -> list[SourceDoc]:
    docs_root = project_root / "docs"
    source_docs: list[SourceDoc] = []

    for path in sorted(docs_root.rglob("*.md")):
        metadata = _load_front_matter(path)
        if metadata.get("status") != "active":
            continue
        if metadata.get("source_of_truth") is not True:
            continue
        related_paths = tuple(
            _normalize_path(raw_path)
            for raw_path in metadata.get("related_paths", [])
            if isinstance(raw_path, str) and raw_path.strip()
        )
        source_docs.append(
            SourceDoc(
                path=_rel(path, project_root),
                related_paths=related_paths,
                doc_surface_paths=_doc_surface_paths(
                    doc_path=_rel(path, project_root),
                    related_paths=related_paths,
                ),
            )
        )

    return source_docs


def _candidate_docs_for_change(
    changed_path: str,
    source_docs: Sequence[SourceDoc],
) -> list[SourceDoc]:
    matches: list[tuple[SourceDoc, int]] = []

    for source_doc in source_docs:
        specificity = max(
            (
                match_length
                for related_path in source_doc.related_paths
                if (match_length := _match_specificity(changed_path, related_path)) is not None
            ),
            default=None,
        )
        if specificity is None:
            continue
        matches.append((source_doc, specificity))

    if not matches:
        return []

    max_specificity = max(score for _, score in matches)
    return [source_doc for source_doc, score in matches if score == max_specificity]


def _doc_surface_paths(*, doc_path: str, related_paths: Sequence[str]) -> tuple[str, ...]:
    ordered_paths = [doc_path]
    ordered_paths.extend(path for path in related_paths if _is_document_path(path))
    return tuple(dict.fromkeys(ordered_paths))


def _match_specificity(changed_path: str, related_path: str) -> int | None:
    normalized_related = related_path.rstrip("/")
    if changed_path == normalized_related:
        return len(normalized_related)
    if changed_path.startswith(f"{normalized_related}/"):
        return len(normalized_related)
    return None


def _is_document_path(path: str) -> bool:
    return path == "README.md" or (path.startswith("docs/") and path.endswith(".md"))


def _is_relevant_code_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in RELEVANT_CODE_PREFIXES)


def _load_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = FRONT_MATTER_PATTERN.match(text)
    if not match:
        return {}
    payload = yaml.safe_load(match.group(1)) or {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _normalize_path(path: str | Path) -> str:
    return Path(path).as_posix().lstrip("./")


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
