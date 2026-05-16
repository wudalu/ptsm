from __future__ import annotations

from ptsm.agent_runtime.nodes.memory import build_memory_node
from ptsm.infrastructure.memory.store import InMemoryExecutionMemory


def test_memory_node_injects_recent_same_playbook_lessons() -> None:
    memory = InMemoryExecutionMemory()
    namespace = ("accounts", "acct-fk-local", "lessons")
    memory.record(
        namespace=namespace,
        item={
            "playbook_id": "other_playbook",
            "scene": "不相关",
            "title": "不相关标题",
            "final_body": "不应该出现",
        },
    )
    for index in range(4):
        memory.record(
            namespace=namespace,
            item={
                "playbook_id": "fengkuang_daily_post",
                "scene": f"第{index}次领导18:57发在吗",
                "title": f"标题{index}",
                "final_body": f"正文{index}，评论区接一句工牌背面的疯话。至少先让工牌替我发言。",
            },
        )

    node = build_memory_node(execution_memory=memory, max_lessons=3)
    result = node(
        {
            "account_id": "acct-fk-local",
            "playbook_id": "fengkuang_daily_post",
            "runtime_skill_contents": ["# XHS Trend Scan Live Context\n主切口：怎么才周四"],
            "runtime_skill_details": [
                {
                    "skill_name": "xhs_trend_scan",
                    "resource_type": "runtime_context",
                    "resource_id": "xhs_trend_scan:runtime_context",
                    "source_path": None,
                    "content_preview": "# XHS Trend Scan Live Context",
                }
            ],
        }
    )

    assert [hit["title"] for hit in result["memory_hits"]] == ["标题1", "标题2", "标题3"]
    context = "\n".join(result["runtime_skill_contents"])
    assert "Avoid repeating recent account posts" in context
    assert "标题1" in context
    assert "标题3" in context
    assert "不相关标题" not in context
    assert result["runtime_skill_details"][-1] == {
        "skill_name": "recent_account_memory",
        "resource_type": "runtime_context",
        "resource_id": "recent_account_memory:runtime_context",
        "source_path": None,
        "content_preview": "# Recent Account Memory",
    }


def test_memory_node_returns_empty_hits_when_no_prior_lessons() -> None:
    node = build_memory_node(execution_memory=InMemoryExecutionMemory())

    result = node(
        {
            "account_id": "acct-empty",
            "playbook_id": "fengkuang_daily_post",
            "runtime_skill_contents": ["# existing"],
        }
    )

    assert result["memory_hits"] == []
    assert result["runtime_skill_contents"] == ["# existing"]
