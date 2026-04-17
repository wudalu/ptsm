from __future__ import annotations

from typing import Any, Callable

from langgraph.graph import END, START, StateGraph

from ptsm.agent_runtime.state import ExecutionState, ReflectionDecision

ExecutionNode = Callable[[ExecutionState], dict[str, Any]]


def build_execution_graph(
    *,
    ingest: ExecutionNode,
    planner: ExecutionNode,
    executor: ExecutionNode,
    reflector: ExecutionNode,
    finalize: ExecutionNode,
    checkpointer: object | None = None,
):
    graph = StateGraph(ExecutionState)
    graph.add_node("ingest", ingest)
    graph.add_node("planner", planner)
    graph.add_node("executor", executor)
    graph.add_node("reflector", reflector)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "ingest")
    graph.add_edge("ingest", "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "reflector")
    graph.add_conditional_edges(
        "reflector",
        _route_after_reflection,
        {
            "continue": "executor",
            "retry": "executor",
            "replan": "planner",
            "finalize": "finalize",
            "fail": "finalize",
        },
    )
    graph.add_edge("finalize", END)
    resolved_checkpointer = False if checkpointer is None else checkpointer
    return graph.compile(checkpointer=resolved_checkpointer)


def _route_after_reflection(state: ExecutionState) -> ReflectionDecision:
    return state.get("reflection_decision", "fail")
