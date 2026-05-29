"""DTOs para el módulo de enrichment de IOCs."""
import ipaddress
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HASH_RE = re.compile(r"^[a-fA-F0-9]{32}$|^[a-fA-F0-9]{40}$|^[a-fA-F0-9]{64}$")


def is_valid_hash(h: str) -> bool:
    return bool(_HASH_RE.match(h))


def is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


class ReputationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hashes: list[str] = Field(default_factory=list)
    ips: list[str] = Field(default_factory=list)

    @field_validator("hashes", "ips", mode="before")
    @classmethod
    def _strip_and_dedupe(cls, v: list[str]) -> list[str]:
        return list(dict.fromkeys(s.strip() for s in v if s.strip()))


class ProviderVerdict(BaseModel):
    provider: str
    indicator: str
    indicator_type: str      # "hash" | "ip"
    malicious_count: int = 0
    total_engines: int | None = None
    reputation: str          # "malicious" | "suspicious" | "harmless" | "unknown"
    last_analysis_date: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ReputationResponse(BaseModel):
    verdicts: list[ProviderVerdict]
    summary: dict[str, int]
