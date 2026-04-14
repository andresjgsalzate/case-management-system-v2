import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.events.base import BaseEvent
from backend.src.core.events.bus import get_event_bus
from backend.src.core.exceptions import NotFoundError
from backend.src.modules.automation.application.engine import RuleAction, evaluate_rule
from backend.src.modules.automation.infrastructure.models import AutomationRuleModel

logger = logging.getLogger(__name__)


class AutomationUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(
        self,
        name: str,
        trigger_event: str,
        conditions: list[dict],
        actions: list[dict],
        created_by_id: str,
        description: str | None = None,
        condition_logic: str = "AND",
        tenant_id: str | None = None,
    ) -> AutomationRuleModel:
        rule = AutomationRuleModel(
            name=name,
            trigger_event=trigger_event,
            conditions=conditions,
            actions=actions,
            created_by_id=created_by_id,
            description=description,
            condition_logic=condition_logic,
            tenant_id=tenant_id,
        )
        self.db.add(rule)
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def list_rules(self, active_only: bool = True) -> list[AutomationRuleModel]:
        stmt = select(AutomationRuleModel)
        if active_only:
            stmt = stmt.where(AutomationRuleModel.is_active.is_(True))
        result = await self.db.execute(stmt.order_by(AutomationRuleModel.created_at.desc()))
        return list(result.scalars().all())

    async def update_rule(
        self,
        rule_id: str,
        name: str | None = None,
        description: str | None = None,
        trigger_event: str | None = None,
        conditions: list[dict] | None = None,
        actions: list[dict] | None = None,
        condition_logic: str | None = None,
    ) -> AutomationRuleModel:
        result = await self.db.execute(
            select(AutomationRuleModel).where(AutomationRuleModel.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise NotFoundError(f"Regla {rule_id} no encontrada")
        if name is not None:
            rule.name = name
        if description is not None:
            rule.description = description
        if trigger_event is not None:
            rule.trigger_event = trigger_event
        if conditions is not None:
            rule.conditions = conditions
        if actions is not None:
            rule.actions = actions
        if condition_logic is not None:
            rule.condition_logic = condition_logic
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def get_rule(self, rule_id: str) -> AutomationRuleModel:
        result = await self.db.execute(
            select(AutomationRuleModel).where(AutomationRuleModel.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        if not rule:
            raise NotFoundError(f"Regla {rule_id} no encontrada")
        return rule

    async def toggle_rule(self, rule_id: str) -> AutomationRuleModel:
        rule = await self.get_rule(rule_id)
        rule.is_active = not rule.is_active
        await self.db.flush()
        await self.db.refresh(rule)
        return rule

    async def evaluate_and_execute(self, event_name: str, context: dict, actor_id: str = "") -> int:
        """
        Evalúa todas las reglas activas para el evento dado y ejecuta las que coincidan.
        Retorna el número de reglas ejecutadas.
        """
        result = await self.db.execute(
            select(AutomationRuleModel).where(
                AutomationRuleModel.trigger_event == event_name,
                AutomationRuleModel.is_active.is_(True),
            )
        )
        rules = result.scalars().all()
        executed = 0
        for rule in rules:
            if evaluate_rule(rule.conditions, context, rule.condition_logic):
                await self._execute_actions(rule.actions, context, actor_id=actor_id)
                rule.execution_count += 1
                executed += 1
        if executed > 0:
            await self.db.flush()
        return executed

    async def _execute_actions(self, actions: list[dict], context: dict, actor_id: str = "") -> None:
        for action_dict in actions:
            action = RuleAction(**action_dict)
            try:
                await self._execute_single_action(action, context, actor_id=actor_id)
            except Exception as e:
                logger.error("Error ejecutando acción %s: %s", action.action_type, e)

    async def _execute_single_action(self, action: RuleAction, context: dict, actor_id: str = "") -> None:
        bus = get_event_bus()
        case_id = context.get("case_id")

        match action.action_type:
            case "send_notification":
                user_id = action.params.get("user_id")
                if user_id and case_id:
                    await bus.publish(BaseEvent(
                        event_name="notification.create",
                        actor_id=actor_id,
                        payload={
                            "user_id": user_id,
                            "title": action.params.get("title", "Automatización"),
                            "body": action.params.get("body", "Una regla de automatización se activó"),
                            "notification_type": "automation",
                            "reference_id": case_id,
                            "reference_type": "case",
                        },
                    ))
            case "change_priority":
                if case_id:
                    await bus.publish(BaseEvent(
                        event_name="automation.change_priority",
                        actor_id=actor_id,
                        payload={"case_id": case_id, "priority_id": action.params.get("priority_id")},
                    ))
            case "assign_agent":
                if case_id:
                    await bus.publish(BaseEvent(
                        event_name="automation.assign_agent",
                        actor_id=actor_id,
                        payload={"case_id": case_id, "agent_id": action.params.get("agent_id")},
                    ))
            case _:
                logger.warning("Tipo de acción no implementada: %s", action.action_type)
