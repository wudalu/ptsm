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

    step_outputs = artifact.get("step_outputs")
    if not isinstance(step_outputs, dict):
        step_outputs = {}

    # Planner target: skill activation and selected plan evidence
    if artifact.get("activated_skill_details"):
        planner_output = {
            "activated_skills": artifact.get("activated_skills"),
            "activated_skill_details": artifact.get("activated_skill_details", []),
        }
        planner_step = step_outputs.get("planner")
        if isinstance(planner_step, dict):
            planner_output = {**planner_step, **planner_output}
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
                output_ref=planner_output,
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
        executor_output = {"final_content": final_content}
        executor_step = step_outputs.get("executor")
        if isinstance(executor_step, dict):
            executor_output = {**executor_step, **executor_output}
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
                output_ref=executor_output,
                metadata={
                    "skill_names": skill_names,
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    reflector_output = step_outputs.get("reflector")
    if isinstance(reflector_output, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:reflector:decision",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="reflector",
                target_type="node_output",
                output_ref=reflector_output,
                metadata={
                    "skill_names": skill_names,
                    "model_provider": artifact.get("drafting_provider"),
                },
            )
        )

    image_generation = artifact.get("image_generation")
    if isinstance(image_generation, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:image:generation",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="image",
                target_type="artifact_slice",
                output_ref=image_generation,
                metadata={"skill_names": skill_names},
            )
        )

    publish_result = artifact.get("publish_result")
    if isinstance(publish_result, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:publish:result",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="publish",
                target_type="artifact_slice",
                output_ref=publish_result,
                metadata={"skill_names": skill_names},
            )
        )

    post_publish_checks = artifact.get("post_publish_checks")
    if isinstance(post_publish_checks, dict):
        targets.append(
            EvalTarget(
                target_id=f"{run_id}:post_publish:checks",
                run_id=run_id,
                artifact_path=str(artifact_path) if artifact_path else None,
                playbook_id=playbook_id,
                account_id=account_id,
                platform=platform,
                phase="post_publish",
                target_type="artifact_slice",
                output_ref=post_publish_checks,
                metadata={"skill_names": skill_names},
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
