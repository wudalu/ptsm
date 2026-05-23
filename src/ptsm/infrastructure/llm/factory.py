from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import StringPromptValue
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.exceptions import OutputParserException
from langchain_core.utils.json import parse_and_check_json_markdown, parse_json_markdown

from ptsm.config.settings import Settings
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
        hard_requirements = _build_deepseek_hard_requirements(
            extra_context=extra_context,
            runtime_context=runtime_context,
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

    if _is_sushi_poetry_context(scene=scene, extra_context=extra_context):
        title = "读苏轼时突然读懂了今天"
        image_text = "把风雨读慢一点"
        body = (
            f"{scene}。\n"
            "再回头看苏轼写风雨和行路，才发现很多狼狈不是非要立刻赢过去，"
            "而是可以先被看见、被安放。"
        )
        hashtags = ["#苏轼", "#诗词赏析", "#小红书读书笔记"]
        if feedback != "无" and "苏轼" not in body:
            body += "\n顺着苏轼再读一遍，情绪也会慢一点落下来。"
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
            "可复制疯话：谢谢关心，但我的工牌现在只想喝下班风。"
            "评论区接一句你遇到过的丝瓜汤式职场回复，我先替大家写进群聊草稿。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#职场情绪实录"]
    elif _is_weekend_rest_scene(scene):
        title = "周六躺平回血实录"
        image_text = "今天先躺"
        body = (
            f"谁懂，周六本来想靠{scene}给自己回口血，结果人是躺下了，脑子还在加班续命。\n"
            "今日可复制疯话：床批了我的假，工位别越权。"
            "评论区接一句你最想贴在床头的周末保命宣言。"
        )
        hashtags = ["#发疯文学", "#周末躺平日记", "#社畜回血现场"]
    elif _is_commute_scene(scene):
        title = "地铁门关上那秒我把灵魂留站台"
        image_text = "灵魂请下一站下车"
        body = (
            f"今日份发疯现场：{scene}，我差点当场把灵魂寄存给下一站。\n"
            "可复制通勤疯话：人在车厢，心已请假。"
            "评论区接一句你最想写在闸机口的打工人暗号。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#通勤崩溃实录"]
    elif _is_meeting_scene(scene):
        title = "周报翻开那秒脑子先离席"
        image_text = "点头模式已开启"
        body = (
            f"今日份崩溃瞬间：{scene}，我感觉自己像被会议室循环播放到只剩下点头功能。\n"
            "我想把这句写在周报封面：收到，但大脑正在加载失败。"
            "评论区接一句你开会时最想打在共享屏上的疯话。"
        )
        hashtags = ["#发疯文学", "#会议崩溃实录", "#打工人日常"]
    elif _is_after_hours_leader_scene(scene):
        title = "领导18:57发「在吗」那一秒"
        image_text = "我的工牌先替我发疯"
        body = (
            f"{scene}，群聊弹出来那一秒，我的工牌已经在桌上替我原地离职。\n"
            "可复制疯话：收到，但灵魂已下班。"
            "评论区接一句你最想写在工牌背面的疯话，明天早会前我先替大家默背。"
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
            "嘴上说着收到，心里已经在工牌背面写好：收到，但灵魂已下班。"
            "评论区接一句你最想发在群里但不敢发的下班疯话。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#职场情绪实录"]
    else:
        title = "今天这口气先写在工牌背面"
        image_text = "收到，但灵魂已下班"
        body = (
            f"今日份发疯现场：{scene}。\n"
            "人看起来还坐得住，情绪其实已经提前一步申请下班了。"
            "可复制疯话：收到，但工牌只负责出勤，不负责续命。"
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
        return "会议室把我循环播放到没电", "点头模式已开启"
    if _is_weekend_rest_scene(scene):
        return "周末回血失败现场", "躺着也在耗电"
    if _is_after_hours_leader_scene(scene):
        return "18:57那句在吗把工牌点燃了", "我的工牌先替我发疯"
    return "今天换个地方发疯", image_text


def _is_sushi_poetry_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in ("苏轼", "诗词赏析", "#苏轼", "定风波", "赤壁赋", "水调歌头")
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


def _build_deepseek_hard_requirements(*, extra_context: str, runtime_context: str) -> str:
    requirements = [
        "只输出 JSON 对象，不要 Markdown 代码块，不要额外解释。",
    ]
    if runtime_context.strip() and _extract_runtime_signal(runtime_context, label="主切口"):
        requirements.append("优先参考实时上下文里的主切口和场景张力，只借情绪结构，不复写原题。")
    for hashtag in ("#发疯文学", "#苏轼"):
        if hashtag in extra_context:
            requirements.append(f"hashtags 数组必须包含 '{hashtag}'。")
    if _is_fengkuang_context(extra_context):
        requirements.append(
            "必须包含一个具体职场物件或社交对象；必须包含评论区接龙/补充提示；"
            "必须包含可复制句或可保存模板；不得用心理疾病、治疗、医院、用药作为笑点。"
        )
    if _has_xhs_image_strategy(extra_context):
        requirements.append(
            "额外输出 image_plan 对象：backend 只能选 local_social_screenshot 或 "
            "provider_image；本地样式 style 只能选 wechat_chat、iphone_notes 或 note_card；"
            "role 必须说明图片承担的任务，如 cover_hook、save_tool、comment_prompt、"
            "evidence_or_scene；text_density 优先 low，max_text_units 写 1、2 或 3；"
            "cover_text_strategy 用一句话说明封面只放哪些短文字；"
            "reason 用一句话解释为什么这个图片形式适合当前主题。"
        )
    if "苏轼" in extra_context:
        requirements.append("正文必须包含“苏轼”。")
    return " ".join(requirements)


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
    if _looks_like_world_cup(context_signal) and _looks_like_note_screenshot(
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


def _normalize_image_plan_payload(raw_plan: dict[str, Any]) -> dict[str, str]:
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
