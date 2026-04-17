from __future__ import annotations

import json
from pathlib import Path

from ptsm.agent_runtime import runtime


def test_generic_plan_execute_reflect_loop_writes_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "artifact.json"

    def ingest(state: dict[str, object]) -> dict[str, object]:
        return {
            "status": "running",
            "account_id": state["account_id"],
            "attempt_count": 0,
            "planner_iterations": 0,
        }

    def planner(state: dict[str, object]) -> dict[str, object]:
        return {
            "planner_iterations": int(state.get("planner_iterations", 0)) + 1,
            "playbook_id": "generic_demo",
        }

    def executor(state: dict[str, object]) -> dict[str, object]:
        attempt_count = int(state.get("attempt_count", 0)) + 1
        body = "第一版草稿"
        if attempt_count > 1:
            body = "第二版草稿，已经补上也算这样的收束。"
        return {
            "attempt_count": attempt_count,
            "draft_content": {
                "title": "demo",
                "image_text": "demo",
                "body": body,
                "hashtags": ["#发疯文学"],
            },
        }

    def reflector(state: dict[str, object]) -> dict[str, object]:
        if state["attempt_count"] == 1:
            return {
                "reflection_decision": "retry",
                "reflection_feedback": "needs a softer close",
            }
        return {
            "reflection_decision": "finalize",
            "final_content": state["draft_content"],
        }

    def finalize(state: dict[str, object]) -> dict[str, object]:
        artifact_path.write_text(
            json.dumps(
                {
                    "playbook_id": state["playbook_id"],
                    "final_content": state["final_content"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {
            "status": "completed",
            "artifact_path": str(artifact_path),
        }

    workflow = runtime.build_execution_graph(
        ingest=ingest,
        planner=planner,
        executor=executor,
        reflector=reflector,
        finalize=finalize,
    )

    result = workflow.invoke(
        {"account_id": "acct-generic"},
        config={"configurable": {"thread_id": "generic-thread-1"}},
    )

    assert result["status"] == "completed"
    assert result["attempt_count"] == 2
    assert Path(result["artifact_path"]).exists()
