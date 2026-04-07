from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.search.application.use_cases import SearchUseCases

router = APIRouter(prefix="/api/v1/search", tags=["search"])
SearchRead = Depends(PermissionChecker("search", "read"))


@router.get("")
async def global_search(
    db: DBSession,
    q: str = Query(..., min_length=2, description="Término de búsqueda"),
    limit: int = Query(default=10, le=25),
    current_user: CurrentUser = SearchRead,
):
    uc = SearchUseCases(db=db)
    results = await uc.search_all(query=q, limit=limit)
    return SuccessResponse.ok(results)
