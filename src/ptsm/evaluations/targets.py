from __future__ import annotations

from typing import Any
from ptsm.evaluations.contracts import EvalTarget


def extract_targets_from_artifact(
    artifact: dict[str, Any], *, run_id: str
) -> list[EvalTarget]:
    playbook_id = str(artifact.get("playbook_id", ""))
    account_id = _account_id(artifact)
    platform = _platform(artifact)
    artifact_path = artifact.get("artifact_path")

    skill_names = [
        str(s.get("skill_name"))
        for s in artifact.get("activated_skill_details", [])
        if isinstance(s, dict) and s.get("skill_name")
    ]

    targets: list[EvalTarget] = []

    # Planner target: skill activation
    if artifact.get("activated_skill_details"):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:planner:skill_activation",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="planner",
                target_type="node_output",
                output_ref={
                    "activated_skills": artifact.get("activated_skills"),
                    "activated_skill_details_count": len(
                        artifact.get("activated_skill_details", [])
                    ),
                },
                metadata={
                    "skill_names": skill_names,
                    "runtime_context_sources": [],
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    # Executor target: final content
    final_content = artifact.get("final_content")
    if isinstance(final_content, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:executor:final_content",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="executor",
                target_type="artifact_slice",
                output_ref={"final_content": final_content},
                metadata={
                    "skill_names": skill_names,
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    # Final target: artifact completeness
    targets.append(
        EvalTarget(
            target_id=f"{run_id}:final:artifact_completeness",
            run_id=run_id,
            artifact_path=str(artifact_path) if artifact_path else None,
            playbook_id=playbook_id,
            account_id=account_id,
            platform=platform,
            phase="final",
            target_type="artifact_slice",
            output_ref=artifact,
            metadata={
                "skill_names": skill_names,
                "model_provider": artifact.get("drafting_provider"),
            },
        )
    )

    return targets


def _account_id(artifact: dict[str, Any]) -> str:
    account = artifact.get("account")
    if isinstance(account, dict):
        return str(account.get("account_id", ""))
    return str(artifact.get("account_id", ""))


def _platform(artifact: dict[str, Any]) -> str | None:
    account = artifact.get("account")
    if isinstance(account, dict):
        return account.get("platform")
    return artifact.get("platform")
