from __future__ import annotations

from ptsm.agent_runtime import runtime


def test_graph_routes_retry_then_finalize() -> None:
    def ingest(_: dict[str, object]) -> dict[str, object]:
        return {
            "status": "running",
            "attempt_count": 0,
            "planner_iterations": 0,
        }

    def planner(state: dict[str, object]) -> dict[str, object]:
        return {
            "planner_iterations": int(state.get("planner_iterations", 0)) + 1,
        }

    def executor(state: dict[str, object]) -> dict[str, object]:
        attempt_count = int(state.get("attempt_count", 0)) + 1
        return {
            "attempt_count": attempt_count,
            "draft_content": {
                "body": f"draft-{attempt_count}",
                "hashtags": ["#发疯文学"],
            },
        }

    def reflector(state: dict[str, object]) -> dict[str, object]:
        if state["attempt_count"] == 1:
            return {
                "reflection_decision": "retry",
                "reflection_feedback": "add a stronger close",
            }
        return {
            "reflection_decision": "finalize",
            "final_content": state["draft_content"],
        }

    def finalize(state: dict[str, object]) -> dict[str, object]:
        return {
            "status": "completed" if state.get("final_content") else "failed",
        }

    workflow = runtime.build_execution_graph(
        ingest=ingest,
        planner=planner,
        executor=executor,
        reflector=reflector,
        finalize=finalize,
    )

    result = workflow.invoke({})

    assert result["status"] == "completed"
    assert result["attempt_count"] == 2


def test_graph_supports_replan_branch() -> None:
    def ingest(_: dict[str, object]) -> dict[str, object]:
        return {
            "status": "running",
            "attempt_count": 0,
            "planner_iterations": 0,
            "replanned": False,
        }

    def planner(state: dict[str, object]) -> dict[str, object]:
        return {
            "planner_iterations": int(state.get("planner_iterations", 0)) + 1,
        }

    def executor(state: dict[str, object]) -> dict[str, object]:
        return {
            "attempt_count": int(state.get("attempt_count", 0)) + 1,
            "draft_content": {
                "body": f"planner-pass-{state['planner_iterations']}",
                "hashtags": ["#发疯文学"],
            },
        }

    def reflector(state: dict[str, object]) -> dict[str, object]:
        if not state.get("replanned", False):
            return {
                "reflection_decision": "replan",
                "replanned": True,
                "reflection_feedback": "planner needs another pass",
            }
        return {
            "reflection_decision": "finalize",
            "final_content": state["draft_content"],
        }

    def finalize(state: dict[str, object]) -> dict[str, object]:
        return {
            "status": "completed",
        }

    workflow = runtime.build_execution_graph(
        ingest=ingest,
        planner=planner,
        executor=executor,
        reflector=reflector,
        finalize=finalize,
    )

    result = workflow.invoke({})

    assert result["status"] == "completed"
    assert result["planner_iterations"] == 2
