"""Event handlers that recalculate case priority when upstream data changes.

Subscribed to the global event bus via register_handlers(). Each handler
opens its own AsyncSession (handlers fire async and shouldn't share the
emitter's session).

Wiring is registered from backend/src/core/events/registry.py.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.events.base import BaseEvent

logger = logging.getLogger(__name__)


# Set of taxonomy fields whose change should trigger recalculation.
# Other field changes (name, description, MITRE techniques, etc.) don't affect
# priority and shouldn't churn cases needlessly.
PRIORITY_AFFECTING_TAXONOMY_FIELDS: frozenset[str] = frozenset({
    "prioritization_formula_id",
    "default_severity",
    "tlp_default",
})


async def process_taxonomy_update(
    db: AsyncSession,
    *,
    taxonomy_id: str,
    changed_fields: set[str],
) -> int:
    """Recalculate priority for all OPEN cases linked to this taxonomy.

    Returns the number of cases successfully recalculated. Skipped if none of
    the changed fields are priority-affecting.
    """
    if not (changed_fields & PRIORITY_AFFECTING_TAXONOMY_FIELDS):
        return 0

    from backend.src.modules.case_statuses.infrastructure.models import (
        CaseStatusModel,
    )
    from backend.src.modules.cases.infrastructure.models import CaseModel
    from backend.src.modules.prioritization.application.use_cases import (
        PrioritizationUseCases,
    )

    stmt = (
        select(CaseModel)
        .join(CaseStatusModel, CaseModel.status_id == CaseStatusModel.id)
        .where(
            CaseModel.taxonomy_id == taxonomy_id,
            CaseStatusModel.is_final.is_(False),
        )
    )
    cases = list((await db.execute(stmt)).scalars().all())
    if not cases:
        return 0

    uc = PrioritizationUseCases(db=db)
    succeeded = 0
    for case in cases:
        try:
            await uc.calculate_priority(
                case_id=case.id, triggered_by="taxonomy_changed",
            )
            succeeded += 1
        except Exception as exc:
            logger.error("Recalc failed for case %s: %s", case.id, exc)
    return succeeded


async def on_taxonomy_updated(event: BaseEvent) -> None:
    """Bus subscriber wrapper — opens its own AsyncSession.

    Expected payload: {"taxonomy_id": str, "changed_fields": list[str]}
    """
    from backend.src.core.database import AsyncSessionLocal

    taxonomy_id = event.payload.get("taxonomy_id")
    raw_fields = event.payload.get("changed_fields", [])
    if not taxonomy_id:
        return
    changed_fields = set(raw_fields) if isinstance(raw_fields, (list, set, tuple)) \
        else set()
    async with AsyncSessionLocal() as db:
        try:
            n = await process_taxonomy_update(
                db, taxonomy_id=taxonomy_id, changed_fields=changed_fields,
            )
            if n > 0:
                await db.commit()
                logger.info(
                    "Taxonomy %s changed → %d cases recalculated",
                    taxonomy_id, n,
                )
        except Exception as exc:
            logger.error("on_taxonomy_updated failed: %s", exc, exc_info=exc)
            await db.rollback()


async def on_asset_criticality_changed(event: BaseEvent) -> None:
    """Stub for Phase 1 — the asset module doesn't exist yet.

    Expected payload: {"asset_id": str}
    When applications/assets gain a `criticality` field + emit this event,
    swap this stub for a real recalc loop over cases linked to that asset.
    """
    logger.debug(
        "on_asset_criticality_changed received (stub): %s", event.payload,
    )


def register_handlers(bus) -> None:
    """Subscribe both handlers to the event bus."""
    bus.subscribe("security_taxonomy.updated", on_taxonomy_updated)
    bus.subscribe("asset.criticality_changed", on_asset_criticality_changed)
