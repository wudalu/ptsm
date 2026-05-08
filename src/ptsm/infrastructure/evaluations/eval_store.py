from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from ptsm.evaluations.contracts import EvalResult


@dataclass(frozen=True)
class EvalRunHandle:
    eval_run_id: str
    run_dir: Path
    results_path: Path
    summary_path: Path


class EvalStore:
    def __init__(self, base_dir: Path | str = ".ptsm/evals") -> None:
        self.base_dir = Path(base_dir)

    def start(
        self,
        *,
        suite_id: str,
        source_kind: str,
        source_path: str | None = None,
    ) -> EvalRunHandle:
        eval_run_id = uuid4().hex[:12]
        run_dir = self.base_dir / eval_run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        handle = EvalRunHandle(
            eval_run_id=eval_run_id,
            run_dir=run_dir,
            results_path=run_dir / "results.jsonl",
            summary_path=run_dir / "summary.json",
        )
        summary = {
            "eval_run_id": eval_run_id,
            "suite_id": suite_id,
            "status": "running",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": {"kind": source_kind, "path": source_path},
            "counts": {
                "targets": 0, "evaluators": 0, "passed": 0,
                "failed": 0, "warnings": 0, "errors": 0,
            },
            "gate": {"required_failed": 0, "warning_failed": 0},
        }
        handle.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return handle

    def append_result(self, eval_run_id: str, result: EvalResult) -> None:
        run_dir = self.base_dir / eval_run_id
        results_path = run_dir / "results.jsonl"
        data = result.to_dict()
        data["eval_run_id"] = eval_run_id
        with results_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def finalize(
        self,
        eval_run_id: str,
        *,
        status: str,
        counts: dict[str, int],
        gate: dict[str, int],
    ) -> None:
        run_dir = self.base_dir / eval_run_id
        summary_path = run_dir / "summary.json"
        current = json.loads(summary_path.read_text(encoding="utf-8"))
        current["status"] = status
        current["counts"] = counts
        current["gate"] = gate
        summary_path.write_text(
            json.dumps(current, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_eval_runs(self, *, limit: int | None = 10) -> list[dict[str, Any]]:
        if not self.base_dir.exists():
            return []
        dirs = sorted(
            [d for d in self.base_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
            reverse=True,
        )
        if limit is not None:
            dirs = dirs[:limit]
        results: list[dict[str, Any]] = []
        for d in dirs:
            summary_path = d / "summary.json"
            if summary_path.exists():
                results.append(json.loads(summary_path.read_text(encoding="utf-8")))
        return results

    def read_results(self, eval_run_id: str) -> list[dict[str, Any]]:
        results_path = self.base_dir / eval_run_id / "results.jsonl"
        if not results_path.exists():
            return []
        results: list[dict[str, Any]] = []
        for line in results_path.read_text(encoding="utf-8").strip().split("\n"):
            if line.strip():
                results.append(json.loads(line))
        return results
