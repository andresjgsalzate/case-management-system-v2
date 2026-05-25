"""CRUD use cases for the triage catalog tables (Phase 5).

Kept separate from triage/use_cases.py (which owns the triage record
flow) so the catalog admin logic stays self-contained. All three
catalogs follow the same shape: list-active / create / update /
soft-or-hard delete.

Delete strategy: tool_types + tool_actions are soft-deleted
(is_active=False) so historical triages that reference them keep their
FK valid. sla_policies are hard-deleted (no FK from case_triages points
at them -- they're looked up by priority_id at calc time, denormalised
onto the triage row).
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import ConflictError, NotFoundError
from backend.src.modules.triage.application.dtos import (
    CreateSlaPolicyPayload,
    CreateToolActionPayload,
    CreateToolTypePayload,
    UpdateSlaPolicyPayload,
    UpdateToolActionPayload,
    UpdateToolTypePayload,
)
from backend.src.modules.triage.infrastructure.models import (
    TriageSlaPolicyModel,
    TriageToolActionModel,
    TriageToolTypeModel,
)


class TriageCatalogUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Tool types ──────────────────────────────────────────────────

    async def list_tool_types(
        self, *, include_inactive: bool = False
    ) -> list[TriageToolTypeModel]:
        stmt = select(TriageToolTypeModel)
        if not include_inactive:
            stmt = stmt.where(TriageToolTypeModel.is_active.is_(True))
        stmt = stmt.order_by(TriageToolTypeModel.name)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_tool_type(
        self, payload: CreateToolTypePayload
    ) -> TriageToolTypeModel:
        await self._guard_unique_name(
            TriageToolTypeModel, payload.name, "tipo de herramienta",
        )
        row = TriageToolTypeModel(
            id=str(uuid.uuid4()),
            tenant_id=None,
            name=payload.name,
            description=payload.description,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def update_tool_type(
        self, tool_type_id: str, payload: UpdateToolTypePayload
    ) -> TriageToolTypeModel:
        row = await self.db.get(TriageToolTypeModel, tool_type_id)
        if row is None:
            raise NotFoundError(f"Tool type {tool_type_id} not found")
        fields = payload.model_dump(exclude_unset=True)
        if "name" in fields and fields["name"] is not None:
            await self._guard_unique_name(
                TriageToolTypeModel, fields["name"], "tipo de herramienta",
                exclude_id=tool_type_id,
            )
            row.name = fields["name"]
        if "description" in fields:
            row.description = fields["description"]
        if "is_active" in fields and fields["is_active"] is not None:
            row.is_active = fields["is_active"]
        await self.db.flush()
        return row

    async def delete_tool_type(self, tool_type_id: str) -> None:
        """Soft-delete: keep the row so referencing triages stay valid."""
        row = await self.db.get(TriageToolTypeModel, tool_type_id)
        if row is None:
            raise NotFoundError(f"Tool type {tool_type_id} not found")
        row.is_active = False
        await self.db.flush()

    # ── Tool actions ────────────────────────────────────────────────

    async def list_tool_actions(
        self, *, include_inactive: bool = False
    ) -> list[TriageToolActionModel]:
        stmt = select(TriageToolActionModel)
        if not include_inactive:
            stmt = stmt.where(TriageToolActionModel.is_active.is_(True))
        stmt = stmt.order_by(TriageToolActionModel.name)
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_tool_action(
        self, payload: CreateToolActionPayload
    ) -> TriageToolActionModel:
        await self._guard_unique_name(
            TriageToolActionModel, payload.name, "acción aplicada",
        )
        row = TriageToolActionModel(
            id=str(uuid.uuid4()),
            tenant_id=None,
            name=payload.name,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def update_tool_action(
        self, action_id: str, payload: UpdateToolActionPayload
    ) -> TriageToolActionModel:
        row = await self.db.get(TriageToolActionModel, action_id)
        if row is None:
            raise NotFoundError(f"Tool action {action_id} not found")
        fields = payload.model_dump(exclude_unset=True)
        if "name" in fields and fields["name"] is not None:
            await self._guard_unique_name(
                TriageToolActionModel, fields["name"], "acción aplicada",
                exclude_id=action_id,
            )
            row.name = fields["name"]
        if "is_active" in fields and fields["is_active"] is not None:
            row.is_active = fields["is_active"]
        await self.db.flush()
        return row

    async def delete_tool_action(self, action_id: str) -> None:
        row = await self.db.get(TriageToolActionModel, action_id)
        if row is None:
            raise NotFoundError(f"Tool action {action_id} not found")
        row.is_active = False
        await self.db.flush()

    # ── SLA policies ────────────────────────────────────────────────

    async def list_sla_policies(self) -> list[TriageSlaPolicyModel]:
        stmt = select(TriageSlaPolicyModel).where(
            TriageSlaPolicyModel.is_active.is_(True)
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def create_sla_policy(
        self, payload: CreateSlaPolicyPayload
    ) -> TriageSlaPolicyModel:
        # One policy per (tenant, priority). Surface a friendly conflict
        # instead of the raw unique-violation IntegrityError.
        existing = (await self.db.execute(
            select(TriageSlaPolicyModel.id).where(
                TriageSlaPolicyModel.tenant_id.is_(None),
                TriageSlaPolicyModel.priority_id == payload.priority_id,
            )
        )).scalar_one_or_none()
        if existing:
            raise ConflictError(
                "Ya existe una política SLA para esa prioridad"
            )
        row = TriageSlaPolicyModel(
            id=str(uuid.uuid4()),
            tenant_id=None,
            priority_id=payload.priority_id,
            sla_minutes=payload.sla_minutes,
            is_active=True,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def update_sla_policy(
        self, policy_id: str, payload: UpdateSlaPolicyPayload
    ) -> TriageSlaPolicyModel:
        row = await self.db.get(TriageSlaPolicyModel, policy_id)
        if row is None:
            raise NotFoundError(f"SLA policy {policy_id} not found")
        fields = payload.model_dump(exclude_unset=True)
        if "sla_minutes" in fields:
            row.sla_minutes = fields["sla_minutes"]
        if "is_active" in fields and fields["is_active"] is not None:
            row.is_active = fields["is_active"]
        await self.db.flush()
        return row

    async def delete_sla_policy(self, policy_id: str) -> None:
        """Hard-delete: nothing FKs to sla_policies (looked up by
        priority at calc time), so removing the row is safe.
        """
        row = await self.db.get(TriageSlaPolicyModel, policy_id)
        if row is None:
            raise NotFoundError(f"SLA policy {policy_id} not found")
        await self.db.delete(row)
        await self.db.flush()

    # ── Helpers ─────────────────────────────────────────────────────

    async def _guard_unique_name(
        self, model, name: str, label: str, *, exclude_id: str | None = None,
    ) -> None:
        stmt = select(model.id).where(
            model.tenant_id.is_(None), model.name == name
        )
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing and existing != exclude_id:
            raise ConflictError(f"Ya existe un {label} con el nombre '{name}'")
