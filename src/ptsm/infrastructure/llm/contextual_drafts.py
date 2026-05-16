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
    if any(keyword in scene for keyword in ("周日", "周一消息", "周一", "预焦虑")):
        body = (
            f"{scene}，人还在周日晚上，脑子已经把明天的消息提示音预演了三遍。\n"
            "这更像是低控制感在提醒你：未知任务越多，大脑越想提前排雷。"
            "不是你没用，也不是你太脆弱，只是身体比日程表更早进入了上班模式。\n"
            "可以先存一个 5分钟落地练习：写下明天最担心的1件事、能做的1个动作、暂时不用处理的1件事。"
            "先把问题从脑内循环挪到纸上。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你周日晚上最容易提前焦虑的瞬间，我们只收集例子，不给自己贴标签。"
        )
        title = "周日晚上怕周一消息，不是你没用"
        image_text = "脑子提前打卡上班"
        hashtags = ["#心理学", "#情绪管理", "#周一焦虑", "#低控制感", "#自我成长"]
    elif any(keyword in scene for keyword in ("想太多", "睡不着", "边界")):
        body = (
            f"{scene}，那句话表面很轻，脑子却像被按下了整晚重播。\n"
            "这可能和边界压力有关：当别人把你的感受轻轻带过，你的大脑会继续确认自己是不是被误解了。"
            "不是你太敏感，也不是你需要立刻证明什么。\n"
            "可以先存一句边界句模板：我知道你是好意，但这件事对我确实有影响，我需要一点时间整理。"
            "先把解释权拿回来一点。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一句你最常听到、但会反复想很久的话，我们只收集例子，不给自己贴标签。"
        )
        title = "被说想太多后睡不着，不是你矫情"
        image_text = "边界句先替你站稳"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#自我成长"]
    elif any(keyword in scene for keyword in ("临时消息", "拉回工位", "下班身份", "工位")):
        body = (
            f"{scene}，人已经切到生活模式，脑子却被一条消息重新拽回工位。\n"
            "这更像是边界压力和低控制感叠在一起：你不是不想休息，而是不确定自己能不能真的离线。"
            "不是你太敏感，也不是你不够敬业。\n"
            "可以先存一个消息草稿：我看到了，明早到工位后先确认优先级，再给你回复进度。"
            "它把立刻响应改成了有边界的下一步。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你最容易被工作消息拉回去的瞬间，我们只收集例子，不给自己贴标签。"
        )
        title = "人下班了，脑子又被消息拽回去"
        image_text = "脑子又被拉回工位"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#关系边界", "#低控制感"]
    elif any(keyword in scene for keyword in ("会议", "尴尬")):
        body = (
            f"{scene}，身体已经离开会议室，脑子还在给那句话反复加字幕。\n"
            "这更像是反刍思维在补安全感：大脑想确认自己有没有说错、有没有被误解。"
            "不是你太敏感，也不是你想太多。\n"
            "可以先存一个事实 / 猜测 / 下一步三栏：事实=对方原话；猜测=我脑补的评价；"
            "下一步=明天要不要用一句轻确认收尾。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你最容易在会议后反复回放的瞬间，我们只收集例子，不给自己贴标签。"
        )
        title = "会议那句话反复倒带，不是你太敏感"
        image_text = "把猜测放回事实栏"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#反刍思维"]
    elif any(keyword in scene for keyword in ("脑内", "白天的自己", "复盘会")):
        body = (
            f"{scene}，像在脑子里给自己开一场没有主持人的会。\n"
            "这更像是反刍思维把白天的低控制感延长到了晚上：你不是不想停，"
            "而是还没找到一个能让事情暂时归档的动作。\n"
            "可以先给脑内会议写一句散会通知：用事实 / 猜测 / 下一步三栏，只记录1个事实、"
            "1个需要确认的问题，剩下明天再看。"
            "先允许自己从复盘里退出来。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你下班后最常重新审判自己的瞬间，我们只收集例子，不给自己贴标签。"
        )
        title = "下班后脑内复盘会，可以先散会"
        image_text = "脑内会议先暂停"
        hashtags = ["#心理学", "#情绪管理", "#自我成长", "#反刍思维"]
    elif any(keyword in scene for keyword in ("普通回复", "收集大家", "常复盘")):
        body = (
            f"{scene}，一条普通回复发出去，脑子却开始自动检查标点、语气和对方会不会多想。\n"
            "这更像是反刍思维在追求确定答案：你想知道关系是不是还安全，"
            "但聊天本来就很少给满分判卷。\n"
            "可以先存一个 5分钟停止循环法：截图前先等5分钟，只问自己一个问题——"
            "我现在有新证据，还是只是在重复同一个担心？\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你最常反复复盘的普通回复，我们只收集例子，不给自己贴标签。"
        )
        title = "一条普通回复，为什么能想一整晚"
        image_text = "回复后脑子还在已读"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#反刍思维"]
    else:
        body = (
            f"{scene}，人已经走在路上，脑子却还在把那句话反复倒带。\n"
            "这更像是反刍思维在工作：大脑想重新找回控制感，所以一遍遍复盘细节。"
            "不是你太敏感，也不是你想太多，只是这件事还没被大脑归档。\n"
            "可以先存一个低风险小工具：事实 / 猜测 / 下一步三栏。"
            "事实=对方原话是什么；猜测=我脑补了什么；下一步=明天要不要确认一句。\n"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。"
            "评论区可以留一个你最容易反复复盘的瞬间，我们只收集例子，不给自己贴标签。"
        )
        title = "下班后还在复盘一句话，不是你太敏感"
        image_text = "脑子在替尴尬加班"
        hashtags = ["#心理学", "#情绪管理", "#自我成长", "#职场焦虑", "#反刍思维"]
    if feedback != "无" and "专业帮助" not in body:
        body += "\n如果这些感受持续影响生活，请优先寻求专业帮助。"
    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }
