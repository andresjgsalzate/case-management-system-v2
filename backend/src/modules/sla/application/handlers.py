from backend.src.core.events.base import BaseEvent


async def handle_case_created_for_sla(event: BaseEvent) -> None:
    case_id = event.payload.get("case_id")
    if not case_id:
        return
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.sla.application.use_cases import start_sla_for_case

    async with AsyncSessionLocal() as db:
        await start_sla_for_case(db, case_id, event.tenant_id)


def register_handlers(bus) -> None:
    bus.subscribe("case.created", handle_case_created_for_sla)
    # Reinicia el SLA al asignar (reseat timer)
    bus.subscribe("case.assigned", handle_case_created_for_sla)
