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


def test_memory_node_hides_reddit_source_markers_from_prompt_context() -> None:
    memory = InMemoryExecutionMemory()
    namespace = ("accounts", "acct-reddit-curation-local", "lessons")
    memory.record(
        namespace=namespace,
        item={
            "playbook_id": "reddit_curation_daily_post",
            "scene": "从Reddit上AI英文讨论里选一个适合中文读者的角度",
            "title": "这个Reddit讨论，像极了消息压力",
            "image_text": "英文讨论翻成中文后更扎心",
            "final_body": "Reddit英文讨论里有个现象很适合翻成中文看。评论区想问问你怎么看。",
        },
    )

    node = build_memory_node(execution_memory=memory, max_lessons=3)
    result = node(
        {
            "account_id": "acct-reddit-curation-local",
            "playbook_id": "reddit_curation_daily_post",
            "runtime_skill_contents": [],
            "runtime_skill_details": [],
        }
    )

    context = "\n".join(result["runtime_skill_contents"])
    assert result["memory_hits"][0]["title"] == "这个Reddit讨论，像极了消息压力"
    assert not any(
        term in context
        for term in ("Reddit", "reddit", "r/", "#Reddit", "英文讨论", "翻成中文")
    )
    assert "这个热点" in context
    assert "same internal-source curation scene" in context


def test_memory_node_skips_history_for_evidence_gated_ai_drafts() -> None:
    memory = InMemoryExecutionMemory()
    namespace = ("accounts", "acct-ai-tech-local", "lessons")
    memory.record(
        namespace=namespace,
        item={
            "playbook_id": "ai_tech_daily_post",
            "scene": "Raw release title https://example.com/release",
            "title": "Raw source title",
            "image_text": "Example Author",
            "final_body": "legacy body with https://example.com/release",
        },
    )
    safe_context = "# AI Tech Evidence Contract\n只使用本次已核验事实。"
    node = build_memory_node(execution_memory=memory, evidence_gated=True)

    result = node(
        {
            "account_id": "acct-ai-tech-local",
            "playbook_id": "ai_tech_daily_post",
            "runtime_skill_contents": [safe_context],
            "runtime_skill_details": [
                {
                    "skill_name": "ai_tech_evidence_contract",
                    "resource_type": "runtime_context",
                    "resource_id": "ai_tech_evidence_contract:runtime_context",
                    "source_path": None,
                    "content_preview": "# AI Tech Evidence Contract",
                }
            ],
        }
    )

    assert result["memory_hits"] == []
    assert result["runtime_skill_contents"] == [safe_context]
    assert "Recent Account Memory" not in "\n".join(result["runtime_skill_contents"])
