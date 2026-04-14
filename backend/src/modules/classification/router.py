import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from sqlalchemy import or_

from backend.src.core.dependencies import DBSession
from backend.src.modules.classification.infrastructure.models import (
    CaseClassificationModel,
    ClassificationCriterionModel,
    ClassificationThresholdModel,
    ClassificationRuleModel,
)
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(tags=["classification"])
ClassRead = Depends(PermissionChecker("classification", "read"))
ClassCreate = Depends(PermissionChecker("classification", "create"))
ClassManage = Depends(PermissionChecker("classification", "manage"))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _calculate_complexity(total: int, low_max: int, medium_max: int) -> str:
    if total <= low_max:
        return "baja"
    if total <= medium_max:
        return "media"
    return "alta"


def _criterion_to_dict(c: ClassificationCriterionModel) -> dict:
    return {
        "id": c.id,
        "order": c.order,
        "name": c.name,
        "score1_description": c.score1_description,
        "score2_description": c.score2_description,
        "score3_description": c.score3_description,
        "is_active": c.is_active,
    }


# ── Classification Criteria ────────────────────────────────────────────────────

class CreateCriterionDTO(BaseModel):
    name: str
    score1_description: str = ""
    score2_description: str = ""
    score3_description: str = ""
    order: int = 0


class UpdateCriterionDTO(BaseModel):
    name: str | None = None
    score1_description: str | None = None
    score2_description: str | None = None
    score3_description: str | None = None
    is_active: bool | None = None


class ReorderItemDTO(BaseModel):
    id: str
    order: int


@router.get("/api/v1/classification-criteria")
async def list_criteria(
    db: DBSession,
    current_user: CurrentUser = ClassRead,
):
    result = await db.execute(
        select(ClassificationCriterionModel)
        .where(
            or_(
                ClassificationCriterionModel.tenant_id == current_user.tenant_id,
                ClassificationCriterionModel.tenant_id.is_(None),
            )
        )
        .order_by(ClassificationCriterionModel.order, ClassificationCriterionModel.created_at)
    )
    criteria = result.scalars().all()
    return SuccessResponse.ok([_criterion_to_dict(c) for c in criteria])


@router.post("/api/v1/classification-criteria", status_code=201)
async def create_criterion(
    dto: CreateCriterionDTO,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    criterion = ClassificationCriterionModel(
        id=str(uuid.uuid4()),
        tenant_id=current_user.tenant_id,
        **dto.model_dump(),
    )
    db.add(criterion)
    await db.commit()
    await db.refresh(criterion)
    return SuccessResponse.ok(_criterion_to_dict(criterion))


@router.put("/api/v1/classification-criteria/{criterion_id}")
async def update_criterion(
    criterion_id: str,
    dto: UpdateCriterionDTO,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    criterion = await db.get(ClassificationCriterionModel, criterion_id)
    if not criterion or criterion.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail="Criterio no encontrado")
    for field, value in dto.model_dump(exclude_none=True).items():
        setattr(criterion, field, value)
    await db.commit()
    await db.refresh(criterion)
    return SuccessResponse.ok(_criterion_to_dict(criterion))


@router.delete("/api/v1/classification-criteria/{criterion_id}", status_code=204)
async def delete_criterion(
    criterion_id: str,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    criterion = await db.get(ClassificationCriterionModel, criterion_id)
    if criterion and criterion.tenant_id == current_user.tenant_id:
        await db.delete(criterion)
        await db.commit()


@router.post("/api/v1/classification-criteria/reorder")
async def reorder_criteria(
    items: list[ReorderItemDTO],
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    for item in items:
        criterion = await db.get(ClassificationCriterionModel, item.id)
        if criterion and criterion.tenant_id == current_user.tenant_id:
            criterion.order = item.order
    await db.commit()
    return SuccessResponse.ok({"reordered": True})


# ── Thresholds ────────────────────────────────────────────────────────────────

class UpdateThresholdsDTO(BaseModel):
    low_max: int
    medium_max: int


@router.get("/api/v1/classification-thresholds")
async def get_thresholds(
    db: DBSession,
    current_user: CurrentUser = ClassRead,
):
    result = await db.execute(
        select(ClassificationThresholdModel)
        .where(
            or_(
                ClassificationThresholdModel.tenant_id == current_user.tenant_id,
                ClassificationThresholdModel.tenant_id.is_(None),
            )
        )
    )
    thresholds = result.scalar_one_or_none()
    if not thresholds:
        return SuccessResponse.ok({"low_max": 6, "medium_max": 11})
    return SuccessResponse.ok({"id": thresholds.id, "low_max": thresholds.low_max, "medium_max": thresholds.medium_max})


@router.put("/api/v1/classification-thresholds")
async def update_thresholds(
    dto: UpdateThresholdsDTO,
    db: DBSession,
    current_user: CurrentUser = ClassManage,
):
    if dto.low_max >= dto.medium_max:
        raise HTTPException(status_code=400, detail="low_max debe ser menor que medium_max")
    result = await db.execute(
        select(ClassificationThresholdModel)
        .where(ClassificationThresholdModel.tenant_id == current_user.tenant_id)
    )
    thresholds = result.scalar_one_or_none()
    if thresholds:
        thresholds.low_max = dto.low_max
        thresholds.medium_max = dto.medium_max
    else:
        thresholds = ClassificationThresholdModel(
            id=str(uuid.uuid4()),
            tenant_id=current_user.tenant_id,
            low_max=dto.low_max,
            medium_max=dto.medium_max,
        )
        db.add(thresholds)
    await db.commit()
    return SuccessResponse.ok({"low_max": dto.low_max, "medium_max": dto.medium_max})


# ── Case Classification ────────────────────────────────────────────────────────

class SaveClassificationDTO(BaseModel):
    scores: dict[str, int]  # {criterion_id: 1|2|3}


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

    # Include current criteria so frontend can show descriptions
    criteria_result = await db.execute(
        select(ClassificationCriterionModel)
        .where(
            or_(
                ClassificationCriterionModel.tenant_id == current_user.tenant_id,
                ClassificationCriterionModel.tenant_id.is_(None),
            )
        )
        .order_by(ClassificationCriterionModel.order)
    )
    criteria = criteria_result.scalars().all()

    return SuccessResponse.ok({
        "id": cls.id,
        "case_id": cls.case_id,
        "scores": cls.scores,
        "total_score": cls.total_score,
        "complexity_level": cls.complexity_level,
        "classified_by": cls.classified_by,
        "classified_at": cls.classified_at.isoformat(),
        "criteria": [_criterion_to_dict(c) for c in criteria],
    })


@router.post("/api/v1/cases/{case_id}/classification", status_code=201)
async def classify_case(
    case_id: str,
    dto: SaveClassificationDTO,
    db: DBSession,
    current_user: CurrentUser = ClassCreate,
):
    # Validate scores (must be 1, 2, or 3)
    for criterion_id, score in dto.scores.items():
        if score not in (1, 2, 3):
            raise HTTPException(status_code=400, detail=f"El puntaje debe ser 1, 2 o 3 (criterio {criterion_id})")

    total = sum(dto.scores.values())

    # Get thresholds
    threshold_result = await db.execute(
        select(ClassificationThresholdModel)
        .where(ClassificationThresholdModel.tenant_id == current_user.tenant_id)
    )
    thresholds = threshold_result.scalar_one_or_none()
    low_max = thresholds.low_max if thresholds else 6
    medium_max = thresholds.medium_max if thresholds else 11

    complexity_level = _calculate_complexity(total, low_max, medium_max)

    # Upsert classification
    existing_result = await db.execute(
        select(CaseClassificationModel).where(CaseClassificationModel.case_id == case_id)
    )
    cls = existing_result.scalar_one_or_none()

    if cls:
        cls.scores = dto.scores
        cls.total_score = total
        cls.complexity_level = complexity_level
        cls.classified_by = current_user.user_id
        cls.classified_at = datetime.now(timezone.utc)
    else:
        cls = CaseClassificationModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            tenant_id=current_user.tenant_id,
            scores=dto.scores,
            total_score=total,
            complexity_level=complexity_level,
            classified_by=current_user.user_id,
            classified_at=datetime.now(timezone.utc),
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
            payload={"case_id": case_id, "total_score": total, "complexity_level": complexity_level},
        )
    )
    return SuccessResponse.ok({
        "total_score": total,
        "complexity_level": complexity_level,
    })


# ── Classification Rules (legacy auto-classification) ─────────────────────────

class CreateRuleDTO(BaseModel):
    name: str
    conditions: list[dict]
    result: dict
    priority: int = 0


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
        {"id": r.id, "name": r.name, "conditions": r.conditions, "result": r.result, "priority": r.priority, "is_active": r.is_active}
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
        **dto.model_dump(),
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
