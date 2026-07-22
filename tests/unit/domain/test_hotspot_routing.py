from __future__ import annotations

from ptsm.domain.hotspot_routing import HotspotRoutingProfile, route_hotspot


def test_route_hotspot_maps_a_clear_existing_playbook_without_copying_headline() -> None:
    headline = "OpenAI 发布面向开发者的新一代 AI Agent"

    route = route_hotspot(
        headline,
        profiles=(
            HotspotRoutingProfile(
                playbook_id="ai_tech_daily_post",
                domain="AI科技资讯",
                include_any=("OpenAI", "ChatGPT", "大模型"),
            ),
        ),
    )

    assert route.status == "existing_playbook_fit"
    assert [candidate.playbook_id for candidate in route.candidates] == [
        "ai_tech_daily_post"
    ]
    assert route.candidates[0].matched_terms == ("OpenAI",)
    assert headline not in route.candidates[0].generation_seed
    assert "AI科技资讯" in route.candidates[0].generation_seed


def test_route_hotspot_marks_multiple_matching_playbooks_as_ambiguous() -> None:
    route = route_hotspot(
        "睡前焦虑怎么缓解",
        profiles=(
            HotspotRoutingProfile(
                playbook_id="human_enrichment_daily_post",
                domain="人类丰容实验",
                include_any=("睡前",),
            ),
            HotspotRoutingProfile(
                playbook_id="modern_psychology_post",
                domain="现代心理困境观察",
                include_any=("焦虑", "睡前"),
            ),
        ),
    )

    assert route.status == "ambiguous"
    assert [candidate.playbook_id for candidate in route.candidates] == [
        "human_enrichment_daily_post",
        "modern_psychology_post",
    ]
    assert route.next_action == "ask_operator_to_choose_playbook"


def test_route_hotspot_keeps_incidental_or_unknown_news_unmapped() -> None:
    route = route_hotspot(
        "斯塔默卸任后穿运动鞋直奔酒吧喝酒",
        profiles=(
            HotspotRoutingProfile(
                playbook_id="modern_psychology_post",
                domain="现代心理困境观察",
                include_any=("情绪内耗", "关系边界", "孤独感"),
            ),
            HotspotRoutingProfile(
                playbook_id="world_cup_daily_post",
                domain="世界杯主题",
                include_any=("世界杯", "美加墨"),
            ),
        ),
    )

    assert route.status == "unmapped"
    assert route.candidates == ()
    assert route.next_action == "monitor_or_new_domain_review"


def test_route_hotspot_requires_all_terms_for_narrow_coverage() -> None:
    profile = HotspotRoutingProfile(
        playbook_id="human_enrichment_daily_post",
        domain="人类丰容实验",
        require_all=(("手作", "钩织"),),
    )

    assert route_hotspot("周末手作市集", profiles=(profile,)).status == "unmapped"
    assert (
        route_hotspot("钩织手作让下班后更有仪式感", profiles=(profile,)).status
        == "existing_playbook_fit"
    )
