from __future__ import annotations

from pathlib import Path

from ptsm.accounts.registry import AccountRegistry
from ptsm.playbooks.registry import PlaybookRegistry


XHS_PLAYBOOK_IDS = [
    "fengkuang_daily_post",
    "classic_poetry_quote_post",
    "wuxia_character_post",
    "ai_tech_daily_post",
    "daily_english_post",
    "modern_psychology_post",
    "human_enrichment_daily_post",
    "world_cup_daily_post",
    "reddit_curation_daily_post",
]


def test_all_xhs_playbooks_use_shared_human_voice_skill() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    for playbook_id in XHS_PLAYBOOK_IDS:
        playbook = registry.get(playbook_id)

        assert "xhs_human_voice" in playbook.required_skills


def test_key_playbook_prompts_include_viral_hook_research_inputs() -> None:
    root = Path("src/ptsm/playbooks/definitions")

    fengkuang = "\n".join(
        (root / "fengkuang_daily_post" / name).read_text(encoding="utf-8")
        for name in ("planner.md", "persona.md", "reflection.md")
    )
    psychology = "\n".join(
        (root / "modern_psychology_post" / name).read_text(encoding="utf-8")
        for name in ("planner.md", "persona.md", "reflection.md")
    )
    enrichment = "\n".join(
        (root / "human_enrichment_daily_post" / name).read_text(encoding="utf-8")
        for name in ("planner.md", "persona.md", "reflection.md")
    )

    for term in ("丝瓜汤", "高雅", "物件发疯"):
        assert term in fengkuang
    for term in ("爱你老己", "三明治拒绝法", "丝瓜汤式沟通"):
        assert term in psychology
    for term in ("适我主义", "新独居", "手作心流"):
        assert term in enrichment

    compact_contracts = {
        "fengkuang": (
            fengkuang,
            ("90-220 字", "2-4 个短拍", "具体崩溃瞬间", "物件发疯", "评论接龙"),
        ),
        "psychology": (
            psychology,
            ("200-380 字", "2-4 个短拍", "微场景", "低风险动作", "自然认领入口"),
        ),
        "enrichment": (
            enrichment,
            ("120-280 字", "2-4 个短拍", "低成本变量", "自然接话口"),
        ),
    }
    for prompt_bundle, expected_terms in compact_contracts.values():
        for term in expected_terms:
            assert term in prompt_bundle


def test_playbook_registry_selects_fengkuang_daily_post() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.select(domain="发疯文学", platform="xiaohongshu")

    assert playbook.playbook_id == "fengkuang_daily_post"
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "xhs_image_strategy",
        "xhs_human_voice",
        "fengkuang_style",
        "positive_reframe",
        "xhs_hashtagging",
    ]


def test_playbook_registry_selects_by_account_domain_and_platform() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-fk-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "fengkuang_daily_post"


def test_playbook_registry_loads_classic_poetry_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("classic_poetry_quote_post")

    assert playbook.domain == "古诗词金句"
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "xhs_image_strategy",
        "xhs_human_voice",
        "classic_poetry_style",
        "xhs_classic_poetry_hashtagging",
    ]


def test_playbook_registry_selects_classic_poetry_by_account_domain_and_platform() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-classic-poetry-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "classic_poetry_quote_post"


def test_registry_loads_wuxia_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("wuxia_character_post")

    assert playbook.domain == "武侠人物评述"
    assert "xiaohongshu" in playbook.platforms
    assert "wuxia_commentary_style" in playbook.required_skills
    assert "xhs_wuxia_hashtagging" in playbook.required_skills
    assert "xhs_image_strategy" in playbook.required_skills
    assert playbook.trend_keywords == [
        "金庸群侠",
        "武侠人物",
        "令狐冲 性格分析",
        "射雕英雄传 人物",
    ]


def test_registry_selects_wuxia_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-wuxia-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "wuxia_character_post"


def test_registry_loads_ai_tech_playbook_with_image_strategy() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("ai_tech_daily_post")

    assert playbook.domain == "AI科技资讯"
    assert "xiaohongshu" in playbook.platforms
    assert "ai_tech_style" in playbook.required_skills
    assert "ai_tech_hashtagging" in playbook.required_skills
    assert "xhs_image_strategy" in playbook.required_skills
    assert playbook.hotspot_routing == {
        "include_any": ["OpenAI", "ChatGPT", "Claude", "大模型", "AI Agent", "提示词"]
    }
    assert playbook.ai_content_policy == {
        "allowed_modes": ["news_brief", "hands_on", "fact_translation"],
        "news_item_count": {"min": 3, "max": 5},
        "hands_on_required_fields": [
            "product",
            "version",
            "tested_at",
            "task",
            "input_summary",
            "observed_output",
            "limitation",
        ],
        "fact_translation_required_fields": [
            "facts",
            "who_should_care",
            "who_can_wait",
        ],
    }
    assert playbook.trend_keywords == []


def test_hotspot_routing_metadata_is_opt_in_and_separate_from_trend_keywords() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    assert registry.get("ai_tech_daily_post").hotspot_routing == {
        "include_any": ["OpenAI", "ChatGPT", "Claude", "大模型", "AI Agent", "提示词"]
    }
    assert registry.get("classic_poetry_quote_post").hotspot_routing == {
        "include_any": ["古诗词", "诗词金句", "苏轼", "东坡", "李白", "杜甫"]
    }
    assert registry.get("daily_english_post").hotspot_routing == {
        "include_any": ["每日英语", "英语", "English", "单词", "短语", "例句"]
    }
    assert registry.get("fengkuang_daily_post").hotspot_routing == {
        "include_any": ["发疯文学", "丝瓜汤"]
    }
    assert registry.get("human_enrichment_daily_post").hotspot_routing == {
        "include_any": ["人类丰容", "Colorwalk", "适我主义"],
        "require_all": [["手作", "钩织"], ["手作", "拼豆"]],
    }
    assert registry.get("modern_psychology_post").hotspot_routing == {
        "include_any": ["情绪内耗", "关系边界", "孤独感", "短视频焦虑"]
    }
    assert registry.get("world_cup_daily_post").hotspot_routing == {
        "include_any": ["世界杯", "美加墨", "FIFA World Cup"]
    }
    assert registry.get("wuxia_character_post").hotspot_routing == {
        "include_any": ["武侠", "金庸", "古龙", "令狐冲", "射雕"]
    }
    assert registry.get("reddit_curation_daily_post").hotspot_routing == {}
    assert registry.get("modern_psychology_post").trend_keywords == [
        "职场焦虑",
        "情绪内耗",
        "关系边界",
        "孤独感",
        "短视频焦虑",
        "睡眠恢复",
    ]


def test_registry_loads_daily_english_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("daily_english_post")

    assert playbook.domain == "每日英语学习"
    assert "xiaohongshu" in playbook.platforms
    assert "daily_english_style" in playbook.required_skills
    assert "daily_english_hashtagging" in playbook.required_skills
    assert "xhs_image_strategy" in playbook.required_skills


def test_registry_selects_daily_english_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-daily-english-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "daily_english_post"


def test_registry_loads_modern_psychology_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("modern_psychology_post")

    assert playbook.domain == "现代心理困境观察"
    assert "xiaohongshu" in playbook.platforms
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "xhs_image_strategy",
        "xhs_human_voice",
        "psychology_style",
        "psychology_safety",
        "xhs_psychology_hashtagging",
    ]
    assert playbook.trend_keywords == [
        "职场焦虑",
        "情绪内耗",
        "关系边界",
        "孤独感",
        "短视频焦虑",
        "睡眠恢复",
    ]
    assert playbook.max_attempts == 3


def test_registry_selects_modern_psychology_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-psychology-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "modern_psychology_post"


def test_registry_loads_human_enrichment_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("human_enrichment_daily_post")

    assert playbook.domain == "人类丰容实验"
    assert "xiaohongshu" in playbook.platforms
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "xhs_image_strategy",
        "xhs_human_voice",
        "human_enrichment_style",
        "xhs_enrichment_visuals",
        "xhs_enrichment_hashtagging",
    ]
    assert playbook.trend_keywords == [
        "人类丰容",
        "家的丰容计划",
        "零成本丰容",
        "工位丰容",
        "Colorwalk",
        "钩织",
    ]
    assert playbook.max_attempts == 3


def test_registry_selects_human_enrichment_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-enrichment-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "human_enrichment_daily_post"


def test_registry_loads_world_cup_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("world_cup_daily_post")

    assert playbook.domain == "世界杯主题"
    assert "xiaohongshu" in playbook.platforms
    assert playbook.required_skills == [
        "xhs_trend_scan",
        "topic_research",
        "xhs_image_strategy",
        "xhs_human_voice",
        "world_cup_style",
        "xhs_world_cup_visuals",
        "xhs_world_cup_hashtagging",
    ]
    assert playbook.trend_keywords == [
        "世界杯",
        "世界杯决赛",
        "小组赛",
        "淘汰赛",
        "足球战术",
        "看球",
    ]
    assert playbook.max_attempts == 3


def test_registry_selects_world_cup_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-world-cup-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "world_cup_daily_post"


def test_registry_loads_reddit_curation_playbook() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )

    playbook = registry.get("reddit_curation_daily_post")

    assert playbook.domain == "Reddit英文讨论转译"
    assert "xiaohongshu" in playbook.platforms
    assert playbook.required_skills == [
        "reddit_discussion_scan",
        "xhs_image_strategy",
        "xhs_human_voice",
        "reddit_curation_style",
        "xhs_reddit_curation_hashtagging",
    ]
    assert playbook.trend_keywords == [
        "OpenAI",
        "ChatGPT",
        "ClaudeAI",
        "psychology",
        "AskPsychology",
        "productivity",
    ]
    assert playbook.max_attempts == 3


def test_registry_selects_reddit_curation_by_account() -> None:
    registry = PlaybookRegistry(
        playbook_root=Path("src/ptsm/playbooks/definitions"),
    )
    account = AccountRegistry().get("acct-reddit-curation-local")

    playbook = registry.select_for_account(account=account)

    assert playbook.playbook_id == "reddit_curation_daily_post"
