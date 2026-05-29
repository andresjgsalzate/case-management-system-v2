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

    # Keycloak (Sub-spec 09) — token validation source for PermissionChecker.
    # JWKS / token / logout URLs are back-channel calls the backend makes;
    # in dev the backend runs on the host (dev.sh) and reaches Keycloak via
    # the host-exposed port. In prod the backend lives on the docker network
    # and uses `http://keycloak:8080/...`.
    # The issuer must match the `iss` claim Keycloak puts on tokens (driven
    # by KC_HOSTNAME in docker-compose), independently of where the back-
    # channel hits Keycloak. ISSUER is also the URL the browser is redirected
    # to for login.
    KEYCLOAK_JWKS_URL: str = (
        "http://localhost:8080/auth/realms/cms/protocol/openid-connect/certs"
    )
    KEYCLOAK_INTERNAL_URL: str = "http://localhost:8080/auth/realms/cms"
    KEYCLOAK_ISSUER: str = "https://cms.local/auth/realms/cms"
    KEYCLOAK_AUDIENCE: str = "cms-frontend"
    KEYCLOAK_FRONTEND_CLIENT_ID: str = "cms-frontend"

    # Public origin for the user-facing application. Used to compose the
    # backend's OIDC callback URL and the post-login landing page.
    CMS_FRONTEND_URL: str = "https://cms.local"

    # n8n Public REST API (sub-spec 09 inventory feature).
    # Dev: backend runs on host so it reaches n8n through nginx at the
    # `/n8n-api/` path that strips the prefix on the way in.
    # Prod: backend joins the docker network -> override with
    # `http://n8n:5678/api/v1`. API key is generated in n8n's UI
    # (Settings -> n8n API -> Create API key).
    N8N_API_BASE_URL: str = "https://cms.local/n8n-api/v1"
    N8N_API_KEY: str | None = None
    # Public base URL n8n uses to build webhook URLs (must match the
    # `WEBHOOK_URL` env var of the n8n container). The inventory page
    # uses this to compose full webhook URLs from a workflow's nodes
    # when an operator registers an orphan -- avoids manual copy/paste.
    # Trailing slash is required to keep the join predictable.
    N8N_WEBHOOK_BASE: str = "https://cms.local/webhook/"

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

    # Velociraptor (Sub-spec 07) — DFIR integration
    # Endpoint is for diagnostics/logging; the actual gRPC connection
    # string comes from `api.config.yaml` so the cert SAN matches.
    VELOCIRAPTOR_ENDPOINT: str | None = None
    # Path to api.config.yaml (mTLS credentials for the Velociraptor API)
    VELOCIRAPTOR_API_CONFIG_PATH: str | None = None

    # Enrichment — VirusTotal + AlienVault OTX (opcional; sin key el proveedor
    # devuelve "unknown" en lugar de crash)
    VT_API_KEY: SecretStr | None = None
    OTX_API_KEY: SecretStr | None = None

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
