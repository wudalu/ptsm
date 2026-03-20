from __future__ import annotations

from types import SimpleNamespace

from ptsm.config.settings import Settings
from ptsm.infrastructure.llm.factory import (
    DeterministicDraftBackend,
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
