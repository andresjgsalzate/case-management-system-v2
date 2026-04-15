import uuid
from collections import defaultdict
from datetime import date, datetime, timezone
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.dispositions.infrastructure.models import DispositionCategoryModel, DispositionModel
from backend.src.core.exceptions import NotFoundError


class DispositionUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Categories ────────────────────────────────────────────────────────────

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

    # ── Dispositions CRUD ─────────────────────────────────────────────────────

    async def create_disposition(
        self,
        category_id: str,
        tenant_id: str | None = None,
        created_by_id: str | None = None,
        disp_date: date | None = None,
        case_number: str | None = None,
        item_name: str | None = None,
        storage_path: str | None = None,
        revision_number: str | None = None,
        observations: str | None = None,
        # Legacy fields kept for backwards compatibility
        title: str | None = None,
        content: str | None = None,
    ) -> DispositionModel:
        disp = DispositionModel(
            id=str(uuid.uuid4()),
            category_id=category_id,
            date=disp_date,
            case_number=case_number,
            item_name=item_name,
            storage_path=storage_path,
            revision_number=revision_number,
            observations=observations,
            title=title,
            content=content,
            created_by_id=created_by_id,
            tenant_id=tenant_id,
        )
        self.db.add(disp)
        await self.db.commit()
        await self.db.refresh(disp)
        return disp

    async def update_disposition(
        self,
        disposition_id: str,
        category_id: str | None = None,
        disp_date: date | None = None,
        case_number: str | None = None,
        item_name: str | None = None,
        storage_path: str | None = None,
        revision_number: str | None = None,
        observations: str | None = None,
        title: str | None = None,
        content: str | None = None,
    ) -> DispositionModel:
        result = await self.db.execute(
            select(DispositionModel).where(DispositionModel.id == disposition_id)
        )
        disp = result.scalar_one_or_none()
        if not disp:
            raise NotFoundError(f"Disposición {disposition_id} no encontrada")

        if category_id is not None:
            disp.category_id = category_id
        if disp_date is not None:
            disp.date = disp_date
        if case_number is not None:
            disp.case_number = case_number
        if item_name is not None:
            disp.item_name = item_name
        if storage_path is not None:
            disp.storage_path = storage_path
        if revision_number is not None:
            disp.revision_number = revision_number
        # observations can be explicitly cleared to None via empty string
        if observations is not None:
            disp.observations = observations or None
        if title is not None:
            disp.title = title
        if content is not None:
            disp.content = content

        disp.updated_at = datetime.now(timezone.utc)
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

    # ── Queries ───────────────────────────────────────────────────────────────

    async def list_all(self, tenant_id: str | None = None) -> list[DispositionModel]:
        stmt = select(DispositionModel).where(DispositionModel.is_active.is_(True))
        if tenant_id is not None:
            stmt = stmt.where(DispositionModel.tenant_id == tenant_id)
        stmt = stmt.order_by(DispositionModel.date.desc().nulls_last(), DispositionModel.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_category(self, category_id: str) -> list[DispositionModel]:
        result = await self.db.execute(
            select(DispositionModel)
            .where(DispositionModel.category_id == category_id, DispositionModel.is_active.is_(True))
            .order_by(DispositionModel.date.desc().nulls_last(), DispositionModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_case_number(self, case_number: str) -> list[DispositionModel]:
        result = await self.db.execute(
            select(DispositionModel)
            .where(
                DispositionModel.case_number == case_number,
                DispositionModel.is_active.is_(True),
            )
            .order_by(DispositionModel.date.desc().nulls_last(), DispositionModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def search_dispositions(self, query: str) -> list[DispositionModel]:
        pattern = f"%{query}%"
        result = await self.db.execute(
            select(DispositionModel).where(
                DispositionModel.is_active.is_(True),
                or_(
                    DispositionModel.case_number.ilike(pattern),
                    DispositionModel.item_name.ilike(pattern),
                    DispositionModel.observations.ilike(pattern),
                    DispositionModel.title.ilike(pattern),
                ),
            ).order_by(DispositionModel.date.desc().nulls_last(), DispositionModel.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_cases_summary(
        self, tenant_id: str | None = None
    ) -> list[dict]:
        """
        Returns dispositions grouped by month/year then by case_number.
        Result structure:
        [
          {
            "period": "2026-04",
            "cases": [
              {"case_number": "REQ-001", "count": 3},
              ...
            ]
          },
          ...
        ]
        """
        stmt = (
            select(DispositionModel)
            .where(DispositionModel.is_active.is_(True), DispositionModel.case_number.isnot(None))
        )
        if tenant_id is not None:
            stmt = stmt.where(DispositionModel.tenant_id == tenant_id)
        stmt = stmt.order_by(DispositionModel.date.desc().nulls_last(), DispositionModel.created_at.desc())
        result = await self.db.execute(stmt)
        dispositions = list(result.scalars().all())

        # Group by period (YYYY-MM) → case_number → count
        period_case: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for d in dispositions:
            ref_date = d.date or d.created_at.date()
            period = ref_date.strftime("%Y-%m")
            period_case[period][d.case_number] += 1  # type: ignore[arg-type]

        # Sort periods descending
        sorted_periods = sorted(period_case.keys(), reverse=True)
        summary = []
        for period in sorted_periods:
            cases_in_period = [
                {"case_number": cn, "count": cnt}
                for cn, cnt in sorted(period_case[period].items(), key=lambda x: -x[1])
            ]
            summary.append({"period": period, "cases": cases_in_period})
        return summary

    # ── Legacy (kept for backwards compat) ───────────────────────────────────

    async def apply_to_case(self, disposition_id: str, case_id: str) -> DispositionModel:
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
