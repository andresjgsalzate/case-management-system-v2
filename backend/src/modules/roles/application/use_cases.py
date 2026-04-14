import uuid
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel
from backend.src.modules.roles.application.dtos import CreateRoleDTO, UpdateRoleDTO, PermissionDTO, RoleResponseDTO
from backend.src.core.exceptions import NotFoundError, ConflictError
from backend.src.core.tenant import catalog_filter


class RoleUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_role(self, dto: CreateRoleDTO, tenant_id: str | None = None) -> RoleResponseDTO:
        existing = await self.db.execute(
            select(RoleModel).where(RoleModel.name == dto.name, RoleModel.tenant_id == tenant_id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Role '{dto.name}' already exists")

        role = RoleModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            description=dto.description,
        )
        self.db.add(role)
        await self.db.flush()

        for perm_dto in dto.permissions:
            perm = PermissionModel(
                id=str(uuid.uuid4()),
                role_id=role.id,
                module=perm_dto.module,
                action=perm_dto.action,
                scope=perm_dto.scope,
            )
            self.db.add(perm)

        await self.db.commit()
        await self.db.refresh(role)
        return await self._to_dto_with_load(role.id)

    async def get_role(self, role_id: str) -> RoleResponseDTO:
        result = await self.db.execute(
            select(RoleModel).options(selectinload(RoleModel.permissions)).where(RoleModel.id == role_id)
        )
        role = result.scalar_one_or_none()
        if not role:
            raise NotFoundError("Role", role_id)
        return self._to_dto(role)

    async def list_roles(self, tenant_id: str | None = None) -> list[RoleResponseDTO]:
        result = await self.db.execute(
            select(RoleModel).options(selectinload(RoleModel.permissions))
            .where(catalog_filter(RoleModel, tenant_id))
        )
        return [self._to_dto(r) for r in result.scalars().all()]

    async def update_role(self, role_id: str, dto: UpdateRoleDTO) -> RoleResponseDTO:
        role = await self.db.get(RoleModel, role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        if dto.name is not None:
            role.name = dto.name
        if dto.description is not None:
            role.description = dto.description
        await self.db.commit()
        return await self.get_role(role_id)

    async def update_permissions(self, role_id: str, permissions: list[PermissionDTO]) -> RoleResponseDTO:
        role = await self.db.get(RoleModel, role_id)
        if not role:
            raise NotFoundError("Role", role_id)

        await self.db.execute(delete(PermissionModel).where(PermissionModel.role_id == role_id))
        for perm_dto in permissions:
            perm = PermissionModel(
                id=str(uuid.uuid4()),
                role_id=role_id,
                module=perm_dto.module,
                action=perm_dto.action,
                scope=perm_dto.scope,
            )
            self.db.add(perm)

        await self.db.commit()
        return await self.get_role(role_id)

    async def delete_role(self, role_id: str) -> None:
        role = await self.db.get(RoleModel, role_id)
        if not role:
            raise NotFoundError("Role", role_id)
        await self.db.delete(role)
        await self.db.commit()

    async def _to_dto_with_load(self, role_id: str) -> RoleResponseDTO:
        return await self.get_role(role_id)

    def _to_dto(self, model: RoleModel) -> RoleResponseDTO:
        return RoleResponseDTO(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at.isoformat(),
            permissions=[
                PermissionDTO(module=p.module, action=p.action, scope=p.scope)
                for p in (model.permissions or [])
            ],
        )
