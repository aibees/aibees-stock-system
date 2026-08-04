from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).parent / "keys" / "anthropic.env"


class AnthropicSettings(BaseSettings):
    secret_key: str

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


# 모듈 레벨 싱글턴 — import 시 한 번만 파싱됨
anthropic_settings = AnthropicSettings()
