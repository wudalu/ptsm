from __future__ import annotations

from ptsm.agent_runtime.state import ExecutionState


def build_ingest_node(*, drafting_provider: str):
    def ingest(state: ExecutionState) -> ExecutionState:
        return {
            "status": "running",
            "attempt_count": 0,
            "planner_iterations": 0,
            "required_revision": False,
            "reflection_decision": "continue",
            "scene": state["scene"],
            "platform": state["platform"],
            "account_id": state["account_id"],
            "drafting_provider": drafting_provider,
        }

    return ingest
