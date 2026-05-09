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
        f"{scene}，这类停不下来的脑内回放，更像是反刍思维在工作。\n"
        "它不是简单的矫情，也不是一句想开点就能关掉。大脑会反复回到那个瞬间，"
        "往往是在试图重新获得控制感，只是这个过程会继续消耗你。\n"
        "可以先做一件很小的事：把脑子里反复出现的句子写下来，再在旁边标出"
        "“事实”和“猜测”。如果痛苦持续、影响工作学习生活，或出现自伤想法，"
        "请尽快寻求专业帮助。"
    )
    if feedback != "无" and "专业帮助" not in body:
        body += "\n如果这些感受持续影响生活，请优先寻求专业帮助。"
    return {
        "title": "下班后还在复盘那句话",
        "image_text": "脑子还没下班",
        "body": body,
        "hashtags": ["#心理学", "#情绪管理", "#自我成长", "#职场焦虑", "#反刍思维"],
    }
