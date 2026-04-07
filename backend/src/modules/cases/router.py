from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

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


@router.get("", response_model=PaginatedResponse[CaseResponseDTO])
async def list_cases(
    db: DBSession,
    pagination: Pagination,
    current_user: CurrentUser = CasesRead,
    status_id: str | None = Query(default=None),
    priority_id: str | None = Query(default=None),
    assigned_to: str | None = Query(default=None),
):
    uc = CaseUseCases(db)
    filters = {
        "status_id": status_id,
        "priority_id": priority_id,
        "assigned_to": assigned_to,
    }
    cases, total = await uc.list_cases(
        current_user.tenant_id,
        current_user.user_id,
        current_user.scope,
        pagination.page,
        pagination.page_size,
        filters,
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
