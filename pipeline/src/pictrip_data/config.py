"""Pipeline settings (independent of backend config).

kto_api_key is stored URL-DECODED; httpx re-encodes it via params=.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://pictrip:pictrip_dev_only@localhost:5432/pictrip"
    kto_api_key: str = ""
    kto_base_url_kor: str = "http://apis.data.go.kr/B551011/KorService2"
    kto_mobile_app: str = "PicTrip"


settings = Settings()
