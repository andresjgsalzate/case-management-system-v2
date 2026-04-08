from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

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
from backend.src.modules.cases.application.number_service import format_case_number
from backend.src.modules.cases.infrastructure.models import CaseNumberSequenceModel
from backend.src.core.responses import SuccessResponse, PaginatedResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from sqlalchemy import select
import uuid

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


# ── Case number sequence configuration ────────────────────────────────────────

class CaseNumberSequenceDTO(BaseModel):
    prefix: str
    padding: int
    last_number: int
    preview: str


class UpdateCaseNumberSequenceDTO(BaseModel):
    prefix: str = Field(min_length=1, max_length=4, pattern=r"^[A-Za-z0-9]+$")
    padding: int = Field(ge=1, le=8)


@router.get("/settings/number-sequence", response_model=SuccessResponse[CaseNumberSequenceDTO])
async def get_number_sequence(
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "manage")),
):
    result = await db.execute(
        select(CaseNumberSequenceModel).where(
            CaseNumberSequenceModel.tenant_id == current_user.tenant_id
        )
    )
    seq = result.scalar_one_or_none()
    if not seq:
        seq = CaseNumberSequenceModel(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            prefix="CASE",
            padding=4,
            last_number=0,
        )
    data = CaseNumberSequenceDTO(
        prefix=seq.prefix,
        padding=seq.padding,
        last_number=seq.last_number,
        preview=format_case_number(seq.prefix, seq.padding, seq.last_number + 1),
    )
    return SuccessResponse.ok(data)


@router.patch("/settings/number-sequence", response_model=SuccessResponse[CaseNumberSequenceDTO])
async def update_number_sequence(
    dto: UpdateCaseNumberSequenceDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "manage")),
):
    result = await db.execute(
        select(CaseNumberSequenceModel).where(
            CaseNumberSequenceModel.tenant_id == current_user.tenant_id
        )
    )
    seq = result.scalar_one_or_none()
    if not seq:
        seq = CaseNumberSequenceModel(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            prefix=dto.prefix.upper(),
            padding=dto.padding,
            last_number=0,
        )
        db.add(seq)
    else:
        seq.prefix = dto.prefix.upper()
        seq.padding = dto.padding
    await db.flush()
    data = CaseNumberSequenceDTO(
        prefix=seq.prefix,
        padding=seq.padding,
        last_number=seq.last_number,
        preview=format_case_number(seq.prefix, seq.padding, seq.last_number + 1),
    )
    return SuccessResponse.ok(data)
