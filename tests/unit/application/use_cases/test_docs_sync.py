from __future__ import annotations

from pathlib import Path

from ptsm.application.use_cases.docs_sync import run_docs_sync


def test_run_docs_sync_requires_most_specific_doc_surface_update(tmp_path: Path) -> None:
    _write_source_doc(
        tmp_path / "docs" / "architecture.md",
        related_paths=["src/ptsm"],
    )
    _write_source_doc(
        tmp_path / "docs" / "operations.md",
        related_paths=[
            "src/ptsm/interfaces/cli/main.py",
            "docs/operations/local-runbook.md",
        ],
    )

    result = run_docs_sync(
        project_root=tmp_path,
        changed_paths=["src/ptsm/interfaces/cli/main.py"],
    )

    assert result["status"] == "error"
    assert result["unmapped_changes"] == []
    assert result["missing_updates"] == [
        {
            "changed_path": "src/ptsm/interfaces/cli/main.py",
            "candidate_docs": [
                {
                    "doc": "docs/operations.md",
                    "doc_surface_paths": [
                        "docs/operations.md",
                        "docs/operations/local-runbook.md",
                    ],
                }
            ],
        }
    ]


def test_run_docs_sync_accepts_related_runbook_update(tmp_path: Path) -> None:
    _write_source_doc(
        tmp_path / "docs" / "operations.md",
        related_paths=[
            "src/ptsm/interfaces/cli/main.py",
            "docs/operations/local-runbook.md",
        ],
    )
    (tmp_path / "docs" / "operations" / "local-runbook.md").parent.mkdir(
        parents=True, exist_ok=True
    )
    (tmp_path / "docs" / "operations" / "local-runbook.md").write_text(
        "# Runbook\n",
        encoding="utf-8",
    )

    result = run_docs_sync(
        project_root=tmp_path,
        changed_paths=[
            "src/ptsm/interfaces/cli/main.py",
            "docs/operations/local-runbook.md",
        ],
    )

    assert result["status"] == "ok"
    assert result["missing_updates"] == []
    assert result["unmapped_changes"] == []


def test_run_docs_sync_prefers_specific_doc_over_broad_map(tmp_path: Path) -> None:
    _write_source_doc(
        tmp_path / "docs" / "architecture.md",
        related_paths=["src/ptsm"],
    )
    _write_source_doc(
        tmp_path / "docs" / "runtime.md",
        related_paths=["src/ptsm/application/use_cases/run_playbook.py"],
    )
    (tmp_path / "docs" / "architecture.md").write_text(
        (
            "---\n"
            "title: Architecture\n"
            "status: active\n"
            "owner: ptsm\n"
            "last_verified: 2026-04-20\n"
            "source_of_truth: true\n"
            "related_paths:\n"
            "  - src/ptsm\n"
            "---\n\n"
            "# Architecture\n"
        ),
        encoding="utf-8",
    )

    result = run_docs_sync(
        project_root=tmp_path,
        changed_paths=[
            "src/ptsm/application/use_cases/run_playbook.py",
            "docs/architecture.md",
        ],
    )

    assert result["status"] == "error"
    assert result["missing_updates"] == [
        {
            "changed_path": "src/ptsm/application/use_cases/run_playbook.py",
            "candidate_docs": [
                {
                    "doc": "docs/runtime.md",
                    "doc_surface_paths": ["docs/runtime.md"],
                }
            ],
        }
    ]


def test_run_docs_sync_reports_unmapped_relevant_changes(tmp_path: Path) -> None:
    _write_source_doc(
        tmp_path / "docs" / "architecture.md",
        related_paths=["src/ptsm/application"],
    )

    result = run_docs_sync(
        project_root=tmp_path,
        changed_paths=["src/ptsm/infrastructure/new_component.py"],
    )

    assert result["status"] == "error"
    assert result["missing_updates"] == []
    assert result["unmapped_changes"] == ["src/ptsm/infrastructure/new_component.py"]


def test_run_docs_sync_ignores_docs_only_changes(tmp_path: Path) -> None:
    _write_source_doc(
        tmp_path / "docs" / "operations.md",
        related_paths=["src/ptsm/interfaces/cli/main.py"],
    )

    result = run_docs_sync(
        project_root=tmp_path,
        changed_paths=["docs/operations.md"],
    )

    assert result["status"] == "ok"
    assert result["relevant_code_paths"] == []


def _write_source_doc(path: Path, *, related_paths: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    related_lines = "\n".join(f"  - {entry}" for entry in related_paths)
    path.write_text(
        (
            "---\n"
            "title: Demo Doc\n"
            "status: active\n"
            "owner: ptsm\n"
            "last_verified: 2026-04-20\n"
            "source_of_truth: true\n"
            "related_paths:\n"
            f"{related_lines}\n"
            "---\n\n"
            "# Demo\n"
        ),
        encoding="utf-8",
    )
