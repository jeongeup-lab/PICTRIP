"""Application settings (pydantic-settings, validated at startup)."""

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
    # Both Kakao keys are valid id_token `aud`: native SDK uses NATIVE_APP_KEY, web/server uses REST_API_KEY.
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
    # Accepted id_token `aud`: Google client_ids and Apple bundle id (Apple id_tokens are RS256-signed).
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
        # The OIDC verifier reads GOOGLE_CLIENT_IDS as the accepted id_token `aud`
        # set. Fold the per-platform client IDs into it so filling
        # GOOGLE_OAUTH_CLIENT_ID_{IOS,ANDROID,WEB} actually enables Google login
        # (they were otherwise dead config — never read by the verifier).
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
    # Cosine-similarity floor (S07 §10); soft top-N floor keeps a sparse result non-empty.
    PHOTO_SEARCH_SIMILARITY_FLOOR: float = 0.60
    PHOTO_SEARCH_MAX: int = 30

    # --- Admin console (A01) ---
    # Auth is DB-backed (admin_users table), NOT an env var (decision 2026-06-27):
    # the credential lives in the shared CT110 DB so it needs no CT112 .env/shell to
    # set or rotate. See app/modules/admin/security.py + migration 0016.

    # --- Collection trigger (A01 §3/§5 Phase 2, decision A7) ---
    # The trigger MECHANISM is config-gated behind an adapter (triggers.py). The
    # recommended mechanism is GitHub ``workflow_dispatch``: when unconfigured
    # (no token) the endpoint returns a clean ADMIN_TRIGGER_FAILED(502) instead
    # of crashing.
    # SECRET — set in .env only (PAT/fine-grained token with ``actions:write``).
    GITHUB_DISPATCH_TOKEN: str = ""
    GITHUB_REPO: str = "jeongeup-lab/PICTRIP"  # owner/repo
    COLLECTION_WORKFLOW: str = "pipeline-sync.yml"  # workflow file id
    COLLECTION_WORKFLOW_REF: str = "main"  # git ref to dispatch on

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
