from __future__ import annotations

import json
from pathlib import Path

import pytest

from ptsm.config.settings import get_settings
from ptsm.evaluations.contracts import EvalTarget
from ptsm.evaluations.contracts_eval import contract_playbook_node_contract
from ptsm.evaluations.playbook_contracts import load_playbook_eval_contract
from ptsm.interfaces.cli.main import main


GENERIC_TITLE_MARKERS = ("日常", "实录", "干货分享", "小红书爆款")
TITLE_CONCRETE_ENTRY_MARKERS = {
    "fengkuang_daily_post": ("工牌", "群聊", "周报", "早会", "下班", "领导", "物件", "地铁", "周六", "需求"),
    "modern_psychology_post": ("下班", "会议", "消息", "睡前", "关系", "脑子", "那句话"),
    "human_enrichment_daily_post": ("丰容", "变量", "角落", "书桌", "路线", "材料", "床头", "一厘米", "那条路"),
    "classic_poetry_quote_post": ("古诗词", "金句", "这一句", "李白", "李清照", "月亮", "王维", "定风波"),
    "daily_english_post": ("开会", "私聊", "例句", "这句", "英语"),
    "ai_tech_daily_post": ("AI", "普通人", "搭子", "工具", "更新"),
    "world_cup_daily_post": ("世界杯", "赛前", "看球", "开球", "终场", "阿根廷", "法国"),
    "reddit_curation_daily_post": ("AI", "工具", "消息", "压力", "普通人"),
    "wuxia_character_post": ("令狐冲", "黄蓉", "郭靖", "老款", "边界", "自由"),
}
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
ABSTRACT_BODY_MARKERS = (
    "本文",
    "本篇",
    "从本质上",
    "总体来说",
    "核心逻辑是",
    "建议大家",
)
BODY_SCENE_SIGNAL_MARKERS = {
    "fengkuang_daily_post": ("领导", "工牌", "群聊", "周报", "早会", "下班", "工位", "地铁"),
    "modern_psychology_post": ("下班", "会议", "消息", "睡前", "关系", "脑子", "身体", "今晚", "那句话"),
    "human_enrichment_daily_post": ("角落", "书桌", "床头", "路线", "材料", "今天", "十分钟", "手边"),
    "classic_poetry_quote_post": ("古诗词", "金句", "这一句", "李白", "李清照", "月亮", "今天"),
    "daily_english_post": ("今天", "开会", "私聊", "这句", "例句", "评论区", "你会怎么说"),
    "ai_tech_daily_post": ("AI", "工具", "普通人", "今天", "工作流", "试", "边界"),
    "world_cup_daily_post": ("赛前", "看球", "普通球迷", "今晚", "这场", "评论区"),
    "reddit_curation_daily_post": ("AI", "工具", "压力", "消息", "普通人", "今天", "你现在"),
    "wuxia_character_post": ("令狐冲", "黄蓉", "郭靖", "这一段", "原文", "今天", "职场"),
}
BODY_HUMAN_ANCHORS = ("我", "你", "我们", "今天", "刚刚", "那一秒", "今晚", "路上", "手边", "这句", "这个")
AI_TECH_NEWS_EVIDENCE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "ai_tech_evidence" / "news_brief.json"
)


@pytest.mark.parametrize(
    ("playbook_id", "scene", "account_id", "body_min", "body_max"),
    [
        (
            "fengkuang_daily_post",
            "领导18:57突然发来一句在吗，明天早会还要我补材料",
            "acct-fk-local",
            90,
            220,
        ),
        (
            "modern_psychology_post",
            "下班路上还在反复复盘会议里一句话，越想越尴尬",
            "acct-psychology-local",
            200,
            380,
        ),
        (
            "human_enrichment_daily_post",
            "把下班后的书桌从堆满快递盒改成一个十分钟手作角",
            "acct-enrichment-local",
            120,
            280,
        ),
        (
            "classic_poetry_quote_post",
            "读到李白长风破浪会有时，想写给低谷里的自己",
            "acct-classic-poetry-local",
            120,
            280,
        ),
        (
            "daily_english_post",
            "想学一个开会和私聊都能用的英语表达",
            "acct-daily-english-local",
            140,
            300,
        ),
        (
            "ai_tech_daily_post",
            "OpenAI 发布一项新的多模态助手更新，普通用户想知道到底值不值得试",
            "acct-ai-tech-local",
            40,
            360,
        ),
        (
            "world_cup_daily_post",
            "阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点",
            "acct-world-cup-local",
            180,
            420,
        ),
        (
            "reddit_curation_daily_post",
            "从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度",
            "acct-reddit-curation-local",
            180,
            420,
        ),
        (
            "wuxia_character_post",
            "分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
            "acct-wuxia-local",
            450,
            750,
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

    command = [
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
    if playbook_id == "ai_tech_daily_post":
        command.extend(
            [
                "--ai-content-mode",
                "news_brief",
                "--ai-evidence-file",
                str(AI_TECH_NEWS_EVIDENCE),
                "--topic-direction-id",
                "ai_news_three_updates_brief",
            ]
        )

    exit_code = main(command)

    payload = json.loads(capsys.readouterr().out)
    content = payload["final_content"]

    assert exit_code == 0
    assert body_min <= len(content["body"]) <= body_max
    body_beats = [line for line in content["body"].splitlines() if line.strip()]
    assert 2 <= len(body_beats) <= 4
    assert len(content["title"]) <= 22
    assert any(cue in content["title"] for cue in TITLE_CONCRETE_ENTRY_MARKERS[playbook_id])
    assert not any(marker in content["title"] for marker in GENERIC_TITLE_MARKERS)
    visible = f"{content['title']}\n{content['image_text']}\n{content['body']}"
    assert not any(marker in visible for marker in FUNCTIONAL_LABEL_MARKERS)
    assert any(marker in content["body"] for marker in BODY_SCENE_SIGNAL_MARKERS[playbook_id])
    if playbook_id != "ai_tech_daily_post":
        assert any(anchor in content["body"] for anchor in BODY_HUMAN_ANCHORS)
    assert not any(marker in content["body"] for marker in ABSTRACT_BODY_MARKERS)

    definitions_root = Path(__file__).resolve().parents[2] / "src" / "ptsm" / "playbooks" / "definitions"
    contract = load_playbook_eval_contract(definitions_root, playbook_id)
    assert contract is not None
    contract_result = contract_playbook_node_contract(
        EvalTarget(
            target_id=f"e2e:{playbook_id}:executor",
            run_id=f"thread-{playbook_id}-title-body-quality",
            playbook_id=playbook_id,
            account_id=account_id,
            phase="executor",
            target_type="artifact_slice",
            output_ref={"final_content": content},
        ),
        contract,
    )
    assert contract_result.status == "passed", contract_result.reason

    get_settings.cache_clear()
