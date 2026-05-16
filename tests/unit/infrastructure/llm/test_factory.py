from __future__ import annotations

from types import SimpleNamespace

from ptsm.config.settings import Settings
from ptsm.infrastructure.llm.factory import (
    DeterministicDraftBackend,
    _parse_json_payload,
    build_drafting_backend,
)


def test_factory_falls_back_to_deterministic_when_deepseek_key_missing() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key=None,
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.7,
        deepseek_max_tokens=4096,
    )

    backend = build_drafting_backend(settings)

    assert isinstance(backend, DeterministicDraftBackend)
    assert backend.provider_name == "deterministic"


class FakeChatDeepSeek:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def invoke(self, _messages):
        return SimpleNamespace(
            content=(
                '{"title":"LLM发疯实录","image_text":"真的疯了",'
                '"body":"会议连开三场，不过熬过去也算今天还有点战绩。",'
                '"hashtags":["#发疯文学","#会议崩溃实录","#打工人日常"]}'
            )
        )


def test_factory_builds_deepseek_backend_when_key_present() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=FakeChatDeepSeek)
    draft = backend.generate(
        scene="周二下午连环会议",
        reflection_feedback="补一个轻量正向收束",
    )

    assert backend.provider_name == "deepseek"
    assert draft["title"] == "LLM发疯实录"
    assert "会议连开三场" in draft["body"]


def test_deterministic_backend_sanitizes_meta_scene_and_adapts_weekend_theme() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="PTSM 自动发布连通性验证，请忽略。周六社畜躺平，本来想补觉，结果躺到下午还是觉得像上了一天班。",
        reflection_feedback="补一个轻量正向收束",
    )

    assert "PTSM" not in draft["body"]
    assert "自动发布" not in draft["body"]
    assert "请忽略" not in draft["body"]
    assert "地铁" not in draft["body"]
    assert "通勤" not in draft["body"]
    assert "周六" in draft["body"]
    assert "补觉" in draft["body"]
    assert "躺平" in draft["title"]
    assert "#发疯文学" in draft["hashtags"]


def test_deterministic_backend_can_follow_sushi_poetry_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="夜里读到《定风波》，突然想把今天的狼狈也写成一段赏析",
        reflection_feedback="正文需要出现苏轼。",
        planner_prompt="# 苏轼诗词赏析 Planner\n目标：写成适合小红书的诗词赏析短帖。",
        skill_contents=[
            "# Sushi Poetry Style\n正文要点出苏轼，并保持可读、亲切。",
            "# XHS Poetry Hashtagging\n标签必须包含 `#苏轼`。",
        ],
    )

    assert "苏轼" in draft["body"]
    assert "#苏轼" in draft["hashtags"]
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_wuxia_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="分析令狐冲的自由人格与当代职场人不愿被体制化的挣扎",
        planner_prompt="# 武侠人物评述 Planner\n目标：写一篇适合小红书的武侠人物评述。",
        skill_contents=[
            "# Wuxia Commentary Style\n必须引用原文并点出金庸人物。",
            "# XHS Wuxia Hashtagging\n必须包含 `#金庸`。",
        ],
    )

    assert "令狐冲" in draft["body"]
    assert "笑傲江湖" in draft["body"]
    assert "#金庸" in draft["hashtags"]
    assert len(draft["body"]) >= 400
    assert "发疯文学" not in draft["body"]


def test_deterministic_backend_can_follow_modern_psychology_context() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下班后还在反复复盘白天一句话",
        planner_prompt="# 现代心理困境观察 Planner\n目标：解释一个心理机制，给低风险行动和专业边界。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
            "# XHS Psychology Hashtagging\n标签必须包含 `#心理学` 或 `#情绪管理`。",
        ],
    )

    assert "反刍思维" in draft["body"]
    assert "专业帮助" in draft["body"]
    assert "诊断" not in draft["title"]
    assert "#心理学" in draft["hashtags"]
    assert "#情绪管理" in draft["hashtags"]
    assert "发疯文学" not in draft["body"]


def test_deterministic_modern_psychology_draft_has_mini_tool_and_example_prompt() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下班路上还在反复复盘会议里一句话，越想越尴尬",
        planner_prompt="# 现代心理困境观察 Planner\n目标：解释一个心理机制，给低风险行动和专业边界。",
        persona_prompt="# Modern Psychology Persona\n有心理学素养但不做诊断。",
        skill_contents=[
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
            "# XHS Psychology Hashtagging\n标签必须包含 `#心理学` 或 `#情绪管理`。",
        ],
    )

    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    assert draft["title"] != "下班后还在复盘那句话"
    assert draft["image_text"] != "脑子还没下班"
    assert "下班路上还在反复复盘会议里一句话" in draft["body"]
    assert draft["body"].index("下班路上还在反复复盘会议里一句话") < draft[
        "body"
    ].index("反刍思维")
    assert any(term in combined for term in ("不是你太敏感", "不是你想太多"))
    assert any(tool in draft["body"] for tool in ("事实 / 猜测 / 下一步", "三栏"))
    assert "专业帮助" in draft["body"]
    assert "评论区" in draft["body"]
    assert any(prompt in draft["body"] for prompt in ("你最容易", "哪类瞬间"))
    assert any(tag in draft["hashtags"] for tag in ("#心理学", "#情绪管理"))
    assert not any(term in combined for term in ("诊断", "治好焦虑", "治愈抑郁", "用药"))


def test_deterministic_modern_psychology_draft_varies_by_scene_mechanic() -> None:
    backend = DeterministicDraftBackend()
    skill_contents = [
        "# Psychology Style\n需要三栏工具、5分钟练习、边界句模板或消息草稿。",
        "# Psychology Safety\n禁止诊断化表达，必须提示专业帮助边界。",
    ]

    sunday = backend.generate(
        scene="周日晚上开始焦虑周一消息",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    boundary = backend.generate(
        scene="别人一句你想太多了之后，晚上一直睡不着",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    pulled_back = backend.generate(
        scene="工作上看起来很稳定，但一收到临时消息就像被拉回工位",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    meeting = backend.generate(
        scene="下班路上反复复盘会议里一句话，越想越尴尬",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    after_work = backend.generate(
        scene="明明已经下班，却还在脑内给白天的自己开复盘会",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )
    ordinary_reply = backend.generate(
        scene="最近总因为一句普通回复反复复盘，想收集大家最常复盘的瞬间",
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=skill_contents,
    )

    drafts = [
        sunday,
        boundary,
        pulled_back,
        meeting,
        after_work,
        ordinary_reply,
    ]
    assert len({draft["title"] for draft in drafts}) == 6
    assert len(
        {
            draft["image_text"]
            for draft in drafts
        }
    ) == 6
    assert "5分钟" in sunday["body"]
    assert "边界句" in boundary["body"]
    assert any(term in pulled_back["body"] for term in ("低控制感", "边界压力"))
    assert "事实 / 猜测 / 下一步" in meeting["body"]
    assert "散会" in after_work["body"]
    assert "评论区" in ordinary_reply["body"]


def test_deterministic_drafts_strip_experiment_variant_instructions() -> None:
    backend = DeterministicDraftBackend()

    fengkuang = backend.generate(
        scene=(
            "领导18:57发来一句在吗，明天早会要我补材料。"
            "变体要求：comment_chain，评论区接一句工牌背面的疯话。"
        ),
        planner_prompt="# 发疯文学 Planner",
        persona_prompt="# 发疯文学 Persona",
        skill_contents=["# Fengkuang Style\n必须有评论区接龙和可复制句。"],
    )
    psychology = backend.generate(
        scene=(
            "周日晚上开始焦虑周一消息。"
            "变体要求：save_tool，给一个5分钟落地练习。"
        ),
        planner_prompt="# 现代心理困境观察 Planner",
        persona_prompt="# Modern Psychology Persona",
        skill_contents=[
            "# Psychology Style\n需要三栏工具和例子型评论提示。",
            "# Psychology Safety\n必须提示专业帮助边界。",
        ],
    )

    combined = "\n".join(
        [
            fengkuang["body"],
            psychology["body"],
        ]
    )
    assert "变体要求" not in combined
    assert "comment_chain" not in combined
    assert "save_tool" not in combined
    assert "identity_conflict" not in combined


class CapturingChatDeepSeek(FakeChatDeepSeek):
    last_messages = None

    def invoke(self, messages):
        CapturingChatDeepSeek.last_messages = messages
        return super().invoke(messages)


def test_factory_sanitizes_scene_before_deepseek_prompt() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="PTSM 自动发布连通性验证，请忽略。周六社畜躺平，本来想补觉。",
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "PTSM" not in user_prompt
    assert "自动发布" not in user_prompt
    assert "请忽略" not in user_prompt
    assert "周六社畜躺平" in user_prompt


def test_factory_deepseek_prompt_hardens_required_hashtag_without_mandating_recommended_phrase() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="周日晚上想到明天又要开工",
        reflection_feedback="# 发疯文学 Reflection\n3. 结尾是否有轻量正向收束，优先包含“也算”这类词。",
        skill_contents=[
            "# Positive Reframe\n结尾加入“也算”“至少”“还能”一类轻量正向缓冲。",
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "正文必须包含“也算”" not in user_prompt
    assert "hashtags 数组必须包含 '#发疯文学'" in user_prompt


def test_factory_includes_persona_prompt_in_deepseek_context() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="周六社畜躺平",
        persona_prompt="# Persona\n普通打工人，表达要有人味和网感，不要 AI 腔。",
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "普通打工人" in user_prompt
    assert "不要 AI 腔" in user_prompt


def test_deterministic_backend_uses_persona_for_more_human_copy() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="周六社畜躺平",
        persona_prompt="# Persona\n普通打工人，表达要有人味和网感。",
    )

    assert "谁懂" in draft["body"]
    assert "评论区" in draft["body"]


def test_deterministic_backend_uses_runtime_trend_context_for_title_hook() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="下午四点半，老板还在群里发新需求",
        runtime_skill_contents=[
            "# XHS Trend Scan Live Context\n"
            "- 主切口：`怎么才周四`\n"
            "- 场景张力：`下班前被新需求拽回工位`\n"
            "- 约束：只借情绪结构和讨论点，不复写原题，不堆砌热词。"
        ],
    )

    assert "怎么才周四" in draft["title"]
    assert "新需求" in draft["body"]


def test_deterministic_backend_avoids_recent_memory_title() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="周一早高峰地铁通勤",
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "Avoid repeating recent account posts:\n"
            "- recent_1_scene: 上周一早高峰地铁通勤\n"
            "  title: 打工人地铁生存实录\n"
            "  body_preview: 今日份发疯现场：上周一早高峰地铁通勤"
        ],
    )

    assert draft["title"] != "打工人地铁生存实录"
    assert "地铁" in draft["title"]


def test_deterministic_backend_keeps_concrete_title_when_avoiding_recent_leader_memory() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="领导18:57发来一句在吗，明天早会要我补材料",
        runtime_skill_contents=[
            "# Recent Account Memory\n"
            "Avoid repeating recent account posts:\n"
            "- recent_1_scene: 昨天领导18:57发在吗\n"
            "  title: 领导18:57发「在吗」那一秒\n"
            "  body_preview: 我的工牌先替我发疯"
        ],
    )

    assert draft["title"] != "领导18:57发「在吗」那一秒"
    assert draft["title"] != "今天换个地方发疯"
    assert any(term in draft["title"] for term in ("18:57", "工牌", "早会", "在吗"))


def test_deterministic_fengkuang_draft_has_comment_and_copyable_mechanics() -> None:
    backend = DeterministicDraftBackend()

    draft = backend.generate(
        scene="领导18:57突然发来一句在吗，明天早会还要我补材料",
        skill_contents=[
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
        ],
    )

    assert draft["title"] not in {
        "打工人地铁生存实录",
        "会议连环暴击实录",
        "社畜崩溃边缘实录",
    }
    combined = f"{draft['title']}\n{draft['image_text']}\n{draft['body']}"
    assert any(obj in combined for obj in ("工牌", "群聊", "周报", "材料", "早会"))
    assert "评论区" in draft["body"]
    assert any(cue in combined for cue in ("接一句", "疯话", "写在", "可复制"))
    assert "#发疯文学" in draft["hashtags"]
    assert not any(term in combined for term in ("精神病", "心理医生", "医院", "治疗", "用药"))


def test_factory_deepseek_prompt_requires_fengkuang_mechanics_and_safety() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="领导18:57突然发来一句在吗，明天早会还要我补材料",
        skill_contents=[
            "# XHS Hashtagging\n发疯文学方向优先包含 `#发疯文学`。",
            "# Fengkuang Style\n需要评论区接龙和可复制疯话。",
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "具体职场物件或社交对象" in user_prompt
    assert "评论区接龙" in user_prompt
    assert "心理疾病、治疗、医院、用药" in user_prompt


def test_factory_puts_runtime_trend_context_in_dedicated_prompt_section() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="下午四点半，老板还在群里发新需求",
        runtime_skill_contents=[
            "# XHS Trend Scan Live Context\n"
            "- 主切口：`怎么才周四`\n"
            "- 场景张力：`下班前被新需求拽回工位`"
        ],
    )

    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "实时上下文" in user_prompt
    assert "怎么才周四" in user_prompt


def test_factory_uses_generic_system_prompt_for_non_fengkuang_playbooks() -> None:
    settings = Settings.model_construct(
        default_model_provider="deepseek",
        default_model="deepseek-chat",
        deepseek_api_key="sk-test",
        deepseek_model="deepseek-chat",
        deepseek_base_url="https://api.deepseek.com/v1",
        deepseek_temperature=0.3,
        deepseek_max_tokens=1024,
    )

    backend = build_drafting_backend(settings, chat_model_cls=CapturingChatDeepSeek)
    backend.generate(
        scene="夜里读到《定风波》",
        planner_prompt="# 苏轼诗词赏析 Planner\n写成小红书诗词赏析短帖。",
        reflection_feedback="# 苏轼诗词赏析 Reflection\n正文需要出现苏轼。",
        skill_contents=["# XHS Poetry Hashtagging\n必须包含 `#苏轼`。"],
    )

    system_prompt = CapturingChatDeepSeek.last_messages[0].content
    user_prompt = CapturingChatDeepSeek.last_messages[1].content
    assert "发疯文学" not in system_prompt
    assert "发疯文学文案" not in user_prompt
    assert "hashtags 数组必须包含 '#苏轼'" in user_prompt


def test_parse_json_payload_accepts_prose_wrapped_fenced_json() -> None:
    content = """
    下面是你要的结果：

    ```json
    {
      "title": "躺平失败实录",
      "image_text": "今天先躺",
      "body": "周六想补觉，结果醒来更像刚开完会。",
      "hashtags": ["#发疯文学", "#周末躺平日记"]
    }
    ```

    祝你发布顺利。
    """

    payload = _parse_json_payload(content)

    assert payload["title"] == "躺平失败实录"
    assert payload["hashtags"] == ["#发疯文学", "#周末躺平日记"]


def test_parse_json_payload_recovers_deepseek_hashtag_formatting_glitch() -> None:
    content = """```json
{
    "title": "谁懂啊！躺平比上班还累的魔咒",
    "image_text": "窗帘缝隙透进的光从清晨移到黄昏｜我像块被反复煎烤的培根",
    "body": "周六发誓要睡到地老天荒\\n结果身体在床上 灵魂在工位流浪\\n闭眼是KPI 睁眼是未读消息幻象\\n躺了八小时竟获得加班同款眩晕感\\n原来真正的休息\\n是连细胞都在偷偷写周报啊（苦涩笑）",
    "hashtags": ["#发疯文学", "#当代年轻人精神状态", "#躺平失败实录",#"周末悖论",#"职场后遗症"]
}
```"""

    payload = _parse_json_payload(content)

    assert payload["title"] == "谁懂啊！躺平比上班还累的魔咒"
    assert payload["hashtags"] == [
        "#发疯文学",
        "#当代年轻人精神状态",
        "#躺平失败实录",
        "#周末悖论",
        "#职场后遗症",
    ]


def test_parse_json_payload_recovers_bare_hashtag_entries_without_opening_quotes() -> None:
    content = """```json
{
    "title": "周一早高峰地铁，我的灵魂被挤成了二维码",
    "image_text": "照片里：一只被挤到变形的帆布包。",
    "body": "周一早高峰地铁通勤，不过熬过去也算今天还有点战绩。",
    "hashtags": ["#发疯文学", "#周一早高峰", #地铁人类观察", "#通勤发疯实录", #我的精神状态]
}
```"""

    payload = _parse_json_payload(content)

    assert payload["hashtags"] == [
        "#发疯文学",
        "#周一早高峰",
        "#地铁人类观察",
        "#通勤发疯实录",
        "#我的精神状态",
    ]


def test_parse_json_payload_normalizes_string_hashtags() -> None:
    content = """
    {
      "title": "谁懂啊！躺平一天比上班还累！",
      "image_text": "瘫在床上，眼神空洞，窗外从清晨到黄昏。",
      "body": "算了，至少床单证明了今天的努力，也算为这个家做出了贡献。",
      "hashtags": "#发疯文学 #成年人的崩溃瞬间 #周末躺平 #精神内耗 #社畜日常"
    }
    """

    payload = _parse_json_payload(content)

    assert payload["hashtags"] == [
        "#发疯文学",
        "#成年人的崩溃瞬间",
        "#周末躺平",
        "#精神内耗",
        "#社畜日常",
    ]
