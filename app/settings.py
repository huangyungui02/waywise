"""应用配置：环境变量优先于项目根目录的 .env。"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    access_token: SecretStr = Field(min_length=1)
    database_url: SecretStr = Field(min_length=1)
    dbos_database_url: SecretStr | None = None
    dbos_retention_days: int = Field(default=7, ge=1)
    max_concurrent_runs: int = Field(default=4, ge=1)
    cors_origins: list[str] = Field(default_factory=list)
    travel_model: str = "qwen3.8-flash"
    compact_max_tokens: int = Field(default=500_000, ge=1)
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: SecretStr = Field(
        validation_alias="DASHSCOPE_API_KEY", min_length=1
    )
    amap_maps_api_key: SecretStr = Field(
        validation_alias="AMAP_MAPS_API_KEY", min_length=1
    )
    flyai_api_key: SecretStr = SecretStr("")
    logfire_token: SecretStr = SecretStr("")
    logfire_environment: str = "development"
    logfire_include_content: bool = False
