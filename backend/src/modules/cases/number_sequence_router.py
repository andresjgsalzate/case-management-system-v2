"""
Router for case number range management.
Endpoint prefix: /api/v1/case-number-ranges
"""
import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.cases.infrastructure.models import CaseNumberRangeModel
from backend.src.modules.cases.application.number_service import format_range_number

router = APIRouter(
    prefix="/api/v1/case-number-ranges",
    tags=["case-number-ranges"],
)

Manage = Depends(PermissionChecker("cases", "manage"))


# ── DTOs ─────────────────────────────────────────────────────────────────────

class RangeResponseDTO(BaseModel):
    id: str
    prefix: str
    range_start: int
    range_end: int
    current_number: int
    total: int
    used: int
    remaining: int
    status: str          # "active" | "pending" | "exhausted"
    preview_first: str   # e.g. REQ-000001
    preview_last: str    # e.g. REQ-200000
    created_at: datetime


class CreateRangeDTO(BaseModel):
    prefix: str = Field(min_length=2, max_length=4)
    range_end: int = Field(ge=1)

    @field_validator("prefix")
    @classmethod
    def prefix_alpha(cls, v: str) -> str:
        v = v.upper()
        if not re.match(r"^[A-Z]{2,4}$", v):
            raise ValueError("El prefijo debe tener entre 2 y 4 letras (solo caracteres alfabéticos)")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_status(rng: CaseNumberRangeModel, is_first_available: bool) -> str:
    if rng.current_number >= rng.range_end:
        return "exhausted"
    if is_first_available:
        return "active"
    return "pending"


def _to_dto(rng: CaseNumberRangeModel, status: str) -> RangeResponseDTO:
    total = rng.range_end - rng.range_start + 1
    used = rng.current_number - (rng.range_start - 1)
    return RangeResponseDTO(
        id=rng.id,
        prefix=rng.prefix,
        range_start=rng.range_start,
        range_end=rng.range_end,
        current_number=rng.current_number,
        total=total,
        used=used,
        remaining=total - used,
        status=status,
        preview_first=format_range_number(rng.prefix, rng.range_start),
        preview_last=format_range_number(rng.prefix, rng.range_end),
        created_at=rng.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=SuccessResponse[list[RangeResponseDTO]])
async def list_ranges(
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    """Returns all ranges for the tenant, ordered by prefix then range_start."""
    result = await db.execute(
        select(CaseNumberRangeModel)
        .where(CaseNumberRangeModel.tenant_id == current_user.tenant_id)
        .order_by(CaseNumberRangeModel.prefix.asc(), CaseNumberRangeModel.range_start.asc())
    )
    ranges = result.scalars().all()

    # Determine which range is "active" per prefix (first non-exhausted)
    seen_active: set[str] = set()
    dtos: list[RangeResponseDTO] = []
    for rng in ranges:
        is_first_available = (
            rng.prefix not in seen_active
            and rng.current_number < rng.range_end
        )
        if is_first_available:
            seen_active.add(rng.prefix)
        status = _compute_status(rng, is_first_available)
        dtos.append(_to_dto(rng, status))

    return SuccessResponse.ok(dtos)


@router.post("", response_model=SuccessResponse[RangeResponseDTO], status_code=201)
async def create_range(
    dto: CreateRangeDTO,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    """
    Creates a new numbered range for a prefix.
    - For a new prefix: range_start = 1
    - For an existing prefix: range_start = max(range_end) + 1 of existing ranges
    - range_end must be >= range_start
    """
    prefix = dto.prefix  # already uppercased by validator

    # Find max range_end for this prefix+tenant to enforce consecutiveness
    max_end_result = await db.execute(
        select(func.max(CaseNumberRangeModel.range_end)).where(
            CaseNumberRangeModel.tenant_id == current_user.tenant_id,
            CaseNumberRangeModel.prefix == prefix,
        )
    )
    max_end: int | None = max_end_result.scalar_one_or_none()

    range_start = 1 if max_end is None else max_end + 1

    if dto.range_end < range_start:
        raise HTTPException(
            status_code=422,
            detail=(
                f"El rango debe terminar en al menos {range_start:,} "
                f"(el prefijo {prefix} ya llega hasta {max_end:,})."
                if max_end is not None
                else f"El rango debe terminar en al menos {range_start:,}."
            ),
        )

    rng = CaseNumberRangeModel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        prefix=prefix,
        range_start=range_start,
        range_end=dto.range_end,
        current_number=range_start - 1,  # nothing generated yet
        created_at=datetime.now(timezone.utc),
    )
    db.add(rng)
    await db.flush()

    # Determine status: active if it's the only/first non-exhausted for this prefix
    prev_active_result = await db.execute(
        select(CaseNumberRangeModel).where(
            CaseNumberRangeModel.tenant_id == current_user.tenant_id,
            CaseNumberRangeModel.prefix == prefix,
            CaseNumberRangeModel.current_number < CaseNumberRangeModel.range_end,
            CaseNumberRangeModel.id != rng.id,
        ).limit(1)
    )
    has_other_active = prev_active_result.scalar_one_or_none() is not None
    status = "pending" if has_other_active else "active"

    return SuccessResponse.ok(_to_dto(rng, status))


@router.delete("/{range_id}", status_code=204)
async def delete_range(
    range_id: str,
    db: DBSession,
    current_user: CurrentUser = Manage,
):
    """
    Deletes a range only if no numbers have been generated from it
    (current_number == range_start - 1).
    """
    result = await db.execute(
        select(CaseNumberRangeModel).where(
            CaseNumberRangeModel.id == range_id,
            CaseNumberRangeModel.tenant_id == current_user.tenant_id,
        )
    )
    rng = result.scalar_one_or_none()
    if not rng:
        raise HTTPException(status_code=404, detail="Rango no encontrado")

    if rng.current_number >= rng.range_start:
        raise HTTPException(
            status_code=409,
            detail=f"No se puede eliminar el rango: ya se generaron {rng.current_number - rng.range_start + 1} número(s) desde él.",
        )

    await db.delete(rng)
