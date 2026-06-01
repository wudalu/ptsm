from __future__ import annotations

import json

import pytest

from ptsm.config.settings import get_settings
from ptsm.interfaces.cli.main import main


GENERIC_TITLE_MARKERS = ("日常", "实录", "干货分享", "小红书爆款")
DRAMATIC_TITLE_CUES = (
    "那一秒",
    "那秒",
    "那句",
    "不是",
    "不代表",
    "不想",
    "不急",
    "不能",
    "别",
    "却",
    "反而",
    "突然",
    "原来",
    "为什么",
    "到底",
    "值不值",
    "被",
    "最累",
    "先别",
    "救",
    "硬仗",
    "冷场",
    "改到",
    "拖回",
)
FUNCTIONAL_LABEL_MARKERS = (
    "可复制疯话：",
    "可复制疯话:",
    "今日可复制疯话：",
    "可复制通勤疯话：",
    "可收藏小结：",
    "可收藏小结:",
    "可收藏句型：",
    "可保存单元：",
    "可保存单元:",
    "评论交接：",
    "评论交接:",
    "可以先收藏清单：",
    "可收藏看球清单：",
    "看球清单可以先收藏：",
    "可保存三步：",
    "可复制疯话",
    "今日可复制疯话",
    "可复制通勤疯话",
    "可收藏小结",
    "可收藏句型",
    "可保存单元",
    "评论交接",
    "可以先收藏清单",
    "可收藏看球清单",
    "看球清单可以先收藏",
    "可保存三步",
)


@pytest.mark.parametrize(
    ("playbook_id", "scene", "account_id", "body_min", "body_max"),
    [
        (
            "fengkuang_daily_post",
            "领导18:57突然发来一句在吗，明天早会还要我补材料",
            "acct-fk-local",
            120,
            380,
        ),
        (
            "modern_psychology_post",
            "下班路上还在反复复盘会议里一句话，越想越尴尬",
            "acct-psychology-local",
            260,
            580,
        ),
        (
            "human_enrichment_daily_post",
            "把下班后的书桌从堆满快递盒改成一个十分钟手作角",
            "acct-enrichment-local",
            180,
            520,
        ),
        (
            "sushi_poetry_daily_post",
            "夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析",
            "acct-sushi-local",
            180,
            520,
        ),
        (
            "daily_english_post",
            "想学一个开会和私聊都能用的英语表达",
            "acct-daily-english-local",
            180,
            520,
        ),
        (
            "ai_tech_daily_post",
            "OpenAI 发布一项新的多模态助手更新，普通用户想知道到底值不值得试",
            "acct-ai-tech-local",
            220,
            650,
        ),
        (
            "world_cup_daily_post",
            "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点",
            "acct-world-cup-local",
            220,
            620,
        ),
        (
            "reddit_curation_daily_post",
            "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度",
            "acct-reddit-curation-local",
            220,
            700,
        ),
        (
            "wuxia_character_post",
            "分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
            "acct-wuxia-local",
            700,
            1100,
        ),
    ],
)
def test_xhs_playbook_dry_runs_fit_title_body_quality_contract(
    capsys,
    monkeypatch,
    playbook_id: str,
    scene: str,
    account_id: str,
    body_min: int,
    body_max: int,
) -> None:
    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deterministic")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_ID", raising=False)
    monkeypatch.delenv("REDDIT_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
    monkeypatch.delenv("REDDIT_PUBLIC_JSON_FALLBACK", raising=False)
    get_settings.cache_clear()

    exit_code = main(
        [
            "run-playbook",
            "--scene",
            scene,
            "--account-id",
            account_id,
            "--playbook-id",
            playbook_id,
            "--thread-id",
            f"thread-{playbook_id}-title-body-quality",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]

    assert exit_code == 0
    assert body_min <= len(content["body"]) <= body_max
    assert len(content["title"]) <= 22
    assert any(cue in content["title"] for cue in DRAMATIC_TITLE_CUES)
    assert not any(marker in content["title"] for marker in GENERIC_TITLE_MARKERS)
    visible = f"{content['title']}\n{content['image_text']}\n{content['body']}"
    assert not any(marker in visible for marker in FUNCTIONAL_LABEL_MARKERS)

    get_settings.cache_clear()
