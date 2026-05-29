from fastapi import APIRouter, Depends

from backend.src.core.config import get_settings
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.responses import SuccessResponse
from backend.src.modules.enrichment.application.dtos import (
    ReputationRequest,
    ReputationResponse,
)
from backend.src.modules.enrichment.application.use_cases import EnrichmentUseCases

router = APIRouter(prefix="/api/v1/enrichment", tags=["enrichment"])

EnrichmentQuery = Depends(PermissionChecker("enrichment", "query"))


@router.post("/reputation", response_model=SuccessResponse[ReputationResponse])
async def get_reputation(
    body: ReputationRequest,
    current_user: CurrentUser = EnrichmentQuery,
):
    settings = get_settings()
    uc = EnrichmentUseCases(
        vt_api_key=settings.VT_API_KEY,
        otx_api_key=settings.OTX_API_KEY,
    )
    result = await uc.get_reputation(body)
    return SuccessResponse.ok(result)
