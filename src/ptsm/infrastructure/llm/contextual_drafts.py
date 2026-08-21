from __future__ import annotations

import json
import re
from typing import Any, Mapping

from pydantic import ValidationError

from ptsm.domain.ai_tech_content import parse_ai_tech_runtime_contract
from ptsm.domain.psychology_carousel import (
    normalize_psychology_carousel_plan,
    psychology_carousel_inner_pages_fingerprint,
)
from ptsm.domain.psychology_learning import (
    parse_psychology_learning_runtime_contract,
    render_psychology_learning_draft,
)


_RECENT_PSYCHOLOGY_CAROUSEL_FINGERPRINT_HEADER = (
    "# Recent Psychology Carousel Fingerprints"
)
_RECENT_PSYCHOLOGY_CAROUSEL_FINGERPRINT_PATTERN = re.compile(
    r"(?m)^- inner_fingerprint: ([0-9a-f]{64})$"
)
# Keep the first sequence byte-for-byte stable.  A 12-fingerprint memory window
# always leaves one of these 13 renderable inner-card variants available.
_MODERN_PSYCHOLOGY_SAVE_TOOL_HEADLINE_VARIANTS = (
    "先把这一刻写清",
    "先给今晚留一小步",
    "先让这一刻停一下",
    "先把问题缩小一点",
    "先停十秒再决定",
    "先换一个更小的动作",
    "先把答案留到明天",
    "先给自己一个暂停键",
    "先从最容易的一步开始",
    "先把这一页存下来",
    "先让注意力回到眼前",
    "先少做一点也可以",
)


def build_contextual_deterministic_draft(
    *,
    scene: str,
    feedback: str,
    extra_context: str,
    runtime_context: str,
) -> dict[str, Any] | None:
    """Return a domain-specific deterministic draft when context is explicit."""
    if _is_reddit_curation_context(scene=scene, extra_context=extra_context):
        return _build_reddit_curation_draft(
            scene=scene,
            feedback=feedback,
            runtime_context=runtime_context,
        )
    if _is_classic_poetry_context(scene=scene, extra_context=extra_context):
        return _build_classic_poetry_draft(scene=scene, feedback=feedback)
    if _is_wuxia_context(scene=scene, extra_context=extra_context):
        return _build_wuxia_draft(scene=scene, feedback=feedback)
    if _is_world_cup_context(scene=scene, extra_context=extra_context):
        return _build_world_cup_draft(scene=scene, feedback=feedback)
    if _is_human_enrichment_context(scene=scene, extra_context=extra_context):
        return _build_human_enrichment_draft(
            scene=scene,
            feedback=feedback,
            runtime_context=runtime_context,
        )
    if _is_ai_tech_context(scene=scene, extra_context=extra_context):
        return _build_ai_tech_draft(runtime_context=runtime_context)
    if _is_psychology_learning_context(runtime_context=runtime_context):
        return _build_psychology_learning_draft(runtime_context=runtime_context)
    if _is_daily_english_context(scene=scene, extra_context=extra_context):
        return _build_daily_english_draft(scene=scene, feedback=feedback)
    if _is_modern_psychology_context(scene=scene, extra_context=extra_context):
        return _build_modern_psychology_draft(
            scene=scene,
            feedback=feedback,
            runtime_context=runtime_context,
        )
    return None


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
            "Sushi Poetry Style",
            "Su Shi Poetry Style",
            "XHS Poetry Hashtagging",
            "#苏轼",
            "定风波",
            "赤壁赋",
            "水调歌头",
        )
    )


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


def _is_world_cup_context(*, scene: str, extra_context: str) -> bool:
    has_playbook_context = any(
        keyword in extra_context
        for keyword in (
            "世界杯主题",
            "World Cup Style",
            "XHS World Cup Hashtagging",
            "world_cup_daily_post",
            "world_cup_style",
            "#世界杯",
        )
    )
    if has_playbook_context:
        return True
    return any(
        keyword in scene
        for keyword in (
            "世界杯",
            "决赛",
            "小组赛",
            "淘汰赛",
            "看球",
        )
    )


def _is_ai_tech_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in (
            "AI科技资讯",
            "AI Tech Style",
            "AI Tech Hashtagging",
            "#AI资讯",
            "OpenAI",
            "多模态",
        )
    )


def _is_daily_english_context(*, scene: str, extra_context: str) -> bool:
    has_playbook_context = any(
        keyword in extra_context
        for keyword in (
            "Daily English Style",
            "Daily English Hashtagging",
            "daily_english_post",
            "#每日英语",
        )
    )
    if has_playbook_context:
        return True
    return any(
        keyword in scene
        for keyword in (
            "每日英语学习",
            "英语表达",
            "英文表达",
            "音标",
        )
    )


def _is_human_enrichment_context(*, scene: str, extra_context: str) -> bool:
    strong_context = any(
        keyword in extra_context
        for keyword in (
            "Human Enrichment Style",
            "human_enrichment_style",
            "human_enrichment_daily_post",
            "#人类丰容计划",
            "#家的丰容计划",
        )
    )
    if strong_context:
        return True
    return any(
        keyword in scene
        for keyword in (
            "人类丰容实验",
            "人类丰容",
            "日常变量",
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


def _is_psychology_learning_context(*, runtime_context: str) -> bool:
    return "# Psychology Learning Series Contract" in runtime_context


def _is_reddit_curation_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in (
            "Reddit英文讨论转译",
            "Reddit Curation Style",
            "XHS Reddit Curation Hashtagging",
            "reddit_curation_daily_post",
            "reddit_discussion_scan",
            "#Reddit",
        )
    )


def _build_human_enrichment_draft(
    *,
    scene: str,
    feedback: str,
    runtime_context: str,
) -> dict[str, Any]:
    hooks = _extract_pattern_hooks(runtime_context)
    if any(keyword in scene for keyword in ("适我主义", "新独居", "一个人住", "独居")):
        title = "床头这一角，先别再亏待我"
        image_text = "一个人住也能先丰容一厘米"
        body = (
            f"{scene}。我不想把新独居写成精致样板间，先让床头角落按自己的节奏舒服一点。\n"
            "我会按十分钟三步清单走：把旧材料平铺出来；只选一个今晚愿意碰的颜色或小物；"
            "做完放在醒来第一眼能看见的位置。\n"
            "这不是要把生活改得多漂亮，而是给自己留一个手作心流的小入口。"
            "评论区交一个你想按适我主义先丰容的角落。"
        )
    elif any(keyword in scene for keyword in ("旧毛线", "毛线", "拼豆", "钩织", "材料")):
        title = (
            "这堆旧材料原来这么适合丰容"
            if "process_or_tutorial" in hooks
            else "旧材料别扔，先救这一角"
        )
        image_text = "旧材料也能变新鲜"
        body = (
            f"{scene}。我不急着买新东西，先把手边材料当成一个小变量。\n"
            "我会按十分钟三步清单走：把旧毛线、拼豆或零散材料平铺出来；只选一个颜色或形状开头；"
            "做完先放在每天能看见的位置。\n"
            "重点不是作品多完整，而是让材料从闲置变成今天可以碰一下的生活入口。"
            "评论区交一个你家最想重新拿出来的旧材料。"
        )
    elif any(keyword in scene for keyword in ("路线", "散步", "Colorwalk", "通勤包", "走路", "路上")):
        title = (
            "突然意识到路线也需要丰容"
            if "sudden_realization" in hooks
            else "常走那条路，突然不无聊了"
        )
        image_text = "换一条路也算丰容"
        body = (
            f"{scene}。今天不把自己塞进新的计划，只给这条熟路加一个低成本变量。\n"
            "我会按十分钟三步清单走：出门前选一个颜色；路上只找三处同色小细节；"
            "回家后记下最想多看一眼的位置。\n"
            "它不会立刻改变生活，但能让一段自动驾驶的路重新有一点感官存在。"
            "评论区交一条你想先丰容的日常路线。"
        )
    elif any(keyword in scene for keyword in ("书桌", "快递盒", "手作", "工位", "桌")):
        title = (
            "突然意识到书桌也需要丰容"
            if "sudden_realization" in hooks
            else "书桌乱到我先救这一角"
        )
        image_text = "今天先丰容这个角落"
        body = (
            f"{scene}。我不打算把生活一次性改造完，只先给这个角落加一个小变量。\n"
            "我会按十分钟三步清单走：先清出一个手掌大的空位；把最常用的杯子和便签放到伸手可及；"
            "给今晚的十分钟手作留一个固定位置。\n"
            "这不是要立刻变精致，只是把日复一日里的一厘米还给自己。"
            "评论区交一个你想先丰容的角落，我来收集零成本版本。"
        )
    elif any(keyword in scene for keyword in ("窗台", "玄关", "床头", "角落")):
        title = "这个角落，先别再当仓库"
        image_text = "给生活留一点新鲜感"
        body = (
            f"{scene}。今天不做大改造，只给它加一个看得见的小变量。\n"
            "我会先存这三步：拿走一个最碍眼的杂物；补一个能每天看见的颜色；"
            "把明天会用到的小东西提前放好。\n"
            "变化很小，但它会提醒我这里不是临时堆放区，也是生活的一部分。"
            "评论区交一个你家最想先微调的角落。"
        )
    else:
        title = "日子太顺手，就先救一厘米"
        image_text = "低成本丰容一下"
        body = (
            f"{scene}。我想先做一个很小的人类丰容实验，不靠大购物，也不假装人生马上焕新。\n"
            "我会先从手边一件旧物开始，按三步走：选一个每天都会经过的位置；加一个不用花钱的小变量；"
            "晚上回来只观察它有没有让自己多停留十秒。\n"
            "如果有，就把它留下；如果没有，明天换一个变量。"
            "评论区交一个你会先试的日常变量。"
        )

    if feedback != "无" and "今天先试" not in body:
        body += "\n今天先试一个最小版本，别把丰容变成新的待办压力。"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": ["#人类丰容计划", "#家的丰容计划", "#低成本生活", "#小红书生活"],
    }


def _build_reddit_curation_draft(
    *,
    scene: str,
    feedback: str,
    runtime_context: str,
) -> dict[str, Any]:
    selected = _extract_selected_reddit_discussion(runtime_context)
    selected_haystack = (
        f"{selected.get('title', '')} {selected.get('fit', '')} {selected.get('excerpt', '')}"
        if selected
        else ""
    ).lower()
    if selected and any(
        keyword in selected_haystack
        for keyword in ("ai", "chatgpt", "agent", "workflow", "coder", "programmer", "claude")
    ):
        title = "AI用顺了以后，人反而更累了"
        image_text = "不是被AI替代，是开始给AI兜底"
        body = (
            "刚把一份 AI 输出贴进文档，我又停下来逐行看了一遍。工具第一次帮我省半小时很爽，"
            "真正累的是后面还得拆任务、查漏、给它兜底。以前我也把它当万能搭子，后来才知道检查不能外包。\n"
            "它更像一个需要照看的 AI保姆，不是替你负责的人。我会把这条先收藏成三句：重复步骤交给 AI；"
            "关键判断留给人；涉及来源、隐私和责任的结果再复核。\n"
            "你现在是在用 AI，还是在照看 AI？评论区说说。"
        )
        hashtags = ["#热点观察", "#AI工具", "#人工智能", "#效率工具", "#职场成长"]
    elif selected:
        title = "消息一响，人就被重新拽回任务里"
        image_text = "真正累的是随时都要回应"
        body = (
            "手机刚扣下，消息又亮了。我还没回到沙发，脑子已经开始算：急不急、对方会不会等、"
            "我不回是不是显得不负责。人没加班，注意力已经先加班了，连吃饭都怕漏掉它；"
            "休息像被借走一半，回朋友一句话也要先算会不会打断谁。\n"
            "真正耗电的不是提醒声，是每次都要重新做选择。我会先收藏这个小顺序：不是现在必须处理的，"
            "就给一个明确回复时间，再留半小时不被打断。\n"
            "你最想先关掉哪一种消息提醒？评论区告诉我。"
        )
        hashtags = ["#热点观察", "#心理学", "#情绪管理", "#注意力管理", "#效率工具"]
    elif any(keyword in scene.lower() for keyword in ("burnout", "心理", "焦虑", "通知", "attention")):
        title = "消息压力最累的不是消息本身"
        image_text = "随时回应才是隐形加班"
        body = (
            "今天刚把手机翻扣，工作群又亮了一下。我人还在休息，脑子已经被拽回去判断，先喘口气："
            "这条消息急不急、对方会不会等、我不回会不会显得不负责，连倒杯水都怕错过它，休息像被借走一半。\n"
            "这就是低控制感最磨人的地方。我会先收藏三个问题：要不要现在处理；能不能给明确回复时间；"
            "提醒能不能先关半小时。不是逃避，是把注意力边界拿回来一点。\n"
            "你最想给哪一种消息设回复边界？评论区说说。"
        )
        hashtags = ["#热点观察", "#心理学", "#情绪管理", "#注意力管理", "#效率工具"]
    else:
        title = "别急着追AI代理，先看这条边界"
        image_text = "别急着追工具，先看边界"
        body = (
            "今天看着 AI agent 把小任务一件件接走，我反而先停了一下：它能写邮件、整理资料、"
            "排计划，但工具越多，越要知道哪些事不该交出去。\n"
            "我会收藏三个检查点：能不能省掉重复整理；能不能让我核对来源；出错时能不能及时停下来。"
            "账号、隐私和关键决策只小范围试，把它当助手，不当替你负责的人；我会先把它当试用，不当承诺。\n"
            "你最不敢交给 AI 的任务是什么？评论区说说吧。"
        )
        hashtags = ["#热点观察", "#AI工具", "#人工智能", "#效率工具", "#职场成长"]

    if feedback != "无":
        body = f"把这条内容收紧成更像中文读者会保存的表达：{body}"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }


def _build_modern_psychology_carousel_plan(
    *,
    scene: str,
    title: str,
    image_text: str,
    recent_inner_fingerprints: set[str] | None = None,
) -> dict[str, Any]:
    """Build semantic pages beside the deterministic draft, without another model call."""
    lane = _modern_psychology_lane(scene)
    if lane == "relationship_uncertainty":
        scene_headline = "忽冷忽热，最磨人的是悬着"
        scene_lines = ["想问清楚，又怕自己显得太需要答案"]
        mechanism_headline = "空白会被补成关系剧情"
        mechanism_lines = ["关系不确定感让每个间隔都像信号"]
        tool_headline = "先写事实、信号、需要"
        tool_lines = ["事实：发生了什么", "信号：哪些变化让我在意", "需要：我要不要问清楚"]
        comment_headline = "你会问清楚，还是先观察？"
        comment_lines = ["A.低压问清楚", "B.先观察真实信号"]
    elif lane == "romantic_waiting":
        scene_headline = "手机只是安静了一会儿"
        scene_lines = ["脑子却开始替沉默写结局"]
        mechanism_headline = "空白越多，剧情越满"
        mechanism_lines = ["关系不确定感会让人先补最坏答案"]
        tool_headline = "先写事实、脑补、需要"
        tool_lines = ["事实：对方暂时没回", "脑补：我们要分开", "需要：一次清楚确认"]
        comment_headline = "没回消息时，你是哪一派？"
        comment_lines = ["A.立刻问答案", "B.忍住却反复想"]
    elif lane == "meeting_replay":
        scene_headline = "人走了，会议还没散"
        scene_lines = ["一句话在脑子里反复加字幕"]
        mechanism_headline = "回放不等于复盘"
        mechanism_lines = ["反刍会重复检查，却不一定带来新信息"]
        tool_headline = "先分三栏"
        tool_lines = ["事实：对方原话", "猜测：我补出的评价", "下一步：是否需要确认"]
        comment_headline = "会后回放时，你是哪一派？"
        comment_lines = ["A.写完小作文删掉", "B.发完又重看十遍"]
    elif lane == "digital_overload":
        scene_headline = "屏幕还亮着，人已经很累"
        scene_lines = ["手指继续往下滑，感受却被往后推"]
        mechanism_headline = "信息过载也会拖延感受"
        mechanism_lines = ["刺激越密，大脑越难收到结束信号"]
        tool_headline = "先做5分钟下线"
        tool_lines = ["把屏幕扣下", "写下我在躲什么", "只做一个身体需要"]
        comment_headline = "你睡前停在哪一种屏幕？"
        comment_lines = ["A.短视频", "B.聊天记录"]
    elif lane == "social_depletion":
        scene_headline = "社交电量见底了"
        scene_lines = ["怕的不是不去，是怕别人觉得我扫兴"]
        mechanism_headline = "疲惫和边界压力叠在一起"
        mechanism_lines = ["需要休息，也想把关系放稳"]
        tool_headline = "先存取消局三句"
        tool_lines = ["承认原来的约定", "说明今天的状态", "给一个下次选项"]
        comment_headline = "社交没电时，你是哪一派？"
        comment_lines = ["A.硬着头皮去", "B.愧疚地取消"]
    elif lane == "loneliness_comparison":
        scene_headline = "别人的高光，按下了扣分键"
        scene_lines = ["看见一桌热闹，就觉得只有自己落单"]
        mechanism_headline = "比较会把片段当成全貌"
        mechanism_lines = ["朋友圈高光不等于别人的全部生活"]
        tool_headline = "先把比较拉回今晚"
        tool_lines = ["我看见了什么", "我给自己扣了什么分", "今晚给自己一个恢复动作"]
        comment_headline = "哪种高光最容易让你扣分？"
        comment_lines = ["A.聚会热闹", "B.工作进度"]
    elif lane == "sunday_anticipation":
        scene_headline = "周一还没来，提醒声先来了"
        scene_lines = ["未知任务越多，脑子越想提前排雷"]
        mechanism_headline = "预演常跟低控制感有关"
        mechanism_lines = ["多想不能把所有未知变成确定"]
        tool_headline = "只留一个可控动作"
        tool_lines = ["最担心的一件事", "现在可控的一小步", "暂时不用处理的一件事"]
        comment_headline = "周日晚上，你先预演什么？"
        comment_lines = ["A.开会", "B.消息"]
    elif lane == "after_hours_message":
        scene_headline = "一条消息，把身体拽回工位"
        scene_lines = ["电脑还没开，心已经开始排优先级"]
        mechanism_headline = "下班边界遇上低控制感"
        mechanism_lines = ["不确定自己能否离线，身体就继续待命"]
        tool_headline = "给消息一个下班后顺序"
        tool_lines = ["先看是否真的紧急", "写清回复时间", "把手机放远一点"]
        comment_headline = "下班消息来了，你会怎么回？"
        comment_lines = ["A.立刻秒回", "B.写清明早回复"]
    elif lane == "sleep_recovery":
        scene_headline = "人下班了，身体还在待命"
        scene_lines = ["没有新消息，肩膀仍像坐在工位"]
        mechanism_headline = "身体也需要收口信号"
        mechanism_lines = ["先认出待命状态，不逼自己立刻放松"]
        tool_headline = "留一个5分钟下班信号"
        tool_lines = ["关掉一个信息入口", "慢慢松三次肩颈", "写下明天第一步"]
        comment_headline = "你最想先关掉哪一种待命？"
        comment_lines = ["A.手机通知", "B.脑内待办"]
    elif lane == "sandwich_boundary":
        scene_headline = "拒绝前，我先替关系道歉"
        scene_lines = ["一句今晚不行，也像在关系里摔门"]
        mechanism_headline = "卡住的是边界压力"
        mechanism_lines = ["确认关系和说明限制可以分开"]
        tool_headline = "把边界说成两部分"
        tool_lines = ["我知道这件事很急", "但今晚我没法接手", "明早可以一起看优先级"]
        comment_headline = "边界句写好后，你是哪一派？"
        comment_lines = ["A.不敢发", "B.发了怕关系变冷"]
    else:
        scene_headline = "事情过去了，脑子还没下班"
        scene_lines = ["同一个片段被反复倒带"]
        mechanism_headline = "重复想不一定有新答案"
        mechanism_lines = ["先把事实和补出的解释分开"]
        tool_headline = "只留一个可控下一步"
        tool_lines = ["写下事实", "写下猜测", "决定明天是否确认"]
        comment_headline = "想太多时，你更像哪一派？"
        comment_lines = ["A.马上找答案", "B.忍住却反复想"]

    plan = normalize_psychology_carousel_plan(
        {
            "backend": "local_social_screenshot",
            "style": "psychology_text_card",
            "role": "text_carousel",
            "text_density": "medium",
            "max_text_units": "4",
            "cover_text_strategy": "封面只放一个具体瞬间和一句短提示。",
            "reason": "同一心理主题用有序文字卡逐步展开。",
            "prompt_focus": "只排版给定文字，不添加新结论。",
            "carousel_style": "psychology_text_card_v1",
            "slides": [
                {
                    "slide_id": "cover",
                    "order": 1,
                    "role": "cover_hook",
                    "headline": title,
                    "body_lines": [image_text],
                },
                {
                    "slide_id": "scene",
                    "order": 2,
                    "role": "concrete_scene",
                    "headline": scene_headline,
                    "body_lines": scene_lines,
                },
                {
                    "slide_id": "mechanism",
                    "order": 3,
                    "role": "light_mechanism",
                    "headline": mechanism_headline,
                    "body_lines": mechanism_lines,
                },
                {
                    "slide_id": "tool",
                    "order": 4,
                    "role": "save_tool",
                    "headline": tool_headline,
                    "body_lines": tool_lines,
                },
                {
                    "slide_id": "boundary",
                    "order": 5,
                    "role": "professional_boundary",
                    "headline": "一张卡有边界",
                    "body_lines": ["持续影响生活时，请及时寻求专业帮助"],
                },
                {
                    "slide_id": "comment",
                    "order": 6,
                    "role": "comment_prompt",
                    "headline": comment_headline,
                    "body_lines": comment_lines,
                },
            ],
        }
    )
    return _select_unused_modern_psychology_inner_plan(
        plan=plan,
        recent_inner_fingerprints=recent_inner_fingerprints or set(),
    )


def _select_unused_modern_psychology_inner_plan(
    *,
    plan: dict[str, Any],
    recent_inner_fingerprints: set[str],
) -> dict[str, Any]:
    candidates = [plan]
    candidates.extend(
        _with_modern_psychology_save_tool_headline(plan, headline)
        for headline in _MODERN_PSYCHOLOGY_SAVE_TOOL_HEADLINE_VARIANTS
    )
    for candidate in candidates:
        if (
            psychology_carousel_inner_pages_fingerprint(candidate)
            not in recent_inner_fingerprints
        ):
            return candidate
    # The caller supplies at most 12 validated hashes, but retaining a stable
    # fallback keeps this deterministic helper safe if a future caller widens
    # that contract.
    return plan


def _with_modern_psychology_save_tool_headline(
    plan: dict[str, Any],
    headline: str,
) -> dict[str, Any]:
    slides: list[dict[str, Any]] = []
    for slide in plan["slides"]:
        copied_slide = dict(slide)
        copied_slide["body_lines"] = list(slide["body_lines"])
        if copied_slide["role"] == "save_tool":
            copied_slide["headline"] = headline
        slides.append(copied_slide)
    return normalize_psychology_carousel_plan({**plan, "slides": slides})


def _modern_psychology_lane(scene: str) -> str:
    """Choose one lane in the same priority order used by body and image copy."""
    if "三明治拒绝法" in scene:
        return "sandwich_boundary"
    if any(
        keyword in scene
        for keyword in (
            "睡眠恢复",
            "轻养生",
            "办公室恢复",
            "下班信号",
            "5分钟",
            "5 分钟",
        )
    ):
        return "sleep_recovery"
    if any(keyword in scene for keyword in ("短视频", "刷手机", "信息过载", "越刷越空")):
        return "digital_overload"
    if any(keyword in scene for keyword in ("忽冷忽热", "想问清楚", "要不要问", "暧昧")):
        return "relationship_uncertainty"
    if any(
        keyword in scene
        for keyword in (
            "社交电量",
            "社交耗竭",
            "约好的局",
            "不想去了",
            "不想去",
            "取消",
            "扫兴",
            "硬着头皮",
        )
    ):
        return "social_depletion"
    if any(keyword in scene for keyword in ("孤独", "聚会", "比较", "失败", "朋友圈")):
        return "loneliness_comparison"
    if any(
        keyword in scene
        for keyword in (
            "分手",
            "猫归谁",
            "没回消息",
            "不回消息",
            "3小时",
            "伴侣",
            "挽留",
            "复合",
            "冷淡",
        )
    ):
        return "romantic_waiting"
    if any(keyword in scene for keyword in ("周日", "周一消息", "周一", "预焦虑")):
        return "sunday_anticipation"
    if any(keyword in scene for keyword in ("想太多", "睡不着", "边界")):
        return "boundary_pressure"
    if any(keyword in scene for keyword in ("临时消息", "拉回工位", "下班身份", "工位")):
        return "after_hours_message"
    if any(keyword in scene for keyword in ("会议", "尴尬")):
        return "meeting_replay"
    if any(keyword in scene for keyword in ("脑内", "白天的自己", "复盘会")):
        return "brain_meeting"
    if any(keyword in scene for keyword in ("普通回复", "收集大家", "常复盘")):
        return "ordinary_reply"
    return "rumination_default"


def _extract_selected_reddit_discussion(runtime_context: str) -> dict[str, str] | None:
    if "- status: available" not in runtime_context:
        return None
    lines = runtime_context.splitlines()
    for index, line in enumerate(lines):
        match = re.match(r"^\d+\.\s+r/([^`\s]+)\s+`(.+)`$", line.strip())
        if not match:
            continue
        details = {
            "subreddit": match.group(1).strip(),
            "title": match.group(2).strip(),
            "fit": "",
            "source_url": "",
            "excerpt": "",
        }
        for detail_line in lines[index + 1 : index + 6]:
            stripped = detail_line.strip()
            if stripped.startswith("- Chinese-reader fit:"):
                details["fit"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- source_url:"):
                details["source_url"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("- excerpt_en:"):
                details["excerpt"] = stripped.split(":", 1)[1].strip()
            elif re.match(r"^\d+\.\s+r/", stripped):
                break
        return details
    return None


def _extract_pattern_hooks(runtime_context: str) -> set[str]:
    if "# XHS Format Pattern Library Context" not in runtime_context:
        return set()
    for line in runtime_context.splitlines():
        if line.startswith("- hook_archetypes:"):
            raw = line.split(":", 1)[1]
            return {part.strip() for part in raw.split(",") if part.strip()}
    return set()


def _build_classic_poetry_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    if any(keyword in scene for keyword in ("李清照", "人比黄花瘦", "声声慢")):
        title = "读到李清照那句，突然不硬撑了"
        image_text = "情绪可以慢慢安放"
        quote = "人比黄花瘦"
        author = "李清照"
        reading = "不是把难过写得好看，而是承认有些时刻人真的会轻不起来。"
    elif any(keyword in scene for keyword in ("王维", "山水", "空山")):
        title = "读到王维那句，突然想留白"
        image_text = "今晚先空出来一点"
        quote = "空山新雨后"
        author = "王维"
        reading = "不是逃进山里，而是在今天也给自己留一小块安静。"
    elif any(keyword in scene for keyword in ("苏轼", "定风波", "风雨")):
        title = "读到定风波那句，突然不急了"
        image_text = "风雨可以先慢一点"
        quote = "莫听穿林打叶声"
        author = "苏轼"
        reading = "不是把狼狈变美，而是提醒自己别把一阵风雨判成失败。"
    else:
        title = "读到李白那句，突然不慌了"
        image_text = "这一句可以先存下"
        quote = "长风破浪会有时"
        author = "李白"
        reading = "不是喊你立刻赢，而是提醒你：看不见风的时候，也可以先把船稳住。"

    body = (
        f"{scene}。我会先想到{author}这句“{quote}”。\n"
        f"{reading}"
        "所以这不是一条讲义，也不是把古诗词金句当成鸡血口号。\n"
        f"这一句可以存下来：先承认今天很难，再给自己留一个还能往前走的小动作。"
        "今晚只做一件事也算，打开文档、发出那条消息，或者早点睡。\n"
        "评论区可以留一句你最近读到会想到自己的古诗词，我想顺着大家的句子再读一遍。"
    )
    if feedback != "无" and "这一句" not in body:
        body += "\n把这一句补回来，读法才不会散成泛泛的文化感。"
    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": ["#古诗词", "#诗词金句", "#读书笔记", "#小红书读书"],
    }


def _build_wuxia_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，最适合拿令狐冲来讲。金庸在《笑傲江湖》里写的不是一个简单浪子，"
        "而是一个有能力进体系、却始终不肯把自己完全交给体系的人。原文里“行事但求无愧于心”"
        "常被读成潇洒，其实更像他的底层规则：敬重师门、珍惜朋友，但不把人的鲜活感磨成标准答案。\n"
        "放到今天的职场看，他像很多不愿被体制化的人。不是不想负责，也不是没有能力，"
        "而是怕自己只剩流程、汇报和绩效表，连喜欢什么都先看组织脸色。《笑傲江湖》最狠的地方也在这："
        "自由的人往往先被误解，岳不群要他成为门派资产，江湖要他选阵营。\n"
        "所以这句很适合截图：令狐冲的自由不是不负责，而是不愿把良心外包给任何体系。"
        "它有刺，是因为很多人不是不努力，只是不想用一生证明自己适合一套并不适合自己的考核表。"
        "他要的不是逃出所有关系，而是在每段关系里还能认出自己。\n"
        "我更愿意把他当作一个提醒：在关系里让人满意之外，也要留住谁值得信、什么底线不能交出去的判断。"
        "这份别扭未必讨喜，却是他没被磨平的证据；这种不肯自欺的劲，放到今天也仍然珍贵。评论区想问问，你还想用今天的处境重读哪个金庸人物？"
        "我下一篇想写黄蓉或郭靖。"
    )
    if feedback != "无" and "#金庸" not in body:
        body += "重读金庸时，这个角度会更清楚。"
    return {
        "title": "令狐冲不是摆烂，他是不想被体制化",
        "image_text": "自由也要有底线",
        "body": body,
        "hashtags": ["#金庸", "#令狐冲", "#笑傲江湖", "#武侠", "#读书笔记"],
    }


def _build_world_cup_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    if any(keyword in scene for keyword in ("赛后", "终场", "点球", "逆转", "加时")):
        title = "终场哨响后，别只盯比分"
        image_text = "终场后别急着只看比分"
        body = (
            f"{scene}。这类世界杯赛后内容，普通球迷可以先别急着把情绪压成一句输赢，"
            "先按三个看点复盘：比赛节奏什么时候变快，哪次边路推进最有威胁，"
            "以及替补上来后有没有改变中场连接。\n"
            "这份看球清单我会这样存：先回看开场15分钟的压迫，再看下半场体能变化，接着看终场前的定位球选择。"
            "这样聊球不会只剩吵架，也能把赛事情绪放回具体瞬间。\n"
            "评论区想问问，你赛后最想复盘的是哪一个回合，还是哪位球员的选择？"
        )
    elif any(keyword in scene for keyword in ("朋友", "宿舍", "酒吧", "客厅", "熬夜", "看球局")):
        title = "看球局冷场，就聊这三秒"
        image_text = "普通球迷也能聊起来"
        body = (
            f"{scene}。世界杯好看的地方不只是强强对话，也有一群人一起等开球的赛事情绪。"
            "如果不是每个人都懂战术，可以先用三个看点把聊天拉到同一频道："
            "谁负责推进，哪一侧边路更活跃，定位球会不会成为转折。\n"
            "这份看球清单可以先这样存：开场看逼抢强度，中场看换人信号，赛后看哪次机会最可惜。"
            "不用争成专家，能一起看懂几个瞬间就很够了。\n"
            "评论区说说你看球时最在意氛围、球星，还是终场前十分钟的心跳。"
        )
    else:
        title = "世界杯开球前，别只猜输赢"
        image_text = "先看懂对位再开球"
        body = (
            f"{scene}。赛前不用把自己逼成战术分析师，普通球迷先抓三个看点就够了："
            "阿根廷能不能把中场节奏稳住，法国的边路速度会不会把防线拉开，"
            "以及定位球和替补变化会不会变成转折。\n"
            "这份看球清单可以先这样存：开场15分钟看谁压得更靠前，中场看哪边体能先掉，"
            "赛后再回看最接近进球的那次推进。这样看球，紧张会更具体，聊天也不只剩支持谁。\n"
            "评论区想问问，你最想看阿根廷的中场控制，还是法国的反击速度？"
        )

    if feedback != "无" and "收藏" not in body:
        body += "\n也可以先存成一张赛前看球清单，开球后按顺序对照。"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": ["#世界杯", "#足球", "#看球笔记", "#赛前看点"],
    }


def _build_ai_tech_draft(*, runtime_context: str) -> dict[str, Any]:
    """Render a deterministic AI post from the bound evidence contract only.

    AI-tech deterministic drafts intentionally ignore the free-text scene and
    reflection text.  The production boundary already binds a validated
    contract; mirroring that boundary here prevents test/dry-run fallbacks
    from quietly returning a generic opinion or an invented prompt recipe.
    """
    contract = _extract_ai_tech_runtime_contract(runtime_context)
    mode = contract["mode"]
    payload = contract["drafting_payload"]
    if not isinstance(payload, Mapping):
        raise ValueError("AI tech evidence contract is missing its drafting payload")

    if mode == "news_brief":
        items = payload.get("news_items")
        if not isinstance(items, (list, tuple)):
            raise ValueError("AI tech news brief evidence is invalid")
        lines: list[str] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, Mapping):
                raise ValueError("AI tech news brief item is invalid")
            label = _required_ai_tech_text(item.get("label"), field="news label")
            facts = _required_ai_tech_texts(item.get("facts"), field="news facts")
            lines.append(f"{index}. {label}｜{'；'.join(facts)}")
        return {
            "title": f"AI 更新｜{len(lines)} 条",
            "image_text": "今天值得记住的更新",
            "body": "\n".join(lines),
            "hashtags": ["#AI资讯", "#AI科技"],
        }

    topic = _required_ai_tech_text(payload.get("topic"), field="topic")
    if mode == "hands_on":
        record = payload.get("hands_on")
        if not isinstance(record, Mapping):
            raise ValueError("AI tech hands-on evidence is invalid")
        product = _required_ai_tech_text(record.get("product"), field="product")
        version = _required_ai_tech_text(record.get("version"), field="version")
        tested_at = _required_ai_tech_text(record.get("tested_at"), field="tested_at")
        task = _required_ai_tech_text(record.get("task"), field="task")
        input_summary = _required_ai_tech_text(record.get("input_summary"), field="input")
        observed_output = _required_ai_tech_text(
            record.get("observed_output"), field="observation"
        )
        limitation = _required_ai_tech_text(record.get("limitation"), field="limitation")
        return {
            "title": f"实测记录｜{topic}",
            "image_text": "一条可复核的 AI 实测",
            "body": "\n".join(
                (
                    f"主题：{topic}",
                    f"产品与版本：{product} {version}",
                    f"测试日期：{tested_at}",
                    f"任务：{task}",
                    f"输入：{input_summary}",
                    f"观察：{observed_output}",
                    f"局限：{limitation}",
                )
            ),
            "hashtags": ["#AI资讯", "#AI实测", "#AI工具"],
        }

    if mode != "fact_translation":
        raise ValueError("AI tech evidence contract has an unknown mode")
    facts = _required_ai_tech_texts(payload.get("facts"), field="facts")
    audience = payload.get("audience")
    if not isinstance(audience, Mapping):
        raise ValueError("AI tech fact-translation audience is invalid")
    who_should_care = _required_ai_tech_text(
        audience.get("who_should_care"), field="who_should_care"
    )
    who_can_wait = _required_ai_tech_text(audience.get("who_can_wait"), field="who_can_wait")
    return {
        "title": f"更新解读｜{topic}",
        "image_text": "这次谁该先看",
        "body": "\n".join(
            (
                f"主题：{topic}",
                *(f"事实：{fact}" for fact in facts),
                f"该关注：{who_should_care}",
                f"可以等等：{who_can_wait}",
            )
        ),
        "hashtags": ["#AI资讯", "#科技解读"],
    }


def _extract_ai_tech_runtime_contract(runtime_context: str) -> dict[str, Any]:
    marker = "# AI Tech Evidence Contract"
    marker_index = runtime_context.find(marker)
    if marker_index < 0:
        raise ValueError("AI tech drafts require a bound evidence contract")
    json_start = runtime_context.find("{", marker_index + len(marker))
    if json_start < 0:
        raise ValueError("AI tech evidence contract is missing JSON")
    try:
        payload, _ = json.JSONDecoder().raw_decode(runtime_context[json_start:])
        return parse_ai_tech_runtime_contract(payload)
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise ValueError("AI tech evidence contract is invalid") from exc


def _build_psychology_learning_draft(*, runtime_context: str) -> dict[str, Any]:
    """Render the closed catalog template for a psychology learning lesson."""
    contract = _extract_psychology_learning_runtime_contract(runtime_context)
    return render_psychology_learning_draft(contract)


def _extract_psychology_learning_runtime_contract(runtime_context: str) -> dict[str, Any]:
    marker = "# Psychology Learning Series Contract"
    marker_index = runtime_context.find(marker)
    if marker_index < 0:
        raise ValueError("psychology learning drafts require a bound catalog contract")
    json_start = runtime_context.find("{", marker_index + len(marker))
    if json_start < 0:
        raise ValueError("psychology learning contract is missing JSON")
    try:
        payload, _ = json.JSONDecoder().raw_decode(runtime_context[json_start:])
        return parse_psychology_learning_runtime_contract(payload)
    except (TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise ValueError("psychology learning contract is invalid") from exc


def _required_ai_tech_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"AI tech evidence {field} is missing")
    return value.strip()


def _required_ai_tech_texts(value: object, *, field: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"AI tech evidence {field} is missing")
    values = [_required_ai_tech_text(item, field=field) for item in value]
    if not values:
        raise ValueError(f"AI tech evidence {field} is missing")
    return values


def _build_daily_english_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，我今天最想存的是 follow up：不是催，是礼貌跟进。"
        "音标：/ˈfɑːloʊ ʌp/；词性：动词短语。\n"
        "真实场景例句：I’ll follow up with you after the meeting. 翻译：会后我再跟你确认一下；"
        "这个句型可以收藏成 I’ll follow up with you after + 时间 / 事件，开会、私聊、邮件都能用。\n"
        "我会把它存进备忘录；评论区用 follow up 造句，看看你会接哪个场景？"
    )
    if feedback != "无" and "#每日英语" not in body:
        body += "\n这条适合放进 #每日英语 系列里慢慢积累。"
    return {
        "title": "开会私聊都能用的follow up",
        "image_text": "一句开会私聊都能用",
        "body": body,
        "hashtags": ["#每日英语", "#英语学习", "#实用英语", "#职场英语"],
    }


def _build_modern_psychology_draft(
    *, scene: str, feedback: str, runtime_context: str
) -> dict[str, Any]:
    lane = _modern_psychology_lane(scene)
    if lane == "sandwich_boundary":
        body = (
            f"{scene}，我最先冒出来的念头不是怎么安排时间，而是他会不会觉得我不够朋友。"
            "于是手机拿起来又放下，连“今晚不行”四个字都像在关系里摔门。\n"
            "这里真正卡住的是边界压力：三明治拒绝法有用，不是因为它好听，"
            "而是把确认关系和说明限制分开放。可以先存一句边界句：我知道这件事急，"
            "但今晚我没法接手；我可以明早帮你看优先级。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.边界句写好不敢发 B.发了又怕冷？"
        )
        title = "同事说帮个忙，我先把道歉打好了"
        image_text = "拒绝也可以有温度"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#自我成长"]
    elif lane == "sleep_recovery":
        body = (
            f"{scene}，我人已经离开工位，肩膀却还像卡在会议室门口。"
            "回家路上没有新消息，身体还是绷着，像随时要重新打开电脑。\n"
            "这更像情绪调节里的身体收口：大脑下班了，身体还没收到停机信号。"
            "我会先存一个 5分钟下班信号：关掉一个信息入口，慢慢松三次肩颈，"
            "把明天第一步写成一句小事。它不要求立刻睡好，只是把睡眠恢复和轻养生"
            "缩成今晚能做的一小步；晚点还是难受，也只做“不再继续处理工作”。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你最需要哪种下班信号：A.身体放松 B.脑子停机 C.手机下线？"
        )
        title = "下班后身体被拖回工位"
        image_text = "5分钟给身体下班信号"
        hashtags = ["#心理学", "#情绪管理", "#睡眠恢复", "#轻养生", "#自我成长"]
    elif lane == "digital_overload":
        body = (
            f"{scene}，手指一直往下滑，身体已经很困了，脑子还在等一个更好笑、"
            "更刺激、或者刚好能把空掉的那块补上的视频。\n"
            "有时屏幕不是放松，而是把白天没处理完的感受延后；这可以理解成信息过载叠着一点情绪回避。"
            "我会先把手机扣在桌上，做一个 5分钟下线练习：写下我在躲什么、身体要什么、下一步只做什么。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你睡前停不下来通常在刷：A.短视频 B.聊天记录 C.搜索答案？"
        )
        title = "睡前越刷越空，手还在自动下滑"
        image_text = "先把屏幕扣下5分钟"
        hashtags = ["#心理学", "#情绪管理", "#信息过载", "#睡眠恢复", "#自我成长"]
    elif lane == "relationship_uncertainty":
        body = (
            f"{scene}，最磨人的不是对方冷了一下，而是脑子开始替每个表情、"
            "每次间隔和每句语气做判卷。想问清楚，又怕自己显得太需要答案；不问，"
            "身体又一直悬在半空。\n"
            "这更像关系不确定感：空白越多，大脑越容易把信号补成剧情。"
            "我会先存一张三栏：事实=发生了什么；信号=哪些变化让我在意；"
            "我要不要问清楚=我真正需要确认什么。写完以后，不急着逼问，也不把冷淡直接当判决，"
            "只选择一句低压确认：我有点感到距离变了，想知道我们现在是不是还在同一边。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.问清楚 B.先观察？"
        )
        title = "忽冷忽热那几天，我想问又怕烦"
        image_text = "先分清事实和信号"
        hashtags = ["#心理学", "#情绪管理", "#亲密关系", "#自我成长"]
    elif lane == "social_depletion":
        body = (
            f"{scene}，真正卡住的不是要不要出门，而是怕别人觉得我扫兴、临时变卦、"
            "不够珍惜关系。身体已经很累了，脑子还在替自己写道歉小作文。\n"
            "这更像社交耗竭叠着关系边界压力：你需要休息，同时也想把关系放稳。"
            "我会先存一个取消局三句：先承认约定，比如我知道我们早就约好了；"
            "再说明状态，比如我今天电量真的很低；再给下一次选项，比如这周换一天我来定时间。"
            "它不是让人失联，而是把真实电量说清楚。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.硬着头皮去 B.愧疚地取消？"
        )
        title = "约好的局，我突然没电了"
        image_text = "取消局三句先存好"
        hashtags = ["#心理学", "#情绪管理", "#社交耗竭", "#关系边界"]
    elif lane == "loneliness_comparison":
        body = (
            f"{scene}，照片里每个人都在笑，我却盯着那一桌菜想：是不是只有我今天没有被任何人想起。\n"
            "这种刺痛常常不只来自热闹本身，也来自比较焦虑和孤独感一起按下了扣分键。"
            "我会先写下来：我看见了什么、我给自己扣了什么分、今晚能给自己安排哪一个小恢复动作；"
            "先去倒杯水，再给自己留十分钟安静，慢一点。把手机扣在手边，先让这一晚不用跟谁比较。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "最容易让你给自己扣分的高光片段是____"
        )
        title = "看到别人周末很热闹，不代表你失败"
        image_text = "别拿高光片段扣自己的分"
        hashtags = ["#心理学", "#情绪管理", "#孤独感", "#比较焦虑", "#自我成长"]
    elif lane == "romantic_waiting":
        body = (
            f"{scene}，手机其实只安静了三小时，我的脑子已经替我们办完分手手续："
            "猫跟谁、钥匙怎么还、朋友圈要不要删。"
            "我甚至开始回看上一条消息，是不是我少发了一个表情，还是他说晚安时已经变冷。\n"
            "最累的不是等，而是每一分钟都像在等一个判决；"
            "关系不确定感会让大脑把空白补成最坏结局，好像先演完就能少痛一点。"
            "我会先存一张三栏：事实=他暂时没回；脑补=我们要分开；我需要=一次清楚但不追问的确认。"
            "写完以后，不急着发一大段话，也不把沉默直接当证据；"
            "等身体没那么慌，再决定要不要问一句清楚的确认。"
            "这不是替对方开脱，也不是逼自己大度，只是把问题从“你是不是不要我了”"
            "换成“我想知道我们现在是不是还在同一边”。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.没回就脑补到分手 B.忍住不问但越想越多？"
        )
        title = "他3小时没回，我已经分好猫了"
        image_text = "先分清事实和脑补"
        hashtags = ["#心理学", "#情绪管理", "#亲密关系", "#自我成长"]
    elif lane == "sunday_anticipation":
        body = (
            f"{scene}，人还在周日晚上，脑子已经把明天的消息提示音预演了三遍。"
            "牙还没刷，会议、催办、未读红点已经排队进场。\n"
            "这类周日晚预演常和低控制感有关：未知任务越多，大脑越想提前排雷。"
            "可以存一个 5分钟落地练习：写下最担心的1件事、能做的1个动作、暂时不用处理的1件事。"
            "纸放在床边，剩下的明早再看。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你周日晚上最常预演的是：A.开会 B.消息 C.被临时安排？"
        )
        title = "周日晚上，我已经听见周一消息提示音"
        image_text = "脑子提前打卡上班"
        hashtags = ["#心理学", "#情绪管理", "#周一焦虑", "#低控制感", "#自我成长"]
    elif lane == "boundary_pressure":
        body = (
            f"{scene}，那句话表面很轻，脑子却像被按下了整晚重播。"
            "你一边告诉自己算了，一边又把对方的语气、表情和停顿翻出来检查。\n"
            "这可能和边界压力有关：感受被轻轻带过时，大脑会继续确认自己是不是被误解。"
            "可以先存一句边界句：我知道你是好意，但这件事对我确实有影响，我需要一点时间整理一下。"
            "先把这句留在备忘录里，今晚不用急着替自己判错。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.当场沉默 B.事后越想越委屈？"
        )
        title = "被说想太多后，我把那句话听了一晚上"
        image_text = "边界句先替你站稳"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#自我成长"]
    elif lane == "after_hours_message":
        body = (
            f"{scene}，鞋刚换好，外卖刚拆开，手机一亮，脑子就自动坐回工位。"
            "最累的是还没打开电脑，心已经开始排任务优先级。\n"
            "这常常是边界压力和低控制感叠在一起：你不确定自己能不能真的离线。"
            "可以存一个消息草稿：我看到了，明早到工位后先确认优先级，再回复进度；今晚先把手机放远一点，明天再说。"
            "这句先躺在草稿箱里，今晚的下班时间先还给自己。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.秒回后内耗 B.写好边界句不敢发？"
        )
        title = "人下班了，脑子又被消息拽回去"
        image_text = "脑子又被拉回工位"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#关系边界", "#低控制感"]
    elif lane == "meeting_replay":
        body = (
            f"{scene}，身体已经离开会议室，脑子还在给那句话反复加字幕。"
            "我甚至能想象所有人回家路上突然想起它，然后在心里给我扣一分。"
            "电梯门关上的时候，我还在想，如果当时换个词，会不会显得更稳一点点。\n"
            "这种会后回放可以叫反刍思维：大脑想确认自己有没有说错、有没有被误解。"
            "我会先存进事实 / 猜测 / 下一步：事实=对方原话；猜测=我补出的评价；"
            "下一步=明天要不要轻轻确认一次。如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.写完小作文秒删 B.发了又后悔？"
        )
        title = "会议那句话，我改到第七版"
        image_text = "把脑补写到猜测栏"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#反刍思维"]
    elif lane == "brain_meeting":
        body = (
            f"{scene}，像在脑子里给自己开一场没有主持人的会。"
            "每个人都在发言，只有你不能离席，连洗澡的时候都在补充议程。\n"
            "这像是反刍思维把白天的低控制感延长到了晚上。可以给脑内会议写一句散会通知："
            "用事实 / 猜测 / 下一步给这场会收尾，今天只记 1 个事实、1 个需要确认的问题，剩下明天再看。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.睡前开会 B.洗澡吵架 C.通勤复盘？"
        )
        title = "下班后脑内复盘会，可以先散会"
        image_text = "脑内会议先暂停"
        hashtags = ["#心理学", "#情绪管理", "#自我成长", "#反刍思维"]
    elif lane == "ordinary_reply":
        body = (
            f"{scene}，一条普通回复发出去，脑子开始自动检查标点、语气和对方会不会多想。"
            "明明只是“好的”，我已经在想是不是该加个表情。\n"
            "这像是反刍思维在追求确定答案：聊天很少给满分判卷。"
            "可以存一个 5分钟停止循环法：先等 5 分钟，只问自己有新证据，还是在重复同一个担心。"
            "先把手机翻过去，让这条回复今晚先停在这里。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "评论区来做个小收集：你是哪派，A.写完秒删 B.发完重看十遍？"
        )
        title = "一条普通回复，为什么能想一整晚"
        image_text = "回复后脑子还在已读"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#反刍思维"]
    else:
        body = (
            f"{scene}，人已经走在路上，脑子却还在把那句话反复倒带。"
            "路灯亮了三盏，我已经给白天的自己补了四版解释，越补越像在写检讨。"
            "明明没人再提那件事，我却像还坐在原地等一个判分结果。\n"
            "这种停不下来的回放可以叫反刍思维：大脑想重新找回控制感，所以一遍遍检查细节。"
            "我会先写下来：事实=对方原话；猜测=我脑补了什么；下一步=明天要不要确认一句。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.写完小作文秒删 B.发了又后悔？"
        )
        title = "下班后，我还在给白天那句话打补丁"
        image_text = "脑子在替尴尬加班"
        hashtags = ["#心理学", "#情绪管理", "#自我成长", "#职场焦虑", "#反刍思维"]
    title, image_text, body = _avoid_recent_modern_psychology_memory(
        title=title,
        image_text=image_text,
        body=body,
        scene=scene,
        runtime_context=runtime_context,
    )
    if feedback != "无" and "专业帮助" not in body:
        body += "\n如果这些感受持续影响生活，请优先寻求专业帮助。"
    draft: dict[str, Any] = {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }
    draft["image_plan"] = _build_modern_psychology_carousel_plan(
        scene=scene,
        title=title,
        image_text=image_text,
        recent_inner_fingerprints=_recent_psychology_carousel_inner_fingerprints(
            runtime_context
        ),
    )
    return draft


def _recent_psychology_carousel_inner_fingerprints(runtime_context: str) -> set[str]:
    if _RECENT_PSYCHOLOGY_CAROUSEL_FINGERPRINT_HEADER not in runtime_context:
        return set()
    fingerprint_context = runtime_context.split(
        _RECENT_PSYCHOLOGY_CAROUSEL_FINGERPRINT_HEADER,
        maxsplit=1,
    )[1]
    fingerprints = _RECENT_PSYCHOLOGY_CAROUSEL_FINGERPRINT_PATTERN.findall(
        fingerprint_context
    )
    return set(fingerprints[-12:])


def _avoid_recent_modern_psychology_memory(
    *,
    title: str,
    image_text: str,
    body: str,
    scene: str,
    runtime_context: str,
) -> tuple[str, str, str]:
    if "# Recent Account Memory" not in runtime_context:
        return title, image_text, body
    if title not in runtime_context and image_text not in runtime_context:
        return title, image_text, body
    if any(
        keyword in scene
        for keyword in (
            "睡眠恢复",
            "轻养生",
            "办公室恢复",
            "下班信号",
            "5分钟",
            "5 分钟",
        )
    ):
        candidates = [
            (
                "洗完澡，我还被工位拽着",
                "先给身体一个收工键",
                (
                    f"{scene}，洗完澡坐到床边，肩膀还是像没退出工作群。"
                    "灯已经关掉一半，脑子没在想大事，身体却还在等下一条消息。\n"
                    "这更像情绪调节里的身体收口：不是靠意志把自己按睡，"
                    "而是给白天的工作模式一个结束动作。"
                    "我会把 5分钟下班信号写进备忘录：先关一个信息入口，"
                    "再让肩颈慢慢松三次，把明天第一步写成一句能做的小事。"
                    "它不把睡着当成任务，也不写成医疗养生建议；只是把睡眠恢复和轻养生"
                    "落到今晚能执行的低成本动作。做完以后，不急着检查效果，"
                    "先让身体从“还要继续处理”的状态里退出来。"
                    "如果最近总是重复这种待命感，可以只记录触发点：哪条消息、"
                    "哪个时间、身体哪里先紧。记录到这里就停，不继续分析原因。"
                    "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
                    "你最想先关掉哪一个：A.手机通知 B.脑内待办 C.肩颈紧绷？"
                ),
            ),
            (
                "关灯后，身体还被工作叫住",
                "5分钟退出待命状态",
                (
                    f"{scene}，灯关了，身体却像还坐在办公室等人叫号。"
                    "手机没有新消息，我也没有真的在加班，但胃口、肩颈和呼吸都还绷着。\n"
                    "这可以理解成情绪调节里的身体收口还没完成：大脑宣布下班，身体还没收到结束提示。"
                    "我会存一张 5分钟卡片：入口只关一个，肩颈只松三次，"
                    "明天第一步只写一句。它不是睡眠任务，也不是养生方案，"
                    "而是把睡眠恢复和轻养生缩成一个低风险的下班信号。"
                    "如果手还想继续点开消息，就倒水、洗杯子，或者把电脑合上放远一点，"
                    "让身体知道今晚不用继续待命。"
                    "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
                    "你是哪派：A.身体停不下 B.脑子关不掉 C.手机放不下？"
                ),
            ),
        ]
        for candidate in candidates:
            candidate_title, candidate_image, _candidate_body = candidate
            if candidate_title not in runtime_context and candidate_image not in runtime_context:
                return candidate
        return candidates[-1]
    if any(keyword in scene for keyword in ("会议", "尴尬")):
        candidates = [
            (
                "下班路上，我又把会议拖回进度条",
                "先分清原话和脑补",
                (
                    f"{scene}，路灯都亮了，脑子还在把会议那一秒拖回进度条。"
                    "我已经把对方的停顿、眼神和那句短回复拆开看了好几遍。"
                    "连电梯里别人一句笑声，都能被我临时配成会议续集。"
                    "回到家换鞋的时候，我还在给那一秒重新配台词。\n"
                    "这种会后回放可以叫反刍思维：大脑想确认自己有没有被误解、有没有漏掉信号。"
                    "可以先存一个事实 / 猜测 / 下一步：事实=对方实际说了什么；猜测=我补出的评价；"
                    "下一步=明天是否用一句轻确认收尾。如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
                    "你是哪派：A.写完小作文秒删 B.发了又后悔？"
                ),
            ),
            (
                "会议回放键，先别再按了",
                "事实先坐前排",
                (
                    f"{scene}，人已经在回家路上，脑子却把会议室重新开了一遍灯。"
                    "那句话本来只有几秒，我却给它补了字幕、背景音和所有人的内心 OS。"
                    "连路过便利店时，我都还在想当时是不是该换一个语气。\n"
                    "这种回放可以叫反刍思维：它想确认那句话到底是事实，还是你临时补出来的评价。"
                    "可以先存一个事实 / 猜测 / 下一步：事实=我听见了哪句话；猜测=我给它加了什么含义；"
                    "下一步=明天是否需要轻轻确认一次。如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
                    "你是哪派：A.睡前开会 B.通勤复盘？"
                ),
            ),
            (
                "一句会议回音，别想成判决书",
                "把脑补写到猜测栏",
                (
                    f"{scene}，那句话像在脑子里开了循环播放，我已经给它写出三种最坏版本。"
                    "回家路上手机没响，我反而更确定自己刚才一定哪里不对。\n"
                    "这种检查可以叫反刍思维：大脑想降低不确定感，所以反复翻同一个片段。"
                    "可以先存一个事实 / 猜测 / 下一步：事实=原话；猜测=我担心的评价；"
                    "下一步=要不要用一句具体问题确认。如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
                    "今天让你在会后反复检查的一句话是____"
                ),
            ),
        ]
        for candidate in candidates:
            candidate_title, candidate_image, _candidate_body = candidate
            if candidate_title not in runtime_context and candidate_image not in runtime_context:
                return candidate
        return candidates[-1]
    return title, f"{image_text}，换个角度存", body
