from __future__ import annotations

import json
import re
from typing import Any, Mapping

from pydantic import ValidationError
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import StringPromptValue
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.exceptions import OutputParserException
from langchain_core.utils.json import parse_and_check_json_markdown, parse_json_markdown

from ptsm.config.settings import Settings
from ptsm.domain.ai_tech_content import parse_ai_tech_runtime_contract
from ptsm.domain.psychology_carousel import normalize_psychology_carousel_plan
from ptsm.domain.psychology_learning import (
    parse_psychology_learning_runtime_contract,
    render_psychology_learning_draft,
)
from ptsm.infrastructure.llm.contextual_drafts import build_contextual_deterministic_draft

XHS_DRAFT_SYSTEM_PROMPT = (
    "你是一个负责小红书中文内容草稿的文案助手。"
    "请输出严格 JSON，对象字段必须是 title, image_text, body, hashtags。"
    "如果上下文要求图片策略，可额外输出 image_plan 对象，说明图片角色和文字密度。"
    "语气要自然、可读、贴近社交媒体发布。"
)

SCENE_META_PATTERNS = (
    r"\bPTSM\b",
    r"自动发布(?:连通性)?验证",
    r"连通性验证",
    r"(?:变体要求|实验变体|variant(?: type)?)[：:][^。.!！?？；;]*",
    r"\b(?:comment_chain|save_tool|identity_conflict)\b",
    r"\bsmoke(?:\s*test)?\b",
    r"\bdry[- ]?run\b",
    r"\bpublish\b",
    r"请忽略",
)

XHS_BODY_LENGTH_RULES = (
    ("90-220", ("Fengkuang Style", "fengkuang_daily_post", "#发疯文学")),
    (
        "200-380",
        (
            "Psychology Style",
            "Psychology Safety",
            "modern_psychology_post",
            "XHS Psychology Hashtagging",
        ),
    ),
    (
        "120-280",
        (
            "Human Enrichment Style",
            "human_enrichment_daily_post",
            "#人类丰容计划",
        ),
    ),
    (
        "120-280",
        (
            "Classic Poetry Quote Style",
            "classic_poetry_quote_post",
            "XHS Classic Poetry Hashtagging",
            "#古诗词",
        ),
    ),
    (
        "140-300",
        ("Daily English Style", "Daily English Hashtagging", "daily_english_post", "#每日英语"),
    ),
    ("180-420", ("AI Tech Style", "AI Tech Hashtagging", "ai_tech_daily_post", "#AI资讯")),
    (
        "180-420",
        (
            "World Cup Style",
            "XHS World Cup Hashtagging",
            "world_cup_daily_post",
            "world_cup_style",
            "#世界杯",
        ),
    ),
    (
        "180-420",
        (
            "Reddit Curation Style",
            "XHS Reddit Curation Hashtagging",
            "reddit_curation_daily_post",
        ),
    ),
    (
        "450-750",
        ("Wuxia Commentary Style", "XHS Wuxia Hashtagging", "wuxia_character_post", "#金庸", "#古龙"),
    ),
)


class DeterministicDraftBackend:
    """Offline-safe drafting backend for development and tests."""

    provider_name = "deterministic"

    def __init__(self) -> None:
        prompt = PromptTemplate.from_template(
            "场景: {scene}\n"
            "修正意见: {reflection_feedback}\n"
            "补充约束开始\n"
            "{extra_context}\n"
            "补充约束结束\n"
            "实时上下文开始\n"
            "{runtime_context}\n"
            "实时上下文结束\n"
            "任务: 生成一条用于小红书 dry-run 的中文内容草稿。"
        )
        self._chain = prompt | RunnableLambda(self._render)

    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        persona_prompt: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
        runtime_skill_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        scene = _normalize_scene(scene)
        return self._chain.invoke(
            {
                "scene": scene,
                "reflection_feedback": reflection_feedback or "无",
                "extra_context": _compose_static_context(
                    persona_prompt=persona_prompt,
                    planner_prompt=planner_prompt,
                    skill_contents=skill_contents,
                ),
                "runtime_context": "\n\n".join(chunk for chunk in (runtime_skill_contents or []) if chunk)
                or "无",
            }
        )

    def _render(self, prompt_value: StringPromptValue) -> dict[str, Any]:
        prompt_text = prompt_value.to_string()
        scene = _normalize_scene(_extract_field(prompt_text, prefix="场景: "))
        feedback = _extract_field(prompt_text, prefix="修正意见: ")
        extra_context = _extract_block(
            prompt_text,
            start_marker="补充约束开始",
            end_marker="补充约束结束",
        )
        runtime_context = _extract_block(
            prompt_text,
            start_marker="实时上下文开始",
            end_marker="实时上下文结束",
        )
        draft = _build_deterministic_draft(
            scene=scene,
            feedback=feedback,
            extra_context=extra_context,
            runtime_context=runtime_context,
        )
        if _has_xhs_image_strategy(extra_context) and "image_plan" not in draft:
            draft["image_plan"] = _build_deterministic_image_plan(
                scene=scene,
                extra_context=extra_context,
                runtime_context=runtime_context,
                draft=draft,
            )
        return draft


class DeepSeekDraftBackend:
    """DeepSeek-backed drafting backend."""

    provider_name = "deepseek"

    def __init__(self, llm: Any):
        self._llm = llm

    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        persona_prompt: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
        runtime_skill_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        scene = _normalize_scene(scene)
        extra_context = _compose_static_context(
            persona_prompt=persona_prompt,
            planner_prompt=planner_prompt,
            skill_contents=skill_contents,
        )
        runtime_context = "\n\n".join(chunk for chunk in (runtime_skill_contents or []) if chunk)
        psychology_learning_contract = _extract_psychology_learning_runtime_contract(
            runtime_context
        )
        if psychology_learning_contract is not None:
            # Psychology learning copy is a reviewed catalog deliverable, not
            # an open-ended model completion.  The runtime gate enforces this
            # same output for custom backends.
            return render_psychology_learning_draft(psychology_learning_contract)
        hard_requirements = _build_deepseek_hard_requirements(
            extra_context=extra_context,
            runtime_context=runtime_context,
            scene=scene,
        )
        user_prompt = (
            f"场景：{scene}\n"
            f"修正意见：{reflection_feedback or '无'}\n"
            "补充约束：\n"
            f"{extra_context or '无'}\n"
            "实时上下文：\n"
            f"{runtime_context or '无'}\n"
            f"硬性约束：{hard_requirements}\n"
            "请生成一条适合小红书发布的中文内容草稿，并返回严格 JSON。"
        )
        response = self._llm.invoke(
            [
                SystemMessage(content=XHS_DRAFT_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        return _parse_json_payload(response.content)


class DeepSeekJudgeBackend:
    """DeepSeek-backed LLM judge for hard content-quality gates."""

    provider_name = "deepseek"

    def __init__(self, llm: Any):
        self._llm = llm

    def judge(self, *, prompt: str) -> str:
        response = self._llm.invoke(
            [
                SystemMessage(
                    content=(
                        "你是小红书内容质量审稿员。只返回调用方要求的严格 JSON，"
                        "不要输出 Markdown，不要额外解释。"
                    )
                ),
                HumanMessage(content=prompt),
            ]
        )
        return str(response.content)


def build_drafting_backend(
    settings: Settings,
    *,
    chat_model_cls: type[Any] | None = None,
    model: str | None = None,
) -> DeterministicDraftBackend | DeepSeekDraftBackend:
    """Build drafting backend from settings with deterministic fallback."""
    provider = settings.default_model_provider.lower().strip()

    if provider == "deepseek" and settings.deepseek_api_key:
        chat_model_cls = chat_model_cls or _load_chat_deepseek()
        llm = chat_model_cls(
            model=model or settings.deepseek_model or settings.default_model,
            api_key=settings.deepseek_api_key,
            api_base=settings.deepseek_base_url,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )
        return DeepSeekDraftBackend(llm)

    return DeterministicDraftBackend()


def build_llm_judge_backend(
    settings: Settings,
    *,
    chat_model_cls: type[Any] | None = None,
) -> DeepSeekJudgeBackend | None:
    """Build a judge backend when a real LLM provider is configured."""
    provider = settings.default_model_provider.lower().strip()
    if provider != "deepseek" or not settings.deepseek_api_key:
        return None
    chat_model_cls = chat_model_cls or _load_chat_deepseek()
    llm = chat_model_cls(
        model=settings.deepseek_model or settings.default_model,
        api_key=settings.deepseek_api_key,
        api_base=settings.deepseek_base_url,
        temperature=0.1,
        max_tokens=min(settings.deepseek_max_tokens, 1024),
    )
    return DeepSeekJudgeBackend(llm)


def _load_chat_deepseek() -> type[Any]:
    try:
        from langchain_deepseek import ChatDeepSeek
    except ImportError as exc:
        raise RuntimeError(
            "langchain-deepseek is required for DeepSeek-backed drafting."
        ) from exc
    return ChatDeepSeek


def _extract_field(prompt_text: str, *, prefix: str) -> str:
    for line in prompt_text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def _extract_block(prompt_text: str, *, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(
        rf"{re.escape(start_marker)}\n(.*?)\n{re.escape(end_marker)}",
        flags=re.DOTALL,
    )
    match = pattern.search(prompt_text)
    if match is None:
        return ""
    return match.group(1).strip()


def _compose_static_context(
    *,
    persona_prompt: str | None,
    planner_prompt: str | None,
    skill_contents: list[str] | None,
) -> str:
    return (
        "\n\n".join(
            chunk
            for chunk in [persona_prompt or "", planner_prompt or "", *(skill_contents or [])]
            if chunk
        )
        or "无"
    )


def _normalize_scene(scene: str) -> str:
    cleaned = scene.strip()
    for pattern in SCENE_META_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[，,。.!！?？；;、]+", "，", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" ，")
    return cleaned or scene.strip()


def _build_deterministic_draft(
    *,
    scene: str,
    feedback: str,
    extra_context: str = "",
    runtime_context: str = "",
) -> dict[str, Any]:
    contextual = build_contextual_deterministic_draft(
        scene=scene,
        feedback=feedback,
        extra_context=extra_context,
        runtime_context=runtime_context,
    )
    if contextual is not None:
        return contextual

    if _is_classic_poetry_context(scene=scene, extra_context=extra_context):
        title = "读到李白那句，突然不慌了"
        image_text = "这一句可以先存下"
        body = (
            f"{scene}。\n"
            "再回头看李白写“长风破浪会有时”，才发现古诗词金句不是让人立刻赢，"
            "而是提醒自己先把今天稳住。"
            "这一句可以存下来：低谷不是结论，只是现在还没到风来的时候。"
            "评论区留一句你最近读到会想到自己的古诗词。"
        )
        hashtags = ["#古诗词", "#诗词金句", "#小红书读书笔记"]
        if feedback != "无" and "这一句" not in body:
            body += "\n把这一句补回来，读法才不会散成泛泛的文化感。"
        return {
            "title": title,
            "image_text": image_text,
            "body": body,
            "hashtags": hashtags,
        }

    if "丝瓜汤" in scene:
        title = "领导递来丝瓜汤那秒工牌沉默了"
        image_text = "这碗汤工牌先不喝"
        body = (
            f"{scene}，我表面点头，工牌已经在桌上把自己扣成了免打扰。\n"
            "丝瓜汤式安慰最会让人卡住：问题没解决，情绪还要被安排成“你先降降火”。"
            "我把这句写在工牌背面：谢谢关心，但我的工牌现在只想喝下班风。"
            "评论区接一句你遇到过的丝瓜汤式职场回复，我先替大家写进群聊草稿。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#职场情绪实录"]
    elif _is_weekend_rest_scene(scene):
        title = "周六躺平，脑子却在加班"
        image_text = "今天先躺"
        body = (
            f"谁懂，周六本来想靠{scene}给自己回口血，结果人是躺下了，脑子还在加班续命。\n"
            "我把这句写在床头：床批了我的假，工位别越权；明早再把工牌翻回来。"
            "评论区接一句你最想贴在床头的周末保命宣言。"
        )
        hashtags = ["#发疯文学", "#周末躺平日记", "#社畜回血现场"]
    elif _is_commute_scene(scene):
        title = "地铁门关上那秒我把灵魂留站台"
        image_text = "灵魂请下一站下车"
        body = (
            f"今日份发疯现场：{scene}，我差点当场把灵魂寄存给下一站。\n"
            "我把这句写在闸机口：人在车厢，心已请假，工牌留在包里，今天别追我，我先下线。"
            "评论区接一句你最想写在闸机口的打工人暗号。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#通勤崩溃实录"]
    elif _is_meeting_scene(scene):
        title = "周报翻开那秒脑子先离席"
        image_text = "点头模式已开启"
        body = (
            f"今日份崩溃瞬间：{scene}，我感觉自己像被会议室循环播放到只剩下点头功能。\n"
            "我想把这句写在周报封面：收到，但大脑正在加载失败，工牌也先别给我点头。"
            "评论区接一句你开会时最想打在共享屏上的疯话。"
        )
        hashtags = ["#发疯文学", "#会议崩溃实录", "#打工人日常"]
    elif _is_after_hours_leader_scene(scene):
        title = "领导18:57发「在吗」那一秒"
        image_text = "我的工牌先替我发疯"
        body = (
            f"{scene}，群聊弹出来那一秒，我的工牌已经在桌上替我原地离职。\n"
            "我只想把这句写在工牌背面：收到，明早处理，今晚工牌先关机。"
            "评论区接一句你最想写在工牌背面的回复，明天早会前我先替大家默背。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#职场发疯实录"]
    elif _should_apply_runtime_trend(scene=scene, runtime_context=runtime_context):
        primary_hook = _extract_runtime_signal(runtime_context, label="主切口")
        tension = _extract_runtime_signal(runtime_context, label="场景张力")
        title = (
            f"{primary_hook}，我又被新需求拽回工位"
            if primary_hook
            else "下班前又被新需求拽回工位"
        )
        image_text = primary_hook or "收到，但灵魂已下班"
        body = (
            f"{scene}，本来都快在心里打卡下班了，结果又被新需求一下子拽回工位。\n"
            f"{tension or '这种临门一脚的回拉感'}真的很会精准挑人快要松口气的时候下手，"
            "嘴上说着收到，心里已经把这句写在工牌背面：收到，但灵魂已下班。"
            "评论区接一句你最想发在群里但不敢发的下班疯话。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#职场情绪实录"]
    else:
        title = "这口气被我写在工牌背面"
        image_text = "收到，但灵魂已下班"
        body = (
            f"今日份发疯现场：{scene}。\n"
            "人看起来还坐得住，情绪其实已经提前一步申请下班了。"
            "我把这句写在工牌背面：收到，但工牌只负责出勤，不负责续命。"
            "评论区接一句你今天最想写进群聊草稿箱的话。"
        )
        hashtags = ["#发疯文学", "#社畜日常", "#打工人情绪实录"]

    title, image_text = _avoid_recent_memory_title(
        title=title,
        image_text=image_text,
        scene=scene,
        runtime_context=runtime_context,
    )
    if feedback != "无":
        body += "\n不过换个角度想，能把这口气慢慢喘匀、还能给自己留点电，也算今天没白扛。"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }


def _avoid_recent_memory_title(
    *, title: str, image_text: str, scene: str, runtime_context: str
) -> tuple[str, str]:
    if "# Recent Account Memory" not in runtime_context or title not in runtime_context:
        return title, image_text
    if _is_commute_scene(scene):
        return "地铁门关上那秒我先下线", "灵魂请下一站下车"
    if _is_meeting_scene(scene):
        return "我被会议室循环播放到没电", "点头模式已开启"
    if _is_weekend_rest_scene(scene):
        return "周末回血失败，脑子却在加班", "躺着也在耗电"
    if _is_after_hours_leader_scene(scene):
        return "18:57那句在吗把工牌点燃了", "我的工牌先替我发疯"
    return "这口气被我换个地方写下", image_text


def _is_classic_poetry_context(*, scene: str, extra_context: str) -> bool:
    if any(
        keyword in extra_context
        for keyword in (
            "Classic Poetry Quote Style",
            "classic_poetry_quote_post",
            "XHS Classic Poetry Hashtagging",
        )
    ):
        return True
    return any(
        keyword in scene
        for keyword in (
            "古诗词金句",
            "古诗词",
            "诗词金句",
            "经典诗句",
            "Classic Poetry Quote Style",
            "XHS Classic Poetry Hashtagging",
            "#古诗词",
            "李白",
            "李清照",
            "王维",
            "杜甫",
            "长风破浪",
            "苏轼",
            "诗词赏析",
            "#苏轼",
            "定风波",
            "赤壁赋",
            "水调歌头",
        )
    )


def _is_weekend_rest_scene(scene: str) -> bool:
    return any(
        keyword in scene
        for keyword in ("周六", "周日", "周末", "躺平", "补觉", "赖床", "沙发", "回血")
    )


def _is_commute_scene(scene: str) -> bool:
    return any(
        keyword in scene
        for keyword in ("地铁", "通勤", "下班路上", "公交", "挤车", "早高峰", "晚高峰")
    )


def _is_meeting_scene(scene: str) -> bool:
    return any(
        keyword in scene
        for keyword in ("会议", "开会", "周报", "汇报", "复盘", "评审")
    )


def _is_after_hours_leader_scene(scene: str) -> bool:
    return any(keyword in scene for keyword in ("领导", "老板")) and any(
        keyword in scene for keyword in ("在吗", "早会", "材料", "下班", "18:")
    )


def _parse_json_payload(content: str) -> dict[str, Any]:
    cleaned = _repair_json_payload_text(content.strip())
    try:
        payload = parse_and_check_json_markdown(
            cleaned,
            ["title", "image_text", "body", "hashtags"],
        )
    except OutputParserException:
        payload = parse_json_markdown(cleaned)
        if not isinstance(payload, dict):
            raise
        if "hashtags" not in payload:
            payload["hashtags"] = _extract_hashtags_from_body(
                payload.get("body", "")
            )
    result = {
        "title": payload["title"],
        "image_text": payload["image_text"],
        "body": _strip_trailing_hashtags(payload["body"]),
        "hashtags": _normalize_hashtags(payload["hashtags"]),
    }
    image_plan = payload.get("image_plan")
    if isinstance(image_plan, dict):
        result["image_plan"] = _normalize_image_plan_payload(image_plan)
    return result


def _repair_json_payload_text(content: str) -> str:
    repaired = content.strip()
    repaired = re.sub(r'(?<=[\[,])\s*#"', ' "#', repaired)
    repaired = re.sub(
        r'([,\[]\s*)(#([^",\]\s]+))"',
        r'\1"\2"',
        repaired,
    )
    repaired = re.sub(
        r'([,\[]\s*)(#([^",\]\s]+))(?=\s*[,}\]])',
        r'\1"\2"',
        repaired,
    )
    return repaired


def _build_deepseek_hard_requirements(
    *,
    extra_context: str,
    runtime_context: str,
    scene: str = "",
) -> str:
    ai_tech_contract = _extract_ai_tech_runtime_contract(runtime_context)
    if ai_tech_contract is not None:
        return _build_ai_tech_evidence_hard_requirements(ai_tech_contract)
    psychology_learning_contract = _extract_psychology_learning_runtime_contract(
        runtime_context
    )
    if psychology_learning_contract is not None:
        return _build_psychology_learning_hard_requirements(
            psychology_learning_contract
        )

    requirements = [
        "只输出 JSON 对象，不要 Markdown 代码块，不要额外解释。",
        "默认采用 xhs_compact_native_v1：标题最多 22 个字符，优先 12-18 字；用具体场景、物件、关系、一句原话或领域对象做入口，不得写成泛标题，不要只写“日常”“实录”“干货分享”“小红书爆款”。",
        "正文用 2-4 个短拍，不要把正文硬拆成四段：先给现场和真人反应，再交一个能立刻拿走的领域细节；保存动作和接话口可以放在同一句自然的话里。",
        "正文必须有现场锚点和真人视角：用时间、物件、关系、一句原话、材料、路线或动作开场，像我/你/我们在今天、刚刚、今晚、路上、手边经历过；不要先总述，不要用“首先”“其次”“最后”“综上”“本文”“本篇”“作为AI”“建议大家”“从本质上”“核心逻辑是”“总体来说”；自然保存，把存、试、截图写进生活句子。",
        "正文要像朋友安利一个刚发现或刚试出来的东西，少解释多交付；只保留一个能立刻拿走的领域细节，例如一句话、一个判断、一个小动作、一个短清单或一段必要 prompt。",
        "不要把内部功能标签直接写进正文，例如“可复制疯话”“可收藏小结”“可收藏句型”“可保存单元”“评论交接”“可收藏看球清单”“可保存三步”，不管有没有冒号都不要露出；把它们改写成自然句子。",
    ]
    body_length_range = _infer_xhs_body_length_range(extra_context)
    if body_length_range is not None:
        requirements.append(f"正文长度控制在 {body_length_range} 字。")
    else:
        requirements.append("正文保持短帖节奏：只保留现场、一个领域细节和自然的接话口。")
    if _is_required_runnable_prompt_scene(scene=scene, extra_context=extra_context):
        requirements.append(
            "只有当题目明确要求完整可运行 prompt，且正文确实包含“任务：”“背景：”“输出格式：”“不要编造”四项时，"
            "才可扩展到 680 字；其他情况仍严格使用上面的短帖字数。"
        )
    if runtime_context.strip() and _extract_runtime_signal(runtime_context, label="主切口"):
        requirements.append("优先参考实时上下文里的主切口和场景张力，只借情绪结构，不复写原题。")
    for hashtag in ("#发疯文学", "#古诗词"):
        if hashtag in extra_context:
            requirements.append(f"hashtags 数组必须包含 '{hashtag}'。")
    if _is_fengkuang_context(extra_context):
        requirements.append(
            "必须包含一个具体职场物件或社交对象；必须包含评论区接龙/补充提示；"
            "必须包含可复制句或可保存模板；不得用心理疾病、治疗、医院、用药作为笑点。"
        )
    if _is_ordinary_modern_psychology_context(extra_context):
        requirements.append(
            "必须额外输出一个心理学文字轮播 image_plan：backend 固定为 local_social_screenshot，"
            "style 固定为 psychology_text_card，role 固定为 text_carousel，text_density 固定为 medium，"
            "max_text_units 固定为字符串 4，carousel_style 固定为 psychology_text_card_v1；"
            "同一主题按内容需要动态组织 1-18 张语义卡片，不得预设页数、按正文字数机械切页或引入第二次改写；图片可见字段不得含 emoji，超过 18 页则停止并要求缩短或拆帖。"
            "slides 必须按发布顺序给出，每页只能包含 slide_id、order、role、headline、body_lines；"
            "order 从 1 连续递增，第一页必须是 cover_hook，后续从具体场景、轻量机制、可保存工具、"
            "边界和评论入口中选择；图片文字不得含话题标签、URL、来源定位、诊断、治疗承诺、药物建议或提示词指令。"
        )
    elif _has_xhs_image_strategy(extra_context):
        requirements.append(
            "额外输出 image_plan 对象：backend 只能选 local_social_screenshot 或 "
            "provider_image；本地样式 style 只能选 wechat_chat、iphone_notes 或 note_card；"
            "role 必须说明图片承担的任务，如 cover_hook、save_tool、comment_prompt、"
            "evidence_or_scene；text_density 优先 low，max_text_units 写 1、2 或 3；"
            "cover_text_strategy 用一句话说明封面只放哪些短文字；"
            "reason 用一句话解释为什么这个图片形式适合当前主题。"
        )
    if _is_classic_poetry_context(scene="", extra_context=extra_context):
        requirements.append("正文必须围绕一句经典古诗词金句展开，并给出可保存的“这一句”读法；不要伪造作者、篇名或原句。")
    return " ".join(requirements)


def _extract_ai_tech_runtime_contract(runtime_context: str) -> dict[str, Any] | None:
    """Read the provenance-safe AI contract rendered by the planner, if any."""
    marker = "# AI Tech Evidence Contract"
    marker_index = runtime_context.find(marker)
    if marker_index < 0:
        return None
    json_start = runtime_context.find("{", marker_index + len(marker))
    if json_start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(runtime_context[json_start:])
        return parse_ai_tech_runtime_contract(value)
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError):
        return None


def _extract_psychology_learning_runtime_contract(
    runtime_context: str,
) -> dict[str, Any] | None:
    """Read the source-free lesson contract rendered by the planner, if any."""
    marker = "# Psychology Learning Series Contract"
    marker_index = runtime_context.find(marker)
    if marker_index < 0:
        return None
    json_start = runtime_context.find("{", marker_index + len(marker))
    if json_start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(runtime_context[json_start:])
        return parse_psychology_learning_runtime_contract(value)
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError):
        return None


def _build_ai_tech_evidence_hard_requirements(contract: Mapping[str, Any]) -> str:
    """Return the mode-specific model instruction for evidence-gated AI posts."""
    mode = str(contract.get("mode") or "")
    shared = [
        "只输出 JSON 对象，不要 Markdown 代码块，不要额外解释。",
        "这是证据受限的 AI 科技帖子：只可使用 AI Tech Evidence Contract 里的字段，不能补充任何未记录的功能、表现、来源、作者、标题、feed 或 URL。",
        "标题最多 22 个字符；正文用短行和清晰标签，像小红书信息卡，不写泛泛感受、营销口号、非投资建议、收藏/评论引导或通用 prompt 模板。",
        "禁止输出原始链接、域名、第一人称未记录体验和无证据的性能结论。",
    ]
    if mode == "news_brief":
        shared.append(
            "news_brief：正文必须是 3-5 个编号条目，每条保留对应标签和所有已批准事实；不写我/实测/体验，也不把热点当作事实。"
        )
    elif mode == "hands_on":
        shared.append(
            "hands_on：正文只写一条可复核实测记录，必须完整包含主题、产品、版本、测试日期、任务、输入、观察结果和局限；只能陈述合同中已记录的测试。"
        )
    elif mode == "fact_translation":
        shared.append(
            "fact_translation：正文必须完整保留主题和所有已批准事实，并明确谁该关注、谁可等待；不写我/实测/体验。"
        )
    else:
        # This function is only reached after strict domain parsing; retain a
        # fail-closed instruction if a future caller changes that boundary.
        shared.append("未知证据模式：不要生成正文。")
    return " ".join(shared)


def _build_psychology_learning_hard_requirements(
    contract: Mapping[str, Any],
) -> str:
    """Give hosted drafting the same closed-course constraints as the runtime."""
    return " ".join(
        [
            "只输出 JSON 对象，不要 Markdown 代码块，不要额外解释。",
            "这是受控心理学学习专题：只能使用 Psychology Learning Series Contract 中的课程合同字段，不能补充诊断、治疗承诺、药物建议、自测、来源、作者、URL 或新的心理学结论。",
            "正文必须逐字保留课程合同里的系列标记、概念名、学习目标、批准解释、适用场景、微练习、适用边界、专业帮助边界和评论提示；它们可以自然串成 2-4 个短拍，但不能删改或换成泛泛感受。",
            "标题最多 22 个字符，且不能出现课程概念名；正文严格 200-380 字，以具体生活瞬间开场，像小红书学习卡而不是讲义。",
            "hashtags 数组必须包含 '#心理学' 和 '#心理学学习'；不要输出来源标记、链接、域名或内部合同字段名。",
            "课程合同（仅供逐项执行，不要在输出中复述为 JSON）："
            + json.dumps(dict(contract), ensure_ascii=False),
        ]
    )


def _infer_xhs_body_length_range(extra_context: str) -> str | None:
    for length_range, markers in XHS_BODY_LENGTH_RULES:
        if any(marker in extra_context for marker in markers):
            return length_range
    return None


def _is_required_runnable_prompt_scene(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}".lower()
    return any(marker in combined for marker in ("prompt", "提示词", "ai 提问", "ai提问")) and any(
        marker in combined for marker in ("ai tech", "ai科技", "#ai资讯", "ai/科技")
    )


def _is_fengkuang_context(extra_context: str) -> bool:
    return any(
        marker in extra_context
        for marker in ("#发疯文学", "发疯文学", "Fengkuang Style", "fengkuang_daily_post")
    )


def _should_apply_runtime_trend(*, scene: str, runtime_context: str) -> bool:
    if not runtime_context.strip() or runtime_context.strip() == "无":
        return False
    return any(cue in scene for cue in ("老板", "领导", "群里", "需求", "下班", "工位"))


def _has_xhs_image_strategy(extra_context: str) -> bool:
    return any(
        marker in extra_context
        for marker in ("XHS Image Strategy", "xhs_image_strategy", "image_plan")
    )


def _build_deterministic_image_plan(
    *,
    scene: str,
    extra_context: str,
    runtime_context: str,
    draft: dict[str, Any],
) -> dict[str, str]:
    content_signal = "\n".join(
        [
            scene,
            _runtime_context_for_image_plan(runtime_context),
            str(draft.get("title", "")),
            str(draft.get("image_text", "")),
            str(draft.get("body", "")),
        ]
    )
    context_signal = f"{extra_context}\n{content_signal}"
    if (
        _looks_like_modern_psychology(context_signal)
        and _looks_like_note_screenshot(content_signal)
        and not _looks_like_explicit_chat_exchange(content_signal)
    ):
        return {
            "backend": "local_social_screenshot",
            "style": "iphone_notes",
            "role": "save_tool",
            "text_density": "low",
            "max_text_units": "3",
            "cover_text_strategy": "只放一个问题和三条可保存短句，不把正文搬进图里。",
            "reason": "心理内容以边界句、三栏或5分钟工具为主，低密度记事本截图更适合收藏。",
            "prompt_focus": "做成低密度工具卡，保留标题、封面语和最多三条短句。",
        }
    if _looks_like_world_cup(content_signal) and _looks_like_note_screenshot(
        content_signal
    ):
        return {
            "backend": "local_social_screenshot",
            "style": "iphone_notes",
            "role": "save_tool",
            "text_density": "low",
            "max_text_units": "3",
            "cover_text_strategy": "只放赛前问题和三条看球清单，不伪造比分或赛程截图。",
            "reason": "世界杯内容以赛前看点和看球清单为主，低密度记事本卡更适合收藏。",
            "prompt_focus": "做成低密度看球清单卡，突出赛前看点和最多三条观察点。",
        }
    if _looks_like_chat_screenshot(content_signal):
        return {
            "backend": "local_social_screenshot",
            "style": "wechat_chat",
            "role": "comment_prompt",
            "text_density": "low",
            "max_text_units": "2",
            "cover_text_strategy": "只保留一条触发消息和一句可复制回复。",
            "reason": "正文像聊天或群聊记录，本地微信聊天截图更贴近真实小红书首屏。",
            "prompt_focus": "把可复制回复做成聊天气泡，不放话题标签。",
        }
    if _looks_like_real_visual(content_signal):
        return {
            "backend": "provider_image",
            "style": "photo_reference",
            "role": "evidence_or_scene",
            "text_density": "low",
            "max_text_units": "1",
            "cover_text_strategy": "真实场景画面优先，只允许一个短标题感文字。",
            "reason": "主题依赖真实物件、空间或过程画面，外部图片模型更适合做生活化氛围参考。",
            "prompt_focus": "生成真实生活角落或材料过程感，避免伪装事实证据。",
        }
    if _looks_like_note_screenshot(content_signal):
        return {
            "backend": "local_social_screenshot",
            "style": "iphone_notes",
            "role": "save_tool",
            "text_density": "low",
            "max_text_units": "3",
            "cover_text_strategy": "只放一个问题和三条可保存短句，不把正文搬进图里。",
            "reason": "内容以清单、句型或可保存工具为主，本地记事本截图更适合截图收藏。",
            "prompt_focus": "做成低密度工具卡，保留标题、封面语和最多三条短句。",
        }
    return {
        "backend": "local_social_screenshot",
        "style": "note_card",
        "role": "cover_hook",
        "text_density": "low",
        "max_text_units": "2",
        "cover_text_strategy": "突出标题和一句封面语，正文只留一个短钩子。",
        "reason": "主题以文字表达和封面句为主，本地笔记卡片足够承载首屏信息。",
        "prompt_focus": "突出标题和封面语，画面干净留白。",
    }


def _runtime_context_for_image_plan(runtime_context: str) -> str:
    """Keep live topic signals but ignore anti-repetition memory when choosing image style."""
    blocks = re.split(r"\n{2,}", runtime_context.strip())
    return "\n\n".join(
        block
        for block in blocks
        if block.strip() and not block.lstrip().startswith("# Recent Account Memory")
    )


def _looks_like_chat_screenshot(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "领导：",
            "老板：",
            "同事：",
            "我：",
            "在吗",
            "群聊",
            "群里",
            "聊天",
            "消息",
            "草稿箱",
        )
    )


def _looks_like_explicit_chat_exchange(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "领导：",
            "老板：",
            "同事：",
            "我：",
            "群聊",
            "群里",
            "对话",
            "聊天气泡",
        )
    )


def _looks_like_modern_psychology(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "Modern Psychology",
            "现代心理困境观察",
            "Psychology Style",
            "Psychology Safety",
            "#心理学",
            "专业帮助",
        )
    )


def _is_ordinary_modern_psychology_context(text: str) -> bool:
    """Identify the playbook, not a cross-domain psychology hashtag mention."""
    return any(
        marker in text
        for marker in (
            "modern_psychology_post",
            "# Modern Psychology Planner",
            "# 现代心理困境观察 Planner",
        )
    )


def _looks_like_world_cup(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "世界杯主题",
            "World Cup Style",
            "XHS World Cup",
            "#世界杯",
            "看球清单",
        )
    )


def _looks_like_note_screenshot(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "三栏",
            "事实 / 猜测 / 下一步",
            "5分钟",
            "边界句",
            "清单",
            "模板",
            "可复制",
            "可收藏",
            "截图",
            "句型",
            "小纸条",
            "记下来",
        )
    )


def _looks_like_real_visual(text: str) -> bool:
    return any(
        cue in text
        for cue in (
            "书桌",
            "角落",
            "桌面",
            "窗台",
            "材料",
            "手作",
            "平铺",
            "前后",
            "变量",
            "空间",
            "路线",
        )
    )


def _extract_runtime_signal(runtime_context: str, *, label: str) -> str:
    pattern = re.compile(rf"{re.escape(label)}[:：]\s*`?([^`\n]+)`?")
    match = pattern.search(runtime_context)
    if match is None:
        return ""
    return match.group(1).strip()


def _extract_hashtags_from_body(body: str) -> list[str]:
    """Extract trailing hashtags from body text when the model embeds them inline."""
    return re.findall(r"#[^\s#]+", body)


def _strip_trailing_hashtags(body: str) -> str:
    """Remove trailing hashtag block from body text."""
    return re.sub(r"(\s*#[^\s#]+)+\s*$", "", body).rstrip()


def _normalize_hashtags(raw_hashtags: object) -> list[str]:
    if isinstance(raw_hashtags, str):
        hashtags = re.findall(r"#[^\s#]+", raw_hashtags)
        if not hashtags:
            hashtags = [
                part if part.startswith("#") else f"#{part}"
                for part in re.split(r"[\s,，]+", raw_hashtags)
                if part.strip()
            ]
        return hashtags

    if isinstance(raw_hashtags, list):
        return [str(tag).strip() for tag in raw_hashtags if str(tag).strip()]

    raise ValueError("hashtags must be a list or string")


def _normalize_image_plan_payload(raw_plan: dict[str, Any]) -> dict[str, Any]:
    if _is_psychology_carousel_plan(raw_plan):
        try:
            return normalize_psychology_carousel_plan(raw_plan)
        except (TypeError, ValueError):
            # The runtime carousel gate owns validation and reflector retries;
            # a slipped schema must not hard-crash the draft pass here.
            return raw_plan
    allowed_fields = (
        "backend",
        "style",
        "reason",
        "prompt_focus",
        "role",
        "text_density",
        "max_text_units",
        "cover_text_strategy",
    )
    return {
        field: str(raw_plan[field]).strip()
        for field in allowed_fields
        if raw_plan.get(field) is not None and str(raw_plan[field]).strip()
    }


def _is_psychology_carousel_plan(raw_plan: Mapping[str, Any]) -> bool:
    return (
        "slides" in raw_plan
        or "carousel_style" in raw_plan
        or raw_plan.get("style") == "psychology_text_card"
        or raw_plan.get("role") == "text_carousel"
    )
