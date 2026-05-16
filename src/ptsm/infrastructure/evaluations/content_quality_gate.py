from __future__ import annotations

from collections.abc import Callable, Mapping

from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.llm_judge import LLMJudgeBackend, run_content_quality_judge


def build_content_quality_judge_gate(
    backend: LLMJudgeBackend,
) -> Callable[[Mapping[str, object], dict[str, object]], dict[str, object]]:
    def judge(state: Mapping[str, object], draft: dict[str, object]) -> dict[str, object]:
        return run_content_quality_judge(
            _build_target(state=state, draft=draft),
            backend=backend,
            gate_level="required",
        ).to_dict()

    return judge


def _build_target(*, state: Mapping[str, object], draft: dict[str, object]) -> EvalTarget:
    attempt_count = int(state.get("attempt_count", 0))
    playbook_id = str(state.get("playbook_id", ""))
    account_id = str(state.get("account_id", ""))
    return EvalTarget(
        target_id=f"{account_id}:{playbook_id}:executor:attempt-{attempt_count}",
        run_id=str(state.get("thread_id", "")),
        playbook_id=playbook_id,
        account_id=account_id,
        platform=str(state.get("platform", "")),
        phase="executor",
        target_type="artifact_slice",
        output_ref={"final_content": draft},
    )
