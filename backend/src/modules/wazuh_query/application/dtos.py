"""DTOs para el módulo wazuh_query."""
from datetime import datetime

from pydantic import BaseModel, Field


class SyscheckMatch(BaseModel):
    agent_id: str
    agent_name: str
    file_path: str
    file_size: int | None = None
    sha256: str
    md5: str | None = None
    last_modified: datetime | None = None


class SyscheckResponse(BaseModel):
    hash: str
    matches: list[SyscheckMatch]
    queried_agents: int
    truncated: bool = Field(
        default=False,
        description="True si hay más resultados que el límite aplicado",
    )
