"""应用配置：环境变量优先于项目根目录的 .env。"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env", env_file_encoding="utf-8", extra="ignore",
    )

    travel_model: str = "qwen3.8-flash"
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: SecretStr = Field(validation_alias="DASHSCOPE_API_KEY", min_length=1)
    amap_maps_api_key: SecretStr = Field(validation_alias="AMAP_MAPS_API_KEY", min_length=1)
    flyai_api_key: SecretStr = SecretStr("")
