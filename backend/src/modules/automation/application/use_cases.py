import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
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
                rule_context = {**context, "tenant_id": rule.tenant_id} if rule.tenant_id else context
                await self._execute_actions(rule.actions, rule_context, actor_id=actor_id)
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
            case "archive_closed_cases":
                days = int(action.params.get("days_after_close", "30"))
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                tenant_id = context.get("tenant_id")

                from backend.src.modules.cases.infrastructure.models import CaseModel
                from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel

                status_q = select(CaseStatusModel).where(CaseStatusModel.slug == "closed")
                if tenant_id:
                    status_q = status_q.where(CaseStatusModel.tenant_id == tenant_id)
                status_result = await self.db.execute(status_q)
                closed_status = status_result.scalar_one_or_none()
                if not closed_status:
                    logger.warning("archive_closed_cases: estado 'closed' no encontrado")
                    return

                case_filters = [
                    CaseModel.status_id == closed_status.id,
                    CaseModel.is_archived.is_(False),
                    CaseModel.closed_at.isnot(None),
                    CaseModel.closed_at <= cutoff,
                ]
                if tenant_id:
                    case_filters.append(CaseModel.tenant_id == tenant_id)
                cases_result = await self.db.execute(
                    select(CaseModel).where(and_(*case_filters))
                )
                cases = cases_result.scalars().all()

                now = datetime.now(timezone.utc)
                archived_by = actor_id if actor_id and actor_id != "system" else None
                for case in cases:
                    case.is_archived = True
                    case.archived_at = now
                    case.archived_by = archived_by

                logger.info(
                    "archive_closed_cases: %d caso(s) archivados (cutoff: %s)",
                    len(cases),
                    cutoff.date(),
                )
            case "change_status":
                if not case_id:
                    logger.warning("change_status: no hay case_id en el contexto")
                    return
                target_status_id = action.params.get("target_status_id")
                if not target_status_id:
                    logger.warning("change_status: target_status_id no configurado")
                    return
                from backend.src.modules.cases.infrastructure.models import CaseModel
                from backend.src.modules.case_statuses.infrastructure.models import CaseStatusModel
                target_status = await self.db.get(CaseStatusModel, target_status_id)
                if not target_status:
                    logger.warning("change_status: estado %s no encontrado", target_status_id)
                    return
                case_obj = await self.db.get(CaseModel, case_id)
                if not case_obj:
                    logger.warning("change_status: caso %s no encontrado", case_id)
                    return
                case_obj.status_id = target_status_id
                if target_status.is_final and not case_obj.closed_at:
                    case_obj.closed_at = datetime.now(timezone.utc)
                logger.info("change_status: caso %s → estado %s", case_id, target_status.name)

            case "create_todo":
                if not case_id:
                    logger.warning("create_todo: no hay case_id en el contexto")
                    return
                title = action.params.get("title", "").strip()
                if not title:
                    logger.warning("create_todo: título vacío")
                    return
                created_by = actor_id if (actor_id and actor_id != "system") else None
                if not created_by:
                    logger.warning("create_todo: actor_id '%s' no es válido para FK", actor_id)
                    return
                import uuid as _uuid
                from backend.src.modules.todos.infrastructure.models import CaseTodoModel
                assigned_to = action.params.get("assigned_to_id") or None
                todo = CaseTodoModel(
                    id=str(_uuid.uuid4()),
                    case_id=case_id,
                    created_by_id=created_by,
                    assigned_to_id=assigned_to,
                    tenant_id=context.get("tenant_id"),
                    title=title,
                )
                self.db.add(todo)
                logger.info("create_todo: tarea '%s' creada en caso %s", title, case_id)

            case "escalate_priority":
                if not case_id:
                    logger.warning("escalate_priority: no hay case_id en el contexto")
                    return
                from sqlalchemy import asc
                from backend.src.modules.cases.infrastructure.models import CaseModel
                from backend.src.modules.case_priorities.infrastructure.models import CasePriorityModel
                case_obj = await self.db.get(CaseModel, case_id)
                if not case_obj or not case_obj.priority_id:
                    logger.warning("escalate_priority: caso %s no encontrado o sin prioridad", case_id)
                    return
                current_priority = await self.db.get(CasePriorityModel, case_obj.priority_id)
                if not current_priority:
                    return
                result = await self.db.execute(
                    select(CasePriorityModel).where(
                        CasePriorityModel.is_active.is_(True),
                        CasePriorityModel.level > current_priority.level,
                        CasePriorityModel.tenant_id == case_obj.tenant_id,
                    ).order_by(asc(CasePriorityModel.level)).limit(1)
                )
                next_priority = result.scalar_one_or_none()
                if not next_priority:
                    logger.info("escalate_priority: caso %s ya tiene la prioridad más alta", case_id)
                    return
                case_obj.priority_id = next_priority.id
                logger.info(
                    "escalate_priority: caso %s nivel %d → %d",
                    case_id, current_priority.level, next_priority.level,
                )

            case _:
                logger.warning("Tipo de acción no implementada: %s", action.action_type)
