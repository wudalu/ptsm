from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any

from ptsm.application.use_cases.topic_guidance_packs import TOPIC_GUIDANCE_PACKS
from ptsm.domain.topic_guidance import (
    TopicDirection,
    TopicPack,
    resolve_topic_lane,
    select_topic_directions,
)


SUPPORTED_PLAYBOOK_ID = "modern_psychology_post"
DEFAULT_ACCOUNT_ID = "acct-psychology-local"
IMAGE_STYLE_CHOICES = ("note_card", "iphone_notes", "wechat_chat")
SUPPORTED_PLAYBOOK_IDS = (SUPPORTED_PLAYBOOK_ID, *TOPIC_GUIDANCE_PACKS.keys())


@dataclass(frozen=True)
class GuidePostRequest:
    scene: str | None = None
    playbook_id: str = SUPPORTED_PLAYBOOK_ID
    account_id: str = DEFAULT_ACCOUNT_ID
    lane: str | None = None
    mechanism: str | None = None
    save_tool: str | None = None
    image_style: str | None = None
    comment_prompt: str | None = None


@dataclass(frozen=True)
class PsychologyLane:
    name: str
    mechanism: str
    reframe: str
    save_tool: str
    comment_prompt: str
    example_scene: str
    keywords: tuple[str, ...]
    image_style: str = "iphone_notes"


PSYCHOLOGY_LANES: tuple[PsychologyLane, ...] = (
    PsychologyLane(
        name="职场复盘 / 低控制感",
        mechanism="反刍思维",
        reframe="这不是你太脆弱，而是大脑在试图把失控感补成一个可解释的故事。",
        save_tool="三栏复盘法：事实、感受、下一次能试的一句话",
        comment_prompt="你也可以在评论区写一个：今天最想放过自己的小瞬间。",
        example_scene="下班后还在反复复盘白天会议里说错的一句话",
        keywords=("工作", "职场", "会议", "领导", "老板", "下班", "复盘", "工位"),
    ),
    PsychologyLane(
        name="关系边界 / 消息压力",
        mechanism="边界压力",
        reframe="你不是不近人情，只是在练习把关系里的责任放回合适的位置。",
        save_tool="边界句草稿：先确认、再表达限制、最后给一个可行选项",
        comment_prompt="你可以在评论区写一个：最难开口的边界句是什么？",
        example_scene="朋友临时把情绪都倒给我，我一边回复一边觉得自己快被掏空",
        keywords=("关系", "边界", "朋友", "伴侣", "回复", "消息", "聊天", "已读", "同事", "家人"),
    ),
    PsychologyLane(
        name="数字生活 / 信息过载",
        mechanism="信息过载",
        reframe="停不下来不等于自控力差，很多时候是信息入口没有被温柔地收口。",
        save_tool="睡前 5 分钟收口法：关入口、写担心、留明天第一步",
        comment_prompt="你也可以在评论区写一个：最想提前收口的信息入口。",
        example_scene="睡前刷短视频停不下来，越刷越焦虑",
        keywords=("短视频", "手机", "刷", "信息", "过载", "熬夜", "睡前", "算法", "AI", "ai", "分析", "越聊"),
    ),
    PsychologyLane(
        name="孤独 / 比较焦虑",
        mechanism="比较焦虑",
        reframe="别人正在热闹，不自动说明你失败；你只是被高光片段临时扣了分。",
        save_tool="比较暂停卡：我看见了什么、我脑补了什么、我此刻需要什么",
        comment_prompt="你会把这句话送给哪一个瞬间？",
        example_scene="看到别人周末都在聚会，自己突然觉得很孤独也很失败",
        keywords=("孤独", "比较", "周末", "聚会", "朋友圈", "失败", "别人", "热闹"),
    ),
    PsychologyLane(
        name="情绪调节 / 恢复练习",
        mechanism="情绪回避",
        reframe="情绪没有立刻消失，不代表你没做好；先让身体知道现在是安全的。",
        save_tool="90 秒落地练习：脚踩地、说出 3 个物体、慢慢呼气",
        comment_prompt="你可以在评论区写一个：今天想先安顿哪一种感受？",
        example_scene="明明没有发生大事，却突然觉得胸口很紧，什么都不想做",
        keywords=("情绪", "焦虑", "崩溃", "呼吸", "恢复", "失眠", "身体", "紧绷"),
    ),
    PsychologyLane(
        name="热点心理化重构",
        mechanism="情绪触发",
        reframe="公共事件可以触发很多旧感受，但我们不需要把任何人简单贴成病理标签。",
        save_tool="热点降噪三问：我被什么触发、哪些信息可靠、我能先照顾什么",
        comment_prompt="你可以在评论区写一个：这件事触发了你哪个普通人的感受？",
        example_scene="看到一个热搜后心里堵了很久，忍不住一直刷新相关讨论",
        keywords=("热搜", "热点", "新闻", "事件", "公共", "刷新", "讨论"),
        image_style="note_card",
    ),
)


PSYCHOLOGY_TOPIC_DIRECTIONS: tuple[TopicDirection, ...] = (
    TopicDirection(
        id="boundary_sandwich_refusal",
        name="边界感：三明治拒绝法",
        trend_signal="边界感 / 主体性",
        viral_hook="可保存话术卡",
        why_it_may_work="收藏价值强，用户能直接改成自己的拒绝话术。",
        best_scenes=(
            "同事临时加需求，不想答应但怕尴尬",
            "朋友一直倾倒情绪，自己已经被掏空",
            "家人提出要求，想拒绝又有负罪感",
        ),
        content_angle="不是你不近人情，是你在练习把责任放回合适的位置。",
        saveable_tool="先确认、再说明限制、最后给一个可行选项",
        comment_prompt="你最难开口的边界句是什么？",
        avoid="不要写成万能沟通术，不要鼓励冷暴力或突然断联。",
        lane_affinity=("关系边界", "职场复盘"),
        scene_keywords=(
            "拒绝",
            "边界",
            "加需求",
            "临时",
            "同事",
            "朋友",
            "家人",
            "负罪感",
        ),
        base_priority=8,
    ),
    TopicDirection(
        id="self_compassion_laoji",
        name="自我关怀：爱你老己",
        trend_signal="爱你老己 / 柔软力",
        viral_hook="低成本自我照顾动作",
        why_it_may_work="语气轻，不像鸡汤，适合让读者把失败感转成一个今天能做的小动作。",
        best_scenes=(
            "看到别人周末都在聚会，自己突然觉得很失败",
            "考砸或工作没做好，忍不住一直审判自己",
            "下班后想给自己一点非购物式照顾",
        ),
        content_angle="爱你老己不是奖励消费，而是把自己从审判席放下来。",
        saveable_tool="今天照顾老己的 3 个非购物动作",
        comment_prompt="你今天想怎么轻轻站到自己这边？",
        avoid="不要写成无边界利己，也不要把自我关怀变成消费口号。",
        lane_affinity=("孤独", "比较焦虑", "情绪调节", "职场复盘"),
        scene_keywords=("失败", "老己", "自己", "审判", "考砸", "没做好", "照顾"),
        base_priority=8,
    ),
    TopicDirection(
        id="loofah_soup_communication",
        name="无效沟通：丝瓜汤式关心",
        trend_signal="丝瓜汤式沟通 / 活人感",
        viral_hook="评论区交案例",
        why_it_may_work="用户容易交自己的案例，评论区天然会讨论假性关心和情绪被解释掉的委屈。",
        best_scenes=(
            "我表达真实不满，对方只让我想开点",
            "家人说是为你好，但我的感受完全没有被接住",
            "职场复盘里问题没被回应，只收到关心式压平",
        ),
        content_angle="真正让人委屈的不是关心本身，而是感受被绕过去了。",
        saveable_tool="事实 / 感受 / 需求三栏沟通卡",
        comment_prompt="你遇到过哪种看起来关心、其实没接住你的话？",
        avoid="只写沟通模式，不攻击某类人，不把家庭议题升级成对立。",
        lane_affinity=("关系边界", "职场复盘"),
        scene_keywords=("关心", "为你好", "想开点", "丝瓜汤", "感受", "安慰", "委屈"),
        base_priority=8,
    ),
    TopicDirection(
        id="ai_companion_boundary",
        name="数字关系：AI 陪伴边界",
        trend_signal="AI 生活搭子 / AI 人格",
        viral_hook="能力边界三问",
        why_it_may_work="新鲜且贴近当下，能把 AI 生活搭子的话题落到孤独、信息过载和情绪外包。",
        best_scenes=(
            "晚上只想跟 AI 说话，但说完反而更空",
            "用 AI 分析关系问题，越分析越停不下来",
            "把所有情绪都交给聊天工具后，现实关系更难开口",
        ),
        content_angle="AI 可以是临时搭子，但不该替你承担全部情绪关系。",
        saveable_tool="AI 陪伴边界三问：我想被接住什么、现实里谁能帮一点、现在先停在哪一步",
        comment_prompt="你会在什么时候最想找 AI 聊两句？",
        avoid="不要恐吓 AI 使用者，不做心理诊断，也不要承诺 AI 能替代专业帮助。",
        lane_affinity=("数字生活",),
        scene_keywords=("AI", "ai", "聊天工具", "陪伴", "数字", "越聊越空", "关系问题"),
        base_priority=6,
    ),
    TopicDirection(
        id="message_boundary_reply_draft",
        name="消息边界：三句不内耗回复",
        trend_signal="边界感 / 可复制句式",
        viral_hook="可复制回复模板",
        why_it_may_work="消息压力场景很高频，读者能把三句回复直接改成自己的版本。",
        best_scenes=(
            "领导下班后发来一句在吗",
            "朋友连续追问为什么不秒回",
            "客户临时催一个今晚不该完成的需求",
        ),
        content_angle="不是每条消息都需要立刻把你拉回关系现场。",
        saveable_tool="三句回复：我看到了、我现在不方便、我会在什么时间处理",
        comment_prompt="把你最难回的那条消息交出来，我帮你改成边界句。",
        avoid="不要写成教人消失，也不要把正常沟通都说成控制。",
        lane_affinity=("关系边界", "职场复盘"),
        scene_keywords=("消息", "回复", "秒回", "已读", "在吗", "催", "客户", "领导"),
        base_priority=3,
    ),
    TopicDirection(
        id="comparison_pause_card",
        name="比较焦虑：朋友圈高光降噪卡",
        trend_signal="反精致 / 活人感",
        viral_hook="三栏截图卡",
        why_it_may_work="比较焦虑有强代入感，三栏卡能把情绪从自责拉回现实信息。",
        best_scenes=(
            "看到别人周末都在旅行聚会，突然觉得自己失败",
            "刷到同龄人升职结婚买房，心里开始扣分",
            "发完朋友圈后反复比较点赞和评论",
        ),
        content_angle="别人展示的高光，不应该自动变成你今天的成绩单。",
        saveable_tool="比较暂停卡：我看见了什么、我脑补了什么、我现在需要什么",
        comment_prompt="哪一个高光片段最容易让你给自己扣分？",
        avoid="不要攻击分享生活的人，也不要把比较焦虑写成读者的错。",
        lane_affinity=("孤独", "比较焦虑"),
        scene_keywords=("比较", "朋友圈", "聚会", "周末", "别人", "点赞", "同龄人", "高光"),
        base_priority=6,
    ),
    TopicDirection(
        id="ai_overanalysis_stop_rule",
        name="AI 分析停不下来：三问刹车法",
        trend_signal="AI 生活搭子 / 信息过载",
        viral_hook="可保存停止规则",
        why_it_may_work="它把 AI 陪聊从新鲜话题落到真实使用风险：越分析越停不下来。",
        best_scenes=(
            "用 AI 分析一段关系，越问越乱",
            "反复让 AI 判断对方是不是讨厌自己",
            "深夜把聊天记录丢给 AI，越看越睡不着",
        ),
        content_angle="分析不是越多越安全，有时只是把不确定感延长了。",
        saveable_tool="停机三问：我已经知道什么、还缺什么现实信息、现在先停在哪里",
        comment_prompt="你最容易把哪类问题交给 AI 反复分析？",
        avoid="不要恐吓 AI 使用者，不把普通使用写成依赖诊断。",
        lane_affinity=("数字生活",),
        scene_keywords=("AI", "ai", "分析", "关系", "越聊越空", "越问越乱", "聊天记录"),
        base_priority=4,
    ),
    TopicDirection(
        id="sleep_scroll_closing_ritual",
        name="睡前信息收口：5 分钟下线仪式",
        trend_signal="睡前十分钟 / 低成本恢复",
        viral_hook="微仪式清单",
        why_it_may_work="睡前刷手机是普遍场景，5 分钟仪式比宏大自律建议更容易收藏。",
        best_scenes=(
            "睡前刷短视频停不下来，越刷越空",
            "想早点睡但总要再看一个帖子",
            "关掉手机后脑子还在滚动信息流",
        ),
        content_angle="停不下来不一定是自控力差，可能是入口没有被收口。",
        saveable_tool="5 分钟收口：关入口、写担心、留明天第一步",
        comment_prompt="你最想先收口的是哪个信息入口？",
        avoid="不要把熬夜都归因于懒，也不要给失眠治疗承诺。",
        lane_affinity=("数字生活", "情绪调节"),
        scene_keywords=("睡前", "短视频", "刷", "手机", "熬夜", "信息", "下线", "停不下来"),
        base_priority=5,
    ),
    TopicDirection(
        id="sunday_work_anxiety_reset",
        name="周日晚预焦虑：把明天缩小一点",
        trend_signal="打工人低控制感 / 周日晚",
        viral_hook="低门槛复盘卡",
        why_it_may_work="周日晚和周一前的低控制感很高频，适合做可保存的明日缩小练习。",
        best_scenes=(
            "周日晚上开始担心周一的会",
            "还没上班就已经在脑内排练明天",
            "休息日最后几个小时被工作感偷走",
        ),
        content_angle="你焦虑的不是明天本身，而是明天在脑子里被放大成了一整面墙。",
        saveable_tool="明天缩小卡：一件必须做、一件可以晚点、一句开场话",
        comment_prompt="你想把明天先缩小成哪一件事？",
        avoid="不要鼓励逃避必要工作，也不要把持续功能受损轻描淡写。",
        lane_affinity=("职场复盘", "情绪调节"),
        scene_keywords=("周日", "周一", "明天", "上班", "工作", "会议", "预焦虑"),
        base_priority=5,
    ),
    TopicDirection(
        id="emotion_grounding_90s",
        name="情绪上头：90 秒落地练习",
        trend_signal="柔软力 / 身体感",
        viral_hook="低成本动作",
        why_it_may_work="它把抽象情绪调节变成马上能做的小动作，降低心理学内容的说教感。",
        best_scenes=(
            "突然胸口很紧，什么都不想做",
            "吵完架后脑子还在转",
            "收到坏消息后手心发麻",
        ),
        content_angle="情绪没有立刻消失，不代表你失败；先让身体知道现在是安全的。",
        saveable_tool="90 秒落地：脚踩地、说出 3 个物体、慢慢呼气",
        comment_prompt="你今天想先安顿哪一种感受？",
        avoid="不要替代专业帮助，也不要承诺练习能处理所有危机。",
        lane_affinity=("情绪调节",),
        scene_keywords=("情绪", "焦虑", "崩溃", "胸口", "呼吸", "紧", "手心", "上头"),
        base_priority=5,
    ),
    TopicDirection(
        id="hot_search_noise_three_questions",
        name="热搜降噪：别把公共情绪全背回家",
        trend_signal="热点心理化重构 / 信息降噪",
        viral_hook="三问降噪卡",
        why_it_may_work="它能承接热点讨论，但把重点放在普通人的情绪边界，不追逐诊断或站队。",
        best_scenes=(
            "看到热搜后心里堵了很久",
            "公共事件刷太多，越看越愤怒",
            "一边刷新讨论一边觉得自己被耗尽",
        ),
        content_angle="公共事件会触发旧感受，但你不需要把所有情绪都背回家。",
        saveable_tool="热点降噪三问：我被什么触发、哪些信息可靠、我现在能照顾什么",
        comment_prompt="这件事触发了你哪个普通人的感受？",
        avoid="不要借热点做诊断，不输出未经确认的信息或极端立场。",
        lane_affinity=("热点心理化重构", "数字生活"),
        scene_keywords=("热搜", "热点", "新闻", "事件", "公共", "刷新", "讨论", "愤怒"),
        base_priority=5,
    ),
    TopicDirection(
        id="real_support_role_pair",
        name="真实支持系统：谁是你的怀民",
        trend_signal="角色认领 / 关系支持",
        viral_hook="A/B 角色评论入口",
        why_it_may_work="角色认领比泛泛谈孤独更容易评论，能自然讨论 AI 和现实支持的边界。",
        best_scenes=(
            "半夜很想找个人说话，但不知道找谁",
            "发现自己只敢跟 AI 讲真实感受",
            "朋友一句普通关心让自己突然被接住",
        ),
        content_angle="真正让人缓过来的，有时不是大道理，而是有人知道你还醒着。",
        saveable_tool="支持系统三格：能听我说的人、能陪我做事的人、现在可先联系的一步",
        comment_prompt="你更像半夜叫人的那个人，还是会被叫起来的那个人？",
        avoid="不要把现实关系浪漫化，也不要说 AI 或任何单一对象能承接全部情绪。",
        lane_affinity=("孤独", "关系边界", "数字生活"),
        scene_keywords=("孤独", "半夜", "支持", "被接住", "AI", "ai", "陪伴", "朋友"),
        base_priority=4,
    ),
    TopicDirection(
        id="office_recovery_without_shopping",
        name="办公室轻恢复：不靠消费的下班信号",
        trend_signal="轻恢复 / 反消费自我关怀",
        viral_hook="低成本动作清单",
        why_it_may_work="它把自我关怀从消费奖励拉回可执行动作，适合职场和恢复练习场景。",
        best_scenes=(
            "下班后想照顾自己，但不想靠买东西",
            "工位上一整天都很紧绷",
            "回家路上还像没从工作里出来",
        ),
        content_angle="照顾自己不一定要奖励消费，也可以是给身体一个下班信号。",
        saveable_tool="3 个不花钱下班信号：换姿势、洗杯子、走慢 5 分钟",
        comment_prompt="你今天想给自己哪个下班信号？",
        avoid="不要把低成本动作写成治愈承诺，也不要羞辱正常消费。",
        lane_affinity=("职场复盘", "情绪调节"),
        scene_keywords=("下班", "工位", "办公室", "消费", "购物", "恢复", "照顾自己"),
        base_priority=4,
    ),
)


def resolve_psychology_lane(
    *,
    lane: str | None = None,
    scene: str | None = None,
) -> PsychologyLane:
    if lane:
        stripped = lane.strip()
        if stripped.isdigit():
            idx = int(stripped)
            if 1 <= idx <= len(PSYCHOLOGY_LANES):
                return PSYCHOLOGY_LANES[idx - 1]
        for candidate in PSYCHOLOGY_LANES:
            if stripped == candidate.name or stripped in candidate.name:
                return candidate
        available = ", ".join(item.name for item in PSYCHOLOGY_LANES)
        raise ValueError(f"Unknown psychology lane {lane!r}. Available lanes: {available}")

    scene_text = scene or ""
    ranked = [
        (_keyword_hits(scene_text, candidate.keywords), index, candidate)
        for index, candidate in enumerate(PSYCHOLOGY_LANES)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if ranked and ranked[0][0] > 0:
        return ranked[0][2]
    return PSYCHOLOGY_LANES[0]


def run_guide_post(request: GuidePostRequest) -> dict[str, Any]:
    if request.playbook_id == SUPPORTED_PLAYBOOK_ID:
        return _run_psychology_guide_post(request)

    pack = TOPIC_GUIDANCE_PACKS.get(request.playbook_id)
    if pack is None:
        supported = ", ".join(SUPPORTED_PLAYBOOK_IDS)
        raise ValueError(
            f"guide-post supports {supported}; got {request.playbook_id!r}"
        )
    return _run_generic_guide_post(request=request, pack=pack)


def _run_psychology_guide_post(request: GuidePostRequest) -> dict[str, Any]:
    lane = resolve_psychology_lane(lane=request.lane, scene=request.scene)
    scene = _clean_or_default(request.scene, lane.example_scene)
    mechanism = _clean_or_default(request.mechanism, lane.mechanism)
    save_tool = _clean_or_default(request.save_tool, lane.save_tool)
    image_style = _clean_or_default(request.image_style, lane.image_style)
    if image_style not in IMAGE_STYLE_CHOICES:
        raise ValueError(
            f"Unknown image style {image_style!r}. Available styles: {', '.join(IMAGE_STYLE_CHOICES)}"
        )
    comment_prompt = _clean_or_default(request.comment_prompt, lane.comment_prompt)
    safety_boundary = (
        "只做非诊断化心理教育：不下诊断、不承诺治疗效果、不提供药物建议；"
        "如果痛苦持续、影响生活或出现危机风险，引导寻求专业帮助。"
    )

    brief = {
        "lane": lane.name,
        "scene": scene,
        "mechanism": mechanism,
        "reframe": lane.reframe,
        "save_tool": save_tool,
        "image_style": image_style,
        "image_form": {
            "backend": "local_social_screenshot",
            "style": image_style,
            "role": "save_tool" if image_style == "iphone_notes" else "cover_hook",
            "text_density": "low",
            "max_text_units": 3,
        },
        "comment_prompt": comment_prompt,
        "safety_boundary": safety_boundary,
    }
    recommended_scene = _build_recommended_scene(brief)
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        default_account_id=DEFAULT_ACCOUNT_ID,
    )
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        scene=recommended_scene,
        image_style=image_style,
    )
    return {
        "status": "completed",
        "playbook_id": SUPPORTED_PLAYBOOK_ID,
        "account_id": account_id,
        "brief": brief,
        "topic_guidance": build_psychology_topic_guidance(scene=scene, lane_name=lane.name),
        "recommended_scene": recommended_scene,
        "run_playbook_command": command,
        "run_playbook_command_text": shlex.join(command),
        "quality_checklist": _build_quality_checklist(),
        "safety_notes": [
            "不要把读者描述成有病、人格有问题或需要被治疗。",
            "不要给药物、诊断、治疗方案或危机处置承诺。",
            "遇到自伤、他伤、持续失眠或功能受损等危机信号时，提示联系当地专业支持。",
        ],
    }


def _run_generic_guide_post(
    *,
    request: GuidePostRequest,
    pack: TopicPack,
) -> dict[str, Any]:
    lane = resolve_topic_lane(
        lanes=pack.lanes,
        lane=request.lane,
        scene=request.scene,
    )
    scene = _clean_or_default(request.scene, lane.default_scene)
    save_tool = _clean_or_default(request.save_tool, lane.default_saveable_tool)
    image_style = _clean_or_default(request.image_style, lane.default_image_style)
    if image_style not in IMAGE_STYLE_CHOICES:
        raise ValueError(
            f"Unknown image style {image_style!r}. Available styles: {', '.join(IMAGE_STYLE_CHOICES)}"
        )
    comment_prompt = _clean_or_default(
        request.comment_prompt,
        lane.default_comment_prompt,
    )
    brief = {
        "lane": lane.name,
        "scene": scene,
        "content_angle": lane.default_content_angle,
        "save_tool": save_tool,
        "image_style": image_style,
        "image_form": {
            "backend": "local_social_screenshot",
            "style": image_style,
            "role": "save_tool" if image_style == "iphone_notes" else "cover_hook",
            "text_density": "low",
            "max_text_units": 3,
        },
        "comment_prompt": comment_prompt,
    }
    recommended_scene = _build_generic_recommended_scene(brief)
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=pack.playbook_id,
        default_account_id=pack.default_account_id,
    )
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=pack.playbook_id,
        scene=recommended_scene,
        image_style=image_style,
    )
    return {
        "status": "completed",
        "playbook_id": pack.playbook_id,
        "account_id": account_id,
        "brief": brief,
        "topic_guidance": build_topic_guidance(
            pack=pack,
            scene=scene,
            lane_name=lane.name,
        ),
        "recommended_scene": recommended_scene,
        "run_playbook_command": command,
        "run_playbook_command_text": shlex.join(command),
        "quality_checklist": _build_generic_quality_checklist(),
        "safety_notes": [
            "不要展示内部研究路径、原始研究笔记、来源 URL 或 provenance。",
            "不要把选题引导写成已经完成的生成结果；先确认方向，再 dry-run 生成。",
        ],
    }


def format_guide_post_markdown(result: dict[str, Any]) -> str:
    brief = result["brief"]
    directions = "\n".join(
        f"- {direction['name']}（trend: {direction['trend_signal']} / "
        f"hook: {direction['viral_hook']}）：{direction['content_angle']}"
        for direction in result.get("topic_guidance", {}).get("directions", [])
    )
    checklist = "\n".join(
        f"- {item['item']}：{item['done_when']}" for item in result["quality_checklist"]
    )
    safety_notes = "\n".join(f"- {note}" for note in result["safety_notes"])
    if "mechanism" not in brief:
        return "\n".join(
            [
                "# Topic Guidance Brief",
                "",
                f"- playbook_id: {result['playbook_id']}",
                f"- account_id: {result['account_id']}",
                f"- lane: {brief['lane']}",
                f"- scene: {brief['scene']}",
                f"- content_angle: {brief['content_angle']}",
                f"- save_tool: {brief['save_tool']}",
                f"- image_style: {brief['image_style']}",
                f"- comment_prompt: {brief['comment_prompt']}",
                "",
                "## Topic Directions",
                "",
                directions,
                "",
                "## Recommended Scene",
                "",
                result["recommended_scene"],
                "",
                "## Quality Checklist",
                "",
                checklist,
                "",
                "## Safety Notes",
                "",
                safety_notes,
                "",
                "## Dry-run Command",
                "",
                f"`{result['run_playbook_command_text']}`",
            ]
        )
    return "\n".join(
        [
            "# Psychology Guidance Brief",
            "",
            f"- lane: {brief['lane']}",
            f"- scene: {brief['scene']}",
            f"- mechanism: {brief['mechanism']}",
            f"- reframe: {brief['reframe']}",
            f"- save_tool: {brief['save_tool']}",
            f"- image_style: {brief['image_style']}",
            f"- comment_prompt: {brief['comment_prompt']}",
            "",
            "## Topic Directions",
            "",
            directions,
            "",
            "## Recommended Scene",
            "",
            result["recommended_scene"],
            "",
            "## Quality Checklist",
            "",
            checklist,
            "",
            "## Safety Notes",
            "",
            safety_notes,
            "",
            "## Dry-run Command",
            "",
            f"`{result['run_playbook_command_text']}`",
        ]
    )


def build_psychology_topic_guidance(*, scene: str = "", lane_name: str = "") -> dict[str, Any]:
    directions = select_topic_directions(
        directions=PSYCHOLOGY_TOPIC_DIRECTIONS,
        scene=scene,
        lane_name=lane_name,
    )
    matched_direction_id = (
        directions[0]["id"]
        if directions
        else _match_topic_direction_id(scene=scene, lane_name=lane_name)
    )
    return {
        "status": "available",
        "message": "这条心理学内容建议先从下面选一个方向，再进入生成。",
        "matched_direction_id": matched_direction_id,
        "directions": directions,
    }


def build_topic_guidance(
    *,
    pack: TopicPack,
    scene: str = "",
    lane_name: str = "",
) -> dict[str, Any]:
    directions = select_topic_directions(
        directions=pack.directions,
        scene=scene,
        lane_name=lane_name,
    )
    return {
        "status": "available",
        "message": pack.guidance_message,
        "matched_direction_id": directions[0]["id"] if directions else "",
        "directions": directions,
    }


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in normalized_text)


def _match_topic_direction_id(*, scene: str, lane_name: str) -> str:
    text = f"{lane_name} {scene}"
    if any(keyword in text for keyword in ("拒绝", "边界", "同事", "朋友", "家人", "责任")):
        return "boundary_sandwich_refusal"
    if any(keyword in text for keyword in ("失败", "老己", "自己", "比较", "审判")):
        return "self_compassion_laoji"
    if any(keyword in text for keyword in ("关心", "为你好", "想开点", "丝瓜汤", "感受")):
        return "loofah_soup_communication"
    if any(keyword in text for keyword in ("AI", "ai", "聊天工具", "陪伴", "数字")):
        return "ai_companion_boundary"
    return "boundary_sandwich_refusal"


def _clean_or_default(value: str | None, default: str) -> str:
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _build_recommended_scene(brief: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"选题lane：{brief['lane']}",
            f"第一人称微场景：{brief['scene']}",
            f"心理机制：{brief['mechanism']}",
            f"非诊断化重构：{brief['reframe']}",
            f"可保存小工具：{brief['save_tool']}",
            f"封面形式：{brief['image_style']}，低密度，只放 1-3 个短文字单元",
            f"评论提示：{brief['comment_prompt']}",
            f"专业边界：{brief['safety_boundary']}",
        ]
    )


def _build_generic_recommended_scene(brief: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"选题lane：{brief['lane']}",
            f"第一人称微场景：{brief['scene']}",
            f"内容角度：{brief['content_angle']}",
            f"可保存小工具：{brief['save_tool']}",
            f"封面形式：{brief['image_style']}，低密度，只放 1-3 个短文字单元",
            f"评论提示：{brief['comment_prompt']}",
        ]
    )


def _resolve_account_id(
    *,
    request_account_id: str | None,
    playbook_id: str,
    default_account_id: str,
) -> str:
    if not request_account_id:
        return default_account_id
    if playbook_id != SUPPORTED_PLAYBOOK_ID and request_account_id == DEFAULT_ACCOUNT_ID:
        return default_account_id
    return request_account_id


def _build_run_playbook_command(
    *,
    account_id: str,
    playbook_id: str,
    scene: str,
    image_style: str,
) -> list[str]:
    return [
        "uv",
        "run",
        "python",
        "-m",
        "ptsm.bootstrap",
        "run-playbook",
        "--scene",
        scene,
        "--account-id",
        account_id,
        "--playbook-id",
        playbook_id,
        "--publish-mode",
        "dry-run",
        "--auto-generate-image",
        "--local-image-style",
        image_style,
    ]


def _build_generic_quality_checklist() -> list[dict[str, str]]:
    return [
        {
            "item": "具体生活场景",
            "done_when": "开头能让读者立刻看见一个普通、可代入的瞬间。",
        },
        {
            "item": "一个内容角度",
            "done_when": "正文围绕一个明确切口展开，不堆多个选题。",
        },
        {
            "item": "可保存结构",
            "done_when": "给出三步以内、今天能试或能改写的小工具。",
        },
        {
            "item": "评论入口",
            "done_when": "评论提示让用户补自己的例子、角色或作业。",
        },
        {
            "item": "低密度封面",
            "done_when": "封面只放 1-3 个短文字单元，不塞长解释。",
        },
    ]


def _build_quality_checklist() -> list[dict[str, str]]:
    return [
        {
            "item": "第一人称微场景",
            "done_when": "开头能让读者立刻看见一个普通生活瞬间。",
        },
        {
            "item": "一个心理机制",
            "done_when": "正文只解释一个机制，不堆多个概念。",
        },
        {
            "item": "非诊断化重构",
            "done_when": "用这更像、可能是、可以先试这样的语气，避免病理化读者。",
        },
        {
            "item": "可保存小工具",
            "done_when": "给出三步以内、今天能试的小动作或句式。",
        },
        {
            "item": "例子型评论",
            "done_when": "评论提示让用户补充自己的例子，而不是回答抽象观点。",
        },
        {
            "item": "专业边界",
            "done_when": "说明内容不是诊断或治疗，严重或持续痛苦需要专业帮助。",
        },
        {
            "item": "低密度封面",
            "done_when": "封面只放 1-3 个短文字单元，不塞心理机制长解释。",
        },
    ]
