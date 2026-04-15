from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import BusinessRuleError


async def validate_max_hours(
    db: AsyncSession,
    case_id: str,
    tenant_id: str | None,
    new_minutes: int,
) -> None:
    """Raises BusinessRuleError if adding new_minutes would exceed the max hours
    configured for the case's complexity level in the SLA integration config."""
    from backend.src.modules.sla.infrastructure.models import SLAIntegrationConfigModel
    from backend.src.modules.classification.infrastructure.models import CaseClassificationModel
    from backend.src.modules.time_entries.infrastructure.models import TimeEntryModel

    if not tenant_id:
        return

    # Check if integration is enabled for this tenant
    cfg_result = await db.execute(
        select(SLAIntegrationConfigModel).where(
            SLAIntegrationConfigModel.tenant_id == tenant_id
        )
    )
    config = cfg_result.scalar_one_or_none()
    if not config or not config.enabled:
        return

    # Get complexity level for this case
    cls_result = await db.execute(
        select(CaseClassificationModel).where(
            CaseClassificationModel.case_id == case_id
        )
    )
    classification = cls_result.scalar_one_or_none()
    if not classification or not classification.complexity_level:
        return

    level = classification.complexity_level.lower()
    max_hours = {
        "baja": config.low_max_hours,
        "media": config.medium_max_hours,
        "alta": config.high_max_hours,
    }.get(level)

    if max_hours is None:
        return  # No limit configured for this level

    max_minutes = int(max_hours * 60)

    # Sum existing time entries for this case
    total_result = await db.execute(
        select(func.sum(TimeEntryModel.minutes)).where(
            TimeEntryModel.case_id == case_id,
            TimeEntryModel.is_deleted == False,
        )
    )
    existing_minutes = total_result.scalar() or 0

    if existing_minutes + new_minutes > max_minutes:
        remaining = max_minutes - existing_minutes
        raise BusinessRuleError(
            f"El caso tiene complejidad {level.upper()} con un máximo de {max_hours}h. "
            f"Ya tienes {existing_minutes // 60}h {existing_minutes % 60}m registradas. "
            f"Solo puedes registrar {max(0, remaining)} minutos más."
        )
