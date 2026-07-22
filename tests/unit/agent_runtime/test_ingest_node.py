from __future__ import annotations

from ptsm.agent_runtime.nodes.ingest import build_ingest_node


def test_ingest_preserves_topic_selection_for_planner_context() -> None:
    topic_selection = {
        "topic_direction_id": "enrichment_desk_corner_variable",
        "source": "guide-post",
        "direction": {
            "id": "enrichment_desk_corner_variable",
            "format_recommendation": {
                "format_archetype": "provider_scene",
                "cover_role": "evidence_or_scene",
                "body_shape": "scene / action / comment",
                "visual_evidence_need": "high",
                "avoid_format": ["dense_text_poster"],
            },
        },
    }
    ingest = build_ingest_node(drafting_provider="deterministic")

    result = ingest(
        {
            "scene": "把书桌改成十分钟手作角",
            "platform": "xiaohongshu",
            "account_id": "acct-enrichment-local",
            "topic_selection": topic_selection,
        }
    )

    assert result["topic_selection"] == topic_selection


def test_ingest_does_not_copy_ai_evidence_into_graph_state() -> None:
    ingest = build_ingest_node(drafting_provider="deterministic")

    result = ingest(
        {
            "scene": "AI 科技资讯简报",
            "platform": "xiaohongshu",
            "account_id": "acct-ai-tech-local",
            "ai_tech_evidence": {"raw_source_url": "https://example.com/release"},
        }
    )

    assert result["status"] == "running"
    assert "ai_tech_evidence" not in result
