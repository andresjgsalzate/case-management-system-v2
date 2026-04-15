import uuid
from backend.src.core.events.base import BaseEvent


EVENT_DESCRIPTIONS = {
    "case.created": lambda p: f"Caso {p.get('case_number', '')} creado: {p.get('title', '')}",
    "case.updated": lambda p: "Caso actualizado",
    "case.status_changed": lambda p: (
        f"Estado cambiado de '{p.get('from_status', '')}' a '{p.get('to_status', '')}'"
    ),
    "case.assigned": lambda p: (
        f"Asignado a {p.get('assigned_to_name', p.get('assigned_to', ''))}"
        if p.get("assigned_to") else "Asignación removida"
    ),
    "case.closed": lambda p: "Caso cerrado",
    "case.archived": lambda p: "Caso archivado",
    "case.restored": lambda p: "Caso restaurado",
    "case.classified": lambda p: (
        f"Caso clasificado como complejidad {p.get('complexity_level', '').upper()} "
        f"({p.get('total_score', '')} pts)"
    ),
    "note.created": lambda p: "Nota interna agregada",
    "chat.message.sent": lambda p: "Mensaje enviado en el chat",
    "chat.message.edited": lambda p: "Mensaje del chat editado",
    "chat.message.deleted": lambda p: "Mensaje del chat eliminado",
    "timer.started": lambda p: "Timer de trabajo iniciado",
    "timer.stopped": lambda p: f"Timer detenido — {p.get('minutes', 0)} min registrados",
    "time_entry.manual_added": lambda p: f"Tiempo manual agregado: {p.get('minutes', 0)} min",
    "todo.completed": lambda p: f"Tarea completada: {p.get('title', '')}",
    "attachment.uploaded": lambda p: f"Archivo adjunto: {p.get('filename', '')}",
    "sla.breached": lambda p: "SLA vencido",
}


def build_activity_description(event_type: str, payload: dict) -> str:
    builder = EVENT_DESCRIPTIONS.get(event_type)
    if builder:
        return builder(payload)
    return f"Evento: {event_type}"


async def handle_case_event(event: BaseEvent) -> None:
    """Handler genérico para eventos de caso — crea entrada en activity timeline."""
    case_id = event.payload.get("case_id")
    if not case_id:
        return

    description = build_activity_description(event.event_type, event.payload)

    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.activity.infrastructure.models import ActivityEntryModel

    async with AsyncSessionLocal() as db:
        entry = ActivityEntryModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            tenant_id=event.tenant_id,
            actor_id=event.actor_id,
            event_type=event.event_type,
            description=description,
            payload=event.payload,
        )
        db.add(entry)
        await db.commit()


def register_handlers(bus) -> None:
    CASE_EVENTS = [
        "case.created",
        "case.updated",
        "case.status_changed",
        "case.assigned",
        "case.closed",
        "case.archived",
        "case.restored",
        "case.classified",
        "note.created",
        "chat.message.sent",
        "chat.message.edited",
        "chat.message.deleted",
        "timer.started",
        "timer.stopped",
        "time_entry.manual_added",
        "todo.completed",
        "attachment.uploaded",
        "sla.breached",
    ]
    for event_type in CASE_EVENTS:
        bus.subscribe(event_type, handle_case_event)
