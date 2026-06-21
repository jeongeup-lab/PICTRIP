"""Pipeline settings (independent of backend config)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/pictrip"
    kto_api_key: str = ""


settings = Settings()
