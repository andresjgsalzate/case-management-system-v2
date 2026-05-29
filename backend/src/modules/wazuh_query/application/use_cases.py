"""Use cases para el módulo wazuh_query."""
from backend.src.core.exceptions import BusinessRuleError
from backend.src.modules.wazuh_query.application.dtos import SyscheckResponse
from backend.src.modules.wazuh_query.infrastructure.wazuh_client import WazuhClient


class WazuhQueryUseCases:
    def __init__(self, client: WazuhClient) -> None:
        self._client = client

    async def find_by_hash(
        self,
        sha256: str,
        agent_id: str | None = None,
        match_limit: int = 200,
    ) -> SyscheckResponse:
        if not sha256 or len(sha256) != 64 or not all(
            c in "abcdefABCDEF0123456789" for c in sha256
        ):
            raise BusinessRuleError("hash debe ser SHA-256 (64 hex chars)")

        matches, queried, truncated = await self._client.find_by_hash(
            sha256=sha256,
            agent_id=agent_id,
            match_limit=match_limit,
        )
        return SyscheckResponse(
            hash=sha256,
            matches=matches,
            queried_agents=queried,
            truncated=truncated,
        )
