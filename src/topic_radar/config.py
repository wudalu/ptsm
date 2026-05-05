from __future__ import annotations

from functools import lru_cache

from pydantic import Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class TopicRadarConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    xhs_mcp_server_url: str = Field(
        default="http://localhost:18060/mcp",
        validation_alias="XHS_MCP_SERVER_URL",
    )

    output_dir: str = Field(
        default="outputs/artifacts",
        validation_alias=AliasChoices("TOPIC_RADAR_OUTPUT_DIR", "OUTPUT_DIR"),
    )

    default_platforms: str = Field(
        default="weibo,douyin,zhihu,bilibili,toutiao,douban,sspai,xiaohongshu",
        validation_alias=AliasChoices("TOPIC_RADAR_PLATFORMS", "DEFAULT_PLATFORMS"),
    )

    scan_sample_limit: int = Field(
        default=20,
        validation_alias="TOPIC_RADAR_SAMPLE_LIMIT",
    )

    llm_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("DEEPSEEK_API_KEY", "LLM_API_KEY"),
    )
    llm_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices("TOPIC_RADAR_LLM_MODEL", "DEEPSEEK_MODEL", "LLM_MODEL"),
    )
    llm_base_url: str = Field(
        default="https://api.deepseek.com/v1",
        validation_alias=AliasChoices("DEEPSEEK_BASE_URL", "LLM_BASE_URL"),
    )


@lru_cache
def get_config() -> TopicRadarConfig:
    return TopicRadarConfig()
