from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4


class FileArtifactStore:
    """Persist final workflow artifacts to the local filesystem."""

    def __init__(self, base_dir: Path | str = "outputs/artifacts"):
        self.base_dir = Path(base_dir)

    def write(self, payload: dict[str, object], *, run_key: str | None = None) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        slug = run_key or str(uuid4())
        path = self.base_dir / f"{slug}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def read(self, path: Path | str) -> dict[str, object]:
        artifact_path = Path(path)
        return json.loads(artifact_path.read_text(encoding="utf-8"))

    def merge(self, path: Path | str, payload: dict[str, object]) -> Path:
        artifact_path = Path(path)
        current = self.read(artifact_path)
        current.update(payload)
        artifact_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return artifact_path
