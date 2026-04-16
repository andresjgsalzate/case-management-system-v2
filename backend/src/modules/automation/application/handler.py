"""
Consumer genérico del Event Bus que evalúa reglas de automatización
para todos los eventos de negocio configurados.
"""
import logging

from backend.src.core.events.base import BaseEvent
from backend.src.core.events.bus import EventBus

logger = logging.getLogger(__name__)

# Eventos que activan la evaluación de reglas de automatización
WATCHED_EVENTS = {
    "case.created",
    "case.status_changed",
    "case.assigned",
    "case.priority_changed",
    "sla.breached",
    "case.closed",
    "resolution.responded",
    "todo.completed",
    "attachment.uploaded",
    "note.created",
}


def register_automation_handler(bus: EventBus) -> None:
    """Registra el handler genérico en el Event Bus para cada evento vigilado."""
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.automation.application.use_cases import AutomationUseCases

    def make_handler(evt_name: str):
        async def handler(event: BaseEvent) -> None:
            async with AsyncSessionLocal() as db:
                uc = AutomationUseCases(db=db)
                executed = await uc.evaluate_and_execute(
                    event_name=evt_name,
                    context=event.payload,
                    actor_id=event.actor_id,
                )
                if executed > 0:
                    await db.commit()
                    logger.info(
                        "Automatización: %d regla(s) ejecutada(s) para evento %s",
                        executed,
                        evt_name,
                    )
        return handler

    for event_name in WATCHED_EVENTS:
        bus.subscribe(event_name, make_handler(event_name))
