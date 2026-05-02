from __future__ import annotations

from ptsm.config.settings import Settings


def test_settings_accepts_pub_and_aether_deepseek_env_names(monkeypatch) -> None:
    for key in [
        "DEFAULT_LLM_PROVIDER",
        "DEFAULT_LLM_MODEL",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_API_BASE",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_TEMPERATURE",
        "DEEPSEEK_MAX_TOKENS",
        "XHS_MCP_SERVER_URL",
        "XHS_DEFAULT_VISIBILITY",
    ]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("DEFAULT_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEFAULT_LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
    monkeypatch.setenv("DEEPSEEK_TEMPERATURE", "0.2")
    monkeypatch.setenv("DEEPSEEK_MAX_TOKENS", "2048")
    monkeypatch.setenv("XHS_MCP_SERVER_URL", "http://localhost:18060/mcp")
    monkeypatch.setenv("XHS_DEFAULT_VISIBILITY", "仅自己可见")

    settings = Settings(_env_file=None)

    assert settings.default_model_provider == "deepseek"
    assert settings.default_model == "deepseek-chat"
    assert settings.deepseek_api_key == "sk-test"
    assert settings.deepseek_base_url == "https://api.deepseek.com/v1"
    assert settings.deepseek_temperature == 0.2
    assert settings.deepseek_max_tokens == 2048
    assert settings.xhs_mcp_server_url == "http://localhost:18060/mcp"
    assert settings.xhs_default_visibility == "仅自己可见"


def test_settings_accept_bailian_image_generation_env_names(monkeypatch) -> None:
    for key in [
        "PIC_MODEL_API_KEY",
        "PIC_MODEL_BASE_URL",
        "PIC_MODEL_MODEL",
        "PIC_MODEL_SIZE",
        "PIC_MODEL_NEGATIVE_PROMPT",
    ]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("PIC_MODEL_API_KEY", "sk-image-test")
    monkeypatch.setenv("PIC_MODEL_MODEL", "qwen-image-2.0-pro")

    settings = Settings(_env_file=None)

    assert settings.pic_model_api_key == "sk-image-test"
    assert settings.pic_model_model == "qwen-image-2.0-pro"
    assert settings.pic_model_base_url == "https://dashscope.aliyuncs.com/api/v1"
    assert settings.pic_model_size == "1104*1472"


def test_settings_accept_jimeng_image_generation_env_names(monkeypatch) -> None:
    for key in [
        "JIMENG_API_KEY",
        "JIMENG_SECRET_KEY",
        "JIMENG_BASE_URL",
        "JIMENG_MODEL",
        "JIMENG_WIDTH",
        "JIMENG_HEIGHT",
        "JIMENG_POLL_INTERVAL_SECONDS",
        "JIMENG_MAX_POLL_ATTEMPTS",
    ]:
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("JIMENG_API_KEY", "ak-test")
    monkeypatch.setenv("JIMENG_SECRET_KEY", "sk-test")
    monkeypatch.setenv("JIMENG_MODEL", "jimeng_t2i_v40")

    settings = Settings(_env_file=None)

    assert settings.jimeng_api_key == "ak-test"
    assert settings.jimeng_secret_key == "sk-test"
    assert settings.jimeng_base_url == "https://visual.volcengineapi.com"
    assert settings.jimeng_model == "jimeng_t2i_v40"
    assert settings.jimeng_width == 1536
    assert settings.jimeng_height == 2048
    assert settings.jimeng_poll_interval_seconds == 2.0
    assert settings.jimeng_max_poll_attempts == 60
