import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.todos.infrastructure.models import CaseTodoModel
from backend.src.core.exceptions import NotFoundError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class TodoUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        case_id: str,
        created_by_id: str,
        tenant_id: str | None,
        title: str,
        description: str | None = None,
        assigned_to_id: str | None = None,
        due_date: datetime | None = None,
    ) -> CaseTodoModel:
        todo = CaseTodoModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            created_by_id=created_by_id,
            tenant_id=tenant_id,
            title=title,
            description=description,
            assigned_to_id=assigned_to_id,
            due_date=due_date,
        )
        self.db.add(todo)
        await self.db.commit()
        await self.db.refresh(todo)
        await event_bus.publish(
            BaseEvent(
                event_name="todo.created",
                tenant_id=tenant_id or "default",
                actor_id=created_by_id,
                payload={"case_id": case_id, "todo_id": todo.id},
            )
        )
        return todo

    async def list_for_case(
        self, case_id: str, include_archived: bool = False
    ) -> list[CaseTodoModel]:
        stmt = select(CaseTodoModel).where(CaseTodoModel.case_id == case_id)
        if not include_archived:
            stmt = stmt.where(CaseTodoModel.is_archived == False)
        stmt = stmt.order_by(CaseTodoModel.created_at.asc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def complete(self, todo_id: str, user_id: str) -> CaseTodoModel:
        todo = await self._get(todo_id)
        todo.is_completed = True
        todo.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(todo)
        await event_bus.publish(
            BaseEvent(
                event_name="todo.completed",
                tenant_id=todo.tenant_id or "default",
                actor_id=user_id,
                payload={"todo_id": todo_id, "case_id": todo.case_id, "title": todo.title},
            )
        )
        return todo

    async def archive(self, todo_id: str) -> None:
        todo = await self._get(todo_id)
        todo.is_archived = True
        await self.db.commit()

    async def _get(self, todo_id: str) -> CaseTodoModel:
        result = await self.db.execute(
            select(CaseTodoModel).where(CaseTodoModel.id == todo_id)
        )
        todo = result.scalar_one_or_none()
        if not todo:
            raise NotFoundError(f"TODO {todo_id} no encontrado")
        return todo
