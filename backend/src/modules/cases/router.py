from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession, Pagination
from backend.src.modules.cases.application.dtos import (
    AssignCaseDTO,
    CreateCaseDTO,
    TransitionCaseDTO,
    UpdateCaseDTO,
    CaseResponseDTO,
)
from backend.src.modules.cases.application.use_cases import CaseUseCases
from backend.src.modules.assignment.application.use_cases import AssignmentUseCases
from backend.src.modules.archive.application.use_cases import ArchiveUseCases
from backend.src.core.responses import SuccessResponse, PaginatedResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])
CasesRead = Depends(PermissionChecker("cases", "read"))
CasesCreate = Depends(PermissionChecker("cases", "create"))
CasesUpdate = Depends(PermissionChecker("cases", "update"))
CasesExport = Depends(PermissionChecker("cases", "export"))


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
):
    uc = CaseUseCases(db)
    filters = {"status_id": status_id, "priority_id": priority_id, "assigned_to": assigned_to}
    cases, total = await uc.list_cases(
        current_user.tenant_id,
        current_user.user_id,
        current_user.scope,
        pagination.page,
        pagination.page_size,
        filters,
        user=current_user,
        queue=queue,
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


@router.patch("/{case_id}", response_model=SuccessResponse[CaseResponseDTO])
async def update_case(
    case_id: str,
    dto: UpdateCaseDTO,
    db: DBSession,
    current_user: CurrentUser = CasesUpdate,
):
    uc = CaseUseCases(db)
    return SuccessResponse.ok(
        await uc.update_case(case_id, dto, current_user.user_id, current_user.tenant_id)
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
        await uc.transition_case(case_id, dto, current_user.user_id, current_user.tenant_id)
    )


@router.get("/{case_id}/export/csv")
async def export_case_csv(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesExport,
):
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

