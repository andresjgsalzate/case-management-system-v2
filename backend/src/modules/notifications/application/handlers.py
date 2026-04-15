"""
Notification event handlers.

Listens to system events, resolves the configured template for each event,
interpolates variables, and persists the notification in the DB.
"""
import uuid
from backend.src.core.events.base import BaseEvent


def _fmt(template: str, variables: dict) -> str:
    """Safe format — missing keys become empty string instead of raising KeyError."""
    try:
        return template.format_map({k: (v or "") for k, v in variables.items()})
    except Exception:
        return template


async def _save_notification(
    user_id: str,
    event: BaseEvent,
    variables: dict,
    reference_id: str | None = None,
    reference_type: str | None = None,
) -> None:
    """Resolve template, format it, and persist the notification."""
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.notifications.infrastructure.models import NotificationModel
    from backend.src.modules.notifications.application.template_use_cases import (
        NotificationTemplateUseCases,
    )

    async with AsyncSessionLocal() as db:
        uc = NotificationTemplateUseCases(db)
        template = await uc.get_by_event(event.event_name)
        if not template or not template.is_enabled:
            return

        notif = NotificationModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=_fmt(template.title, variables),
            body=_fmt(template.body, variables),
            notification_type=template.notification_type,
            reference_id=reference_id,
            reference_type=reference_type,
            tenant_id=event.tenant_id,
        )
        db.add(notif)
        await db.commit()


async def _send_email_for_event(
    user_id: str,
    subject: str,
    event_name: str,
    variables: dict,
) -> None:
    """Resolve email template for event, render HTML, send to user's email."""
    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.email_config.application.template_use_cases import EmailTemplateUseCases
    from backend.src.modules.notifications.application.email_client import render_email_html, send_email
    from backend.src.modules.users.infrastructure.models import UserModel
    from sqlalchemy import select
    import logging

    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(UserModel).where(UserModel.id == user_id))
            user = result.scalar_one_or_none()
            if not user or not user.email:
                return

            uc = EmailTemplateUseCases(db)
            template = await uc.resolve_for_event(event_name)
            if not template:
                return

            html = render_email_html(template.blocks, variables)
            await send_email(user.email, subject, html)
    except Exception as e:
        logging.getLogger(__name__).error("Error sending email notification: %s", e)


# ── Handlers ──────────────────────────────────────────────────────────────────

async def handle_notification_create(event: BaseEvent) -> None:
    """Direct notification.create — publisher provides all fields explicitly."""
    p = event.payload
    user_id = p.get("user_id")
    if not user_id:
        return

    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.notifications.infrastructure.models import NotificationModel

    async with AsyncSessionLocal() as db:
        notif = NotificationModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=p.get("title", "Notificación"),
            body=p.get("body", ""),
            notification_type=p.get("notification_type", "info"),
            reference_id=p.get("reference_id"),
            reference_type=p.get("reference_type"),
            tenant_id=event.tenant_id,
        )
        db.add(notif)
        await db.commit()


async def handle_case_assigned(event: BaseEvent) -> None:
    p = event.payload
    assigned_to = p.get("assigned_to")
    if not assigned_to:
        return

    await _save_notification(
        user_id=assigned_to,
        event=event,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "assigned_by": p.get("assigned_by_name", "Sistema"),
        },
        reference_id=p.get("case_id"),
        reference_type="case",
    )
    await _send_email_for_event(
        user_id=assigned_to,
        subject=f"Caso asignado: {p.get('case_number', '')}",
        event_name=event.event_name,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "assigned_by": p.get("assigned_by_name", "Sistema"),
        },
    )


async def handle_case_status_changed(event: BaseEvent) -> None:
    """Notifica al creador del caso cuando cambia el estado."""
    p = event.payload
    created_by = p.get("created_by")
    actor_id = event.actor_id
    # No notificar si el creador es quien hizo el cambio
    if not created_by or created_by == actor_id:
        return

    await _save_notification(
        user_id=created_by,
        event=event,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "from_status": p.get("from_status", ""),
            "to_status": p.get("to_status", ""),
        },
        reference_id=p.get("case_id"),
        reference_type="case",
    )
    await _send_email_for_event(
        user_id=created_by,
        subject=f"Estado actualizado: {p.get('case_number', '')}",
        event_name=event.event_name,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "from_status": p.get("from_status", ""),
            "to_status": p.get("to_status", ""),
        },
    )


async def handle_case_updated(event: BaseEvent) -> None:
    """Notifica al agente asignado cuando le modifican el caso."""
    p = event.payload
    assigned_to = p.get("assigned_to")
    actor_id = event.actor_id
    # No notificar si el asignado es quien hizo el cambio
    if not assigned_to or assigned_to == actor_id:
        return

    await _save_notification(
        user_id=assigned_to,
        event=event,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "updated_by": p.get("updated_by", "Sistema"),
        },
        reference_id=p.get("case_id"),
        reference_type="case",
    )
    await _send_email_for_event(
        user_id=assigned_to,
        subject=f"Caso actualizado: {p.get('case_number', '')}",
        event_name=event.event_name,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": p.get("case_title", ""),
            "updated_by": p.get("updated_by", "Sistema"),
        },
    )


async def handle_sla_breached(event: BaseEvent) -> None:
    p = event.payload
    case_id = p.get("case_id")
    if not case_id:
        return

    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.cases.infrastructure.models import CaseModel
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(CaseModel).where(CaseModel.id == case_id))
        case = result.scalar_one_or_none()
        if not case or not case.assigned_to:
            return

        # Inject case data so _save_notification can use a fresh db session
    await _save_notification(
        user_id=case.assigned_to,
        event=event,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": case.title or "",
        },
        reference_id=case_id,
        reference_type="case",
    )
    await _send_email_for_event(
        user_id=case.assigned_to,
        subject=f"SLA vencido: {p.get('case_number', '')}",
        event_name=event.event_name,
        variables={
            "case_number": p.get("case_number", ""),
            "case_title": case.title or "",
        },
    )


async def handle_kb_review_requested(event: BaseEvent) -> None:
    """Notifica a los revisores (admins/managers) cuando un artículo pide revisión."""
    p = event.payload
    reviewer_id = p.get("reviewer_id")
    if not reviewer_id:
        return

    await _save_notification(
        user_id=reviewer_id,
        event=event,
        variables={
            "article_title": p.get("article_title", ""),
            "requested_by": p.get("requested_by", "Sistema"),
        },
        reference_id=p.get("article_id"),
        reference_type="article",
    )
    await _send_email_for_event(
        user_id=reviewer_id,
        subject=f"Artículo en revisión: {p.get('article_title', '')}",
        event_name=event.event_name,
        variables={
            "article_title": p.get("article_title", ""),
            "requested_by": p.get("requested_by", "Sistema"),
        },
    )


def register_handlers(bus) -> None:
    bus.subscribe("notification.create",  handle_notification_create)
    bus.subscribe("case.assigned",        handle_case_assigned)
    bus.subscribe("case.status_changed",  handle_case_status_changed)
    bus.subscribe("case.updated",         handle_case_updated)
    bus.subscribe("sla.breached",         handle_sla_breached)
    bus.subscribe("kb.review_requested",  handle_kb_review_requested)
