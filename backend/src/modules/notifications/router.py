import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.notifications.application.use_cases import NotificationUseCases
from backend.src.modules.notifications.infrastructure.models import NotificationModel

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])
NotifRead = Depends(PermissionChecker("notifications", "read"))
NotifWrite = Depends(PermissionChecker("notifications", "create"))


async def _sse_event_stream(user_id: str, request: Request):
    """
    Genera eventos SSE haciendo polling cada 5 segundos.
    Sólo envía notificaciones nuevas (id > last_sent_id no aplica con UUID,
    se usa created_at como cursor en vez).
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
                        "type": notif.notification_type,
                        "reference_id": notif.reference_id,
                        "reference_type": notif.reference_type,
                        "created_at": notif.created_at.isoformat(),
                    })
                    yield f"data: {payload}\n\n"
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
