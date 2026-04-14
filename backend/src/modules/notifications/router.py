import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.notifications.application.use_cases import NotificationUseCases
from backend.src.modules.notifications.application.template_use_cases import NotificationTemplateUseCases
from backend.src.modules.notifications.infrastructure.models import NotificationModel

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
NotifRead = Depends(PermissionChecker("notifications", "read"))
NotifWrite = Depends(PermissionChecker("notifications", "create"))


# ── Template DTOs ─────────────────────────────────────────────────────────────

class UpdateTemplateDTO(BaseModel):
    title: str | None = None
    body: str | None = None
    is_enabled: bool | None = None


# ── Template endpoints ────────────────────────────────────────────────────────

@router.get("/templates", response_model=SuccessResponse[list[dict]])
async def list_templates(
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationTemplateUseCases(db=db)
    templates = await uc.list_all()
    return SuccessResponse.ok([_serialize_template(t) for t in templates])


@router.patch("/templates/{template_id}", response_model=SuccessResponse[dict])
async def update_template(
    template_id: str,
    body: UpdateTemplateDTO,
    db: DBSession,
    current_user: CurrentUser = NotifWrite,
):
    uc = NotificationTemplateUseCases(db=db)
    tpl = await uc.update(
        template_id=template_id,
        title=body.title,
        body=body.body,
        is_enabled=body.is_enabled,
    )
    return SuccessResponse.ok(_serialize_template(tpl))


@router.post("/templates/{template_id}/reset", response_model=SuccessResponse[dict])
async def reset_template(
    template_id: str,
    db: DBSession,
    current_user: CurrentUser = NotifWrite,
):
    uc = NotificationTemplateUseCases(db=db)
    tpl = await uc.reset_to_default(template_id=template_id)
    return SuccessResponse.ok(_serialize_template(tpl))


def _serialize_template(t) -> dict:
    return {
        "id": t.id,
        "event_name": t.event_name,
        "notification_type": t.notification_type,
        "title": t.title,
        "body": t.body,
        "is_enabled": t.is_enabled,
        "variables": t.variables,
        "updated_at": t.updated_at.isoformat(),
    }


async def _sse_event_stream(user_id: str, request: Request):
    """
    Genera eventos SSE haciendo polling cada 5 segundos.
    Envía notificaciones nuevas no leídas y un heartbeat cada ciclo
    para mantener la conexión viva a través de proxies/firewalls.
    """
    from backend.src.core.database import AsyncSessionLocal
    import sqlalchemy as sa

    last_ids: set[str] = set()

    while True:
        if await request.is_disconnected():
            break
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                sa.select(NotificationModel)
                .where(
                    NotificationModel.user_id == user_id,
                    NotificationModel.is_read.is_(False),
                )
                .order_by(NotificationModel.created_at.desc())
                .limit(10)
            )
            notifs = result.scalars().all()
            for notif in notifs:
                if notif.id not in last_ids:
                    last_ids.add(notif.id)
                    payload = json.dumps({
                        "id": notif.id,
                        "title": notif.title,
                        "body": notif.body,
                        "notification_type": notif.notification_type,
                        "reference_id": notif.reference_id,
                        "reference_type": notif.reference_type,
                        "is_read": False,
                        "read_at": None,
                        "created_at": notif.created_at.isoformat(),
                    })
                    yield f"data: {payload}\n\n"

        # Heartbeat — SSE comment, ignored by client, keeps connection alive
        yield ": heartbeat\n\n"
        await asyncio.sleep(5)


@router.get("/stream")
async def notifications_stream(
    request: Request,
    current_user: CurrentUser = NotifRead,
):
    """SSE endpoint. Cliente conecta con EventSource('/api/v1/notifications/stream')."""
    return StreamingResponse(
        _sse_event_stream(current_user.user_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_notifications(
    db: DBSession,
    unread_only: bool = Query(default=False),
    limit: int = Query(default=30, le=100),
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationUseCases(db=db)
    notifs = await uc.list_for_user(
        user_id=current_user.user_id, unread_only=unread_only, limit=limit
    )
    return SuccessResponse.ok([_serialize(n) for n in notifs])


@router.get("/unread-count", response_model=SuccessResponse[dict])
async def get_unread_count(
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationUseCases(db=db)
    count = await uc.get_unread_count(user_id=current_user.user_id)
    return SuccessResponse.ok({"unread_count": count})


@router.post("/{notification_id}/read", status_code=204)
async def mark_read(
    notification_id: str,
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationUseCases(db=db)
    await uc.mark_read(notification_id=notification_id, user_id=current_user.user_id)


@router.post("/read-all", status_code=204)
async def mark_all_read(
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationUseCases(db=db)
    await uc.mark_all_read(user_id=current_user.user_id)


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: str,
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    uc = NotificationUseCases(db=db)
    await uc.delete(notification_id=notification_id, user_id=current_user.user_id)


@router.delete("", status_code=204)
async def delete_read_notifications(
    db: DBSession,
    current_user: CurrentUser = NotifRead,
):
    """Elimina todas las notificaciones ya leídas del usuario."""
    uc = NotificationUseCases(db=db)
    await uc.delete_all_read(user_id=current_user.user_id)


# ── Manual notification ───────────────────────────────────────────────────────

class CreateManualNotificationDTO(BaseModel):
    user_ids: list[str]
    title: str
    body: str
    notification_type: str = "info"
    reference_id: str | None = None
    reference_type: str | None = None


@router.post("/manual", status_code=201, response_model=SuccessResponse[dict])
async def create_manual_notification(
    payload: CreateManualNotificationDTO,
    db: DBSession,
    current_user: CurrentUser = NotifWrite,
):
    """
    Send a manual notification to one or more users.
    Title and body support {full_name} and {email} placeholders resolved per recipient.
    """
    from sqlalchemy import select
    from backend.src.modules.users.infrastructure.models import UserModel

    result = await db.execute(
        select(UserModel).where(UserModel.id.in_(payload.user_ids))
    )
    users = result.scalars().all()

    created = 0
    for user in users:
        variables = {"full_name": user.full_name or "", "email": user.email or ""}
        title = payload.title.format_map({k: (v or "") for k, v in variables.items()})
        body = payload.body.format_map({k: (v or "") for k, v in variables.items()})

        uc = NotificationUseCases(db=db)
        await uc.create(
            user_id=user.id,
            title=title,
            body=body,
            notification_type=payload.notification_type,
            reference_id=payload.reference_id,
            reference_type=payload.reference_type,
            tenant_id=current_user.tenant_id if hasattr(current_user, "tenant_id") else None,
        )
        created += 1

    await db.commit()
    return SuccessResponse.ok({"created": created})


def _serialize(n: NotificationModel) -> dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "notification_type": n.notification_type,
        "reference_id": n.reference_id,
        "reference_type": n.reference_type,
        "is_read": n.is_read,
        "read_at": n.read_at.isoformat() if n.read_at else None,
        "created_at": n.created_at.isoformat(),
    }
