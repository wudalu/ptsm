from __future__ import annotations

from typing import Any


def build_contextual_deterministic_draft(
    *,
    scene: str,
    feedback: str,
    extra_context: str,
    runtime_context: str,
) -> dict[str, Any] | None:
    """Return a domain-specific deterministic draft when context is explicit."""
    if _is_modern_psychology_context(scene=scene, extra_context=extra_context):
        return _build_modern_psychology_draft(scene=scene, feedback=feedback)
    return None


def _is_modern_psychology_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in (
            "现代心理困境观察",
            "Psychology Safety",
            "Psychology Style",
            "#心理学",
            "反刍思维",
            "专业帮助",
        )
    )


def _build_modern_psychology_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，人已经走在路上，脑子却还在把那句话反复倒带。\n"
        "这更像是反刍思维在工作：大脑想重新找回控制感，所以一遍遍复盘细节。"
        "不是你太敏感，也不是你想太多，只是这件事还没被大脑归档。\n"
        "可以先存一个低风险小工具：事实 / 猜测 / 下一步三栏。"
        "事实=对方原话是什么；猜测=我脑补了什么；下一步=明天要不要确认一句。\n"
        "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
        "评论区可以留一个你最容易反复复盘的瞬间，我们只收集例子，不给自己贴标签。"
    )
    if feedback != "无" and "专业帮助" not in body:
        body += "\n如果这些感受持续影响生活，请优先寻求专业帮助。"
    return {
        "title": "下班后还在复盘一句话，不是你太敏感",
        "image_text": "脑子在替尴尬加班",
        "body": body,
        "hashtags": ["#心理学", "#情绪管理", "#自我成长", "#职场焦虑", "#反刍思维"],
    }
