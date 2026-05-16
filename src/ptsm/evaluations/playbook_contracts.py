from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import yaml


@dataclass
class PlaybookEvalContract:
    suite_id: str
    version: int = 1
    uses: dict[str, str] = field(default_factory=dict)
    node_contracts: dict[str, dict[str, Any]] = field(default_factory=dict)
    warning_judges: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "version": self.version,
            "uses": self.uses,
            "node_contracts": self.node_contracts,
            "warning_judges": self.warning_judges,
        }


def load_playbook_eval_contract(
    definitions_root: Path, playbook_id: str
) -> PlaybookEvalContract | None:
    eval_path = definitions_root / playbook_id / "evaluation.yaml"
    if not eval_path.exists():
        return None

    raw = yaml.safe_load(eval_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"evaluation.yaml for {playbook_id} must be a mapping")

    suite_id = raw.get("suite_id")
    if not suite_id:
        raise ValueError(f"evaluation.yaml for {playbook_id} must have suite_id")

    return PlaybookEvalContract(
        suite_id=suite_id,
        version=raw.get("version", 1),
        uses=raw.get("uses", {}) or {},
        node_contracts=raw.get("node_contracts", {}) or {},
        warning_judges=raw.get("warning_judges", {}) or {},
    )
