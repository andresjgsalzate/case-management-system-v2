from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.automation.application.use_cases import AutomationUseCases

router = APIRouter(prefix="/api/v1/automation/rules", tags=["automation"])
AutoRead = Depends(PermissionChecker("automation", "read"))
AutoWrite = Depends(PermissionChecker("automation", "create"))
AutoManage = Depends(PermissionChecker("automation", "manage"))


class RuleCreateDTO(BaseModel):
    name: str
    description: str | None = None
    trigger_event: str
    conditions: list[dict[str, Any]] = []
    actions: list[dict[str, Any]]
    condition_logic: str = "AND"


class RuleUpdateDTO(BaseModel):
    name: str | None = None
    description: str | None = None
    trigger_event: str | None = None
    conditions: list[dict[str, Any]] | None = None
    actions: list[dict[str, Any]] | None = None
    condition_logic: str | None = None


@router.get("", response_model=SuccessResponse[list[dict]])
async def list_rules(
    db: DBSession,
    active_only: bool = True,
    current_user: CurrentUser = AutoRead,
):
    uc = AutomationUseCases(db=db)
    rules = await uc.list_rules(active_only=active_only)
    return SuccessResponse.ok([_serialize(r) for r in rules])


@router.post("", status_code=201)
async def create_rule(
    body: RuleCreateDTO,
    db: DBSession,
    current_user: CurrentUser = AutoWrite,
):
    uc = AutomationUseCases(db=db)
    rule = await uc.create_rule(
        name=body.name,
        trigger_event=body.trigger_event,
        conditions=body.conditions,
        actions=body.actions,
        created_by_id=current_user.user_id,
        description=body.description,
        condition_logic=body.condition_logic,
        tenant_id=current_user.tenant_id,
    )
    return SuccessResponse.ok(_serialize(rule))


@router.post("/{rule_id}/toggle")
async def toggle_rule(
    rule_id: str,
    db: DBSession,
    current_user: CurrentUser = AutoManage,
):
    uc = AutomationUseCases(db=db)
    rule = await uc.toggle_rule(rule_id=rule_id)
    return SuccessResponse.ok(_serialize(rule))


def _serialize(r) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "trigger_event": r.trigger_event,
        "conditions": r.conditions,
        "actions": r.actions,
        "condition_logic": r.condition_logic,
        "is_active": r.is_active,
        "execution_count": r.execution_count,
        "created_by_id": r.created_by_id,
        "created_at": r.created_at.isoformat(),
        "updated_at": r.updated_at.isoformat(),
    }


@router.patch("/{rule_id}")
async def update_rule(
    rule_id: str,
    body: RuleUpdateDTO,
    db: DBSession,
    current_user: CurrentUser = AutoManage,
):
    uc = AutomationUseCases(db=db)
    rule = await uc.update_rule(
        rule_id=rule_id,
        name=body.name,
        description=body.description,
        trigger_event=body.trigger_event,
        conditions=body.conditions,
        actions=body.actions,
        condition_logic=body.condition_logic,
    )
    return SuccessResponse.ok(_serialize(rule))


@router.delete("/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    db: DBSession,
    current_user: CurrentUser = AutoManage,
):
    from sqlalchemy import select
    from backend.src.modules.automation.infrastructure.models import AutomationRuleModel
    result = await db.execute(select(AutomationRuleModel).where(AutomationRuleModel.id == rule_id))
    rule = result.scalar_one_or_none()
    if rule:
        await db.delete(rule)
        await db.commit()
