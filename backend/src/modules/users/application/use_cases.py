import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.users.application.dtos import (
    CreateUserDTO, UpdateUserDTO, ChangePasswordDTO, UserResponseDTO,
)
from backend.src.core.security import hash_password, verify_password
from backend.src.core.exceptions import NotFoundError, ConflictError, UnauthorizedError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class UserUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_user(
        self, dto: CreateUserDTO, actor_id: str, tenant_id: str | None = None
    ) -> UserResponseDTO:
        existing = await self.db.execute(
            select(UserModel).where(UserModel.email == dto.email)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Email {dto.email} already registered")

        user = UserModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            email=dto.email,
            full_name=dto.full_name,
            hashed_password=hash_password(dto.password),
            role_id=dto.role_id,
            team_id=dto.team_id,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        await event_bus.publish(BaseEvent(
            event_name="user.created",
            tenant_id=tenant_id or "default",
            actor_id=actor_id,
            payload={"user_id": user.id, "email": user.email},
        ))

        return self._to_dto(user)

    async def get_user(self, user_id: str) -> UserResponseDTO:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise NotFoundError("User", user_id)
        return self._to_dto(user)

    async def list_users(
        self, tenant_id: str | None, page: int = 1, page_size: int = 20,
        all_tenants: bool = False,
    ) -> tuple[list[UserResponseDTO], int]:
        query = select(UserModel)
        if not all_tenants:
            query = query.where(UserModel.tenant_id == tenant_id)
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0
        result = await self.db.execute(
            query.offset((page - 1) * page_size).limit(page_size)
        )
        return [self._to_dto(u) for u in result.scalars().all()], total

    async def update_user(
        self, user_id: str, dto: UpdateUserDTO, actor_id: str
    ) -> UserResponseDTO:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise NotFoundError("User", user_id)
        for field_name, value in dto.model_dump(exclude_none=True).items():
            setattr(user, field_name, value)
        await self.db.commit()
        await self.db.refresh(user)
        return self._to_dto(user)

    async def deactivate_user(
        self, user_id: str, actor_id: str, tenant_id: str
    ) -> None:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise NotFoundError("User", user_id)
        user.is_active = False
        await self.db.commit()
        await event_bus.publish(BaseEvent(
            event_name="user.deactivated",
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload={"user_id": user_id},
        ))

    async def reactivate_user(self, user_id: str) -> None:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise NotFoundError("User", user_id)
        user.is_active = True
        await self.db.commit()

    async def change_password(self, user_id: str, dto: ChangePasswordDTO) -> None:
        user = await self.db.get(UserModel, user_id)
        if not user:
            raise NotFoundError("User", user_id)
        if not verify_password(dto.current_password, user.hashed_password):
            raise UnauthorizedError("Current password is incorrect")
        user.hashed_password = hash_password(dto.new_password)
        await self.db.commit()

    def _to_dto(self, model: UserModel) -> UserResponseDTO:
        return UserResponseDTO(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            role_id=model.role_id,
            team_id=model.team_id,
            tenant_id=model.tenant_id,
            is_active=model.is_active,
            email_notifications=model.email_notifications,
            avatar_url=model.avatar_url,
            created_at=model.created_at.isoformat(),
        )
