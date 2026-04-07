import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from backend.src.core.dependencies import DBSession
from backend.src.modules.classification.infrastructure.models import (
    CaseClassificationModel,
    ClassificationRuleModel,
)
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(tags=["classification"])
ClassRead = Depends(PermissionChecker("classification", "read"))
ClassManage = Depends(PermissionChecker("classification", "manage"))


class ClassifyDTO(BaseModel):
    category: str | None = None
    urgency: str | None = None
    area: str | None = None
    complexity_detail: str | None = None
    origin_detail: str | None = None


class CreateRuleDTO(BaseModel):
    name: str
    conditions: list[dict]
    result: dict
    priority: int = 0


@router.get("/api/v1/cases/{case_id}/classification")
async def get_classification(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = ClassRead,
):
    result = await db.execute(
        select(CaseClassificationModel).where(CaseClassificationModel.case_id == case_id)
    )
    cls = result.scalar_one_or_none()
    if not cls:
        return SuccessResponse.ok(None)
    return SuccessResponse.ok({
        "id": cls.id,
        "case_id": cls.case_id,
        "category": cls.category,
        "urgency": cls.urgency,
        "area": cls.area,
        "complexity_detail": cls.complexity_detail,
        "origin_detail": cls.origin_detail,
        "classified_by": cls.classified_by,
        "classified_at": cls.classified_at.isoformat(),
    })


@router.post("/api/v1/cases/{case_id}/classification", status_code=201)
async def classify_case(
    case_id: str,
    dto: ClassifyDTO,
    db: DBSession,
    current_user: CurrentUser = Depends(PermissionChecker("classification", "create")),
):
    existing = await db.execute(
        select(CaseClassificationModel).where(CaseClassificationModel.case_id == case_id)
    )
    cls = existing.scalar_one_or_none()
    if cls:
        for field, value in dto.model_dump(exclude_none=True).items():
            setattr(cls, field, value)
    else:
        cls = CaseClassificationModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            tenant_id=current_user.tenant_id,
            classified_by=current_user.user_id,
            classified_at=datetime.now(timezone.utc),
            **dto.model_dump(exclude_none=True),
        )
        db.add(cls)
    await db.commit()

    from backend.src.core.events.bus import event_bus
    from backend.src.core.events.base import BaseEvent
    await event_bus.publish(
        BaseEvent(
            event_name="case.classified",
            tenant_id=current_user.tenant_id,
            actor_id=current_user.user_id,
            payload={"case_id": case_id},
        )
    )
    return SuccessResponse.ok({"classified": True})


# ─── Classification Rules ─────────────────────────────────────────────────────

@router.get("/api/v1/classification-rules")
async def list_rules(
    db: DBSession,
    current_user: CurrentUser = ClassRead,
):
    result = await db.execute(
        select(ClassificationRuleModel)
        .where(ClassificationRuleModel.tenant_id == current_user.tenant_id)
        .order_by(ClassificationRuleModel.priority)
    )
    rules = result.scalars().all()
    return SuccessResponse.ok([
        {
            "id": r.id,
            "name": r.name,
            "conditions": r.conditions,
            "result": r.result,
            "priority": r.priority,
            "is_active": r.is_active,
        }
        for r in rules
    ])


@router.post("/api/v1/classification-rules", status_code=201)
async def create_rule(
    dto: CreateRuleDTO,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    rule = ClassificationRuleModel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        name=dto.name,
        conditions=dto.conditions,
        result=dto.result,
        priority=dto.priority,
    )
    db.add(rule)
    await db.commit()
    return SuccessResponse.ok({"id": rule.id})


@router.delete("/api/v1/classification-rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    rule = await db.get(ClassificationRuleModel, rule_id)
    if rule:
        await db.delete(rule)
        await db.commit()
