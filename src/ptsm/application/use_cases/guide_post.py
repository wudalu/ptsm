from __future__ import annotations

from dataclasses import asdict, dataclass
import shlex
from typing import Any


SUPPORTED_PLAYBOOK_ID = "modern_psychology_post"
DEFAULT_ACCOUNT_ID = "acct-psychology-local"
IMAGE_STYLE_CHOICES = ("note_card", "iphone_notes", "wechat_chat")


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


@dataclass(frozen=True)
class PsychologyTopicDirection:
    id: str
    name: str
    why_it_may_work: str
    best_scenes: tuple[str, ...]
    content_angle: str
    saveable_tool: str
    comment_prompt: str
    avoid: str


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
        keywords=("关系", "边界", "朋友", "伴侣", "回复", "消息", "聊天", "已读"),
    ),
    PsychologyLane(
        name="数字生活 / 信息过载",
        mechanism="信息过载",
        reframe="停不下来不等于自控力差，很多时候是信息入口没有被温柔地收口。",
        save_tool="睡前 5 分钟收口法：关入口、写担心、留明天第一步",
        comment_prompt="你也可以在评论区写一个：最想提前收口的信息入口。",
        example_scene="睡前刷短视频停不下来，越刷越焦虑",
        keywords=("短视频", "手机", "刷", "信息", "过载", "熬夜", "睡前", "算法"),
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


PSYCHOLOGY_TOPIC_DIRECTIONS: tuple[PsychologyTopicDirection, ...] = (
    PsychologyTopicDirection(
        id="boundary_sandwich_refusal",
        name="边界感：三明治拒绝法",
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
    ),
    PsychologyTopicDirection(
        id="self_compassion_laoji",
        name="自我关怀：爱你老己",
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
    ),
    PsychologyTopicDirection(
        id="loofah_soup_communication",
        name="无效沟通：丝瓜汤式关心",
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
    ),
    PsychologyTopicDirection(
        id="ai_companion_boundary",
        name="数字关系：AI 陪伴边界",
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
    for candidate in PSYCHOLOGY_LANES:
        if any(keyword in scene_text for keyword in candidate.keywords):
            return candidate
    return PSYCHOLOGY_LANES[0]


def run_guide_post(request: GuidePostRequest) -> dict[str, Any]:
    if request.playbook_id != SUPPORTED_PLAYBOOK_ID:
        raise ValueError(
            f"guide-post only supports {SUPPORTED_PLAYBOOK_ID!r}; got {request.playbook_id!r}"
        )

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
    command = _build_run_playbook_command(
        account_id=request.account_id,
        scene=recommended_scene,
        image_style=image_style,
    )
    return {
        "status": "completed",
        "playbook_id": SUPPORTED_PLAYBOOK_ID,
        "account_id": request.account_id,
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


def format_guide_post_markdown(result: dict[str, Any]) -> str:
    brief = result["brief"]
    directions = "\n".join(
        f"- {direction['name']}：{direction['content_angle']}"
        for direction in result.get("topic_guidance", {}).get("directions", [])
    )
    checklist = "\n".join(
        f"- {item['item']}：{item['done_when']}" for item in result["quality_checklist"]
    )
    safety_notes = "\n".join(f"- {note}" for note in result["safety_notes"])
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
    return {
        "status": "available",
        "message": "这条心理学内容建议先从下面选一个方向，再进入生成。",
        "matched_direction_id": _match_topic_direction_id(scene=scene, lane_name=lane_name),
        "directions": [asdict(direction) for direction in PSYCHOLOGY_TOPIC_DIRECTIONS],
    }


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


def _build_run_playbook_command(
    *,
    account_id: str,
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
        SUPPORTED_PLAYBOOK_ID,
        "--publish-mode",
        "dry-run",
        "--auto-generate-image",
        "--local-image-style",
        image_style,
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
