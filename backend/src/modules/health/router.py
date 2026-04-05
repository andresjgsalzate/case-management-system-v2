from fastapi import APIRouter
from backend.src.core.responses import SuccessResponse

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", response_model=SuccessResponse[dict])
async def health_check():
    return SuccessResponse(data={"status": "ok"}, message="Service is healthy")
