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
