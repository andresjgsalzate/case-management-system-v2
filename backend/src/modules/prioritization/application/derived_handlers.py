"""Named handlers for criteria whose data_source is 'derived'.

Each handler takes a (case, db_session) pair and returns a DerivedResult
with .value (int in the criterion scale) + .label (human-readable).

Registered in DERIVED_HANDLERS by source_field_key.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class DerivedResult:
    value: int
    label: str


async def repetition_count_handler(case, db: AsyncSession) -> DerivedResult:
    """Counts cases with the same taxonomy_id created in last 7 days.

    Maps the raw count onto the 1-5 scale: 1=Aislado, 5=Crítico (masivo).
    """
    from backend.src.modules.cases.infrastructure.models import CaseModel

    if not case.taxonomy_id:
        return DerivedResult(value=1, label="Aislado")

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    stmt = (
        select(func.count())
        .select_from(CaseModel)
        .where(
            CaseModel.taxonomy_id == case.taxonomy_id,
            CaseModel.tenant_id == case.tenant_id,
            CaseModel.created_at >= cutoff,
            CaseModel.id != case.id,
        )
    )
    count = (await db.execute(stmt)).scalar() or 0

    if count == 0:
        return DerivedResult(value=1, label="Aislado")
    if count <= 2:
        return DerivedResult(value=2, label="Bajo")
    if count <= 5:
        return DerivedResult(value=3, label="Medio")
    if count <= 10:
        return DerivedResult(value=4, label="Alto")
    return DerivedResult(value=5, label="Crítico (masivo)")


# Dispatch table — source_field_key → handler coroutine
DERIVED_HANDLERS = {
    "repetition_count_handler": repetition_count_handler,
}
