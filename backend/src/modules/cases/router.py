from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from backend.src.core.dependencies import DBSession, Pagination
from backend.src.modules.cases.application.dtos import (
    AssignCaseDTO,
    CreateCaseDTO,
    PromoteEventDTO,
    TransitionCaseDTO,
    UpdateCaseDTO,
    CaseResponseDTO,
)
from backend.src.modules.cases.application.use_cases import CaseUseCases
from backend.src.modules.cases.application.transfer_dtos import (
    TransferCaseDTO,
    TransferResponseDTO,
)
from backend.src.modules.cases.application.transfer_use_cases import CaseTransferUseCases
from backend.src.modules.assignment.application.use_cases import AssignmentUseCases
from backend.src.modules.archive.application.use_cases import ArchiveUseCases
from backend.src.core.responses import SuccessResponse, PaginatedResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.service_catalog.application.dtos import CaseCustomValueDTO


class CaseCustomValuesUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[CaseCustomValueDTO]


router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
CasesRead = Depends(PermissionChecker("cases", "read"))
CasesCreate = Depends(PermissionChecker("cases", "create"))
CasesUpdate = Depends(PermissionChecker("cases", "update"))
CasesExport = Depends(PermissionChecker("cases", "export"))


@router.get("/search", response_model=SuccessResponse[list[CaseResponseDTO]])
async def search_cases(
    db: DBSession,
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(default=10, ge=1, le=25),
    current_user: CurrentUser = CasesRead,
):
    """Global case search: activos + archivados, respetando RBAC del usuario."""
    uc = CaseUseCases(db)
    cases = await uc.search_cases(
        tenant_id=current_user.tenant_id,
        q=q,
        user=current_user,
        limit=limit,
    )
    return SuccessResponse.ok(cases)


@router.get("/archived", response_model=PaginatedResponse[CaseResponseDTO])
async def list_archived_cases(
    db: DBSession,
    pagination: Pagination,
    search: str | None = Query(default=None),
    current_user: CurrentUser = CasesRead,
):
    uc = CaseUseCases(db)
    cases, total = await uc.list_archived(
        current_user.tenant_id,
        actor_id=current_user.user_id,
        scope=current_user.scope,
        search=search,
        page=pagination.page,
        page_size=pagination.page_size,
    )
    return PaginatedResponse.ok(cases, pagination.page, pagination.page_size, total)


@router.get("", response_model=PaginatedResponse[CaseResponseDTO])
async def list_cases(
    db: DBSession,
    pagination: Pagination,
    current_user: CurrentUser = CasesRead,
    status_id: str | None = Query(default=None),
    priority_id: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
    queue: str = Query(default="all", pattern="^(mine|team|all)$"),
    case_type: str | None = Query(default=None, pattern="^(request|incident|event)$"),
    case_types: str | None = Query(default=None, description="Comma-separated list of case types"),
):
    uc = CaseUseCases(db)
    filters = {"status_id": status_id, "priority_id": priority_id, "assigned_to": assigned_to}

    # Parse case_type filter: single type or comma-separated list
    types_filter: list[str] | None = None
    if case_type:
        types_filter = [case_type]
    elif case_types:
        types_filter = [t.strip() for t in case_types.split(",") if t.strip()]

    cases, total = await uc.list_cases(
        current_user.tenant_id,
        current_user.user_id,
        current_user.scope,
        pagination.page,
        pagination.page_size,
        filters,
        user=current_user,
        queue=queue,
        case_types=types_filter,
    )
    return PaginatedResponse.ok(cases, pagination.page, pagination.page_size, total)


@router.post("", response_model=SuccessResponse[CaseResponseDTO], status_code=201)
async def create_case(
    dto: CreateCaseDTO,
    db: DBSession,
    current_user: CurrentUser = CasesCreate,
):
    uc = CaseUseCases(db)
    case = await uc.create_case(dto, current_user.user_id, current_user.tenant_id)
    return SuccessResponse.ok(case)


@router.get("/{case_id}", response_model=SuccessResponse[CaseResponseDTO])
async def get_case(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    uc = CaseUseCases(db)
    return SuccessResponse.ok(await uc.get_case(case_id))


@router.get("/{case_id}/custom-values")
async def get_case_custom_values(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    from backend.src.modules.service_catalog.application.use_cases import (
        CaseCustomValueUseCases,
    )
    cv_uc = CaseCustomValueUseCases(db)
    values = await cv_uc.list_for_case(case_id)
    return SuccessResponse.ok(values)


@router.put("/{case_id}/custom-values")
async def upsert_case_custom_values(
    case_id: str,
    body: CaseCustomValuesUpsertRequest,
    db: DBSession,
    current_user: CurrentUser = CasesUpdate,
):
    from backend.src.modules.service_catalog.application.use_cases import (
        CaseCustomValueUseCases,
    )
    cv_uc = CaseCustomValueUseCases(db)
    await cv_uc.upsert_values(case_id, body.values, current_user.tenant_id)
    return SuccessResponse.ok(await cv_uc.list_for_case(case_id))


@router.patch("/{case_id}", response_model=SuccessResponse[CaseResponseDTO])
async def update_case(
    case_id: str,
    dto: UpdateCaseDTO,
    db: DBSession,
    current_user: CurrentUser = CasesUpdate,
):
    uc = CaseUseCases(db)
    return SuccessResponse.ok(
        await uc.update_case(case_id, dto, current_user.user_id, current_user.tenant_id, user=current_user)
    )


@router.post("/{case_id}/transition", response_model=SuccessResponse[CaseResponseDTO])
async def transition_case(
    case_id: str,
    dto: TransitionCaseDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "transition")),
):
    uc = CaseUseCases(db)
    return SuccessResponse.ok(
        await uc.transition_case(case_id, dto, current_user.user_id, current_user.tenant_id, user=current_user)
    )


@router.get("/export/csv")
async def export_cases_csv(
    db: DBSession,
    current_user: CurrentUser = CasesExport,
):
    """Export all non-archived cases for the current tenant as CSV.

    Path was previously /{case_id}/export/csv but the use case ignored
    case_id (always returns all tenant cases). Renamed to match real
    behavior; audit showed zero callers of the old path.
    """
    uc = CaseUseCases(db)
    csv_content = await uc.export_csv(current_user.tenant_id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cases.csv"},
    )


@router.post("/{case_id}/assign", status_code=204)
async def assign_case(
    case_id: str,
    dto: AssignCaseDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "assign")),
):
    uc = AssignmentUseCases(db)
    await uc.assign_case(
        case_id, dto.assigned_to, dto.team_id, current_user.user_id, current_user.tenant_id
    )


@router.post("/{case_id}/transfer", response_model=SuccessResponse[TransferResponseDTO])
async def transfer_case(
    case_id: str,
    dto: TransferCaseDTO,
    db: DBSession,
    current_user: CurrentUser = CasesUpdate,
):
    uc = CaseTransferUseCases(db)
    result = await uc.transfer(case_id, dto, current_user)
    return SuccessResponse.ok(result)


@router.get("/{case_id}/transfers", response_model=SuccessResponse[list[TransferResponseDTO]])
async def list_case_transfers(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    uc = CaseTransferUseCases(db)
    items = await uc.list_transfers(case_id)
    return SuccessResponse.ok(items)


@router.get("/{case_id}/assignments")
async def list_case_assignments(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    from sqlalchemy import select
    from backend.src.modules.assignment.infrastructure.models import CaseAssignmentModel
    from backend.src.modules.users.infrastructure.models import UserModel

    result = await db.execute(
        select(CaseAssignmentModel)
        .where(CaseAssignmentModel.case_id == case_id)
        .order_by(CaseAssignmentModel.assigned_at.desc())
    )
    assignments = result.scalars().all()

    user_ids = set()
    for a in assignments:
        if a.assigned_to:
            user_ids.add(a.assigned_to)
        if a.assigned_by:
            user_ids.add(a.assigned_by)

    users_map: dict[str, str] = {}
    if user_ids:
        users_result = await db.execute(
            select(UserModel).where(UserModel.id.in_(user_ids))
        )
        for u in users_result.scalars().all():
            users_map[u.id] = u.full_name

    return SuccessResponse.ok([
        {
            "id": a.id,
            "assigned_to": a.assigned_to,
            "assigned_to_name": users_map.get(a.assigned_to) if a.assigned_to else None,
            "assigned_by": a.assigned_by,
            "assigned_by_name": users_map.get(a.assigned_by) if a.assigned_by else None,
            "team_id": a.team_id,
            "assigned_at": a.assigned_at.isoformat(),
        }
        for a in assignments
    ])


@router.post("/{case_id}/promote", response_model=SuccessResponse[CaseResponseDTO])
async def promote_event_to_incident(
    case_id: str,
    dto: PromoteEventDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "update")),
):
    uc = CaseUseCases(db)
    result = await uc.promote_event_to_incident(
        case_id=case_id,
        promoted_by=current_user.user_id,
        reason=dto.reason,
        new_taxonomy_id=dto.new_taxonomy_id,
        new_service_item_id=dto.new_service_item_id,
        new_priority_id=dto.new_priority_id,
        new_team_id=dto.new_team_id,
    )
    return SuccessResponse.ok(result)


@router.post("/{case_id}/archive", status_code=204)
async def archive_case(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "archive")),
):
    uc = ArchiveUseCases(db)
    await uc.archive_case(case_id, current_user.user_id, current_user.tenant_id)


@router.post("/{case_id}/restore", status_code=204)
async def restore_case(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "archive")),
):
    uc = ArchiveUseCases(db)
    await uc.restore_case(case_id, current_user.user_id, current_user.tenant_id)


@router.get("/{case_id}/kb-articles", response_model=SuccessResponse[list[dict]])
async def list_case_kb_articles(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    from backend.src.modules.knowledge_base.application.use_cases import KBUseCases
    uc = KBUseCases(db=db)
    items = await uc.list_case_articles(case_id=case_id, user=current_user)
    return SuccessResponse.ok(items)

