import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, field_validator

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.core.websocket_manager import manager
from backend.src.modules.chat.application.use_cases import ChatUseCases

router = APIRouter(prefix="/api/v1/cases/{case_id}/chat", tags=["chat"])
ChatRead = Depends(PermissionChecker("cases", "read"))
ChatCreate = Depends(PermissionChecker("cases", "read"))


class MessageCreate(BaseModel):
    content: str
    content_type: str = "text"
    attachment_id: str | None = None

    @field_validator("content_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("text", "image", "file"):
            raise ValueError("content_type debe ser text, image o file")
        return v


class MessageUpdate(BaseModel):
    content: str


@router.websocket("/ws")
async def websocket_endpoint(
    case_id: str,
    websocket: WebSocket,
    token: str,  # query param: ?token=<jwt>
):
    from backend.src.core.security import decode_access_token
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub", "unknown")
    except Exception:
        await websocket.close(code=1008)
        return

    await manager.connect(case_id=case_id, user_id=user_id, websocket=websocket)
    listener_task = asyncio.create_task(manager.subscribe_and_forward(case_id))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(case_id=case_id, user_id=user_id)
        listener_task.cancel()


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_messages(
    case_id: str,
    db: DBSession,
    limit: int = 50,
    offset: int = 0,
    current_user: CurrentUser = ChatRead,
):
    uc = ChatUseCases(db=db)
    messages = await uc.list_messages(case_id=case_id, limit=limit, offset=offset)
    return SuccessResponse.ok([
        {
            "id": m.id,
            "user_id": m.user_id,
            "sender_name": m.sender.full_name if m.sender else "Usuario",
            "content": m.content,
            "content_type": m.content_type,
            "is_deleted": m.is_deleted,
            "is_edited": m.is_edited,
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ])


@router.post("", status_code=201)
async def send_message(
    case_id: str,
    body: MessageCreate,
    db: DBSession,
    current_user: CurrentUser = ChatCreate,
):
    uc = ChatUseCases(db=db)
    msg = await uc.send_message(
        case_id=case_id,
        user_id=current_user.user_id,
        tenant_id=current_user.tenant_id,
        content=body.content,
        content_type=body.content_type,
        attachment_id=body.attachment_id,
    )
    payload = {
        "type": "new_message",
        "data": {"id": msg.id, "user_id": msg.user_id, "content": msg.content},
    }
    await manager.broadcast(case_id=case_id, message=payload)
    return SuccessResponse.ok({"id": msg.id})


@router.patch("/{message_id}", response_model=SuccessResponse[dict])
async def edit_message(
    case_id: str,
    message_id: str,
    body: MessageUpdate,
    db: DBSession,
    current_user: CurrentUser = ChatCreate,
):
    uc = ChatUseCases(db=db)
    msg = await uc.edit_message(
        message_id=message_id,
        user_id=current_user.user_id,
        new_content=body.content,
    )
    await manager.broadcast(
        case_id=case_id,
        message={"type": "message_edited", "data": {"message_id": message_id, "content": msg.content}},
    )
    return SuccessResponse.ok({"id": msg.id, "content": msg.content})


@router.delete("/{message_id}", status_code=204)
async def delete_message(
    case_id: str,
    message_id: str,
    db: DBSession,
    current_user: CurrentUser = ChatCreate,
):
    uc = ChatUseCases(db=db)
    await uc.delete_message(message_id=message_id, user_id=current_user.user_id)
    await manager.broadcast(
        case_id=case_id,
        message={"type": "message_deleted", "data": {"message_id": message_id}},
    )
