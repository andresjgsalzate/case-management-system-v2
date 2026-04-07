from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.audit.application.use_cases import AuditUseCases
from backend.src.modules.audit.infrastructure.models import AuditLogModel

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
AuditRead = Depends(PermissionChecker("audit", "read"))


@router.get("", response_model=SuccessResponse[list[dict]])
async def get_audit_logs(
    db: DBSession,
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = AuditRead,
):
    uc = AuditUseCases(db=db)
    logs = await uc.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return SuccessResponse.ok([_serialize(log) for log in logs])


def _serialize(log: AuditLogModel) -> dict:
    return {
        "id": log.id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "changes": log.changes,
        "actor_id": log.actor_id,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat(),
    }
