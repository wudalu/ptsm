from __future__ import annotations

import re
from typing import Any


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
    if _is_sushi_poetry_context(scene=scene, extra_context=extra_context):
        return _build_sushi_poetry_draft(scene=scene, feedback=feedback)
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
        return _build_ai_tech_draft(scene=scene, feedback=feedback)
    if _is_daily_english_context(scene=scene, extra_context=extra_context):
        return _build_daily_english_draft(scene=scene, feedback=feedback)
    if _is_modern_psychology_context(scene=scene, extra_context=extra_context):
        return _build_modern_psychology_draft(
            scene=scene,
            feedback=feedback,
            runtime_context=runtime_context,
        )
    return None


def _is_sushi_poetry_context(*, scene: str, extra_context: str) -> bool:
    combined = f"{scene}\n{extra_context}"
    return any(
        keyword in combined
        for keyword in (
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
        title = "给床头角落一点适我主义"
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
            else "给旧材料一个十分钟丰容流程"
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
            else "给常走路线加一个低成本变量"
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
            else "给书桌加一个零成本变量"
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
        title = "这个小角落先丰容一厘米"
        image_text = "给生活留一点新鲜感"
        body = (
            f"{scene}。今天不做大改造，只给它加一个看得见的小变量。\n"
            "我会先存这三步：拿走一个最碍眼的杂物；补一个能每天看见的颜色；"
            "把明天会用到的小东西提前放好。\n"
            "变化很小，但它会提醒我这里不是临时堆放区，也是生活的一部分。"
            "评论区交一个你家最想先微调的角落。"
        )
    else:
        title = "今天先试一个日常变量"
        image_text = "低成本丰容一下"
        body = (
            f"{scene}。我想先做一个很小的人类丰容实验，不靠大购物，也不假装人生马上焕新。\n"
            "我会先按三步走：选一个每天都会经过的位置；加一个不用花钱的小变量；"
            "晚上回来只观察它有没有让自己多停留十秒。\n"
            "如果有，就把它留下；如果没有，明天换一个变量。"
            "评论区交一个你会先试的日常变量。"
        )

    body = _ensure_body_min_chars(
        body,
        minimum=180,
        addition="如果不想把它变成任务，就只记录一个变化：今天哪个角落让自己愿意多停十秒。",
        before="评论区",
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
            "AI 工具第一次帮你省下半小时的时候，很容易让人产生一种错觉：以后是不是都可以交给它了。\n"
            "但真正用久了会发现，最累的部分没有消失，只是换了名字：你要把任务拆清楚，"
            "判断结果靠不靠谱，把漏掉的细节补回来，最后还要替它的错误负责。\n"
            "这就是很多打工人现在的隐形劳动：看起来是在用工具，实际上是在照看工具，"
            "有点像 AI保姆，工具跑得越快，人越需要守住判断边界。\n"
            "我会把这条先收藏成三句话：重复步骤可以交出去；关键判断不能外包；涉及来源、隐私和责任的结果一定要自己复核。\n"
            "评论区想问问，你现在更像是在用 AI，还是在照看 AI？"
        )
        hashtags = ["#热点观察", "#AI工具", "#人工智能", "#效率工具", "#职场成长"]
    elif selected:
        title = "消息一响，人就被重新拽回任务里"
        image_text = "真正累的是随时都要回应"
        body = (
            "很多压力不是来自某一条消息，而是来自那种“我好像随时都要回应”的低控制感。\n"
            "手机一亮，人就被重新拽回工作、关系或任务里。你明明在休息，脑子却要立刻判断："
            "这件事急不急、对方会不会等、我不回是不是显得不负责。\n"
            "真正消耗注意力的不是提醒声，而是每一次提醒后都要重新做选择。\n"
            "这条我会先存成一个小顺序：先问这件事是不是必须现在处理；再给出一个明确回复时间；"
            "最后给自己留一个不被打断的小窗口。\n"
            "评论区想问问，你最想先关掉哪一种消息提醒？"
        )
        hashtags = ["#热点观察", "#心理学", "#情绪管理", "#注意力管理", "#效率工具"]
    elif any(keyword in scene.lower() for keyword in ("burnout", "心理", "焦虑", "通知", "attention")):
        title = "消息压力最累的不是消息本身"
        image_text = "随时回应才是隐形加班"
        body = (
            "很多人不是讨厌消息本身，而是被“随时都要回应”的预期拖住。\n"
            "它背后其实是低控制感：通知一响，人就被重新拉回工作、关系或任务里，"
            "注意力还没恢复，又要开始判断对方是不是在等我。\n"
            "这种压力在日常里很常见，因为微信群、工作软件和短视频提醒常常混在一起，"
            "休息时间也会变成半在线状态。\n"
            "这条可以先收藏成三个问题：这条消息要不要现在处理；能不能给一个明确回复时间；"
            "有没有必要把提醒关掉半小时。这样不是逃避，而是把注意力边界拿回来一点。\n"
            "评论区想问问，你最想给哪一种消息设一个回复边界？"
        )
        hashtags = ["#热点观察", "#心理学", "#情绪管理", "#注意力管理", "#效率工具"]
    else:
        title = "别急着追AI代理，先看这条边界"
        image_text = "别急着追工具，先看边界"
        body = (
            "AI agent 看起来能替你处理小任务，但工具越多，普通人反而越需要判断哪些事不该交出去。\n"
            "这不是简单的“AI又变强了”，而是一个更贴近日常的变化："
            "从写邮件、整理资料到排计划，很多人开始把重复步骤拆给工具，但也担心隐私、权限和结果是否可靠。\n"
            "可以先抓住一个判断框架：它能不能省掉重复整理；能不能让你检查来源；"
            "能不能在出错时及时停下来。满足这三点，才值得放进工作流。\n"
            "我会先把边界写清楚：AI工具小范围试，不把账号、隐私和关键决策一次性交给它；"
            "把它当助手，不当替你负责的人。不是投资建议，只是工具使用观察。\n"
            "评论区想问问，你最不敢交给 AI 的任务是什么？"
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


def _build_sushi_poetry_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，我会想到苏轼《定风波》里那种把狼狈放慢一点看的劲儿。\n"
        "他不是把风雨写成胜利宣言，而是先承认：人走在雨里，衣角会湿，心也会乱。"
        "但只要还能往前走，很多难堪就不会永远停在原地。\n"
        "这一句可以存下来：别急着把今天解释成失败，先把它当成一段正在过去的风雨。"
        "它不是鸡血，更像给自己留一点缓冲。\n"
        "评论区可以留一句你最近读到会想到自己的苏轼词，我也想顺着大家的句子再读一遍。"
    )
    if feedback != "无" and "苏轼" not in body:
        body += "\n顺着苏轼再读一遍，情绪也会慢一点落下来。"
    return {
        "title": "读苏轼，突然不急着赢过今天了",
        "image_text": "风雨可以先慢一点",
        "body": body,
        "hashtags": ["#苏轼", "#诗词赏析", "#读书笔记", "#小红书读书"],
    }


def _build_wuxia_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，最适合拿令狐冲来讲。金庸在《笑傲江湖》里写他，不是写一个简单的浪子，"
        "而是写一个明明有能力进入体系、却始终无法把自己完全交给体系的人。\n"
        "原文里写他“行事但求无愧于心”，这句话常被读成潇洒，其实更像令狐冲的底层规则。"
        "他可以敬重师门，也可以珍惜朋友，但一旦规则要求他把人的鲜活感磨成标准答案，他就开始本能地后退。"
        "所以他在华山派里显得不够上进，在江湖里却反而更像一个完整的人。\n"
        "放到今天看，令狐冲像很多不愿被体制化的职场人。不是不想负责，也不是没有专业能力，"
        "而是害怕自己有一天只剩流程、汇报和绩效表，连喜欢什么、讨厌什么都要先看组织脸色。"
        "他真正珍贵的地方，不是喝酒，不是逃跑，而是能在关系、人情和权力夹缝里，还保留一点不被驯化的判断。\n"
        "这也是《笑傲江湖》最狠的地方：它写的不是“自由的人多快乐”，而是自由的人常常先被误解。"
        "岳不群需要他成为门派资产，江湖需要他选择阵营，旁观者需要他给出标准答案。"
        "可令狐冲偏偏最怕的就是把自己交给某种标准答案。\n"
        "适合截图的那一句是：令狐冲的自由不是不负责，而是不愿把良心外包给任何体系。"
        "这句话放在今天依然有刺。很多人不是不努力，而是不想用一生证明自己适合某套并不适合自己的考核表。"
        "他们可能会慢一点、别扭一点、显得不够合群一点，但那一点别扭，恰恰是自我还没被磨平的证据。\n"
        "更有意思的是，令狐冲并不是没有关系。他有师门、有朋友、有爱人，也会被人情拖住。"
        "所以他的自由不是把所有关系都切断，而是在关系里保留判断：谁值得信，哪条路不能走，"
        "什么评价听一听就好，什么底线不能交出去。这个层次，比单纯说他潇洒要复杂得多。\n"
        "所以我更愿意把令狐冲看成一种提醒：成长不只有被规训成“正确的人”这一条路。"
        "有些人最终要学会的，不是如何让所有人满意，而是如何承担“不被所有人理解”的代价。"
        "评论区想问问，你还想用今天的处境重读哪个金庸人物？我下一篇想写黄蓉或郭靖。"
    )
    if feedback != "无" and "#金庸" not in body:
        body += "\n重读金庸时，这个角度会更清楚。"
    return {
        "title": "令狐冲不是摆烂，他是不想被体制化",
        "image_text": "自由不是不负责",
        "body": body,
        "hashtags": ["#金庸", "#令狐冲", "#笑傲江湖", "#武侠", "#读书笔记"],
    }


def _build_world_cup_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    if any(keyword in scene for keyword in ("赛后", "终场", "点球", "逆转", "加时")):
        title = "这场世界杯赛后先复盘三件事"
        image_text = "终场后别急着只看比分"
        body = (
            f"{scene}。这类世界杯赛后内容，普通球迷可以先别急着把情绪压成一句输赢，"
            "先按三个看点复盘：比赛节奏什么时候变快，哪次边路推进最有威胁，"
            "以及替补上来后有没有改变中场连接。\n"
            "这份看球清单我会这样存：先回看开场15分钟的压迫，再看下半场体能变化，最后看终场前的定位球选择。"
            "这样聊球不会只剩吵架，也能把赛事情绪放回具体瞬间。\n"
            "评论区想问问，你赛后最想复盘的是哪一个回合，还是哪位球员的选择？"
        )
    elif any(keyword in scene for keyword in ("朋友", "宿舍", "酒吧", "客厅", "熬夜", "看球局")):
        title = "世界杯看球局先存这份清单"
        image_text = "普通球迷也能聊起来"
        body = (
            f"{scene}。世界杯好看的地方不只是强强对话，也有一群人一起等开球的赛事情绪。"
            "如果不是每个人都懂战术，可以先用三个看点把聊天拉到同一频道："
            "谁负责推进，哪一侧边路更活跃，定位球会不会成为转折。\n"
            "这份看球清单可以先这样存：开场看逼抢强度，中场看换人信号，赛后看哪次机会最可惜。"
            "不用争成专家，能一起看懂几个瞬间就很够了。\n"
            "评论区说说你看球时最在意氛围、球星，还是最后十分钟的心跳。"
        )
    else:
        title = "这场世界杯赛前，普通球迷看三点"
        image_text = "先看懂对位再开球"
        body = (
            f"{scene}。赛前不用把自己逼成战术分析师，普通球迷先抓三个看点就够了："
            "阿根廷能不能把中场节奏稳住，法国的边路速度会不会把防线拉开，"
            "以及定位球和替补变化会不会变成转折。\n"
            "这份看球清单可以先这样存：开场15分钟看谁压得更靠前，中场看哪边体能先掉，"
            "赛后再回看最接近进球的那次推进。这样看球，紧张会更具体，聊天也不只剩支持谁。\n"
            "评论区想问问，你最想看阿根廷的中场控制，还是法国的反击速度？"
        )

    body = _ensure_body_min_chars(
        body,
        minimum=220,
        addition="如果只想轻松看球，就先抓一个回合和一个换人信号，聊起来会更有画面。",
        before="评论区",
    )
    if feedback != "无" and "收藏" not in body:
        body += "\n也可以先存成一张赛前看球清单，开球后按顺序对照。"

    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": ["#世界杯", "#足球", "#看球笔记", "#赛前看点"],
    }


def _build_ai_tech_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"3秒核心信息：{scene}。这类更新值得看，不是因为它又喊了一句“AI改变世界”，"
        "而是它开始把多模态能力放进更日常的使用入口里。\n"
        "是什么：简单说，就是助手不只处理文字，还能把图片、语音、文件和上下文放在一起理解。"
        "你问一个问题，它不再只像搜索框，而更像能看材料、听需求、给步骤的工作搭子。\n"
        "为什么重要：过去很多 AI 产品卡在“演示很强，落地很窄”。多模态如果稳定下来，"
        "最先变化的会是学习整理、会议纪要、内容初稿、客服排查这类高频但重复的工作。\n"
        "普通人影响：暂时不用焦虑被替代，更现实的是先学会把任务说清楚。"
        "你给它的材料越具体，它越可能帮你省掉整理、改写和对照的时间。\n"
        "这份清单我会先按三点收藏：1. 看它能不能读懂你的真实文件；2. 看输出能不能追问修正；"
        "3. 看隐私和权限设置是否清楚。非投资建议，只是我对工具使用价值的观察。\n"
        "评论区想问问，你会先拿这种助手处理工作、学习，还是生活里的杂事？"
    )
    if feedback != "无" and "#AI资讯" not in body:
        body += "\n这条更适合放在 #AI资讯 方向里做工具观察。"
    return {
        "title": "这次AI更新，普通人先看这三点",
        "image_text": "别只看热闹，先看能不能真省事",
        "body": body,
        "hashtags": ["#AI资讯", "#人工智能", "#效率工具", "#科技观察"],
    }


def _build_daily_english_draft(*, scene: str, feedback: str) -> dict[str, Any]:
    body = (
        f"{scene}，今天可以学一个很实用的表达：follow up。\n"
        "音标：/ˈfɑːloʊ ʌp/\n"
        "词性：动词短语，也可以作名词。\n"
        "中文意思：继续跟进、补充确认，不是催命式追问，而是把事情往前推一步。\n"
        "真实场景例句：I’ll follow up with you after the meeting.\n"
        "翻译：会后我再跟你确认一下。\n"
        "这个句型我会直接收藏成：I’ll follow up with you after + 时间 / 事件。"
        "比如 after the call, after I check the file, after lunch，都能替换。\n"
        "小提醒：它比 ask again 更自然，也比 push you 更礼貌，适合开会、私聊、邮件都想显得稳一点的时候。\n"
        "评论区可以用 follow up 造句，我帮你看看哪一句更像真实英文。"
    )
    if feedback != "无" and "#每日英语" not in body:
        body += "\n这条适合放进 #每日英语 系列里慢慢积累。"
    return {
        "title": "follow up 不是催，是礼貌跟进",
        "image_text": "一句开会私聊都能用",
        "body": body,
        "hashtags": ["#每日英语", "#英语学习", "#实用英语", "#职场英语"],
    }


def _build_modern_psychology_draft(
    *, scene: str, feedback: str, runtime_context: str
) -> dict[str, Any]:
    if "三明治拒绝法" in scene:
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
    elif any(keyword in scene for keyword in ("短视频", "刷手机", "信息过载", "越刷越空")):
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
    elif any(keyword in scene for keyword in ("孤独", "聚会", "比较", "失败", "朋友圈")):
        body = (
            f"{scene}，照片里每个人都在笑，我却盯着那一桌菜想：是不是只有我今天没有被任何人想起。\n"
            "这种刺痛常常不只来自热闹本身，也来自比较焦虑和孤独感一起按下了扣分键。"
            "我会先写下来：我看见了什么、我给自己扣了什么分、今晚能给自己安排哪一个小恢复动作。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "最容易让你给自己扣分的高光片段是____"
        )
        title = "看到别人周末很热闹，不代表你失败"
        image_text = "别拿高光片段扣自己的分"
        hashtags = ["#心理学", "#情绪管理", "#孤独感", "#比较焦虑", "#自我成长"]
    elif any(keyword in scene for keyword in ("周日", "周一消息", "周一", "预焦虑")):
        body = (
            f"{scene}，人还在周日晚上，脑子已经把明天的消息提示音预演了三遍。"
            "牙还没刷，会议、催办、未读红点已经排队进场。\n"
            "这类周日晚预演常和低控制感有关：未知任务越多，大脑越想提前排雷。"
            "可以存一个 5分钟落地练习：写下最担心的1件事、能做的1个动作、暂时不用处理的1件事。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你周日晚上最常预演的是：A.开会 B.消息 C.被临时安排？"
        )
        title = "周日晚上，我已经听见周一消息提示音"
        image_text = "脑子提前打卡上班"
        hashtags = ["#心理学", "#情绪管理", "#周一焦虑", "#低控制感", "#自我成长"]
    elif any(keyword in scene for keyword in ("想太多", "睡不着", "边界")):
        body = (
            f"{scene}，那句话表面很轻，脑子却像被按下了整晚重播。"
            "你一边告诉自己算了，一边又把对方的语气、表情和停顿翻出来检查。\n"
            "这可能和边界压力有关：感受被轻轻带过时，大脑会继续确认自己是不是被误解。"
            "可以先存一句边界句：我知道你是好意，但这件事对我确实有影响，我需要一点时间整理。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.当场沉默 B.事后越想越委屈？"
        )
        title = "被说想太多后，我把那句话听了一晚上"
        image_text = "边界句先替你站稳"
        hashtags = ["#心理学", "#情绪管理", "#关系边界", "#自我成长"]
    elif any(keyword in scene for keyword in ("临时消息", "拉回工位", "下班身份", "工位")):
        body = (
            f"{scene}，鞋刚换好，外卖刚拆开，手机一亮，脑子就自动坐回工位。"
            "最累的是还没打开电脑，心已经开始排任务优先级。\n"
            "这常常是边界压力和低控制感叠在一起：你不确定自己能不能真的离线。"
            "可以存一个消息草稿：我看到了，明早到工位后先确认优先级，再回复进度。"
            "如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.秒回后内耗 B.写好边界句不敢发？"
        )
        title = "人下班了，脑子又被消息拽回去"
        image_text = "脑子又被拉回工位"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#关系边界", "#低控制感"]
    elif any(keyword in scene for keyword in ("会议", "尴尬")):
        body = (
            f"{scene}，身体已经离开会议室，脑子还在给那句话反复加字幕。"
            "我甚至能想象所有人回家路上突然想起它，然后在心里给我扣一分。"
            "电梯门关上的时候，我还在想，如果当时换个词，会不会显得更稳一点点。\n"
            "这种会后回放可以叫反刍思维：大脑想确认自己有没有说错、有没有被误解。"
            "我会把它写进事实 / 猜测 / 下一步：事实=对方原话；猜测=我补出的评价；"
            "下一步=明天要不要轻轻确认一次。如果痛苦持续、影响工作学习生活，或出现自伤想法，请尽快寻求专业帮助。\n"
            "你是哪派：A.写完小作文秒删 B.发了又后悔？"
        )
        title = "会议那句话，我在脑子里改到第七版"
        image_text = "把脑补写到猜测栏"
        hashtags = ["#心理学", "#情绪管理", "#职场焦虑", "#反刍思维"]
    elif any(keyword in scene for keyword in ("脑内", "白天的自己", "复盘会")):
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
    elif any(keyword in scene for keyword in ("普通回复", "收集大家", "常复盘")):
        body = (
            f"{scene}，一条普通回复发出去，脑子开始自动检查标点、语气和对方会不会多想。"
            "明明只是“好的”，我已经在想是不是该加个表情。\n"
            "这像是反刍思维在追求确定答案：聊天很少给满分判卷。"
            "可以存一个 5分钟停止循环法：先等 5 分钟，只问自己有新证据，还是在重复同一个担心。"
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
    body = _ensure_body_min_chars(
        body,
        minimum=350,
        addition=(
            "先把这件事写成一句具体问题，再把原话和脑补分开放。"
            "很多时候，真正让人累的不是那句话本身，而是后面自动补上的一整套剧情。"
            "我会把它当成一张小纸条存下来：左边写现实里发生了什么，右边写我脑内追加了什么，"
            "末尾只留一个明天能确认的小动作，让今晚先从审判里退出来。"
        ),
        before="如果痛苦持续",
    )

    if feedback != "无" and "专业帮助" not in body:
        body += "\n如果这些感受持续影响生活，请优先寻求专业帮助。"
    return {
        "title": title,
        "image_text": image_text,
        "body": body,
        "hashtags": hashtags,
    }


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
                "会议后的回放键，可以先暂停一下",
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
                "一句会议回音，不用想成判决书",
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


def _ensure_body_min_chars(
    body: str,
    *,
    minimum: int,
    addition: str,
    before: str | None = None,
) -> str:
    if len(body) >= minimum:
        return body
    if before is not None and before in body:
        return body.replace(before, f"{addition}{before}", 1)
    return f"{body}{addition}"
