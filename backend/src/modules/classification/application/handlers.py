import uuid
from datetime import datetime, timezone

from backend.src.core.events.base import BaseEvent


async def handle_case_created_for_classification(event: BaseEvent) -> None:
    case_id = event.payload.get("case_id")
    title = event.payload.get("title", "")
    tenant_id = event.tenant_id

    from backend.src.core.database import AsyncSessionLocal
    from backend.src.modules.classification.infrastructure.models import (
        ClassificationRuleModel,
        CaseClassificationModel,
    )
    from backend.src.modules.classification.application.rule_engine import apply_rules
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(ClassificationRuleModel)
            .where(
                ClassificationRuleModel.tenant_id == tenant_id,
                ClassificationRuleModel.is_active == True,
            )
            .order_by(ClassificationRuleModel.priority)
        )
        rules = result.scalars().all()
        rules_data = [
            {"conditions": r.conditions, "result": r.result, "priority": r.priority}
            for r in rules
        ]
        matched_result = apply_rules(title, rules_data)

        if matched_result:
            VALID_FIELDS = {"category", "urgency", "area", "complexity_detail", "origin_detail"}
            classification = CaseClassificationModel(
                id=str(uuid.uuid4()),
                case_id=case_id,
                tenant_id=tenant_id,
                classified_by=event.actor_id,
                classified_at=datetime.now(timezone.utc),
                **{k: v for k, v in matched_result.items() if k in VALID_FIELDS},
            )
            db.add(classification)
            await db.commit()

            from backend.src.core.events.bus import event_bus
            await event_bus.publish(
                BaseEvent(
                    event_name="case.auto_classified",
                    tenant_id=tenant_id,
                    actor_id=event.actor_id,
                    payload={"case_id": case_id, "result": matched_result},
                )
            )


def register_handlers(bus) -> None:
    bus.subscribe("case.created", handle_case_created_for_classification)
