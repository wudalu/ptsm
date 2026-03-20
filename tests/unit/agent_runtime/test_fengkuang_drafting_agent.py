from __future__ import annotations

from ptsm.agent_runtime.agents import FengkuangDraftingAgent


def test_drafting_agent_adds_positive_reframe_when_feedback_exists() -> None:
    agent = FengkuangDraftingAgent()

    draft = agent.generate(
        scene="周一早高峰地铁通勤",
        reflection_feedback="补一个带'也算'的正向收束，避免只有负面情绪。",
    )

    assert draft["title"] == "打工人地铁生存实录"
    assert "周一早高峰地铁通勤" in draft["body"]
    assert "也算" in draft["body"]
    assert draft["hashtags"][0] == "#发疯文学"
