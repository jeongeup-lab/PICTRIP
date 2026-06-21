"""Application settings. Single source for env-driven config.

Lives at app/config.py (NOT app/core/) — ADMIN_PASSWORD, SENTRY_DSN, KTO/Kakao
keys all follow this pattern.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # database
    postgres_host: str = "localhost"
    postgres_db: str = "pictrip"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    # redis
    redis_url: str = "redis://localhost:6379/0"

    # external
    kto_api_key: str = ""
    kakao_rest_api_key: str = ""
    anthropic_api_key: str = ""

    # admin console (HTTP Basic)
    admin_password: str = ""

    # observability
    sentry_dsn: str = ""


settings = Settings()
