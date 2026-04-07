import uuid
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel, DispositionModel
from backend.src.core.exceptions import NotFoundError


class DispositionUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_category(
        self,
        name: str,
        tenant_id: str | None = None,
        description: str | None = None,
    ) -> DispositionCategoryModel:
        cat = DispositionCategoryModel(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            tenant_id=tenant_id,
        )
        self.db.add(cat)
        await self.db.commit()
        await self.db.refresh(cat)
        return cat

    async def list_categories(self, tenant_id: str | None = None) -> list[DispositionCategoryModel]:
        stmt = select(DispositionCategoryModel).where(
            DispositionCategoryModel.is_active.is_(True)
        )
        if tenant_id is not None:
            stmt = stmt.where(DispositionCategoryModel.tenant_id == tenant_id)
        stmt = stmt.order_by(DispositionCategoryModel.name)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_disposition(
        self,
        category_id: str,
        title: str,
        content: str,
        tenant_id: str | None = None,
        created_by_id: str | None = None,
    ) -> DispositionModel:
        disp = DispositionModel(
            id=str(uuid.uuid4()),
            category_id=category_id,
            title=title,
            content=content,
            created_by_id=created_by_id,
            tenant_id=tenant_id,
        )
        self.db.add(disp)
        await self.db.commit()
        await self.db.refresh(disp)
        return disp

    async def list_by_category(self, category_id: str) -> list[DispositionModel]:
        result = await self.db.execute(
            select(DispositionModel)
            .where(DispositionModel.category_id == category_id, DispositionModel.is_active.is_(True))
            .order_by(DispositionModel.usage_count.desc())
        )
        return list(result.scalars().all())

    async def list_all(self, tenant_id: str | None = None) -> list[DispositionModel]:
        stmt = select(DispositionModel).where(DispositionModel.is_active.is_(True))
        if tenant_id is not None:
            stmt = stmt.where(DispositionModel.tenant_id == tenant_id)
        stmt = stmt.order_by(DispositionModel.usage_count.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_dispositions(self, query: str) -> list[DispositionModel]:
        """Búsqueda por título y contenido (ILIKE — portátil entre PostgreSQL y SQLite)."""
        pattern = f"%{query}%"
        result = await self.db.execute(
            select(DispositionModel).where(
                DispositionModel.is_active.is_(True),
                or_(
                    DispositionModel.title.ilike(pattern),
                    DispositionModel.content.ilike(pattern),
                ),
            ).order_by(DispositionModel.usage_count.desc())
        )
        return list(result.scalars().all())

    async def apply_to_case(self, disposition_id: str, case_id: str) -> DispositionModel:
        """Incrementa el contador de uso al aplicar la disposición a un caso."""
        result = await self.db.execute(
            select(DispositionModel).where(DispositionModel.id == disposition_id)
        )
        disp = result.scalar_one_or_none()
        if not disp:
            raise NotFoundError(f"Disposición {disposition_id} no encontrada")
        disp.usage_count += 1
        await self.db.commit()
        await self.db.refresh(disp)
        return disp

    async def update_disposition(
        self,
        disposition_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> DispositionModel:
        result = await self.db.execute(
            select(DispositionModel).where(DispositionModel.id == disposition_id)
        )
        disp = result.scalar_one_or_none()
        if not disp:
            raise NotFoundError(f"Disposición {disposition_id} no encontrada")
        if title is not None:
            disp.title = title
        if content is not None:
            disp.content = content
        await self.db.commit()
        await self.db.refresh(disp)
        return disp

    async def deactivate(self, disposition_id: str) -> None:
        result = await self.db.execute(
            select(DispositionModel).where(DispositionModel.id == disposition_id)
        )
        disp = result.scalar_one_or_none()
        if not disp:
            raise NotFoundError(f"Disposición {disposition_id} no encontrada")
        disp.is_active = False
        await self.db.commit()
