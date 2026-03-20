from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with env compatibility for reference projects."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "ptsm"
    environment: str = "development"
    log_level: str = "INFO"

    default_model_provider: str = Field(
        default="deepseek",
        validation_alias=AliasChoices("DEFAULT_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    default_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices("DEFAULT_LLM_MODEL", "LLM_MODEL"),
    )

    deepseek_api_key: str | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "DEEPSEEK_API_BASE"),
    )
    deepseek_temperature: float = Field(
        default=0.7,
        validation_alias="DEEPSEEK_TEMPERATURE",
    )
    deepseek_max_tokens: int = Field(
        default=2048,
        validation_alias="DEEPSEEK_MAX_TOKENS",
    )
    xhs_mcp_server_url: str = Field(
        default="http://localhost:18060/mcp",
        validation_alias="XHS_MCP_SERVER_URL",
    )
    xhs_default_visibility: str = Field(
        default="仅自己可见",
        validation_alias="XHS_DEFAULT_VISIBILITY",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
