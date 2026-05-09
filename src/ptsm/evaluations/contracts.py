from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class EvalTarget:
    target_id: str
    run_id: str
    playbook_id: str
    account_id: str
    phase: str
    target_type: str
    artifact_path: str | None = None
    platform: str | None = None
    input_ref: dict[str, Any] | None = None
    output_ref: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class EvalResult:
    eval_result_id: str
    eval_run_id: str
    target_id: str
    evaluator_id: str
    evaluator_version: str
    status: str  # passed | failed | warning | skipped | error
    reason: str
    score: float | None = None
    label: str | None = None
    evidence: list[dict[str, Any]] | None = None
    confidence: float | None = None
    cost: dict[str, Any] | None = None
    gate_level: str = "required"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass
class EvaluatorSpec:
    evaluator_id: str
    version: str
    type: str  # rule | contract | llm_judge | human_review | aggregate
    owner: str
    applies_to: dict[str, Any] = field(default_factory=dict)
    threshold: float = 0.8
    gate_level: str = "required"  # required | warning | manual_review | experimental

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvalSuite:
    suite_id: str
    scope: dict[str, Any]
    evaluators: list[str]
    thresholds: dict[str, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}
