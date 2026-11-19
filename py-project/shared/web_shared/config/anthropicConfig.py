"""
Anthropic API 키 설정(양봉상회·비밀상회 웹서버 공용).

키를 읽는 순서(pydantic-settings):
  1. 환경변수 SECRET_KEY
  2. 키 파일 — 환경변수 ANTHROPIC_ENV_FILE 이 있으면 그 경로, 없으면 **각 서버의 작업 폴더** 기준
     app/config/keys/anthropic.env (Docker 에서는 /workdir/app/config/keys/anthropic.env).
     키 파일은 gitignored — 서버에 두면 이미지에 복사된다(py-project/.dockerignore 는 *.env 를 빼지 않는다).

2026-11-19: 이 모듈을 web_shared 로 옮기면서 경로 기준을 '이 파일 위치'에서 '작업 폴더'로 바꿨다
(예전 기준이면 shared/web_shared/config/keys/ 를 찾게 되어 두 서버 모두 키를 못 읽는다).
"""
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(os.environ.get("ANTHROPIC_ENV_FILE") or Path.cwd() / "app" / "config" / "keys" / "anthropic.env")


class AnthropicSettings(BaseSettings):
    secret_key: str

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
    )


# 모듈 레벨 싱글턴 — import 시 한 번만 파싱됨
anthropic_settings = AnthropicSettings()
