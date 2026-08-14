from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from html import escape as html_escape
import shlex
from typing import Any

from ptsm.application.use_cases.psychology_learning_series import (
    PsychologyLearningSeriesStore,
)
from ptsm.application.use_cases.topic_guidance_packs import TOPIC_GUIDANCE_PACKS
from ptsm.domain.topic_guidance import (
    FormatRecommendation,
    TopicDirection,
    TopicPack,
    resolve_topic_lane,
    select_topic_directions,
)
from ptsm.domain.psychology_learning import (
    PSYCHOLOGY_LEARNING_MODE,
    STARTER_SERIES_ID,
    list_psychology_learning_series,
    load_confirmed_psychology_learning_catalog,
    render_psychology_learning_draft,
    resolve_psychology_learning_selection,
)


SUPPORTED_PLAYBOOK_ID = "modern_psychology_post"
DEFAULT_ACCOUNT_ID = "acct-psychology-local"
IMAGE_STYLE_CHOICES = ("note_card", "iphone_notes", "wechat_chat")
SUPPORTED_PLAYBOOK_IDS = (SUPPORTED_PLAYBOOK_ID, *TOPIC_GUIDANCE_PACKS.keys())
TOPIC_GUIDANCE_SELECTION_POLICY = "dynamic_scene_diversity_rerank"
IMAGE_RECOMMENDATION_DECISION_STAGE = "after_topic_direction_confirmation"
AI_TECH_PLAYBOOK_ID = "ai_tech_daily_post"
AI_TECH_CONTENT_MODES = ("news_brief", "hands_on", "fact_translation")
PSYCHOLOGY_LEARNING_CONTENT_MODE = PSYCHOLOGY_LEARNING_MODE
PROVIDER_IMAGE_PROVIDER = "bailian"
PROVIDER_IMAGE_MODEL = "qwen-image-2.0-pro"
CHAT_IMAGE_KEYWORDS = (
    "消息",
    "回复",
    "聊天",
    "群聊",
    "对话",
    "评论接龙",
    "接一句",
    "在吗",
    "秒回",
    "已读",
    "英文回复",
    "发来",
    "怎么回",
)
SAVE_TOOL_IMAGE_KEYWORDS = (
    "边界句",
    "三栏",
    "清单",
    "练习",
    "步骤",
    "句型",
    "单词",
    "词汇",
    "小任务",
    "看点清单",
    "复盘顺序",
    "保存",
    "工具",
    "5 分钟",
    "5分钟",
    "三问",
    "三句",
)
NOTE_CARD_IMAGE_KEYWORDS = (
    "古诗词",
    "诗词金句",
    "经典诗句",
    "李白",
    "李清照",
    "王维",
    "杜甫",
    "苏轼",
    "怀民",
    "定风波",
    "一句",
    "金句",
    "短句",
    "重构",
    "判断",
    "角色",
)
PROVIDER_IMAGE_KEYWORDS = (
    "书桌",
    "角落",
    "床头",
    "材料",
    "手作",
    "过程",
    "完成品",
    "空间",
    "物件",
    "路线",
    "colorwalk",
    "球衣",
    "围巾",
    "客厅",
    "设备",
    "界面",
    "人物",
    "姿态",
    "氛围",
    "场景",
    "产品",
    "食物",
    "房间",
    "桌面",
    "改造",
)
RELATIONSHIP_UNCERTAINTY_IMAGE_KEYWORDS = (
    "亲密关系 / 不确定感",
    "关系不确定感",
    "事实 / 脑补 / 我需要什么",
    "分手",
    "猫归谁",
    "没回消息",
    "不回消息",
    "3小时",
    "挽留",
    "复合",
    "冷淡",
)
VISUAL_EVIDENCE_PLAYBOOK_IDS = (
    "human_enrichment_daily_post",
    "wuxia_character_post",
)


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
    ai_content_mode: str | None = None
    ai_evidence_file_path: str | None = None
    psychology_content_mode: str | None = None
    psychology_series_id: str | None = None
    psychology_lesson_id: str | None = None
    psychology_curriculum_version: str | None = None


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
        reframe="大脑在试图把失控感补成一个可解释的故事。",
        save_tool="三栏复盘法：事实、感受、下一次能试的一句话",
        comment_prompt="你是哪派：A.写完小作文秒删 B.发了又后悔？",
        example_scene="下班后还在反复复盘白天会议里说错的一句话",
        keywords=(
            "工作",
            "职场",
            "会议",
            "领导",
            "老板",
            "下班",
            "复盘",
            "工位",
            "18:57",
            "下班消息",
            "在吗",
            "拉回工位",
            "临时消息",
        ),
    ),
    PsychologyLane(
        name="亲密关系 / 不确定感",
        mechanism="关系不确定感",
        reframe="先把事实、脑补和真正想确认的需要分开放，别急着把沉默写成结局。",
        save_tool="事实 / 脑补 / 我需要什么",
        comment_prompt="你是哪派：A.没回就脑补到分手 B.忍住不问但越想越多？",
        example_scene="他3小时没回消息，我已经想好分手后猫归谁了",
        keywords=(
            "分手",
            "猫归谁",
            "没回消息",
            "不回消息",
            "3小时",
            "伴侣",
            "挽留",
            "复合",
            "冷淡",
            "突然冷淡",
            "忽冷忽热",
            "暧昧",
            "要不要问",
            "想问清楚",
            "站队",
            "怕烦",
        ),
    ),
    PsychologyLane(
        name="关系边界 / 消息压力",
        mechanism="边界压力",
        reframe="练习边界，是把关系里的责任放回合适的位置。",
        save_tool="边界句草稿：先确认、再表达限制、最后给一个可行选项",
        comment_prompt="你是哪派：A.写好边界句不敢发 B.发了又怕冷？",
        example_scene="朋友临时把情绪都倒给我，我一边回复一边觉得自己快被掏空",
        keywords=("关系", "边界", "朋友", "伴侣", "回复", "消息", "聊天", "已读", "同事", "家人"),
    ),
    PsychologyLane(
        name="数字生活 / 信息过载",
        mechanism="信息过载",
        reframe="停不下来不等于自控力差，很多时候是信息入口没有被温柔地收口。",
        save_tool="睡前 5 分钟收口法：关入口、写担心、留明天第一步",
        comment_prompt="你睡前停不下来通常在刷：A.短视频 B.聊天记录 C.搜索答案？",
        example_scene="睡前刷短视频停不下来，越刷越焦虑",
        keywords=("短视频", "手机", "刷", "信息", "过载", "熬夜", "睡前", "算法", "AI", "ai", "分析", "越聊"),
    ),
    PsychologyLane(
        name="孤独 / 比较焦虑",
        mechanism="比较焦虑",
        reframe="别人正在热闹，不自动说明你失败；你只是被高光片段临时扣了分。",
        save_tool="比较暂停卡：我看见了什么、我脑补了什么、我此刻需要什么",
        comment_prompt="最容易让你给自己扣分的高光片段是____",
        example_scene="看到别人周末都在聚会，自己突然觉得很孤独也很失败",
        keywords=(
            "孤独",
            "比较",
            "周末",
            "聚会",
            "朋友圈",
            "失败",
            "别人",
            "热闹",
            "社交耗竭",
            "社交电量",
            "取消",
            "约好的局",
            "扫兴",
            "不想去",
        ),
    ),
    PsychologyLane(
        name="情绪调节 / 恢复练习",
        mechanism="情绪回避",
        reframe="情绪没有立刻消失，不代表你没做好；先让身体知道现在是安全的。",
        save_tool="90 秒落地练习：脚踩地、说出 3 个物体、慢慢呼气",
        comment_prompt="你是哪派：A.先沉默 B.先找人说 C.先刷手机？",
        example_scene="明明没有发生大事，却突然觉得胸口很紧，什么都不想做",
        keywords=("情绪", "焦虑", "崩溃", "呼吸", "恢复", "失眠", "身体", "紧绷"),
    ),
    PsychologyLane(
        name="睡眠恢复 / 轻养生",
        mechanism="身体收口",
        reframe="身体没有立刻松下来，不代表你矫情；它只是还没收到下班和入睡的信号。",
        save_tool="5 分钟下班信号：关入口、松肩颈、写明天第一步",
        comment_prompt="你最需要哪种下班信号：A.身体放松 B.脑子停机 C.手机下线？",
        example_scene="办公室下班后还是很紧绷，想写一个睡眠恢复和轻养生的5分钟下班信号",
        keywords=(
            "睡眠恢复",
            "轻养生",
            "办公室恢复",
            "下班信号",
            "疲惫",
            "睡前",
            "下线",
            "紧绷",
            "5分钟",
            "5 分钟",
        ),
    ),
    PsychologyLane(
        name="热点心理化重构",
        mechanism="情绪触发",
        reframe="公共事件可以触发很多旧感受，但我们不需要把任何人简单贴成病理标签。",
        save_tool="热点降噪三问：我被什么触发、哪些信息可靠、我能先照顾什么",
        comment_prompt="这件事触发你的普通人感受是____",
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
        content_angle="真正难的不是拒绝本身，而是把责任放回合适的位置。",
        saveable_tool="先确认、再说明限制、最后给一个可行选项",
        comment_prompt="你是哪派：A.边界句写好不敢发 B.发了又怕冷？",
        avoid="不要写成万能沟通术，不要鼓励冷暴力或突然断联。",
        format_recommendation=FormatRecommendation(
            format_archetype="note_card",
            cover_role="save_tool",
            body_shape="micro scene / 3-part boundary sentence / A-B comment vote",
            visual_evidence_need="low",
            avoid_format=("dense_text_poster", "universal_script_wall"),
        ),
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
        comment_prompt="你今天想站到自己这边的动作是____",
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
        comment_prompt="你是哪派：A.当场沉默 B.事后越想越委屈？",
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
        comment_prompt="你最想找 AI 聊两句的时候通常是____",
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
        content_angle="一条消息不该总是把你立刻拉回关系现场。",
        saveable_tool="三句回复：我看到了、我现在不方便、我会在什么时间处理",
        comment_prompt="你是哪派：A.秒回后内耗 B.写好边界句不敢发？",
        avoid="不要写成教人消失，也不要把正常沟通都说成控制。",
        lane_affinity=("关系边界", "职场复盘"),
        scene_keywords=("消息", "回复", "秒回", "已读", "在吗", "催", "客户", "领导"),
        base_priority=3,
    ),
    TopicDirection(
        id="relationship_mixed_signal_camp_vote",
        name="关系忽冷忽热：要不要问清楚",
        trend_signal="关系不确定感 / A-B 阵营",
        viral_hook="评论区站队",
        why_it_may_work="忽冷忽热有强代入和强分歧，A/B 阵营能把读者从围观带到评论认领。",
        best_scenes=(
            "对方忽冷忽热，我想问清楚又怕显得烦",
            "暧昧关系突然冷淡，不知道要不要追问",
            "朋友或伴侣态度变了，自己一直在猜是不是做错了什么",
        ),
        content_angle="不急着替对方下结论，先分开事实、信号和自己真正想确认的需要。",
        saveable_tool="事实 / 信号 / 我要不要问清楚",
        comment_prompt="你是哪派：A.问清楚 B.先观察？",
        avoid="不要教读者读心，不把冷淡默认成背叛，也不要鼓励逼问或冷处理。",
        lane_affinity=("亲密关系", "关系边界"),
        scene_keywords=(
            "忽冷忽热",
            "突然冷淡",
            "冷淡",
            "暧昧",
            "要不要问",
            "想问清楚",
            "站队",
            "怕烦",
            "不确定",
        ),
        base_priority=10,
        diversity_key="relationship-camp-vote",
    ),
    TopicDirection(
        id="relationship_uncertainty_waiting_message",
        name="亲密关系：没回消息后的脑内分手剧场",
        trend_signal="关系不确定感 / 角色认领",
        viral_hook="从没回消息演到分手后猫归谁",
        why_it_may_work="强场景有自嘲和关系认领感，读者容易在评论区认领自己是哪种等消息的人。",
        best_scenes=(
            "他3小时没回消息，我已经想好分手后猫归谁了",
            "对方突然冷淡，我已经在脑内排练分手",
            "发完消息没人回，越等越想确认自己是不是被丢下",
        ),
        content_angle="写等消息时不确定感如何把一个安静手机补成分手剧本，而不是教人发职场协作式边界句。",
        saveable_tool="事实 / 脑补 / 我需要什么",
        comment_prompt="你是哪派：A.没回就脑补到分手 B.忍住不问但越想越多？",
        avoid="不要写成职场回复、处理时间或催对方秒回；也不要默认对方有错或把不回消息病理化。",
        lane_affinity=("亲密关系", "关系边界"),
        scene_keywords=(
            "分手",
            "猫归谁",
            "没回消息",
            "不回消息",
            "3小时",
            "伴侣",
            "挽留",
            "复合",
            "冷淡",
        ),
        base_priority=9,
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
        comment_prompt="最容易让你给自己扣分的高光片段是____",
        avoid="不要攻击分享生活的人，也不要把比较焦虑写成读者的错。",
        lane_affinity=("孤独", "比较焦虑"),
        scene_keywords=("比较", "朋友圈", "聚会", "周末", "别人", "点赞", "同龄人", "高光"),
        base_priority=6,
    ),
    TopicDirection(
        id="social_battery_cancel_plan_boundary",
        name="社交电量：临时不想去的边界",
        trend_signal="社交耗竭 / 低成本边界",
        viral_hook="A/B 角色认领",
        why_it_may_work="取消局的愧疚和社交耗竭都很高频，读者容易在评论里认领自己是硬去派还是取消派。",
        best_scenes=(
            "约好的局临时不想去了，怕扫兴又很累",
            "社交电量快没了，但已经答应朋友见面",
            "周末聚会前突然很想躲起来，又怕自己扫大家兴",
        ),
        content_angle="有边界不是不珍惜关系，而是先承认自己现在的电量。",
        saveable_tool="取消局三句：承认约定、说明状态、给下一次选项",
        comment_prompt="你是哪派：A.硬着头皮去 B.愧疚地取消？",
        avoid="不要羞辱社交，也不要鼓励突然消失；给低风险、可解释的边界表达。",
        lane_affinity=("孤独", "关系边界", "情绪调节"),
        scene_keywords=(
            "社交耗竭",
            "社交电量",
            "约好的局",
            "不想去了",
            "不想去",
            "取消",
            "扫兴",
            "聚会",
            "很累",
            "硬着头皮",
        ),
        base_priority=10,
        diversity_key="social-battery-boundary",
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
        comment_prompt="你最容易交给 AI 反复分析的问题是____",
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
        content_angle="睡前停不下来，常常是入口还没有被收口。",
        saveable_tool="5 分钟收口：关入口、写担心、留明天第一步",
        comment_prompt="你睡前最想先收口的是：A.短视频 B.聊天 C.搜索？",
        avoid="不要把熬夜都归因于懒，也不要给失眠治疗承诺。",
        lane_affinity=("数字生活", "情绪调节", "睡眠恢复", "轻养生"),
        scene_keywords=("睡前", "短视频", "刷", "手机", "熬夜", "信息", "下线", "停不下来"),
        base_priority=5,
    ),
    TopicDirection(
        id="after_hours_message_body_alarm",
        name="下班消息：身体被拉回工位",
        trend_signal="下班消息 / 身体警报",
        viral_hook="A/B/C 工位身份评论",
        why_it_may_work="下班消息有强点击瞬间，身体被拉回工位的说法能把职场低控制感和评论站队接起来。",
        best_scenes=(
            "领导18:57发来一句在吗，下班后身体被消息拉回工位",
            "人已经到家，临时消息又把脑子拽回工位",
            "下班后看到工作消息，身体先紧了一下",
        ),
        content_angle="真正累人的不只是一条消息，而是身体又被拉回待命状态。",
        saveable_tool="下班消息三步：先看紧急度、给处理时间、把身体带回来",
        comment_prompt="你是哪派：A.秒回 B.装没看见 C.先写明天再回？",
        avoid="不要教人消失，也不要把必要沟通都写成控制；保留现实工作边界。",
        lane_affinity=("职场复盘", "关系边界", "情绪调节"),
        scene_keywords=(
            "18:57",
            "下班消息",
            "在吗",
            "领导",
            "临时消息",
            "消息",
            "拉回工位",
            "工位",
            "下班",
            "身体",
        ),
        base_priority=10,
        diversity_key="after-hours-message-body-alarm",
    ),
    TopicDirection(
        id="sleep_recovery_shutdown_card",
        name="睡眠恢复：办公室下班信号卡",
        trend_signal="轻养生 / 办公室恢复",
        viral_hook="5 分钟低成本恢复卡",
        why_it_may_work="睡眠和轻养生有常青需求，5 分钟下班信号能把收藏动作、身体感和职场场景连起来。",
        best_scenes=(
            "办公室下班后身体还很紧绷，回家也睡不踏实",
            "想写睡眠恢复，但不想做医疗建议或养生玄学",
            "下班后还像在工位上，想给身体一个停机信号",
        ),
        content_angle="不是教人立刻睡好，而是把身体从工作模式轻轻带回生活模式。",
        saveable_tool="5 分钟下班信号：关入口、松肩颈、写明天第一步",
        comment_prompt="你最需要哪种下班信号：A.身体放松 B.脑子停机 C.手机下线？",
        avoid="不要承诺改善睡眠，不给医疗、营养、药物或治疗建议。",
        format_recommendation=FormatRecommendation(
            format_archetype="note_card",
            cover_role="save_tool",
            body_shape="office shutdown scene / 5-minute recovery card / non-medical boundary note / A-B-C comment vote",
            visual_evidence_need="low",
            avoid_format=("dense_text_poster", "medical_before_after"),
        ),
        lane_affinity=("睡眠恢复", "轻养生", "情绪调节", "职场复盘"),
        scene_keywords=(
            "睡眠恢复",
            "轻养生",
            "办公室",
            "办公室恢复",
            "下班信号",
            "5分钟",
            "5 分钟",
            "疲惫",
            "紧绷",
            "睡前",
            "下线",
        ),
        base_priority=9,
        diversity_key="sleep-recovery-tool",
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
        content_angle="周日晚最累的地方，是明天在脑子里被放大成一整面墙。",
        saveable_tool="明天缩小卡：一件必须做、一件可以晚点、一句开场话",
        comment_prompt="你想把明天先缩小成哪一件事____",
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
        comment_prompt="你是哪派：A.先沉默 B.先找人说 C.先刷手机？",
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
        comment_prompt="这件事触发你的普通人感受是____",
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
        comment_prompt="你更像：A.半夜叫人的那个人 B.会被叫起来的人？",
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
        comment_prompt="你今天想给自己哪个下班信号____",
        avoid="不要把低成本动作写成治愈承诺，也不要羞辱正常消费。",
        lane_affinity=("职场复盘", "情绪调节", "睡眠恢复", "轻养生"),
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
    psychology_learning_requested = _is_psychology_learning_request(request)
    if (
        psychology_learning_requested
        and request.playbook_id != SUPPORTED_PLAYBOOK_ID
    ):
        raise ValueError(
            "psychology learning guidance is only supported by modern_psychology_post"
        )
    if request.playbook_id == SUPPORTED_PLAYBOOK_ID:
        if psychology_learning_requested:
            return _run_psychology_learning_series_guide_post(request)
        return _run_psychology_guide_post(request)

    pack = TOPIC_GUIDANCE_PACKS.get(request.playbook_id)
    if pack is None:
        supported = ", ".join(SUPPORTED_PLAYBOOK_IDS)
        raise ValueError(
            f"guide-post supports {supported}; got {request.playbook_id!r}"
        )
    if pack.playbook_id == AI_TECH_PLAYBOOK_ID:
        return _run_ai_tech_guide_post(request=request, pack=pack)
    return _run_generic_guide_post(request=request, pack=pack)


def _is_psychology_learning_request(request: GuidePostRequest) -> bool:
    mode = (request.psychology_content_mode or "").strip()
    has_selection = any(
        value is not None
        for value in (
            request.psychology_series_id,
            request.psychology_lesson_id,
            request.psychology_curriculum_version,
        )
    )
    if not mode and has_selection:
        raise ValueError(
            "psychology_content_mode=learning_series is required when selecting a psychology learning series"
        )
    if not mode:
        return False
    if mode != PSYCHOLOGY_LEARNING_CONTENT_MODE:
        raise ValueError(
            "psychology_content_mode must be learning_series for modern psychology learning guidance"
        )
    return True


def _run_psychology_learning_series_guide_post(
    request: GuidePostRequest,
) -> dict[str, Any]:
    series_id = (request.psychology_series_id or "").strip()
    if not series_id:
        raise ValueError("psychology_series_id is required for learning_series guidance")
    requested_curriculum_version = (
        (request.psychology_curriculum_version or "").strip()
    )
    lesson_id = (request.psychology_lesson_id or "").strip()
    if (
        series_id != STARTER_SERIES_ID
        and lesson_id
        and not requested_curriculum_version
    ):
        raise ValueError(
            "custom psychology learning selection requires an explicit curriculum_version"
        )
    lessons = list_psychology_learning_series(
        series_id=series_id,
        curriculum_version=requested_curriculum_version or None,
    )
    curriculum_version = lessons[0].curriculum_version
    custom_catalog = (
        load_confirmed_psychology_learning_catalog(
            series_id=series_id,
            curriculum_version=curriculum_version,
        )
        if series_id != STARTER_SERIES_ID
        else None
    )
    series_payload: dict[str, Any] = {
        "series_id": series_id,
        "series_title": lessons[0].series_title,
        "curriculum_version": curriculum_version,
        "roadmap": [lesson.roadmap_item for lesson in lessons],
    }
    if custom_catalog is not None:
        series_payload["origin"] = custom_catalog.origin
        series_payload.update(
            _build_custom_psychology_learning_sequence(custom_catalog)
        )
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        default_account_id=DEFAULT_ACCOUNT_ID,
    )
    directions = [lesson.public_direction for lesson in lessons]
    if not lesson_id:
        return {
            "status": "selection_required",
            "playbook_id": SUPPORTED_PLAYBOOK_ID,
            "account_id": account_id,
            "series": series_payload,
            "topic_guidance": {
                "status": "selection_required",
                "message": "请先从已审核路线中明确选择一课；未选择时不会默认生成第一课。",
                "selection_policy": "catalog_learning_series",
                "matched_direction_id": "",
                "open_direction_id": "",
                "open_direction_ids": [],
                "direction_type_counts": {"learning_series_lesson": len(lessons)},
                "directions": directions,
            },
            "next_step": _psychology_learning_selection_next_step(
                curriculum_version=curriculum_version,
                requires_explicit_version=custom_catalog is not None,
            ),
            "quality_checklist": _build_psychology_learning_quality_checklist(),
            "safety_notes": _psychology_learning_safety_notes(),
        }
    bundle = resolve_psychology_learning_selection(
        series_id=series_id,
        lesson_id=lesson_id,
        curriculum_version=curriculum_version,
    )
    contract = bundle.runtime_contract
    image_plan = render_psychology_learning_draft(contract)["image_plan"]
    image_style = str(image_plan.get("carousel_style") or image_plan["style"])
    image_recommendation = _build_psychology_learning_image_recommendation(
        image_plan=image_plan
    )
    brief = {
        "content_mode": PSYCHOLOGY_LEARNING_CONTENT_MODE,
        "series_id": bundle.series_id,
        "series_title": contract["series_title"],
        "curriculum_version": contract["curriculum_version"],
        "lesson_id": bundle.lesson_id,
        "lesson_number": bundle.lesson_number,
        "lesson_title": contract["lesson_title"],
        "concept_label": contract["concept_label"],
        "learning_goal": contract["learning_goal"],
        "micro_exercise": contract["micro_exercise"],
        "image_style": image_style,
        "image_form": {
            "backend": image_plan["backend"],
            "style": image_style,
            "role": image_plan["role"],
            "text_density": image_plan["text_density"],
            "max_text_units": int(image_plan["max_text_units"]),
            **(
                {
                    "format_archetype": "text_carousel",
                    "carousel_style": image_plan["carousel_style"],
                    "page_count": {
                        "min": len(image_plan["slides"]),
                        "max": len(image_plan["slides"]),
                    },
                }
                if isinstance(image_plan.get("slides"), list)
                else {}
            ),
        },
    }
    topic_guidance = {
        "status": "available",
        "message": "这是已审核的学习专题课次；确认一课后再生成，不用自由场景改写概念。",
        "selection_policy": "catalog_learning_series",
        "matched_direction_id": bundle.direction_id,
        "open_direction_id": "",
        "open_direction_ids": [],
        "direction_type_counts": {"learning_series_lesson": len(lessons)},
        "directions": directions,
        "image_recommendation": image_recommendation,
    }
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        scene=None,
        # The catalog renderer owns this image plan. Passing a local style
        # would make a succeeding guide command fail the learning preflight.
        image_style=None,
        topic_direction_id=bundle.direction_id,
        psychology_content_mode=PSYCHOLOGY_LEARNING_CONTENT_MODE,
        psychology_series_id=bundle.series_id,
        psychology_lesson_id=bundle.lesson_id,
        psychology_curriculum_version=contract["curriculum_version"],
    )
    return {
        "status": "completed",
        "playbook_id": SUPPORTED_PLAYBOOK_ID,
        "account_id": account_id,
        "brief": brief,
        "series": series_payload,
        "topic_guidance": topic_guidance,
        "recommended_scene": _build_psychology_learning_recommended_scene(
            contract=contract,
            image_recommendation=image_recommendation,
        ),
        "run_playbook_command": command,
        "run_playbook_command_text": shlex.join(command),
        "quality_checklist": _build_psychology_learning_quality_checklist(),
        "safety_notes": _psychology_learning_safety_notes(),
    }


def _build_custom_psychology_learning_sequence(catalog: Any) -> dict[str, Any]:
    """Expose safe operator posting advice from a frozen custom curriculum.

    This is intentionally content-production state, not a reader-learning
    tracker. A recommendation is informative only: the caller must still name
    a lesson id before any guide command becomes available.
    """
    progress = PsychologyLearningSeriesStore().read_production_progress(
        series_id=catalog.series_id,
        curriculum_version=catalog.curriculum_version,
    )
    lessons_by_id = {lesson.lesson_id: lesson for lesson in catalog.lessons}
    publication_plan = [
        {
            "publication_order": item.publication_order,
            "lesson_id": item.lesson_id,
            "canonical_lesson_number": item.canonical_lesson_number,
            "lesson_title": lessons_by_id[item.lesson_id].lesson_title,
            "instructional_stage": item.instructional_stage,
            "rationale": item.rationale,
        }
        for item in catalog.publication_plan.items
    ]
    completed_lesson_ids = set(progress.completed_lesson_ids)
    production_progress = {
        "kind": "operator_content_production",
        "completed_lesson_ids": list(progress.completed_lesson_ids),
        "completed_count": len(progress.completed_lesson_ids),
        "total_lessons": len(catalog.lessons),
    }
    recommended = next(
        (
            item
            for item in publication_plan
            if item["lesson_id"] not in completed_lesson_ids
        ),
        None,
    )
    if recommended is None:
        return {
            "publication_plan": publication_plan,
            "production_progress": production_progress,
            "recommended_next_lesson": None,
            "recommended_next_lesson_id": None,
            "recommendation_status": "all_completed",
            "recommendation_message": "所有建议发布课次均已完成；没有下一课建议。",
        }
    return {
        "publication_plan": publication_plan,
        "production_progress": production_progress,
        "recommended_next_lesson": recommended,
        "recommended_next_lesson_id": recommended["lesson_id"],
        "recommendation_status": "recommended",
        "recommendation_message": "这是建议发布顺序；请仍然明确选择 lesson_id，不会自动选课。",
    }


def _psychology_learning_selection_next_step(
    *,
    curriculum_version: str,
    requires_explicit_version: bool,
) -> str:
    """Tell custom-series callers how to pin the reviewed immutable revision."""
    if requires_explicit_version:
        return (
            "Choose one returned learning_series_lesson lesson_id and pass "
            f"--psychology-curriculum-version {curriculum_version} when requesting "
            "guidance again before generating the post."
        )
    return (
        "Choose one returned learning_series_lesson lesson_id, then request guidance "
        "again before generating the post."
    )


def _run_ai_tech_guide_post(
    *,
    request: GuidePostRequest,
    pack: TopicPack,
) -> dict[str, Any]:
    content_mode = _require_ai_tech_content_mode(request.ai_content_mode)
    lane = resolve_topic_lane(
        lanes=pack.lanes,
        lane=request.lane,
        scene=request.scene,
    )
    scene = _clean_or_default(request.scene, lane.default_scene)
    image_style = _clean_or_default(request.image_style, pack.default_image_style)
    if image_style not in IMAGE_STYLE_CHOICES:
        raise ValueError(
            f"Unknown image style {image_style!r}. Available styles: {', '.join(IMAGE_STYLE_CHOICES)}"
        )
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=pack.playbook_id,
        default_account_id=pack.default_account_id,
    )
    evidence_required = _ai_tech_evidence_requirement(content_mode)
    brief = {
        "lane": lane.name,
        "scene": scene,
        "content_mode": content_mode,
        "evidence_required": evidence_required,
        "image_style": image_style,
        "image_form": {
            "backend": "local_social_screenshot",
            "style": image_style,
            "role": "cover_hook",
            "text_density": "low",
            "max_text_units": 2,
        },
    }
    topic_guidance = build_topic_guidance(
        pack=pack,
        scene=scene,
        lane_name=lane.name,
        brief=brief,
        content_mode=content_mode,
    )
    image_recommendation = topic_guidance["image_recommendation"]
    matched_direction_id = str(topic_guidance["matched_direction_id"])
    recommended_scene = _build_ai_tech_recommended_scene(
        content_mode=content_mode,
        evidence_required=evidence_required,
        image_recommendation=image_recommendation,
        brief=brief,
    )
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=pack.playbook_id,
        scene=None,
        image_style=(
            str(image_recommendation["local_style"])
            if image_recommendation["recommended_backend"] == "local_social_screenshot"
            else None
        ),
        topic_direction_id=matched_direction_id,
        ai_content_mode=content_mode,
        ai_evidence_file_path=request.ai_evidence_file_path,
    )
    return {
        "status": "completed",
        "playbook_id": pack.playbook_id,
        "account_id": account_id,
        "brief": brief,
        "topic_guidance": topic_guidance,
        "recommended_scene": recommended_scene,
        "run_playbook_command": command,
        "run_playbook_command_text": shlex.join(command),
        "quality_checklist": _build_ai_tech_quality_checklist(content_mode),
        "safety_notes": [
            "热点只用于选择方向；正文只能使用证据文件中的已核验事实或测试记录。",
            "不要把来源 URL、作者、原始标题或未记录的体验写进正文。",
            "提示词相关内容也必须是一次可复现的 hands_on 测试复盘，不提供通用可复制模板。",
        ],
    }


def _run_psychology_guide_post(request: GuidePostRequest) -> dict[str, Any]:
    lane = resolve_psychology_lane(lane=request.lane, scene=request.scene)
    scene = _clean_or_default(request.scene, lane.example_scene)
    mechanism = _clean_or_default(request.mechanism, lane.mechanism)
    save_tool = _clean_or_default(request.save_tool, lane.save_tool)
    explicit_image_style = (request.image_style or "").strip()
    if explicit_image_style and explicit_image_style not in IMAGE_STYLE_CHOICES:
        raise ValueError(
            f"Unknown image style {explicit_image_style!r}. Available styles: {', '.join(IMAGE_STYLE_CHOICES)}"
        )
    image_style = explicit_image_style or "psychology_text_card_v1"
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
        "image_form": (
            {
                "backend": "local_social_screenshot",
                "style": image_style,
                "role": "save_tool" if image_style == "iphone_notes" else "cover_hook",
                "text_density": "low",
                "max_text_units": 3,
            }
            if explicit_image_style
            else {
                "backend": "local_social_screenshot",
                "style": "psychology_text_card",
                "role": "text_carousel",
                "text_density": "medium",
                "max_text_units": 4,
                "format_archetype": "text_carousel",
                "carousel_style": "psychology_text_card_v1",
                "page_count": {"min": 4, "max": 7},
            }
        ),
        "comment_prompt": comment_prompt,
        "safety_boundary": safety_boundary,
    }
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        default_account_id=DEFAULT_ACCOUNT_ID,
    )
    topic_guidance = build_psychology_topic_guidance(
        scene=scene,
        lane_name=lane.name,
        brief=brief,
    )
    image_recommendation = topic_guidance["image_recommendation"]
    recommended_scene = _build_recommended_scene(
        brief,
        image_recommendation=image_recommendation,
    )
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=SUPPORTED_PLAYBOOK_ID,
        scene=recommended_scene,
        image_style=(
            str(image_recommendation["local_style"])
            if explicit_image_style
            and image_recommendation["recommended_backend"] == "local_social_screenshot"
            else None
        ),
    )
    return {
        "status": "completed",
        "playbook_id": SUPPORTED_PLAYBOOK_ID,
        "account_id": account_id,
        "brief": brief,
        "topic_guidance": topic_guidance,
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
    account_id = _resolve_account_id(
        request_account_id=request.account_id,
        playbook_id=pack.playbook_id,
        default_account_id=pack.default_account_id,
    )
    topic_guidance = build_topic_guidance(
        pack=pack,
        scene=scene,
        lane_name=lane.name,
        brief=brief,
    )
    image_recommendation = topic_guidance["image_recommendation"]
    recommended_scene = _build_generic_recommended_scene(
        brief,
        image_recommendation=image_recommendation,
    )
    command = _build_run_playbook_command(
        account_id=account_id,
        playbook_id=pack.playbook_id,
        scene=recommended_scene,
        image_style=(
            str(image_recommendation["local_style"])
            if image_recommendation["recommended_backend"] == "local_social_screenshot"
            else None
        ),
    )
    return {
        "status": "completed",
        "playbook_id": pack.playbook_id,
        "account_id": account_id,
        "brief": brief,
        "topic_guidance": topic_guidance,
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
    if result.get("status") == "selection_required":
        return _format_psychology_learning_selection_markdown(result)
    brief = result["brief"]
    directions = "\n".join(
        _format_topic_direction_markdown(direction)
        for direction in result.get("topic_guidance", {}).get("directions", [])
    )
    checklist = "\n".join(
        f"- {item['item']}：{item['done_when']}" for item in result["quality_checklist"]
    )
    safety_notes = "\n".join(f"- {note}" for note in result["safety_notes"])
    image_recommendation = _format_image_recommendation(
        result.get("topic_guidance", {}).get("image_recommendation")
    )
    if brief.get("content_mode") == PSYCHOLOGY_LEARNING_CONTENT_MODE:
        series = result.get("series", {})
        roadmap = series.get("roadmap", []) if isinstance(series, dict) else []
        roadmap_lines = "\n".join(
            f"- 第{item['lesson_number']}课：{_markdown_inline(item['lesson_title'])}"
            f"（{_markdown_inline(item['learning_goal'])}）"
            for item in roadmap
            if isinstance(item, dict)
        )
        sequence_lines = _format_custom_psychology_learning_sequence_markdown(
            series if isinstance(series, dict) else {}
        )
        return "\n".join(
            [
                "# Psychology Learning Series Brief",
                "",
                f"- playbook_id: {result['playbook_id']}",
                f"- account_id: {result['account_id']}",
                f"- series: {_markdown_inline(brief['series_title'])} ({brief['series_id']})",
                f"- curriculum_version: {brief['curriculum_version']}",
                f"- selected_lesson: 第{brief['lesson_number']}课 {_markdown_inline(brief['lesson_title'])}",
                f"- concept: {_markdown_inline(brief['concept_label'])}",
                "",
                "## Series Roadmap",
                "",
                roadmap_lines,
                *sequence_lines,
                "",
                "## Topic Directions",
                "",
                directions,
                "",
                "## Image Recommendation",
                "",
                image_recommendation,
                "",
                "## Selected Lesson Contract",
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
    if "content_mode" in brief:
        return "\n".join(
            [
                "# AI Tech Evidence Brief",
                "",
                f"- playbook_id: {result['playbook_id']}",
                f"- account_id: {result['account_id']}",
                f"- lane: {brief['lane']}",
                f"- content_mode: {brief['content_mode']}",
                f"- evidence_required: {brief['evidence_required']}",
                f"- image_style: {brief['image_style']}",
                "",
                "## Topic Directions",
                "",
                directions,
                "",
                "## Image Recommendation",
                "",
                image_recommendation,
                "",
                "## Evidence Gate",
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
                "## Image Recommendation",
                "",
                image_recommendation,
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
            "## Image Recommendation",
            "",
            image_recommendation,
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


def _format_topic_direction_markdown(direction: dict[str, Any]) -> str:
    format_recommendation = direction.get("format_recommendation")
    if not isinstance(format_recommendation, dict):
        format_recommendation = {}
    render_value = (
        _markdown_inline
        if _is_custom_psychology_learning_direction(direction)
        else str
    )
    return (
        f"- {render_value(direction['name'])}（trend: "
        f"{render_value(direction['trend_signal'])} / "
        f"type: {render_value(direction.get('direction_type', 'curated'))} / "
        f"mode: {render_value(direction.get('content_mode', ''))} / "
        f"hook: {render_value(direction['viral_hook'])} / "
        f"format: {render_value(format_recommendation.get('format_archetype', ''))} / "
        f"cover: {render_value(format_recommendation.get('cover_role', ''))} / "
        f"visual: {render_value(format_recommendation.get('visual_evidence_need', ''))} / "
        f"fit: {render_value(direction.get('scene_fit', ''))}）"
        f"：{render_value(direction['content_angle'])}"
    )


def _is_custom_psychology_learning_direction(direction: dict[str, Any]) -> bool:
    """Identify topic directions whose prose comes from operator input."""
    return (
        direction.get("direction_type") == "learning_series_lesson"
        and direction.get("series_id") != STARTER_SERIES_ID
    )


def _markdown_inline(value: object) -> str:
    """Render untrusted text as one literal Markdown line.

    HTML escaping happens before Markdown escaping so an entity-looking input
    cannot be decoded back into a tag by a downstream Markdown renderer.
    """
    text = html_escape(" ".join(str(value).split()), quote=False)
    markdown_control_characters = frozenset("\\`*_{}[]()#+-.!|~")
    return "".join(
        f"\\{character}" if character in markdown_control_characters else character
        for character in text
    )


def _format_image_recommendation(recommendation: Any) -> str:
    if not isinstance(recommendation, dict):
        return "- status: unavailable"
    lines = [
            f"- decision_stage: {recommendation['decision_stage']}",
            f"- recommended_backend: {recommendation['recommended_backend']}",
            f"- local_style: {recommendation['local_style']}",
            f"- provider: {recommendation['provider']}",
            f"- model: {recommendation['model']}",
            f"- role: {recommendation['role']}",
            f"- text_density: {recommendation['text_density']}",
            f"- max_text_units: {recommendation['max_text_units']}",
            f"- reason: {recommendation['reason']}",
            f"- command_hint: `{recommendation['command_hint']}`",
            f"- fallback: {recommendation['fallback']}",
    ]
    if recommendation.get("format_archetype") == "text_carousel":
        page_count = recommendation["page_count"]
        lines.extend(
            [
                "- format_archetype: text_carousel",
                f"- carousel_style: {recommendation['carousel_style']}",
                f"- page_count: {page_count['min']}-{page_count['max']}",
                f"- ordered_roles: {', '.join(recommendation['ordered_roles'])}",
            ]
        )
    return "\n".join(lines)


def build_psychology_topic_guidance(
    *,
    scene: str = "",
    lane_name: str = "",
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    directions = select_topic_directions(
        directions=PSYCHOLOGY_TOPIC_DIRECTIONS,
        scene=scene,
        lane_name=lane_name,
        include_open_slot=True,
        dynamic_breadth=True,
    )
    return {
        "status": "available",
        "message": "这条心理学内容建议先从下面选一个方向，再进入生成。",
        "directions": directions,
        **_topic_guidance_selection_metadata(
            directions=directions,
            fallback_matched_direction_id=_match_topic_direction_id(
                scene=scene,
                lane_name=lane_name,
            ),
        ),
        "image_recommendation": _build_image_recommendation(
            playbook_id=SUPPORTED_PLAYBOOK_ID,
            scene=scene,
            lane_name=lane_name,
            brief=brief or {},
        ),
    }


def build_topic_guidance(
    *,
    pack: TopicPack,
    scene: str = "",
    lane_name: str = "",
    brief: dict[str, Any] | None = None,
    content_mode: str | None = None,
) -> dict[str, Any]:
    directions = select_topic_directions(
        directions=pack.directions,
        scene=scene,
        lane_name=lane_name,
        include_open_slot=content_mode is None,
        dynamic_breadth=content_mode is None,
        content_mode=content_mode,
    )
    if content_mode is not None and not directions:
        raise ValueError(
            f"No evidence-backed topic direction is available for ai_content_mode={content_mode!r}"
        )
    return {
        "status": "available",
        "message": (
            _ai_tech_guidance_message(content_mode)
            if pack.playbook_id == AI_TECH_PLAYBOOK_ID and content_mode is not None
            else pack.guidance_message
        ),
        "directions": directions,
        **_topic_guidance_selection_metadata(directions=directions),
        "image_recommendation": _build_image_recommendation(
            playbook_id=pack.playbook_id,
            scene=scene,
            lane_name=lane_name,
            brief=brief or {},
        ),
    }


def _build_image_recommendation(
    *,
    playbook_id: str,
    scene: str,
    lane_name: str,
    brief: dict[str, Any],
) -> dict[str, Any]:
    image_form = brief.get("image_form")
    if (
        playbook_id == SUPPORTED_PLAYBOOK_ID
        and isinstance(image_form, dict)
        and image_form.get("format_archetype") == "text_carousel"
    ):
        return _psychology_text_carousel_recommendation()

    signal_text = " ".join(
        str(value)
        for value in (
            scene,
            lane_name,
            brief.get("save_tool", ""),
            brief.get("mechanism", ""),
        )
        if value
    )
    if playbook_id == SUPPORTED_PLAYBOOK_ID and _contains_any(
        signal_text,
        RELATIONSHIP_UNCERTAINTY_IMAGE_KEYWORDS,
    ):
        return _local_image_recommendation(
            style="iphone_notes",
            role="save_tool",
            max_text_units=3,
            reason="这个方向要把亲密关系里的事实、脑补和需要分开放，用 iPhone 备忘录式工具卡比聊天截图更准确。",
        )
    if _contains_any(scene, CHAT_IMAGE_KEYWORDS):
        return _local_image_recommendation(
            style="wechat_chat",
            role="comment_prompt",
            max_text_units=2,
            reason="这个方向的首屏资产是消息、对话或可复制回复，用微信聊天截图更容易触发评论接龙。",
        )
    if _needs_provider_image(playbook_id=playbook_id, signal_text=signal_text):
        return _provider_image_recommendation()
    if _contains_any(signal_text, SAVE_TOOL_IMAGE_KEYWORDS):
        return _local_image_recommendation(
            style="iphone_notes",
            role="save_tool",
            max_text_units=3,
            reason="这个方向需要用户保存边界句、步骤或工具卡，用 iPhone 备忘录式截图更清楚。",
        )
    if _contains_any(signal_text, NOTE_CARD_IMAGE_KEYWORDS):
        return _local_image_recommendation(
            style="note_card",
            role="cover_hook",
            max_text_units=2,
            reason="这个方向适合把一句强判断或短重构放在封面上，用笔记卡保持低密度。",
        )

    style = _normalize_local_image_style(
        image_form.get("style") if isinstance(image_form, dict) else None,
        brief.get("image_style"),
    )
    if style == "wechat_chat":
        return _local_image_recommendation(
            style=style,
            role="comment_prompt",
            max_text_units=2,
            reason="沿用当前 playbook 的本地聊天截图样式，只保留少量对话或评论入口。",
        )
    if style == "iphone_notes":
        return _local_image_recommendation(
            style=style,
            role="save_tool",
            max_text_units=3,
            reason="沿用当前 playbook 的本地备忘录样式，把选定方向收束成可保存工具卡。",
        )
    return _local_image_recommendation(
        style="note_card",
        role="cover_hook",
        max_text_units=2,
        reason="当前方向不依赖真实空间或物件证据，用低密度笔记卡承接封面钩子。",
    )


def _needs_provider_image(*, playbook_id: str, signal_text: str) -> bool:
    if playbook_id in VISUAL_EVIDENCE_PLAYBOOK_IDS:
        return True
    return _contains_any(signal_text, PROVIDER_IMAGE_KEYWORDS)


def _provider_image_recommendation() -> dict[str, Any]:
    return {
        "status": "available",
        "decision_stage": IMAGE_RECOMMENDATION_DECISION_STAGE,
        "recommended_backend": "provider_image",
        "local_style": "",
        "provider": PROVIDER_IMAGE_PROVIDER,
        "model": PROVIDER_IMAGE_MODEL,
        "role": "evidence_or_scene",
        "text_density": "low",
        "max_text_units": 1,
        "reason": "这个方向需要看见空间、物件、材料、人物或场景证据，用 LLM/provider 图片更适合做视觉氛围。",
        "command_hint": "--auto-generate-image",
        "fallback": "如果没有 provider 配置，退回 --local-image-style note_card，只保留一个短判断，避免伪装真实证据。",
    }


def _local_image_recommendation(
    *,
    style: str,
    role: str,
    max_text_units: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "available",
        "decision_stage": IMAGE_RECOMMENDATION_DECISION_STAGE,
        "recommended_backend": "local_social_screenshot",
        "local_style": style,
        "provider": "",
        "model": "",
        "role": role,
        "text_density": "low",
        "max_text_units": max_text_units,
        "reason": reason,
        "command_hint": f"--local-image-style {style}",
        "fallback": "如果选定方向最终改成空间、物件、材料、人物或过程证据，再改用 --auto-generate-image。",
    }


def _psychology_text_carousel_recommendation() -> dict[str, Any]:
    return {
        "status": "available",
        "decision_stage": IMAGE_RECOMMENDATION_DECISION_STAGE,
        "recommended_backend": "local_social_screenshot",
        "local_style": "psychology_text_card_v1",
        "provider": "",
        "model": "",
        "format_archetype": "text_carousel",
        "carousel_style": "psychology_text_card_v1",
        "role": "text_carousel",
        "text_density": "medium",
        "max_text_units": 4,
        "page_count": {"min": 4, "max": 7},
        "ordered_roles": [
            "cover_hook",
            "concrete_scene",
            "light_mechanism",
            "save_tool",
            "scope_boundary",
            "comment_prompt",
        ],
        "reason": (
            "把一个主题依次讲成心理学封面、具体场景、轻机制、可保存工具、"
            "边界和评论入口，适合用 4-7 张有序文字卡表达。"
        ),
        "command_hint": "--auto-generate-image",
        "fallback": (
            "如明确只需要一张普通封面，可直接运行时使用既有 --local-image-style 覆盖；"
            "学习系列不接受该覆盖。"
        ),
    }


def _normalize_local_image_style(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value in IMAGE_STYLE_CHOICES:
            return value
    return "note_card"


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def _topic_guidance_selection_metadata(
    *,
    directions: list[dict[str, Any]],
    fallback_matched_direction_id: str = "",
) -> dict[str, Any]:
    curated_directions = [
        direction
        for direction in directions
        if direction.get("direction_type", "curated") == "curated"
    ]
    open_direction_ids = [
        direction["id"]
        for direction in directions
        if direction.get("direction_type") == "open_scene"
    ]
    direction_type_counts = Counter(
        direction.get("direction_type", "curated") for direction in directions
    )
    matched_direction_id = (
        curated_directions[0]["id"]
        if curated_directions
        else (directions[0]["id"] if directions else fallback_matched_direction_id)
    )
    return {
        "selection_policy": TOPIC_GUIDANCE_SELECTION_POLICY,
        "matched_direction_id": matched_direction_id,
        "open_direction_id": open_direction_ids[0] if open_direction_ids else "",
        "open_direction_ids": open_direction_ids,
        "direction_type_counts": dict(direction_type_counts),
    }


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> int:
    normalized_text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in normalized_text)


def _match_topic_direction_id(*, scene: str, lane_name: str) -> str:
    text = f"{lane_name} {scene}"
    if any(
        keyword in text
        for keyword in ("分手", "猫归谁", "没回消息", "不回消息", "3小时", "复合")
    ):
        return "relationship_uncertainty_waiting_message"
    if any(keyword in text for keyword in ("拒绝", "边界", "同事", "朋友", "家人", "责任")):
        return "boundary_sandwich_refusal"
    if any(keyword in text for keyword in ("失败", "老己", "自己", "比较", "审判")):
        return "self_compassion_laoji"
    if any(keyword in text for keyword in ("关心", "为你好", "想开点", "丝瓜汤", "感受")):
        return "loofah_soup_communication"
    if any(keyword in text for keyword in ("AI", "ai", "聊天工具", "陪伴", "数字")):
        return "ai_companion_boundary"
    if any(
        keyword in text
        for keyword in (
            "睡眠恢复",
            "轻养生",
            "办公室恢复",
            "下班信号",
            "5分钟",
            "5 分钟",
        )
    ):
        return "sleep_recovery_shutdown_card"
    return "boundary_sandwich_refusal"


def _clean_or_default(value: str | None, default: str) -> str:
    if value is None:
        return default
    stripped = value.strip()
    return stripped or default


def _build_recommended_scene(
    brief: dict[str, Any],
    *,
    image_recommendation: dict[str, Any] | None = None,
) -> str:
    return "\n".join(
        [
            f"选题lane：{brief['lane']}",
            f"第一人称微场景：{brief['scene']}",
            f"心理机制：{brief['mechanism']}",
            f"非诊断化重构：{brief['reframe']}",
            f"可保存动作/工具：{brief['save_tool']}",
            f"封面形式：{_image_recommendation_scene_summary(image_recommendation, brief)}",
            f"评论提示：{brief['comment_prompt']}",
            f"专业边界：{brief['safety_boundary']}",
        ]
    )


def _build_generic_recommended_scene(
    brief: dict[str, Any],
    *,
    image_recommendation: dict[str, Any] | None = None,
) -> str:
    return "\n".join(
        [
            f"选题lane：{brief['lane']}",
            f"第一人称微场景：{brief['scene']}",
            f"内容角度：{brief['content_angle']}",
            f"可保存小工具：{brief['save_tool']}",
            f"封面形式：{_image_recommendation_scene_summary(image_recommendation, brief)}",
            f"评论提示：{brief['comment_prompt']}",
        ]
    )


def _require_ai_tech_content_mode(value: str | None) -> str:
    content_mode = (value or "").strip()
    if content_mode not in AI_TECH_CONTENT_MODES:
        choices = ", ".join(AI_TECH_CONTENT_MODES)
        raise ValueError(
            f"ai_content_mode is required for AI tech guidance; choose one of: {choices}"
        )
    return content_mode


def _ai_tech_evidence_requirement(content_mode: str) -> str:
    return {
        "news_brief": "3–5 条互不重复的事件；每条都要有标签、已核验事实和不透明来源引用。",
        "hands_on": "一个主题的一次可复现实测：产品、版本、日期、任务、输入、观察结果、局限和测试引用。",
        "fact_translation": "一个主题、至少两条已核验事实，以及“谁该关注 / 谁可以等等”的明确边界。",
    }[content_mode]


def _ai_tech_guidance_message(content_mode: str) -> str:
    return {
        "news_brief": "选择一个快讯方向后，先补齐 3–5 条独立事件的核验事实，再生成短简报。",
        "hands_on": "选择一个实测方向后，先记录一次可复现任务的输入、输出与局限，再生成复盘帖。",
        "fact_translation": "选择一个转译方向后，先补齐至少两条核验事实和受众边界，再生成判断帖。",
    }[content_mode]


def _build_ai_tech_recommended_scene(
    *,
    content_mode: str,
    evidence_required: str,
    image_recommendation: dict[str, Any],
    brief: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"内容模式：{content_mode}",
            f"证据门槛：{evidence_required}",
            "运行时只读取 --ai-evidence-file 中的安全事实/测试记录，不读取自由场景。",
            f"封面形式：{_image_recommendation_scene_summary(image_recommendation, brief)}",
        ]
    )


def _build_psychology_learning_recommended_scene(
    *,
    contract: dict[str, Any],
    image_recommendation: dict[str, Any],
) -> str:
    return "\n".join(
        [
            f"学习专题：{_markdown_inline(contract['series_title'])}（课程版本 {contract['curriculum_version']}）",
            f"本课：{_markdown_inline(contract['series_badge'])}｜{_markdown_inline(contract['lesson_title'])}",
            f"场景：{_markdown_inline(contract['scene_anchor'])}",
            f"概念：{_markdown_inline(contract['concept_label'])}",
            f"学习目标：{_markdown_inline(contract['learning_goal'])}",
            f"可保存练习：{_markdown_inline(contract['micro_exercise'])}",
            f"封面形式：{_image_recommendation_scene_summary(image_recommendation, {'image_style': 'iphone_notes'})}",
            "运行时只使用这个已审核课次的合同，不读取自由场景、来源或热点标题。",
        ]
    )


def _build_psychology_learning_image_recommendation(
    *,
    image_plan: dict[str, Any],
) -> dict[str, Any]:
    """Expose the approved image plan without offering an override flag."""
    recommendation = {
        "status": "available",
        "decision_stage": IMAGE_RECOMMENDATION_DECISION_STAGE,
        "recommended_backend": image_plan["backend"],
        "local_style": image_plan.get("carousel_style") or image_plan["style"],
        "provider": "",
        "model": "",
        "role": image_plan["role"],
        "text_density": image_plan["text_density"],
        "max_text_units": int(image_plan["max_text_units"]),
        "reason": image_plan["reason"],
        "command_hint": "无需传 --local-image-style；PTSM 会按已审核课程图片方案生成。",
        "fallback": "学习系列不接受手工图片样式或图片文件覆盖。",
    }
    slides = image_plan.get("slides")
    if isinstance(slides, list):
        recommendation.update(
            {
                "format_archetype": "text_carousel",
                "carousel_style": image_plan["carousel_style"],
                "page_count": {"min": len(slides), "max": len(slides)},
                "ordered_roles": [slide["role"] for slide in slides],
            }
        )
    return recommendation


def _psychology_learning_safety_notes() -> list[str]:
    return [
        "课程概念、解释、微练习和边界只能来自 PTSM 已审核课程目录。",
        "不要把普通情绪写成诊断、治疗、药物建议或自测结论。",
        "如果这种状态持续影响生活或出现危机风险，优先寻求当地专业支持。",
    ]


def _format_psychology_learning_selection_markdown(result: dict[str, Any]) -> str:
    series = result.get("series", {})
    roadmap = series.get("roadmap", []) if isinstance(series, dict) else []
    roadmap_lines = "\n".join(
        (
            f"- 第{item.get('lesson_number')}课："
            f"{_markdown_inline(item.get('lesson_title'))} "
            f"(`{item.get('lesson_id')}`)"
        )
        for item in roadmap
        if isinstance(item, dict)
    )
    directions = "\n".join(
        _format_topic_direction_markdown(direction)
        for direction in result.get("topic_guidance", {}).get("directions", [])
    )
    sequence_lines = _format_custom_psychology_learning_sequence_markdown(
        series if isinstance(series, dict) else {}
    )
    return "\n".join(
        [
            "# Psychology Learning Series",
            "",
            "## Choose a Lesson",
            "",
            str(result.get("topic_guidance", {}).get("message", "")),
            "",
            "## Roadmap",
            "",
            roadmap_lines,
            *sequence_lines,
            "",
            "## Available Lesson Directions",
            "",
            directions,
            "",
            "## Next Step",
            "",
            str(result.get("next_step", "")),
        ]
    )


def _format_custom_psychology_learning_sequence_markdown(
    series: dict[str, Any],
) -> list[str]:
    """Render custom-only schedule advice without exposing private receipts."""
    publication_plan = series.get("publication_plan")
    if not isinstance(publication_plan, list):
        return []
    plan_lines = "\n".join(
        (
            f"- 发布第{item.get('publication_order')}篇：第"
            f"{item.get('canonical_lesson_number')}课 "
            f"{_markdown_inline(item.get('lesson_title'))} "
            f"(`{item.get('lesson_id')}`)｜{_markdown_inline(item.get('rationale'))}"
        )
        for item in publication_plan
        if isinstance(item, dict)
    )
    progress = series.get("production_progress")
    completed = (
        progress.get("completed_lesson_ids", [])
        if isinstance(progress, dict)
        else []
    )
    completed_text = "、".join(str(item) for item in completed) if completed else "暂无"
    recommended = series.get("recommended_next_lesson")
    if isinstance(recommended, dict):
        recommendation_line = (
            f"- 建议下一篇：发布第{recommended.get('publication_order')}篇，"
            f"第{recommended.get('canonical_lesson_number')}课 "
            f"{_markdown_inline(recommended.get('lesson_title'))} "
            f"(`{recommended.get('lesson_id')}`)"
        )
    else:
        recommendation_line = "- 没有下一课建议：所有建议发布课次均已完成。"
    return [
        "",
        "## Recommended Publication Order",
        "",
        plan_lines,
        "",
        "## Production Progress",
        "",
        f"- operator_content_production：已完成 {completed_text}",
        "",
        "## Recommended Next Lesson",
        "",
        recommendation_line,
        "- 建议不代替选择；请明确传入一个 lesson_id。",
    ]


def _image_recommendation_scene_summary(
    recommendation: dict[str, Any] | None,
    brief: dict[str, Any],
) -> str:
    if not recommendation:
        return f"{brief['image_style']}，低密度，只放 1-3 个短文字单元"
    if recommendation["recommended_backend"] == "provider_image":
        return (
            f"provider_image（{recommendation['provider']} / {recommendation['model']}），"
            f"{recommendation['role']}，低密度，最多 {recommendation['max_text_units']} 个短文字单元"
        )
    if recommendation.get("format_archetype") == "text_carousel":
        page_count = recommendation["page_count"]
        return (
            f"{recommendation['local_style']}，{page_count['min']}-{page_count['max']} 张有序文字卡，"
            "同一主题依次呈现场景、轻机制、工具、边界与评论入口"
        )
    return (
        f"{recommendation['local_style']}，{recommendation['role']}，"
        f"低密度，最多 {recommendation['max_text_units']} 个短文字单元"
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
    scene: str | None,
    image_style: str | None,
    topic_direction_id: str | None = None,
    ai_content_mode: str | None = None,
    ai_evidence_file_path: str | None = None,
    psychology_content_mode: str | None = None,
    psychology_series_id: str | None = None,
    psychology_lesson_id: str | None = None,
    psychology_curriculum_version: str | None = None,
) -> list[str]:
    command = [
        "uv",
        "run",
        "python",
        "-m",
        "ptsm.bootstrap",
        "run-playbook",
    ]
    if scene:
        command.extend(["--scene", scene])
    command.extend([
        "--account-id",
        account_id,
        "--playbook-id",
        playbook_id,
        "--publish-mode",
        "dry-run",
        "--auto-generate-image",
    ])
    if image_style:
        command.extend(["--local-image-style", image_style])
    if topic_direction_id:
        command.extend(["--topic-direction-id", topic_direction_id])
    if ai_content_mode:
        command.extend(["--ai-content-mode", ai_content_mode])
    if ai_content_mode:
        command.extend([
            "--ai-evidence-file",
            ai_evidence_file_path or "<operator-ai-evidence.json>",
        ])
    if psychology_content_mode:
        command.extend(["--psychology-content-mode", psychology_content_mode])
    if psychology_series_id:
        command.extend(["--psychology-series-id", psychology_series_id])
    if psychology_lesson_id:
        command.extend(["--psychology-lesson-id", psychology_lesson_id])
    if psychology_curriculum_version:
        command.extend(
            ["--psychology-curriculum-version", psychology_curriculum_version]
        )
    return command


def _build_ai_tech_quality_checklist(content_mode: str) -> list[dict[str, str]]:
    shared = [
        {
            "item": "短帖与事实边界",
            "done_when": "标题短、正文可扫读；不加证据文件之外的事实、来源路径或个人体验。",
        },
        {
            "item": "低密度封面",
            "done_when": "封面只放一个模式钩子或一个事实标签，不把正文塞进图里。",
        },
    ]
    by_mode = {
        "news_brief": [
            {
                "item": "三到五条独立快讯",
                "done_when": "每条都有事件标签和原样核验事实；不串成一段泛泛感受。",
            },
        ],
        "hands_on": [
            {
                "item": "可复现实测记录",
                "done_when": "完整写出产品/版本/日期/任务/输入/观察结果/局限，读者能判断测试范围。",
            },
        ],
        "fact_translation": [
            {
                "item": "事实与决策边界",
                "done_when": "至少两条核验事实后，明确写出谁该关注、谁可以等等。",
            },
        ],
    }
    return [*by_mode[content_mode], *shared]


def _build_psychology_learning_quality_checklist() -> list[dict[str, str]]:
    return [
        {
            "item": "固定课次",
            "done_when": "正文保留系列课次、概念和学习目标，不把普通心理学帖伪装成课程。",
        },
        {
            "item": "一个可保存练习",
            "done_when": "只交付本课已审核的微练习，不追加自测、万能话术或治疗承诺。",
        },
        {
            "item": "适用边界",
            "done_when": "写清这张卡适合什么日常时刻，以及何时应转向专业帮助。",
        },
        {
            "item": "短帖人味",
            "done_when": "用一个下班后的真实瞬间开场，正文保持短、可扫读、可接话。",
        },
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
            "item": "可保存动作/工具",
            "done_when": "给出三步以内、今天能试的小动作或句式。",
        },
        {
            "item": "角色认领评论",
            "done_when": "评论提示让用户选阵营、认领角色或填一个具体空。",
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
