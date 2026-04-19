from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import StringPromptValue
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_core.utils.json import parse_and_check_json_markdown

from ptsm.config.settings import Settings

FENGKUANG_SYSTEM_PROMPT = (
    "你是一个负责小红书发疯文学草稿的文案助手。"
    "请输出严格 JSON，对象字段必须是 title, image_text, body, hashtags。"
    "语气要自嘲、有共鸣、不过度攻击。"
)

SCENE_META_PATTERNS = (
    r"\bPTSM\b",
    r"自动发布(?:连通性)?验证",
    r"连通性验证",
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
            "任务: 生成一条用于小红书 dry-run 的发疯文学文案。"
        )
        self._chain = prompt | RunnableLambda(self._render)

    def generate(
        self,
        *,
        scene: str,
        reflection_feedback: str | None = None,
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        scene = _normalize_scene(scene)
        return self._chain.invoke(
            {
                "scene": scene,
                "reflection_feedback": reflection_feedback or "无",
            }
        )

    def _render(self, prompt_value: StringPromptValue) -> dict[str, Any]:
        prompt_text = prompt_value.to_string()
        scene = _normalize_scene(_extract_field(prompt_text, prefix="场景: "))
        feedback = _extract_field(prompt_text, prefix="修正意见: ")
        return _build_deterministic_draft(scene=scene, feedback=feedback)


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
        planner_prompt: str | None = None,
        skill_contents: list[str] | None = None,
    ) -> dict[str, Any]:
        scene = _normalize_scene(scene)
        extra_context_chunks = [
            planner_prompt or "",
            reflection_feedback or "",
            *(skill_contents or []),
        ]
        extra_context = "\n\n".join(chunk for chunk in extra_context_chunks if chunk)
        hard_requirements = _build_deepseek_hard_requirements(extra_context)
        user_prompt = (
            f"场景：{scene}\n"
            f"修正意见：{reflection_feedback or '无'}\n"
            f"补充约束：{extra_context or '无'}\n"
            f"硬性约束：{hard_requirements}\n"
            "请生成一条小红书发疯文学文案，并返回严格 JSON。"
        )
        response = self._llm.invoke(
            [
                SystemMessage(content=FENGKUANG_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        return _parse_json_payload(response.content)


def build_drafting_backend(
    settings: Settings,
    *,
    chat_model_cls: type[Any] | None = None,
) -> DeterministicDraftBackend | DeepSeekDraftBackend:
    """Build drafting backend from settings with deterministic fallback."""
    provider = settings.default_model_provider.lower().strip()

    if provider == "deepseek" and settings.deepseek_api_key:
        chat_model_cls = chat_model_cls or _load_chat_deepseek()
        llm = chat_model_cls(
            model=settings.deepseek_model or settings.default_model,
            api_key=settings.deepseek_api_key,
            api_base=settings.deepseek_base_url,
            temperature=settings.deepseek_temperature,
            max_tokens=settings.deepseek_max_tokens,
        )
        return DeepSeekDraftBackend(llm)

    return DeterministicDraftBackend()


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


def _normalize_scene(scene: str) -> str:
    cleaned = scene.strip()
    for pattern in SCENE_META_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[，,。.!！?？；;、]+", "，", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" ，")
    return cleaned or scene.strip()


def _build_deterministic_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    if _is_weekend_rest_scene(scene):
        title = "周六躺平回血实录"
        image_text = "今天先躺"
        body = (
            f"周六本来想靠{scene}给自己回口血，结果人是躺下了，脑子还在加班续命。\n"
            "床和沙发都同意我休息了，只有打工人的后劲还在体内偷偷加钟。"
        )
        hashtags = ["#发疯文学", "#周末躺平日记", "#社畜回血现场"]
    elif _is_commute_scene(scene):
        title = "打工人地铁生存实录"
        image_text = "今日已疯"
        body = (
            f"今日份发疯现场：{scene}，我差点当场把灵魂寄存给下一站。\n"
            "打工和通勤联手把人折叠成了地铁门缝里的表情包。"
        )
        hashtags = ["#发疯文学", "#打工人日常", "#通勤崩溃实录"]
    elif _is_meeting_scene(scene):
        title = "会议连环暴击实录"
        image_text = "脑子已掉线"
        body = (
            f"今日份崩溃瞬间：{scene}，我感觉自己像被会议室循环播放到只剩下点头功能。\n"
            "嘴上在复盘，灵魂已经先一步把工牌摘了。"
        )
        hashtags = ["#发疯文学", "#会议崩溃实录", "#打工人日常"]
    else:
        title = "社畜崩溃边缘实录"
        image_text = "先别找我"
        body = (
            f"今日份发疯现场：{scene}。\n"
            "人看起来还坐得住，情绪其实已经提前一步申请下班了。"
        )
        hashtags = ["#发疯文学", "#社畜日常", "#打工人情绪实录"]

    if feedback != "无":
        body += "\n不过换个角度想，能把这口气慢慢喘匀、还能给自己留点电，也算今天没白扛。"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }


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


def _parse_json_payload(content: str) -> dict[str, Any]:
    cleaned = _repair_json_payload_text(content.strip())
    payload = parse_and_check_json_markdown(
        cleaned,
        ["title", "image_text", "body", "hashtags"],
    )
    return {
        "title": payload["title"],
        "image_text": payload["image_text"],
        "body": payload["body"],
        "hashtags": _normalize_hashtags(payload["hashtags"]),
    }


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


def _build_deepseek_hard_requirements(extra_context: str) -> str:
    requirements = [
        "只输出 JSON 对象，不要 Markdown 代码块，不要额外解释。",
    ]
    if "#发疯文学" in extra_context:
        requirements.append("hashtags 数组必须包含 '#发疯文学'。")
    if "也算" in extra_context:
        requirements.append("正文必须包含“也算”，并把它放在结尾的轻量正向收束句里。")
    return " ".join(requirements)


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
