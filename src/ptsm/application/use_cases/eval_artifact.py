from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.evaluations.contracts import EvalResult
from ptsm.evaluations.targets import extract_targets_from_artifact
from ptsm.evaluations.rules import (
    rule_final_content_fields,
    rule_hashtags_non_empty,
    rule_hashtags_bounded,
    rule_publish_mode_valid,
    rule_no_real_publish_in_dry_run,
)
from ptsm.evaluations.contracts_eval import (
    contract_artifact_root_fields,
    contract_skill_details_match,
)
from ptsm.infrastructure.evaluations.eval_store import EvalStore


from ptsm.evaluations.rules import ALL_RULE_EVALUATORS
from ptsm.evaluations.contracts_eval import ALL_CONTRACT_EVALUATORS


RULE_EVALUATOR_FNS = {
    "final_content.required_fields": rule_final_content_fields,
    "hashtags.non_empty": rule_hashtags_non_empty,
    "hashtags.bounded": rule_hashtags_bounded,
    "publish_mode.valid": rule_publish_mode_valid,
    "publish.dry_run_safety": rule_no_real_publish_in_dry_run,
}

CONTRACT_EVALUATOR_FNS = {
    "artifact.root_fields": contract_artifact_root_fields,
    "skill_activation.details_match": contract_skill_details_match,
}


def _evaluator_applies(evaluator_id: str, specs: list, target_phase: str) -> bool:
    for spec in specs:
        if spec.evaluator_id == evaluator_id:
            phases = spec.applies_to.get("phases", [])
            if not phases:
                return True
            return target_phase in phases
    return True  # if no spec found, run it anyway


def run_eval_artifact(
    *,
    artifact_path: Path | str,
    evals_base_dir: Path | str = ".ptsm/evals",
    run_id: str | None = None,
) -> dict[str, Any]:
    artifact_path = Path(artifact_path)
    if not artifact_path.exists():
        return {
            "status": "error",
            "reason": f"artifact not found: {artifact_path}",
        }

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    effective_run_id = run_id or artifact_path.stem

    targets = extract_targets_from_artifact(artifact, run_id=effective_run_id)
    store = EvalStore(base_dir=evals_base_dir)

    suite_id = f"{artifact.get('playbook_id', 'unknown')}.default"
    handle = store.start(
        suite_id=suite_id,
        source_kind="artifact",
        source_path=str(artifact_path),
    )

    all_results: list[EvalResult] = []
    all_specs = list(ALL_RULE_EVALUATORS) + list(ALL_CONTRACT_EVALUATORS)
    for target in targets:
        for evaluator_id, fn in RULE_EVALUATOR_FNS.items():
            if not _evaluator_applies(evaluator_id, all_specs, target.phase):
                continue
            result = fn(target)
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

        for evaluator_id, fn in CONTRACT_EVALUATOR_FNS.items():
            if not _evaluator_applies(evaluator_id, all_specs, target.phase):
                continue
            result = fn(target)
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

    counts = _aggregate_counts(all_results, len(targets))
    gate = _gate_counts(all_results)

    status = "passed"
    if gate["required_failed"] > 0:
        status = "failed"
    elif counts["errors"] > 0:
        status = "error"

    store.finalize(handle.eval_run_id, status=status, counts=counts, gate=gate)

    return {
        "eval_run_id": handle.eval_run_id,
        "status": status,
        "suite_id": suite_id,
        "counts": counts,
        "gate": gate,
        "source": {"kind": "artifact", "path": str(artifact_path)},
    }


def _aggregate_counts(results: list[EvalResult], num_targets: int) -> dict[str, int]:
    return {
        "targets": num_targets,
        "evaluators": len(results),
        "passed": sum(1 for r in results if r.status == "passed"),
        "failed": sum(1 for r in results if r.status == "failed"),
        "warnings": sum(1 for r in results if r.status == "warning"),
        "errors": sum(1 for r in results if r.status == "error"),
    }


def _gate_counts(results: list[EvalResult]) -> dict[str, int]:
    required_failed = sum(1 for r in results if r.status in ("failed", "error"))
    return {"required_failed": required_failed, "warning_failed": 0}
