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
    assert "也算" in draft["body"]


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


def test_factory_deepseek_prompt_hardens_required_phrase_and_hashtag() -> None:
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
    assert "正文必须包含“也算”" in user_prompt
    assert "hashtags 数组必须包含 '#发疯文学'" in user_prompt


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
