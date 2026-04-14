from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.cases.infrastructure.models import CaseNumberRangeModel


def format_range_number(prefix: str, number: int) -> str:
    """Formats a case number: PREFIX-000001 (always 6-digit zero-padded)."""
    return f"{prefix.upper()}{number:06d}"


async def next_case_number(db: AsyncSession, tenant_id: str | None) -> str:
    """
    Generates the next case number atomically using SELECT FOR UPDATE.
    Picks the first non-exhausted range ordered by range_start.
    Raises 400 if no available ranges exist for the tenant.
    """
    result = await db.execute(
        select(CaseNumberRangeModel)
        .where(
            CaseNumberRangeModel.tenant_id == tenant_id,
            CaseNumberRangeModel.current_number < CaseNumberRangeModel.range_end,
        )
        .order_by(CaseNumberRangeModel.range_start.asc())
        .limit(1)
        .with_for_update()
    )
    rng = result.scalar_one_or_none()

    if not rng:
        raise HTTPException(
            status_code=400,
            detail="No hay rangos de numeración disponibles. Configure un rango en Ajustes → Numeración de Casos.",
        )

    rng.current_number += 1
    await db.flush()

    return format_range_number(rng.prefix, rng.current_number)
