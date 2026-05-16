from functools import lru_cache
from typing import List
from pydantic import field_validator, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters long")
        return v

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # Upload
    MAX_FILE_SIZE_MB: int = 10
    UPLOAD_DIR: str = "uploads"

    # SLA
    SLA_CHECK_INTERVAL_MINUTES: int = 5

    # Integrations (Sub-spec 04) — Fernet symmetric key (urlsafe-base64 32 bytes)
    # Generate via: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    INTEGRATIONS_ENCRYPTION_KEY: str | None = None

    # n8n Bridge (Sub-spec 05) — short-lived JWT signing for n8n→CMS callbacks.
    # Falls back to SECRET_KEY when unset.
    N8N_CALLBACK_JWT_SECRET: str | None = None

    # Public base URL the worker embeds in `callback_url` so n8n knows where
    # to call back. Override in production with the externally-reachable host.
    CMS_BASE_URL: str = "http://localhost:8000"

    # Email (optional)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: SecretStr = SecretStr("")
    SMTP_FROM: str = "noreply@example.com"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
