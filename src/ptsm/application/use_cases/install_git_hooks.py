from __future__ import annotations

from pathlib import Path
import stat
import subprocess


def install_git_hooks(
    *,
    project_root: Path | str = ".",
    base_ref: str = "origin/main",
    force: bool = False,
) -> dict[str, object]:
    root = Path(project_root)
    git_dir = _git_dir(root)
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    hook_path = hooks_dir / "pre-push"
    if hook_path.exists() and not force:
        return {
            "status": "skipped",
            "reason": "hook_exists",
            "hook_path": str(hook_path),
        }

    hook_path.write_text(_pre_push_script(base_ref=base_ref), encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return {
        "status": "installed",
        "hook_path": str(hook_path),
        "base_ref": base_ref,
    }


def _git_dir(project_root: Path) -> Path:
    completed = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return (project_root / completed.stdout.strip()).resolve()


def _pre_push_script(*, base_ref: str) -> str:
    return f"""#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

BASE_REF="{base_ref}"

if ! git rev-parse --verify "$BASE_REF" >/dev/null 2>&1; then
  echo "harness-check: base ref '$BASE_REF' not found" >&2
  exit 1
fi

MERGE_BASE="$(git merge-base HEAD "$BASE_REF")"
uv run python -m ptsm.bootstrap harness-check --base-ref "$MERGE_BASE"
"""
