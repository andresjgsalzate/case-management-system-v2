import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.cases.infrastructure.models import CaseNumberSequenceModel


def format_case_number(prefix: str, padding: int, number: int) -> str:
    """Formatea un número de caso. El padding es mínimo — si el número supera el padding, se expande."""
    padded = str(number).zfill(padding)
    return f"{prefix.upper()}-{padded}"


async def next_case_number(db: AsyncSession, tenant_id: str | None) -> str:
    """
    Genera el siguiente número de caso de forma atómica usando SELECT FOR UPDATE.
    Garantiza unicidad incluso con múltiples requests concurrentes.
    """
    result = await db.execute(
        select(CaseNumberSequenceModel)
        .where(CaseNumberSequenceModel.tenant_id == tenant_id)
        .with_for_update()
    )
    sequence = result.scalar_one_or_none()

    if not sequence:
        sequence = CaseNumberSequenceModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            prefix="CASE",
            padding=4,
            last_number=0,
        )
        db.add(sequence)
        await db.flush()

    sequence.last_number += 1
    await db.flush()

    return format_case_number(sequence.prefix, sequence.padding, sequence.last_number)
