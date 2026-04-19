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
    pic_model_api_key: str | None = Field(default=None, validation_alias="PIC_MODEL_API_KEY")
    pic_model_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/api/v1",
        validation_alias="PIC_MODEL_BASE_URL",
    )
    pic_model_model: str = Field(
        default="qwen-image-2.0-pro",
        validation_alias="PIC_MODEL_MODEL",
    )
    pic_model_size: str = Field(
        default="1104*1472",
        validation_alias="PIC_MODEL_SIZE",
    )
    pic_model_negative_prompt: str = Field(
        default=(
            "低清晰度，文字残缺，脸部畸形，四肢异常，构图混乱，"
            "过曝，过度饱和，模糊，水印，logo。"
        ),
        validation_alias="PIC_MODEL_NEGATIVE_PROMPT",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
