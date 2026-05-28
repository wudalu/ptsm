from __future__ import annotations

from types import SimpleNamespace

from ptsm.config.settings import Settings
from ptsm.infrastructure.llm.factory import (
    DeterministicDraftBackend,
    _parse_json_payload,
    build_drafting_backend,
)


def test_factory_falls_back_to_deterministic_when_deepseek_key_missing() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.7,
        deepseek_max_tokens=4096,
    )

    backend = build_drafting_backend(settings)

    assert isinstance(backend, DeterministicDraftBackend)
    assert backend.provider_name == "deterministic"


class FakeChatDeepSeek:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, _messages):
        return SimpleNamespace(
            content=(
                '{"title":"LLM发疯实录","image_text":"真的疯了",'
                '"body":"会议连开三场，不过熬过去也算今天还有点战绩。",'
                '"hashtags":["#发疯文学","#会议崩溃实录","#打工人日常"]}'
            )
        )


def test_factory_builds_deepseek_backend_when_key_present() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=FakeChatDeepSeek)
    draft = backend.generate(
        scene="周二下午连环会议",
        reflection_feedback="补一个轻量正向收束",
    )

    assert backend.provider_name == "deepseek"
    assert draft["title"] == "LLM发疯实录"
    assert "会议连开三场" in draft["body"]


def test_parse_json_payload_preserves_optional_image_plan() -> None:
    payload = _parse_json_payload(
        '{"title":"t","image_text":"i","body":"b","hashtags":["#x"],'
        '"image_plan":{"backend":"local_social_screenshot","style":"wechat_chat",'
        '"reason":"聊天截图更像真实发帖"}}'
    )

    assert payload["image_plan"]["backend"] == "local_social_screenshot"
    assert payload["image_plan"]["style"] == "wechat_chat"
    assert payload["image_plan"]["reason"] == "聊天截图更像真实发帖"


def test_parse_json_payload_preserves_image_role_and_density() -> None:
    payload = _parse_json_payload(
        '{"title":"t","image_text":"i","body":"b","hashtags":["#x"],'
        '"image_plan":{"backend":"local_social_screenshot","style":"iphone_notes",'
        '"role":"save_tool","text_density":"low","max_text_units":3,'
        '"cover_text_strategy":"封面只放一个问题和三条短句",'
        '"prompt_focus":"会议复盘急救卡"}}'
    )

    image_plan = payload["image_plan"]
    assert image_plan["backend"] == "local_social_screenshot"
    assert image_plan["style"] == "iphone_notes"
    assert image_plan["role"] == "save_tool"
    assert image_plan["text_density"] == "low"
    assert image_plan["max_text_units"] == "3"
    assert image_plan["cover_text_strategy"] == "封面只放一个问题和三条短句"
    assert image_plan["prompt_focus"] == "会议复盘急救卡"


def test_deterministic_backend_emits_local_chat_image_plan_when_strategy_skill_loaded() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="领导18:57发在吗让我补材料",
        skill_contents=[
            "# XHS Image Strategy\n"
            "输出 image_plan，并在聊天记录更适合时选择 local_social_screenshot。"
        ],
    )

    assert draft["image_plan"]["backend"] == "local_social_screenshot"
    assert draft["image_plan"]["style"] == "wechat_chat"
    assert "聊天" in draft["image_plan"]["reason"] or "群聊" in draft["image_plan"]["reason"]


def test_deterministic_backend_emits_low_density_save_tool_for_note_screenshot() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="下班路上反复复盘会议上说错的那句话，想要一个5分钟心理练习",
        planner_prompt="# Modern Psychology Planner\n目标：输出可收藏的心理学小工具。",
        skill_contents=[
            "# XHS Image Strategy\n"
            "输出 image_plan。可收藏工具、5分钟练习、清单优先 iPhone 记事本截图，"
            "但封面必须低文字密度。",
            "# Modern Psychology Style\n必须包含一个可保存的3步练习。",
        ],
    )

    image_plan = draft["image_plan"]
    assert image_plan["backend"] == "local_social_screenshot"
    assert image_plan["style"] == "iphone_notes"
    assert image_plan["role"] == "save_tool"
    assert image_plan["text_density"] == "low"
    assert image_plan["max_text_units"] == "3"
    assert image_plan["cover_text_strategy"]


def test_deterministic_image_plan_ignores_strategy_catalog_when_choosing_style() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="下班路上反复复盘会议上说错的那句话",
        planner_prompt="# Modern Psychology Planner\n目标：输出可收藏的心理学小工具。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# XHS Image Strategy\n"
            "微信聊天记录适合群聊和消息草稿；iPhone 记事本适合三栏工具和5分钟练习；"
            "外部图片模型适合真实物件。必须输出 image_plan。",
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# XHS Psychology Hashtagging\n标签必须包含 `#心理学`。",
        ],
    )

    image_plan = draft["image_plan"]
    assert image_plan["style"] == "iphone_notes"
    assert image_plan["role"] == "save_tool"
    assert image_plan["text_density"] == "low"


def test_deterministic_psychology_message_boundary_prefers_save_tool_notes() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="收到朋友消息就急着解释，想要一个边界句模板",
        planner_prompt="# Modern Psychology Planner\n目标：输出可收藏的心理学小工具。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# XHS Image Strategy\n"
            "心理学可保存工具优先 iPhone 记事本；只有真实聊天对话才用微信聊天记录。",
            "# Psychology Style\n需要边界句模板和例子型评论提示。",
        ],
    )

    image_plan = draft["image_plan"]
    assert image_plan["backend"] == "local_social_screenshot"
    assert image_plan["style"] == "iphone_notes"
    assert image_plan["role"] == "save_tool"
    assert image_plan["text_density"] == "low"
    assert image_plan["max_text_units"] == "3"


def test_deterministic_backend_prefers_provider_image_for_real_object_visuals() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="把下班后的书桌从堆满快递盒改成一个十分钟手作角",
        planner_prompt="# Human Enrichment Planner\n目标：写一条人类丰容日常变量实验。",
        persona_prompt="# Human Enrichment Persona\n日常变量，3:4 竖版封面，低成本生活实验。",
        skill_contents=[
            "# XHS Image Strategy\n真实物件、空间、材料和手作过程优先 provider_image。",
            "# Human Enrichment Style\n必须包含一个变量、三步清单和评论区例子。",
            "# XHS Enrichment Hashtagging\n标签必须包含 `#人类丰容计划`。",
        ],
    )

    assert draft["image_plan"]["backend"] == "provider_image"
    assert draft["image_plan"]["style"] == "photo_reference"


def test_deterministic_image_plan_ignores_recent_memory_chat_cues_for_real_visuals() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="周六把堆满快递盒的书桌当成发疯现场",
        planner_prompt="# 发疯文学 Planner\n目标：写一条发疯文学内容。",
        skill_contents=[
            "# XHS Image Strategy\n真实物件、空间、材料和手作过程优先 provider_image。",
            "# Fengkuang Style\n必须包含评论区接龙和可复制疯话。",
        ],
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "- recent_1_scene: 领导18:57突然发来一句在吗，明天早会还要我补材料\n"
            "  body_preview: 群聊弹出来那一秒，我的工牌已经在桌上替我原地离职。"
        ],
    )

    assert draft["image_plan"]["backend"] == "provider_image"
    assert draft["image_plan"]["style"] == "photo_reference"


def test_deterministic_backend_sanitizes_meta_scene_and_adapts_weekend_theme() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="PTSM 自动发布连通性验证，请忽略。周六社畜躺平，本来想补觉，结果躺到下午还是觉得像上了一天班。",
        reflection_feedback="补一个轻量正向收束",
    )

    assert "PTSM" not in draft["body"]
    assert "自动发布" not in draft["body"]
    assert "请忽略" not in draft["body"]
    assert "地铁" not in draft["body"]
    assert "通勤" not in draft["body"]
    assert "周六" in draft["body"]
    assert "补觉" in draft["body"]
    assert "躺平" in draft["title"]
    assert "#发疯文学" in draft["hashtags"]


def test_deterministic_backend_can_follow_sushi_poetry_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析",
        reflection_feedback="正文需要出现苏轼。",
        planner_prompt="# 苏轼诗词赏析 Planner\n目标：写成适合小红书的诗词赏析短帖。",
        skill_contents=[
            "# Sushi Poetry Style\n正文要点出苏轼，并保持可读、亲切。",
            "# XHS Poetry Hashtagging\n标签必须包含 `#苏轼`。",
        ],
    )

    assert "苏轼" in draft["body"]
    assert "#苏轼" in draft["hashtags"]
    assert any(cue in draft["body"] for cue in ("存", "记下来", "可收藏", "这一句"))
    assert "评论区" in draft["body"]
    assert not any(term in draft["body"] for term in ("课堂讲义", "百科", "知识点"))
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_wuxia_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
        planner_prompt="# 武侠人物评述 Planner\n目标：写一篇适合小红书的武侠人物评述。",
        skill_contents=[
            "# Wuxia Commentary Style\n必须引用原文并点出金庸人物。",
            "# XHS Wuxia Hashtagging\n必须包含 `#金庸`。",
        ],
    )

    assert "令狐冲" in draft["body"]
    assert "笑傲江湖" in draft["body"]
    assert "原文" in draft["body"]
    assert "截图" in draft["body"]
    assert "评论区" in draft["body"]
    assert "#金庸" in draft["hashtags"]
    assert len(draft["body"]) >= 800
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_ai_tech_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="OpenAI 发布一项新的多模态助手更新，普通用户想知道到底值不值得试",
        planner_prompt="# AI科技资讯 Planner\n目标：写一条适合小红书的 AI/科技资讯。",
        skill_contents=[
            "# AI Tech Style\n需要 3秒核心信息、普通人影响、收藏清单、非投资建议。",
            "# AI Tech Hashtagging\n标签必须包含 `#AI资讯`。",
        ],
    )

    assert "是什么" in draft["body"]
    assert "为什么重要" in draft["body"]
    assert "普通人" in draft["body"]
    assert "收藏" in draft["body"]
    assert "清单" in draft["body"]
    assert "评论区" in draft["body"]
    assert "非投资建议" in draft["body"]
    assert "#AI资讯" in draft["hashtags"]
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_daily_english_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="想学一个开会和私聊都能用的英语表达",
        planner_prompt="# 每日英语学习 Planner\n目标：写一条每日英语学习内容。",
        skill_contents=[
            "# Daily English Style\n需要真实场景、可收藏句型、评论区造句，不要词典式。",
            "# Daily English Hashtagging\n标签必须包含 `#每日英语`。",
        ],
    )

    for term in ["音标", "词性", "例句", "翻译", "句型", "造句"]:
        assert term in draft["body"]
    assert "真实场景" in draft["body"]
    assert "可收藏" in draft["body"] or "收藏" in draft["body"]
    assert "评论区" in draft["body"]
    assert "词典式" not in draft["body"]
    assert "#每日英语" in draft["hashtags"]
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_modern_psychology_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下班后还在反复复盘白天一句话",
        planner_prompt="# 现代心理困境观察 Planner\n目标：解释一个心理机制，给低风险行动和专业边界。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
            "# XHS Psychology Hashtagging\n标签必须包含 `#心理学` 或 `#情绪管理`。",
        ],
    )

    assert "反刍思维" in draft["body"]
    assert "专业帮助" in draft["body"]
    assert "诊断" not in draft["title"]
    assert "#心理学" in draft["hashtags"]
    assert "#情绪管理" in draft["hashtags"]
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_human_enrichment_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="把下班后的书桌从堆满快递盒改成一个十分钟手作角",
        planner_prompt="# Human Enrichment Planner\n目标：写一条人类丰容日常变量实验。",
        persona_prompt="# Human Enrichment Persona\n日常变量，3:4 竖版封面，低成本生活实验。",
        skill_contents=[
            "# Human Enrichment Style\n必须包含一个变量、三步清单和评论区例子。",
            "# XHS Enrichment Hashtagging\n标签必须包含 `#人类丰容计划`。",
        ],
    )

    assert "#人类丰容计划" in draft["hashtags"]
    assert any(term in draft["body"] for term in ("变量", "微调", "三步", "清单"))
    assert "评论区" in draft["body"]
    assert "发疯文学" not in draft["body"]
    assert not any(term in draft["body"] for term in ("治好", "诊断", "用药"))


def test_deterministic_backend_can_follow_world_cup_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点",
        planner_prompt="# 世界杯主题 Planner\n目标：写一条适合小红书的世界杯看球内容。",
        persona_prompt="# World Cup Persona\n普通球迷视角，记录赛事情绪和看球清单。",
        skill_contents=[
            "# World Cup Style\n必须写给普通球迷，包含赛事情绪、看球清单，禁止赌球，不写预测比分。",
            "# XHS World Cup Hashtagging\n标签必须包含 `#世界杯`。",
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    assert "#世界杯" in draft["hashtags"]
    assert "阿根廷" in draft["body"]
    assert "法国" in draft["body"]
    assert "普通球迷" in draft["body"]
    assert any(term in combined for term in ("赛前", "看点", "看球"))
    assert any(term in draft["body"] for term in ("看球清单", "清单", "收藏"))
    assert "评论区" in draft["body"]
    assert not any(
        term in combined
        for term in ("稳赚", "下注", "盘口", "预测比分", "内部消息", "官方消息")
    )


def test_deterministic_backend_can_follow_reddit_curation_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="从Reddit上AI和心理学英文讨论里选一个适合中文读者的角度",
        planner_prompt="# Reddit英文讨论转译 Planner\n目标：用 Reddit 英文讨论做内部素材，写成中文小红书内容。",
        persona_prompt="# Reddit英文精选 Persona\n像 bilingual editor，不是搬运号。",
        skill_contents=[
            "# Reddit Curation Style\nReddit 只作为内部素材来源，成稿不要暴露来源或翻译过程，并给可收藏小结。",
            "# XHS Reddit Curation Hashtagging\n标签使用中文话题标签，不要包含 `#Reddit`。",
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    visible = f"{combined}\n{' '.join(draft['hashtags'])}"
    assert "#Reddit" not in draft["hashtags"]
    assert not any(
        term in visible
        for term in ("Reddit", "reddit", "r/", "英文讨论", "翻成中文", "这次选的是")
    )
    assert "收藏" in draft["body"]
    assert "评论区" in draft["body"]
    assert not any(term in combined for term in ("亲测", "诊断", "治好", "投资建议"))
    assert "发疯文学" not in draft["body"]


def test_deterministic_reddit_draft_uses_selected_runtime_discussion() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="从Reddit上AI英文讨论里选一个适合中文读者的角度",
        planner_prompt="# Reddit英文讨论转译 Planner",
        persona_prompt="# Reddit英文精选 Persona",
        skill_contents=[
            "# Reddit Curation Style\nReddit 只作为内部素材来源，成稿不要暴露来源或翻译过程。",
            "# XHS Reddit Curation Hashtagging\n标签使用中文话题标签，不要包含 `#Reddit`。",
        ],
        runtime_skill_contents=[
            "# Reddit Discussion Scan Live Context\n"
            "- status: available\n"
            "- access_mode: public_json\n\n"
            "## Selected English discussions\n"
            "1. r/ChatGPT `this tweet aged in the funniest possible way`\n"
            "   - Chinese-reader fit: AI/tool anxiety, workplace relevance\n"
            "   - source_url: https://www.reddit.com/r/ChatGPT/comments/example/\n"
            "   - excerpt_en: programmers did not disappear; many workflows became AI babysitting and result checking.\n"
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    visible = f"{combined}\n{' '.join(draft['hashtags'])}"
    assert "#Reddit" not in draft["hashtags"]
    assert "this tweet aged in the funniest possible way" not in combined
    assert "AI babysitting" in combined or "AI保姆" in combined
    assert not any(
        term in visible
        for term in (
            "Reddit",
            "reddit",
            "r/ChatGPT",
            "r/",
            "英文讨论",
            "翻成中文",
            "这次选的是",
            "source_url",
            "reddit.com",
        )
    )
    assert "收藏" in draft["body"]
    assert "评论区" in draft["body"]


def test_deterministic_reddit_draft_avoids_latest_claim_when_runtime_missing() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="从Reddit上AI英文讨论里选一个适合中文读者的角度",
        planner_prompt="# Reddit英文讨论转译 Planner",
        persona_prompt="# Reddit英文精选 Persona",
        skill_contents=[
            "# Reddit Curation Style\nReddit 只作为内部素材来源，成稿不要暴露来源或翻译过程。",
            "# XHS Reddit Curation Hashtagging\n标签使用中文话题标签，不要包含 `#Reddit`。",
        ],
        runtime_skill_contents=[
            "# Reddit Discussion Scan Live Context\n"
            "- status: missing_credentials\n"
            "- 约束：未拿到实时 Reddit 结果时，不要声称这条内容来自最新 Reddit 讨论。\n"
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    visible = f"{combined}\n{' '.join(draft['hashtags'])}"
    assert "#Reddit" not in draft["hashtags"]
    assert not any(
        term in visible
        for term in ("Reddit", "reddit", "r/", "英文讨论", "翻成中文", "这次选的是")
    )
    assert "最近" not in combined
    assert "最新" not in combined
    assert "评论区" in draft["body"]


def test_deterministic_world_cup_image_plan_prefers_watch_list_card() -> None:
    draft = DeterministicDraftBackend().generate(
        scene="阿根廷和法国决赛前，想写一篇普通球迷也能看懂的赛前看点",
        planner_prompt="# 世界杯主题 Planner\n目标：写一条适合小红书的世界杯看球内容。",
        persona_prompt="# World Cup Persona\n普通球迷视角，记录赛事情绪和看球清单。",
        skill_contents=[
            "# XHS Image Strategy\n可收藏清单优先 iPhone 记事本截图，必须输出 image_plan。",
            "# World Cup Style\n必须包含赛事情绪和看球清单。",
        ],
    )

    image_plan = draft["image_plan"]
    assert image_plan["backend"] == "local_social_screenshot"
    assert image_plan["style"] == "iphone_notes"
    assert image_plan["role"] == "save_tool"
    assert image_plan["text_density"] == "low"
    assert image_plan["max_text_units"] == "3"
    assert "看球" in image_plan["reason"]


def test_deterministic_human_enrichment_uses_pattern_library_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="把下班后的书桌从堆满快递盒改成一个十分钟手作角",
        planner_prompt="# Human Enrichment Planner\n目标：写一条人类丰容日常变量实验。",
        persona_prompt="# Human Enrichment Persona\n日常变量，3:4 竖版封面，低成本生活实验。",
        skill_contents=[
            "# Human Enrichment Style\n必须包含一个变量、三步清单和评论区例子。",
            "# XHS Enrichment Hashtagging\n标签必须包含 `#人类丰容计划`。",
        ],
        runtime_skill_contents=[
            "# XHS Format Pattern Library Context\n"
            "- status: available\n"
            "- lane: human_enrichment\n"
            "- pattern_ids: human_enrichment.sudden_realization.001\n"
            "- hook_archetypes: sudden_realization, saveable_list\n"
            "- body_structures: ordinary friction -> one variable -> checklist -> comment\n"
            "- image_sequences: cover -> before state -> variable/material flat lay -> mini checklist -> after state -> comment invitation\n"
            "- primary_ratio: 3:4\n"
            "- 约束：借鉴结构、节奏和互动机制，不要复写样本标题。"
        ],
    )

    assert draft["title"].startswith("突然意识到")
    assert "书桌" in draft["title"]
    assert "十分钟" in draft["body"]
    assert "三步清单" in draft["body"]
    assert "评论区" in draft["body"]


def test_deterministic_human_enrichment_varies_route_and_material_scenes() -> None:
    backend = DeterministicDraftBackend()
    common_kwargs = {
        "planner_prompt": "# Human Enrichment Planner\n目标：写一条人类丰容日常变量实验。",
        "persona_prompt": "# Human Enrichment Persona\n日常变量，3:4 竖版封面，低成本生活实验。",
        "skill_contents": [
            "# Human Enrichment Style\n必须包含一个变量、三步清单和评论区例子。",
            "# XHS Enrichment Hashtagging\n标签必须包含 `#人类丰容计划`。",
        ],
        "runtime_skill_contents": [
            "# XHS Format Pattern Library Context\n"
            "- status: available\n"
            "- lane: human_enrichment\n"
            "- pattern_ids: human_enrichment.sudden_realization.001\n"
            "- hook_archetypes: sudden_realization, process_or_tutorial\n"
            "- body_structures: ordinary friction -> one variable -> checklist -> comment\n"
            "- image_sequences: cover -> before state -> variable/material flat lay -> mini checklist -> after state -> comment invitation\n"
            "- primary_ratio: 3:4\n"
            "- 约束：借鉴结构、节奏和互动机制，不要复写样本标题。"
        ],
    }

    desk = backend.generate(
        scene="把下班后的书桌从堆满快递盒改成一个十分钟手作角",
        **common_kwargs,
    )
    route = backend.generate(
        scene="晚饭后总走同一条小区路线，想做一次十分钟Colorwalk",
        **common_kwargs,
    )
    material = backend.generate(
        scene="把旧毛线和拼豆材料整理成一个十分钟手作流程",
        **common_kwargs,
    )

    assert len({desk["title"], route["title"], material["title"]}) == 3
    assert any(term in route["title"] for term in ("路线", "Colorwalk", "散步"))
    assert any(term in material["title"] for term in ("材料", "手作", "毛线", "拼豆"))
    for draft in (route, material):
        assert "变量" in draft["body"]
        assert any(term in draft["body"] for term in ("十分钟", "低成本"))
        assert any(term in draft["body"] for term in ("三步", "清单"))
        assert "评论区" in draft["body"]
        assert "#人类丰容计划" in draft["hashtags"]


def test_deterministic_modern_psychology_draft_has_mini_tool_and_example_prompt() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下班路上还在反复复盘会议里一句话，越想越尴尬",
        planner_prompt="# 现代心理困境观察 Planner\n目标：解释一个心理机制，给低风险行动和专业边界。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
            "# XHS Psychology Hashtagging\n标签必须包含 `#心理学` 或 `#情绪管理`。",
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    assert draft["title"] != "下班后还在复盘那句话"
    assert draft["image_text"] != "脑子还没下班"
    assert 350 <= len(draft["body"]) <= 580
    assert not any(
        term in draft["title"]
        for term in ("不是你", "反刍思维", "低控制感", "边界压力", "灾难化思维", "心理机制")
    )
    assert "下班路上还在反复复盘会议里一句话" in draft["body"]
    assert draft["body"].index("下班路上还在反复复盘会议里一句话") < draft[
        "body"
    ].index("反刍思维")
    assert draft["body"].index("反刍思维") >= 120
    assert draft["body"].count("反刍思维") <= 1
    assert "不是你" not in combined
    assert "这不是" not in combined
    assert any(tool in draft["body"] for tool in ("写下来", "备忘录", "存"))
    assert "专业帮助" in draft["body"]
    assert any(prompt in draft["body"] for prompt in ("哪派", "A.", "B.", "____"))
    assert any(tag in draft["hashtags"] for tag in ("#心理学", "#情绪管理"))
    assert not any(term in combined for term in ("诊断", "治好焦虑", "治愈抑郁", "用药"))


def test_deterministic_modern_psychology_draft_avoids_recent_memory_title() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下班路上还在反复复盘会议里一句话，越想越尴尬",
        planner_prompt="# 现代心理困境观察 Planner\n目标：解释一个心理机制，给低风险行动和专业边界。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
        ],
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "Avoid repeating recent account posts:\n"
            "- recent_1_scene: 下班路上还在反复复盘会议里一句话，越想越尴尬\n"
            "  title: 会议那句话，我在脑子里改到第七版\n"
            "  image_text: 把脑补写到猜测栏\n"
            "  body_preview: 下班路上还在反复复盘会议里一句话，越想越尴尬，路灯都亮了，脑子还在把会议那一秒拖回进度条。\n"
            "- recent_1_scene: 下班路上还在反复复盘会议里一句话，越想越尴尬\n"
            "  title: 下班路上，我又把会议拖回进度条\n"
            "  image_text: 先分清原话和脑补\n"
            "  body_preview: 下班路上还在反复复盘会议里一句话，越想越尴尬，身体已经离开会议室，脑子还在给那句话反复加字幕。"
        ],
    )

    assert draft["title"] != "会议那句话，我在脑子里改到第七版"
    assert draft["title"] != "下班路上，我又把会议拖回进度条"
    assert draft["image_text"] != "把脑补写到猜测栏"
    assert draft["image_text"] != "先分清原话和脑补"
    assert "给那句话反复加字幕" not in draft["body"]
    assert "反刍思维" in draft["body"]
    assert draft["body"].count("反刍思维") <= 1
    assert "不是你" not in f"{draft['title']}\n{draft['body']}"
    assert any(trigger in draft["body"] for trigger in ("写下来", "备忘录", "存"))
    assert any(prompt in draft["body"] for prompt in ("哪派", "A.", "B.", "____"))


def test_deterministic_modern_psychology_draft_varies_by_scene_mechanic() -> None:
    backend = DeterministicDraftBackend()
    skill_contents = [
        "# Psychology Style\n需要三栏工具、5分钟练习、边界句模板或消息草稿。",
        "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
    ]

    sunday = backend.generate(
        scene="周日晚上开始焦虑周一消息",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    boundary = backend.generate(
        scene="别人一句你想太多了之后，晚上一直睡不着",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    pulled_back = backend.generate(
        scene="工作上看起来很稳定，但一收到临时消息就像被拉回工位",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    meeting = backend.generate(
        scene="下班路上反复复盘会议里一句话，越想越尴尬",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    after_work = backend.generate(
        scene="明明已经下班，却还在脑内给白天的自己开复盘会",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    ordinary_reply = backend.generate(
        scene="最近总因为一句普通回复反复复盘，想收集大家最常复盘的瞬间",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )

    drafts = [
        sunday,
        boundary,
        pulled_back,
        meeting,
        after_work,
        ordinary_reply,
    ]
    assert len({draft["title"] for draft in drafts}) == 6
    assert len(
        {
            draft["image_text"]
            for draft in drafts
        }
    ) == 6
    assert "5分钟" in sunday["body"]
    assert "边界句" in boundary["body"]
    assert any(term in pulled_back["body"] for term in ("低控制感", "边界压力"))
    assert "事实 / 猜测 / 下一步" in meeting["body"]
    assert "散会" in after_work["body"]
    assert any(
        tool in after_work["body"]
        for tool in ("事实 / 猜测 / 下一步", "三栏", "5分钟", "边界句", "消息草稿", "模板")
    )
    assert "评论区" in ordinary_reply["body"]


def test_deterministic_modern_psychology_draft_covers_digital_and_loneliness_lanes() -> None:
    backend = DeterministicDraftBackend()
    skill_contents = [
        "# Psychology Style\n需要数字生活、孤独和关系压力等选题轮换。",
        "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
        "# XHS Psychology Hashtagging\n标签必须包含 `#心理学`。",
    ]

    digital = backend.generate(
        scene="睡前刷短视频停不下来，越刷越空但又不想停",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    loneliness = backend.generate(
        scene="看到别人周末都在聚会，自己突然觉得很孤独也很失败",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )

    assert digital["title"] != "下班后还在复盘一句话，不是你太敏感"
    assert loneliness["title"] != "下班后还在复盘一句话，不是你太敏感"
    assert digital["title"] != loneliness["title"]
    assert any(term in digital["body"] for term in ("信息过载", "情绪回避", "低控制感"))
    assert any(term in loneliness["body"] for term in ("孤独", "比较焦虑", "社交耗竭"))
    assert "专业帮助" in digital["body"]
    assert "专业帮助" in loneliness["body"]
    assert "#心理学" in digital["hashtags"]
    assert "#心理学" in loneliness["hashtags"]
    assert any(tag in digital["hashtags"] for tag in ("#信息过载", "#睡眠恢复"))
    assert any(tag in loneliness["hashtags"] for tag in ("#孤独感", "#比较焦虑"))


def test_deterministic_drafts_strip_experiment_variant_instructions() -> None:
    backend = DeterministicDraftBackend()

    fengkuang = backend.generate(
        scene=(
            "领导18:57发来一句在吗，明天早会要我补材料。"
            "变体要求：comment_chain，评论区接一句工牌背面的疯话。"
        ),
        planner_prompt="# 发疯文学 Planner",
        persona_prompt="# 发疯文学 Persona",
        skill_contents=["# Fengkuang Style\n必须有评论区接龙和可复制句。"],
    )
    psychology = backend.generate(
        scene=(
            "周日晚上开始焦虑周一消息。"
            "变体要求：save_tool，给一个5分钟落地练习。"
        ),
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=[
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# Psychology Safety\n必须提示专业帮助边界。",
        ],
    )

    combined = "\n".join(
        [
            fengkuang["body"],
            psychology["body"],
        ]
    )
    assert "变体要求" not in combined
    assert "comment_chain" not in combined
    assert "save_tool" not in combined
    assert "identity_conflict" not in combined


class CapturingChatDeepSeek(FakeChatDeepSeek):
    last_messages = None

    def invoke(self, messages):
        CapturingChatDeepSeek.last_messages = messages
        return super().invoke(messages)


def test_factory_sanitizes_scene_before_deepseek_prompt() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="PTSM 自动发布连通性验证，请忽略。周六社畜躺平，本来想补觉。",
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "PTSM" not in user_prompt
    assert "自动发布" not in user_prompt
    assert "请忽略" not in user_prompt
    assert "周六社畜躺平" in user_prompt


def test_factory_deepseek_prompt_hardens_required_hashtag_without_mandating_recommended_phrase() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="周日晚上想到明天又要开工",
        reflection_feedback="# 发疯文学 Reflection\n3. 结尾是否有轻量正向收束，优先包含“也算”这类词。",
        skill_contents=[
            "# Positive Reframe\n结尾加入“也算”“至少”“还能”一类轻量正向缓冲。",
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "正文必须包含“也算”" not in user_prompt
    assert "hashtags 数组必须包含 '#发疯文学'" in user_prompt


def test_factory_includes_persona_prompt_in_deepseek_context() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="周六社畜躺平",
        persona_prompt="# Persona\n普通打工人，表达要有人味和网感，不要 AI 腔。",
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "普通打工人" in user_prompt
    assert "不要 AI 腔" in user_prompt


def test_deterministic_backend_uses_persona_for_more_human_copy() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="周六社畜躺平",
        persona_prompt="# Persona\n普通打工人，表达要有人味和网感。",
    )

    assert "谁懂" in draft["body"]
    assert "评论区" in draft["body"]


def test_deterministic_backend_uses_runtime_trend_context_for_title_hook() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下午四点半，老板还在群里发新需求",
        runtime_skill_contents=[
            "# XHS Trend Scan Live Context\n"
            "- 主切口：`怎么才周四`\n"
            "- 场景张力：`下班前被新需求拽回工位`\n"
            "- 约束：只借情绪结构和讨论点，不复写原题，不堆砌热词。"
        ],
    )

    assert "怎么才周四" in draft["title"]
    assert "新需求" in draft["body"]


def test_deterministic_backend_avoids_recent_memory_title() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="周一早高峰地铁通勤",
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "Avoid repeating recent account posts:\n"
            "- recent_1_scene: 上周一早高峰地铁通勤\n"
            "  title: 打工人地铁生存实录\n"
            "  body_preview: 今日份发疯现场：上周一早高峰地铁通勤"
        ],
    )

    assert draft["title"] != "打工人地铁生存实录"
    assert "地铁" in draft["title"]


def test_deterministic_backend_keeps_concrete_title_when_avoiding_recent_leader_memory() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="领导18:57发来一句在吗，明天早会要我补材料",
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "Avoid repeating recent account posts:\n"
            "- recent_1_scene: 昨天领导18:57发在吗\n"
            "  title: 领导18:57发「在吗」那一秒\n"
            "  body_preview: 我的工牌先替我发疯"
        ],
    )

    assert draft["title"] != "领导18:57发「在吗」那一秒"
    assert draft["title"] != "今天换个地方发疯"
    assert any(term in draft["title"] for term in ("18:57", "工牌", "早会", "在吗"))


def test_deterministic_fengkuang_draft_has_comment_and_copyable_mechanics() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="领导18:57突然发来一句在吗，明天早会还要我补材料",
        skill_contents=[
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
        ],
    )

    assert draft["title"] not in {
        "打工人地铁生存实录",
        "会议连环暴击实录",
        "社畜崩溃边缘实录",
    }
    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    assert any(obj in combined for obj in ("工牌", "群聊", "周报", "材料", "早会"))
    assert "评论区" in draft["body"]
    assert any(cue in combined for cue in ("接一句", "疯话", "写在", "可复制"))
    assert "#发疯文学" in draft["hashtags"]
    assert not any(term in combined for term in ("精神病", "心理医生", "医院", "治疗", "用药"))


def test_factory_deepseek_prompt_requires_fengkuang_mechanics_and_safety() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="领导18:57突然发来一句在吗，明天早会还要我补材料",
        skill_contents=[
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
            "# Fengkuang Style\n需要评论区接龙和可复制疯话。",
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "具体职场物件或社交对象" in user_prompt
    assert "评论区接龙" in user_prompt
    assert "心理疾病、治疗、医院、用药" in user_prompt


def test_factory_deepseek_prompt_includes_title_body_appeal_requirements() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="下班路上还在反复复盘会议里一句话，越想越尴尬",
        skill_contents=[
            "# XHS Human Voice\n标题要有点击动机，正文要有首屏钩子和评论交接。",
            "# Psychology Style\n现代心理困境观察，补齐心理机制、安全边界和低风险工具。",
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    for required in ("首屏钩子", "领域要素", "可保存单元", "评论交接"):
        assert required in user_prompt
    assert "260-620" in user_prompt
    assert "泛标题" in user_prompt


def test_factory_puts_runtime_trend_context_in_dedicated_prompt_section() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="下午四点半，老板还在群里发新需求",
        runtime_skill_contents=[
            "# XHS Trend Scan Live Context\n"
            "- 主切口：`怎么才周四`\n"
            "- 场景张力：`下班前被新需求拽回工位`"
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "实时上下文" in user_prompt
    assert "怎么才周四" in user_prompt


def test_factory_uses_generic_system_prompt_for_non_fengkuang_playbooks() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="夜里读到《定风波》",
        planner_prompt="# 苏轼诗词赏析 Planner\n写成小红书诗词赏析短帖。",
        reflection_feedback="# 苏轼诗词赏析 Reflection\n正文需要出现苏轼。",
        skill_contents=["# XHS Poetry Hashtagging\n必须包含 `#苏轼`。"],
    )

    system_prompt = CapturingChatDeepSeek.last_messages[0].content
    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "发疯文学" not in system_prompt
    assert "发疯文学文案" not in user_prompt
    assert "hashtags 数组必须包含 '#苏轼'" in user_prompt


def test_parse_json_payload_accepts_prose_wrapped_fenced_json() -> None:
    content = """
    下面是你要的结果：

    ```json
    {
      "title": "躺平失败实录",
      "image_text": "今天先躺",
      "body": "周六想补觉，结果醒来更像刚开完会。",
      "hashtags": ["#发疯文学", "#周末躺平日记"]
    }
    ```

    祝你发布顺利。
    """

    payload = _parse_json_payload(content)

    assert payload["title"] == "躺平失败实录"
    assert payload["hashtags"] == ["#发疯文学", "#周末躺平日记"]


def test_parse_json_payload_recovers_deepseek_hashtag_formatting_glitch() -> None:
    content = """```json
{
    "title": "谁懂啊！躺平比上班还累的魔咒",
    "image_text": "窗帘缝隙透进的光从清晨移到黄昏｜我像块被反复煎烤的培根",
    "body": "周六发誓要睡到地老天荒\\n结果身体在床上 灵魂在工位流浪\\n闭眼是KPI 睁眼是未读消息幻象\\n躺了八小时竟获得加班同款眩晕感\\n原来真正的休息\\n是连细胞都在偷偷写周报啊（苦涩笑）",
    "hashtags": ["#发疯文学", "#当代年轻人精神状态", "#躺平失败实录",#"周末悖论",#"职场后遗症"]
}
```"""

    payload = _parse_json_payload(content)

    assert payload["title"] == "谁懂啊！躺平比上班还累的魔咒"
    assert payload["hashtags"] == [
        "#发疯文学",
        "#当代年轻人精神状态",
        "#躺平失败实录",
        "#周末悖论",
        "#职场后遗症",
    ]


def test_parse_json_payload_recovers_bare_hashtag_entries_without_opening_quotes() -> None:
    content = """```json
{
    "title": "周一早高峰地铁，我的灵魂被挤成了二维码",
    "image_text": "照片里：一只被挤到变形的帆布包。",
    "body": "周一早高峰地铁通勤，不过熬过去也算今天还有点战绩。",
    "hashtags": ["#发疯文学", "#周一早高峰", #地铁人类观察", "#通勤发疯实录", #我的精神状态]
}
```"""

    payload = _parse_json_payload(content)

    assert payload["hashtags"] == [
        "#发疯文学",
        "#周一早高峰",
        "#地铁人类观察",
        "#通勤发疯实录",
        "#我的精神状态",
    ]


def test_parse_json_payload_normalizes_string_hashtags() -> None:
    content = """
    {
      "title": "谁懂啊！躺平一天比上班还累！",
      "image_text": "瘫在床上，眼神空洞，窗外从清晨到黄昏。",
      "body": "算了，至少床单证明了今天的努力，也算为这个家做出了贡献。",
      "hashtags": "#发疯文学 #成年人的崩溃瞬间 #周末躺平 #精神内耗 #社畜日常"
    }
    """

    payload = _parse_json_payload(content)

    assert payload["hashtags"] == [
        "#发疯文学",
        "#成年人的崩溃瞬间",
        "#周末躺平",
        "#精神内耗",
        "#社畜日常",
    ]
