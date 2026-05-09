from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ptsm.evaluations.contracts import EvalResult
from ptsm.evaluations.llm_judge import LLMJudgeBackend, run_llm_judge
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
    contract_playbook_node_contract,
    contract_skill_details_match,
)
from ptsm.evaluations.playbook_contracts import load_playbook_eval_contract
from ptsm.infrastructure.evaluations.eval_store import EvalStore


from ptsm.evaluations.rules import ALL_RULE_EVALUATORS
from ptsm.evaluations.contracts_eval import ALL_CONTRACT_EVALUATORS


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAYBOOK_DEFINITIONS_ROOT = PACKAGE_ROOT / "playbooks" / "definitions"


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
    playbook_definitions_root: Path | str = DEFAULT_PLAYBOOK_DEFINITIONS_ROOT,
    enable_llm_judges: bool = False,
    llm_judge_backend: LLMJudgeBackend | None = None,
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
    source_metadata = _source_metadata(artifact, run_id=effective_run_id)
    playbook_contract = load_playbook_eval_contract(
        Path(playbook_definitions_root),
        source_metadata["playbook_id"],
    )

    suite_id = f"{artifact.get('playbook_id', 'unknown')}.default"
    handle = store.start(
        suite_id=suite_id,
        source_kind="artifact",
        source_path=str(artifact_path),
        source_metadata=source_metadata,
    )

    all_results: list[EvalResult] = []
    all_specs = list(ALL_RULE_EVALUATORS) + list(ALL_CONTRACT_EVALUATORS)
    specs_by_id = {spec.evaluator_id: spec for spec in all_specs}
    for target in targets:
        for evaluator_id, fn in RULE_EVALUATOR_FNS.items():
            if not _evaluator_applies(evaluator_id, all_specs, target.phase):
                continue
            result = fn(target)
            _apply_spec_metadata(result, specs_by_id.get(evaluator_id))
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

        for evaluator_id, fn in CONTRACT_EVALUATOR_FNS.items():
            if not _evaluator_applies(evaluator_id, all_specs, target.phase):
                continue
            result = fn(target)
            _apply_spec_metadata(result, specs_by_id.get(evaluator_id))
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

        if playbook_contract is not None:
            result = contract_playbook_node_contract(target, playbook_contract)
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

        if enable_llm_judges and llm_judge_backend is not None and target.phase == "executor":
            result = run_llm_judge(
                target,
                evaluator_id="llm.executor.semantic_quality",
                rubric="Evaluate whether the final content fits the scene, playbook persona, platform, and available runtime context.",
                backend=llm_judge_backend,
            )
            result.eval_run_id = handle.eval_run_id
            all_results.append(result)
            store.append_result(handle.eval_run_id, result)

    counts = _aggregate_counts(all_results, len(targets))
    gate = _gate_counts(all_results)

    status = "passed"
    if gate["required_failed"] > 0:
        status = "failed"
    elif gate["warning_failed"] > 0 or counts["warnings"] > 0:
        status = "warning"
    elif counts["errors"] > 0:
        status = "error"

    store.finalize(handle.eval_run_id, status=status, counts=counts, gate=gate)

    return {
        "eval_run_id": handle.eval_run_id,
        "status": status,
        "suite_id": suite_id,
        "counts": counts,
        "gate": gate,
        "source": {"kind": "artifact", "path": str(artifact_path), **source_metadata},
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
    required_failed = 0
    warning_failed = 0
    for result in results:
        if result.status not in ("failed", "error"):
            continue
        if result.gate_level == "required":
            required_failed += 1
        else:
            warning_failed += 1
    return {"required_failed": required_failed, "warning_failed": warning_failed}


def _apply_spec_metadata(result: EvalResult, spec: object | None) -> None:
    if spec is None:
        return
    gate_level = getattr(spec, "gate_level", None)
    if isinstance(gate_level, str) and gate_level:
        result.gate_level = gate_level


def _source_metadata(artifact: dict[str, Any], *, run_id: str) -> dict[str, str]:
    return {
        "run_id": run_id,
        "account_id": _account_id(artifact),
        "platform": _platform(artifact),
        "playbook_id": str(artifact.get("playbook_id", "")),
    }


def _account_id(artifact: dict[str, Any]) -> str:
    account = artifact.get("account")
    if isinstance(account, dict):
        return str(account.get("account_id", ""))
    return str(artifact.get("account_id", ""))


def _platform(artifact: dict[str, Any]) -> str:
    account = artifact.get("account")
    if isinstance(account, dict):
        return str(account.get("platform", ""))
    return str(artifact.get("platform", ""))
