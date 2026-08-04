from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Environment = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    API_V1_PREFIX: str = "/v1"
    CORS_ORIGINS: list[str] = Field(default_factory=list)
    TRUSTED_HOSTS: list[str] = Field(default_factory=lambda: ["*"])

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

    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")  # type: ignore[assignment]

    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_TTL_SECONDS: int = 900
    JWT_REFRESH_TOKEN_TTL_SECONDS: int = 2_592_000
    JWT_PRIVATE_KEY: str = ""
    JWT_PUBLIC_KEY: str = ""

    ADMIN_SESSION_SECRET: str = "dev-insecure-admin-session-secret-change-me"
    ADMIN_SESSION_TTL_SECONDS: int = 28_800

    KAKAO_REST_API_KEY: str = ""
    KAKAO_NATIVE_APP_KEY: str = ""
    GOOGLE_OAUTH_CLIENT_ID_IOS: str = ""
    GOOGLE_OAUTH_CLIENT_ID_ANDROID: str = ""
    GOOGLE_OAUTH_CLIENT_ID_WEB: str = ""

    KAKAO_JWKS_URL: str = "https://kauth.kakao.com/.well-known/jwks.json"
    KAKAO_OIDC_ISSUER: str = "https://kauth.kakao.com"
    KAKAO_JWKS_CACHE_TTL_SECONDS: int = 3600
    KAKAO_JWKS_STALE_ON_ERROR_TTL_SECONDS: int = 86400

    GOOGLE_CLIENT_IDS: list[str] = Field(default_factory=list)
    GOOGLE_JWKS_URL: str = "https://www.googleapis.com/oauth2/v3/certs"
    GOOGLE_OIDC_ISSUERS: list[str] = Field(
        default_factory=lambda: ["accounts.google.com", "https://accounts.google.com"]
    )
    APPLE_BUNDLE_ID: str | None = None
    APPLE_OIDC_ISSUER: str = "https://appleid.apple.com"
    APPLE_JWKS_URL: str = "https://appleid.apple.com/auth/keys"

    @model_validator(mode="after")
    def _merge_google_client_ids(self) -> Settings:
        merged = list(self.GOOGLE_CLIENT_IDS)
        for cid in (
            self.GOOGLE_OAUTH_CLIENT_ID_IOS,
            self.GOOGLE_OAUTH_CLIENT_ID_ANDROID,
            self.GOOGLE_OAUTH_CLIENT_ID_WEB,
        ):
            if cid and cid not in merged:
                merged.append(cid)
        self.GOOGLE_CLIENT_IDS = merged
        return self

    KTO_SERVICE_KEY: str = ""
    KTO_BASE_URL_KOR: str = "https://apis.data.go.kr/B551011/KorService2"
    KTO_BASE_URL_TARRLTE: str = "https://apis.data.go.kr/B551011/TarRlteTarService1"
    KTO_BASE_URL_CNCTR: str = "https://apis.data.go.kr/B551011/TatsCnctrRateService"
    KTO_BASE_URL_PET: str = "https://apis.data.go.kr/B551011/KorPetTourService2"
    KTO_BASE_URL_GALLERY: str = "https://apis.data.go.kr/B551011/PhotoGalleryService1"
    KTO_MOBILE_APP: str = "PicTrip"

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    YOUTUBE_API_KEY: str = ""

    CLIP_MODEL_NAME: str = "openai/clip-vit-base-patch32"
    CLIP_DEVICE: Literal["cpu", "cuda", "mps"] = "cpu"

    MATCH_DISTANCE_MAX: float = 0.32
    MATCH_CANDIDATES: int = 40

    IMG_PROXY_ORIGIN: str = "https://img.pictrip.org"
    IMG_PROXY_T1_SECRET: str = ""

    GITHUB_DISPATCH_TOKEN: str = ""
    GITHUB_REPO: str = "jeongeup-lab/PICTRIP"
    COLLECTION_WORKFLOW: str = "pipeline-sync.yml"
    COLLECTION_WORKFLOW_REF: str = "main"

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
