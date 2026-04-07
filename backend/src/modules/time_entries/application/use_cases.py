import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.time_entries.infrastructure.models import TimeEntryModel, ActiveTimerModel
from backend.src.core.exceptions import BusinessRuleError, NotFoundError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class TimeEntryUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_timer(
        self, case_id: str, user_id: str, tenant_id: str | None
    ) -> ActiveTimerModel:
        existing = await self._get_active_timer(user_id)
        if existing:
            raise BusinessRuleError(
                f"Ya tienes un timer activo en el caso {existing.case_id}. Detén ese timer primero."
            )
        timer = ActiveTimerModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        self.db.add(timer)
        await self.db.commit()
        await self.db.refresh(timer)
        return timer

    async def stop_timer(self, user_id: str) -> TimeEntryModel:
        timer = await self._get_active_timer(user_id)
        if not timer:
            raise NotFoundError("No tienes ningún timer activo")
        now = datetime.now(timezone.utc)
        started = timer.started_at
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        elapsed_seconds = (now - started).total_seconds()
        # ceil garantiza al menos 1 minuto; evita registros de 0 minutos
        minutes = max(1, math.ceil(elapsed_seconds / 60))
        entry = TimeEntryModel(
            id=str(uuid.uuid4()),
            case_id=timer.case_id,
            user_id=user_id,
            tenant_id=timer.tenant_id,
            entry_type="auto",
            minutes=minutes,
            started_at=started,
            stopped_at=now,
        )
        self.db.add(entry)
        await self.db.delete(timer)
        await self.db.commit()
        await self.db.refresh(entry)
        await event_bus.publish(
            BaseEvent(
                event_name="time_entry.created",
                tenant_id=timer.tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": timer.case_id, "minutes": minutes},
            )
        )
        return entry

    async def add_manual(
        self,
        case_id: str,
        user_id: str,
        tenant_id: str | None,
        minutes: int,
        description: str | None = None,
    ) -> TimeEntryModel:
        if minutes <= 0:
            raise BusinessRuleError("Los minutos deben ser un número positivo")
        entry = TimeEntryModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            user_id=user_id,
            tenant_id=tenant_id,
            entry_type="manual",
            minutes=minutes,
            description=description,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(entry)
        await event_bus.publish(
            BaseEvent(
                event_name="time_entry.created",
                tenant_id=tenant_id or "default",
                actor_id=user_id,
                payload={"case_id": case_id, "minutes": minutes},
            )
        )
        return entry

    async def list_for_case(self, case_id: str) -> list[TimeEntryModel]:
        result = await self.db.execute(
            select(TimeEntryModel)
            .where(TimeEntryModel.case_id == case_id, TimeEntryModel.is_deleted == False)
            .order_by(TimeEntryModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_total_minutes(self, case_id: str) -> int:
        result = await self.db.execute(
            select(func.sum(TimeEntryModel.minutes)).where(
                TimeEntryModel.case_id == case_id,
                TimeEntryModel.is_deleted == False,
            )
        )
        total = result.scalar()
        return total or 0

    async def delete_entry(self, entry_id: str, user_id: str) -> None:
        entry = await self.db.get(TimeEntryModel, entry_id)
        if not entry:
            raise NotFoundError(f"Entrada de tiempo {entry_id} no encontrada")
        entry.is_deleted = True
        await self.db.commit()

    async def _get_active_timer(self, user_id: str) -> ActiveTimerModel | None:
        result = await self.db.execute(
            select(ActiveTimerModel).where(ActiveTimerModel.user_id == user_id)
        )
        return result.scalar_one_or_none()
