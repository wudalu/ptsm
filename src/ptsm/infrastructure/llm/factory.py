from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompt_values import StringPromptValue
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda

from ptsm.config.settings import Settings

FENGKUANG_SYSTEM_PROMPT = (
    "你是一个负责小红书发疯文学草稿的文案助手。"
    "请输出严格 JSON，对象字段必须是 title, image_text, body, hashtags。"
    "语气要自嘲、有共鸣、不过度攻击。"
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
        return self._chain.invoke(
            {
                "scene": scene,
                "reflection_feedback": reflection_feedback or "无",
            }
        )

    def _render(self, prompt_value: StringPromptValue) -> dict[str, Any]:
        prompt_text = prompt_value.to_string()
        scene = _extract_field(prompt_text, prefix="场景: ")
        feedback = _extract_field(prompt_text, prefix="修正意见: ")
        body = (
            f"今日份发疯现场：{scene}，我差点当场把灵魂寄存给下一站。\n"
            "打工和通勤联手把人折叠成了地铁门缝里的表情包。"
        )
        if feedback != "无":
            body += "\n不过换个角度想，能平安挤出来、还能喝到冰美式，也算今天没白活。"

        return {
            "title": "打工人地铁生存实录",
            "image_text": "今日已疯",
            "body": body,
            "hashtags": ["#发疯文学", "#打工人日常", "#通勤崩溃实录"],
        }


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
        extra_context = "\n\n".join(
            chunk for chunk in [planner_prompt or "", *(skill_contents or [])] if chunk
        )
        user_prompt = (
            f"场景：{scene}\n"
            f"修正意见：{reflection_feedback or '无'}\n"
            f"补充约束：{extra_context or '无'}\n"
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


def _parse_json_payload(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()

    payload = json.loads(cleaned)
    return {
        "title": payload["title"],
        "image_text": payload["image_text"],
        "body": payload["body"],
        "hashtags": list(payload["hashtags"]),
    }
