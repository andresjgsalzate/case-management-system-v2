from fastapi import APIRouter, Depends
from sqlalchemy import select

from backend.src.core.dependencies import DBSession
from backend.src.modules.activity.infrastructure.models import ActivityEntryModel
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/api/v1/cases", tags=["activity"])


@router.get("/{case_id}/activity", response_model=SuccessResponse[list[dict]])
async def get_activity(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("cases", "read")),
):
    from backend.src.modules.users.infrastructure.models import UserModel

    result = await db.execute(
        select(ActivityEntryModel)
        .where(ActivityEntryModel.case_id == case_id)
        .order_by(ActivityEntryModel.created_at.desc())
    )
    entries = result.scalars().all()

    # Batch-load actor names
    actor_ids = {e.actor_id for e in entries if e.actor_id}
    actors: dict[str, str] = {}
    if actor_ids:
        users_result = await db.execute(
            select(UserModel).where(UserModel.id.in_(actor_ids))
        )
        for u in users_result.scalars().all():
            actors[u.id] = u.full_name

    return SuccessResponse.ok(
        [
            {
                "id": e.id,
                "event_type": e.event_type,
                "description": e.description,
                "actor_id": e.actor_id,
                "actor_name": actors.get(e.actor_id) if e.actor_id else None,
                "payload": e.payload,
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ]
    )
