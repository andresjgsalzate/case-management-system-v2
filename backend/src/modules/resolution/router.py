import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.websocket_manager import manager
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.chat.infrastructure.models import ChatMessageModel
from backend.src.modules.resolution.infrastructure.models import CaseResolutionRequestModel
from backend.src.modules.users.infrastructure.models import UserModel

router = APIRouter(prefix="/api/v1/cases/{case_id}", tags=["resolution"])
CasesRead = Depends(PermissionChecker("cases", "read"))


# ── DTO ───────────────────────────────────────────────────────────────────────

class RespondDTO(BaseModel):
    request_id: str
    accepted: bool
    rating: int | None = Field(default=None, ge=1, le=5)
    observation: str | None = None


# ── Helper ────────────────────────────────────────────────────────────────────

def _msg_content(
    request_id: str,
    requested_by_name: str,
    status: str = "pending",
    rating: int | None = None,
    observation: str | None = None,
    responded_by_name: str | None = None,
    responded_at: str | None = None,
) -> str:
    return json.dumps({
        "request_id": request_id,
        "requested_by_name": requested_by_name,
        "status": status,
        "rating": rating,
        "observation": observation,
        "responded_by_name": responded_by_name,
        "responded_at": responded_at,
    }, ensure_ascii=False)


# ── Responder a la solicitud ──────────────────────────────────────────────────

@router.post("/resolution-request/respond")
async def respond_resolution_request(
    case_id: str,
    dto: RespondDTO,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    """El reportador acepta o rechaza la solicitud de confirmación de resolución."""
    case = await db.get(CaseModel, case_id)
    if not case:
        raise HTTPException(404, "Caso no encontrado")

    if case.created_by != current_user.user_id:
        raise HTTPException(403, "Solo el solicitante del caso puede responder a la solicitud")

    req = await db.get(CaseResolutionRequestModel, dto.request_id)
    if not req or req.case_id != case_id:
        raise HTTPException(404, "Solicitud no encontrada")
    if req.status != "pending":
        raise HTTPException(409, "Esta solicitud ya fue respondida")

    if dto.accepted and not dto.rating:
        raise HTTPException(400, "La calificación es requerida para aceptar la solución")

    responder = await db.get(UserModel, current_user.user_id)
    responder_name = responder.full_name if responder else "Solicitante"

    now = datetime.now(timezone.utc)
    req.status = "accepted" if dto.accepted else "rejected"
    req.responded_by = current_user.user_id
    req.responded_at = now
    req.rating = dto.rating if dto.accepted else None
    req.observation = dto.observation

    # Actualizar el JSON del mensaje para que todos los clientes vean el resultado
    if req.chat_message_id:
        chat_msg = await db.get(ChatMessageModel, req.chat_message_id)
        if chat_msg:
            original = json.loads(chat_msg.content)
            chat_msg.content = _msg_content(
                request_id=req.id,
                requested_by_name=original.get("requested_by_name", "Agente"),
                status=req.status,
                rating=req.rating,
                observation=req.observation,
                responded_by_name=responder_name,
                responded_at=now.isoformat(),
            )

    await db.commit()

    # Si rechazado: restaurar el estado anterior del caso
    if not dto.accepted and req.previous_status_id:
        case.status_id = req.previous_status_id
        await db.commit()

    # Notificar clientes WS para recargar el chat
    await manager.broadcast(
        case_id=case_id,
        message={"type": "new_message", "data": {"id": req.chat_message_id}},
    )

    from backend.src.core.events.bus import event_bus
    from backend.src.core.events.base import BaseEvent
    # Obtener nombre del agente que solicitó la resolución
    requester = await db.get(UserModel, req.requested_by)
    requester_name = requester.full_name if requester else "Agente"

    await event_bus.publish(BaseEvent(
        event_name="resolution.responded",
        tenant_id=current_user.tenant_id,
        actor_id=current_user.user_id,
        payload={
            "case_id": case_id,
            "accepted": dto.accepted,
            "rating": dto.rating,
            "responder_name": responder_name,
            "requester_name": requester_name,
        },
    ))

    return SuccessResponse.ok({"status": req.status})


# ── Consultar resultado (para el tab Detalles) ────────────────────────────────

@router.get("/resolution-request/result")
async def get_resolution_result(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = CasesRead,
):
    """Devuelve la respuesta más reciente del reportador (para mostrar en el detalle del caso)."""
    result = await db.execute(
        select(CaseResolutionRequestModel)
        .where(CaseResolutionRequestModel.case_id == case_id)
        .order_by(CaseResolutionRequestModel.requested_at.desc())
        .limit(1)
    )
    req = result.scalar_one_or_none()
    if not req:
        return SuccessResponse.ok(None)

    # Cargar nombres
    requester = await db.get(UserModel, req.requested_by)
    responder = await db.get(UserModel, req.responded_by) if req.responded_by else None

    return SuccessResponse.ok({
        "id": req.id,
        "status": req.status,
        "requested_by_name": requester.full_name if requester else "Agente",
        "requested_at": req.requested_at.isoformat(),
        "responded_by_name": responder.full_name if responder else None,
        "responded_at": req.responded_at.isoformat() if req.responded_at else None,
        "rating": req.rating,
        "observation": req.observation,
    })
