from fastapi import APIRouter, Depends, Query

from backend.src.core.config import get_settings
from backend.src.core.exceptions import OperationalError
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.responses import SuccessResponse
from backend.src.modules.wazuh_query.application.dtos import SyscheckResponse
from backend.src.modules.wazuh_query.application.use_cases import WazuhQueryUseCases
from backend.src.modules.wazuh_query.infrastructure.wazuh_client import WazuhClient

router = APIRouter(prefix="/api/v1/wazuh", tags=["wazuh"])

WazuhQuerySyscheck = Depends(PermissionChecker("wazuh", "query_syscheck"))


@router.get("/syscheck", response_model=SuccessResponse[SyscheckResponse])
async def query_syscheck(
    hash: str = Query(..., description="SHA-256 del archivo a buscar"),
    agent_id: str | None = Query(
        default=None,
        description="ID de agente específico. Sin este parámetro se consultan todos los agentes activos.",
    ),
    _current_user: CurrentUser = WazuhQuerySyscheck,
):
    settings = get_settings()
    if not settings.WAZUH_API_URL or not settings.WAZUH_API_USER or not settings.WAZUH_API_PASSWORD:
        raise OperationalError(
            "Wazuh not configured (WAZUH_API_URL, WAZUH_API_USER, WAZUH_API_PASSWORD required)"
        )

    client = WazuhClient(
        base_url=settings.WAZUH_API_URL,
        username=settings.WAZUH_API_USER,
        password=settings.WAZUH_API_PASSWORD,
        verify_ssl=settings.WAZUH_VERIFY_SSL,
    )
    uc = WazuhQueryUseCases(client)
    result = await uc.find_by_hash(sha256=hash, agent_id=agent_id)
    return SuccessResponse.ok(result)
