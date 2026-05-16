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
    if _is_wuxia_context(scene=scene, extra_context=extra_context):
        return _build_wuxia_draft(scene=scene, feedback=feedback)
    if _is_modern_psychology_context(scene=scene, extra_context=extra_context):
        return _build_modern_psychology_draft(scene=scene, feedback=feedback)
    return None


def _is_wuxia_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in (
            "武侠人物评述",
            "Wuxia Commentary Style",
            "XHS Wuxia Hashtagging",
            "#金庸",
            "#古龙",
            "令狐冲",
            "笑傲江湖",
        )
    )


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


def _build_wuxia_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，最适合拿令狐冲来讲。金庸在《笑傲江湖》里写他，不是写一个简单的浪子，"
        "而是写一个明明有能力进入体系、却始终无法把自己交给体系的人。\n"
        "原文里那句“行事但求无愧于心”，其实就是令狐冲的底层算法。他可以敬重师门，"
        "也可以珍惜朋友，但一旦规则要求他把人的鲜活感磨成标准答案，他就开始本能地后退。"
        "这也是为什么他在华山派里显得“不够上进”，在江湖里却反而更像一个完整的人。\n"
        "放到今天看，令狐冲像很多不愿被体制化的职场人：不是不想负责，也不是没有专业能力，"
        "而是害怕自己有一天只剩流程、汇报和绩效表，连喜欢什么、讨厌什么都要先看组织脸色。"
        "他真正珍贵的地方，不是潇洒喝酒，而是能在关系、人情和权力夹缝里，还保留一点不被驯化的判断。\n"
        "所以令狐冲的自由不是逃班式自由，而是一种更难的自由：知道代价，也知道自己不适合成为某种标准答案。"
        "这类人未必适合所有单位，但他们提醒我们，成长不只有被规训成“正确的人”这一条路。"
    )
    if feedback != "无" and "#金庸" not in body:
        body += "\n重读金庸时，这个角度会更清楚。"
    return {
        "title": "令狐冲不是摆烂，他是不想被体制化",
        "image_text": "自由不是不负责",
        "body": body,
        "hashtags": ["#金庸", "#令狐冲", "#笑傲江湖", "#武侠", "#读书笔记"],
    }


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
