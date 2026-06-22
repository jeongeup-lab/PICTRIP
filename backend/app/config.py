"""Application settings loaded from environment.

Composed via pydantic-settings BaseSettings — see .env.example for the full list.
Settings are validated at process startup; missing required values fail fast.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    ENVIRONMENT: Environment = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "pictrip-backend"

    # --- API ---
    API_V1_PREFIX: str = "/v1"
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])

    # --- Database ---
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "pictrip"
    POSTGRES_USER: str = "pictrip"
    POSTGRES_PASSWORD: str = "pictrip_dev_only"
    DATABASE_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return str(
            PostgresDsn.build(
                scheme="postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                path=self.POSTGRES_DB,
            )
        )

    # --- Redis ---
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]

    # --- Auth ---
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_TTL_SECONDS: int = 900
    JWT_REFRESH_TOKEN_TTL_SECONDS: int = 2_592_000
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""

    # --- OAuth ---
    # Kakao id_token's `aud` claim equals the app key used by the client when
    # initiating login. Mobile native SDK uses NATIVE_APP_KEY; web/server OAuth
    # uses REST_API_KEY. Both are valid audiences for our backend.
    KAKAO_REST_API_KEY: str = ""
    KAKAO_NATIVE_APP_KEY: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_CLIENT_ID_IOS: str = ""
    GOOGLE_OAUTH_CLIENT_ID_ANDROID: str = ""
    GOOGLE_OAUTH_CLIENT_ID_WEB: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_SERVICES_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY: str = ""

    # --- Kakao OIDC ---
    KAKAO_JWKS_URL: str = "https://kauth.kakao.com/.well-known/jwks.json"
    KAKAO_OIDC_ISSUER: str = "https://kauth.kakao.com"
    KAKAO_JWKS_CACHE_TTL_SECONDS: int = 3600
    KAKAO_JWKS_STALE_ON_ERROR_TTL_SECONDS: int = 86400

    # --- Google / Apple OIDC (S09 §3.1) ---
    # id_token verification accepts these as `aud`. Google: iOS/Android/web
    # client_ids; Apple: the app bundle id. (Apple id_tokens are RS256-signed —
    # the ES256 key is only for the client_secret we send to Apple.)
    GOOGLE_CLIENT_IDS: list[str] = Field(default_factory=list)
    GOOGLE_JWKS_URL: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_OIDC_ISSUERS: list[str] = Field(
        default_factory=lambda: ["accounts.google.com", "https://accounts.google.com"]
    )
    APPLE_BUNDLE_ID: str | None = None
    APPLE_OIDC_ISSUER: str = "https://appleid.apple.com"
    APPLE_JWKS_URL: str = "https://appleid.apple.com/auth/keys"

    # --- Refresh rotation ---
    AUTH_REFRESH_GRACE_SECONDS: int = 5

    # --- KTO ---
    KTO_SERVICE_KEY: str = ""
    KTO_BASE_URL_KOR: str = "http://apis.data.go.kr/B551011/KorService2"
    KTO_BASE_URL_TARRLTE: str = "https://apis.data.go.kr/B551011/TarRlteTarService1"
    KTO_BASE_URL_CNCTR: str = "https://apis.data.go.kr/B551011/TatsCnctrRateService"
    KTO_BASE_URL_DATALAB: str = "https://apis.data.go.kr/B551011/DataLabService"
    KTO_MOBILE_APP: str = "PicTrip"

    # --- LLM ---
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_REASON_CACHE_TTL_DAYS: int = 30

    # --- Embedding ---
    CLIP_MODEL_NAME: str = "openai/clip-vit-base-patch32"
    CLIP_DEVICE: Literal["cpu", "cuda", "mps"] = "cpu"

    # --- Photo search (TST) ---
    # Calibrated cosine-similarity floor for photo-search matches (S07 §10).
    # Matches below this are dropped — *unless* the whole set is below it, in
    # which case a top-N soft floor still surfaces the best ones (a sparse
    # result must not be empty). Cap the returned matches at PHOTO_SEARCH_MAX.
    PHOTO_SEARCH_SIMILARITY_FLOOR: float = 0.60
    PHOTO_SEARCH_MAX: int = 30

    # --- Admin console (A01) ---
    # Used by the separate admin plan; required to be set before /admin is wired,
    # otherwise /admin/* returns 503.
    ADMIN_PASSWORD: str | None = None

    # --- Observability ---
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.05

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
