from fastapi import APIRouter, Request
from backend.src.core.dependencies import DBSession
from backend.src.modules.auth.application.dtos import LoginDTO, RefreshDTO, TokenResponseDTO
from backend.src.modules.auth.application.use_cases import AuthUseCases
from backend.src.core.responses import SuccessResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=SuccessResponse[TokenResponseDTO])
async def login(dto: LoginDTO, request: Request, db: DBSession):
    uc = AuthUseCases(db)
    tokens = await uc.login(dto, ip_address=request.client.host if request.client else None)
    return SuccessResponse.ok(tokens)


@router.post("/refresh", response_model=SuccessResponse[TokenResponseDTO])
async def refresh(dto: RefreshDTO, db: DBSession):
    uc = AuthUseCases(db)
    tokens = await uc.refresh(dto.refresh_token)
    return SuccessResponse.ok(tokens)


@router.post("/logout", status_code=204)
async def logout(dto: RefreshDTO, db: DBSession):
    uc = AuthUseCases(db)
    await uc.logout(dto.refresh_token)
