"""n8n workflow catalog — CRUD use cases.

Decoupled from n8n_bridge.use_cases (runtime trigger/callback logic).
Operators register named workflows via /n8n-workflows so the case
trigger UI shows a dropdown instead of asking them to paste a URL.

Authorization (RBAC) is enforced in the router via PermissionChecker.
This module assumes the caller is already authorized.
"""
import uuid
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import ConflictError, NotFoundError
from backend.src.modules.n8n_bridge.infrastructure.models import (
    N8nWorkflowModel,
)


# ── DTOs ──────────────────────────────────────────────────────────


class CreateN8nWorkflowDTO(BaseModel):
    """Caller payload to register a new workflow."""
    # tenant_id None = global workflow (super-admin only).
    tenant_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    # HttpUrl rejects non-http schemes (file://, ftp://) at validation.
    workflow_url: HttpUrl
    is_active: bool = True
    requires_approval: bool = False
    allowed_role_ids: list[str] | None = None


class UpdateN8nWorkflowDTO(BaseModel):
    """All fields optional — None means leave unchanged. To clear
    `description` or `allowed_role_ids` send an empty value (`""`
    or `[]`); we distinguish ``not set`` from ``set to falsy`` via
    Pydantic ``model_fields_set`` rather than this DTO."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    workflow_url: HttpUrl | None = None
    is_active: bool | None = None
    requires_approval: bool | None = None
    allowed_role_ids: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class N8nWorkflowResponseDTO(BaseModel):
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    workflow_url: str
    is_active: bool
    requires_approval: bool
    allowed_role_ids: list[str] | None
    created_at: str
    updated_at: str
    created_by_user_id: str | None


# ── Use cases ─────────────────────────────────────────────────────


class N8nWorkflowCatalogUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- list ----------

    async def list(
        self,
        tenant_id: str | None,
        only_active: bool = False,
        include_global: bool = True,
    ) -> list[N8nWorkflowResponseDTO]:
        """List workflows visible to ``tenant_id``.

        When ``tenant_id`` is None the caller is treated as super-admin and
        we return everything (subject to ``only_active``). Otherwise return
        tenant-scoped rows plus global rows (when ``include_global``).
        """
        stmt = select(N8nWorkflowModel)
        if tenant_id is not None:
            if include_global:
                stmt = stmt.where(
                    or_(
                        N8nWorkflowModel.tenant_id == tenant_id,
                        N8nWorkflowModel.tenant_id.is_(None),
                    )
                )
            else:
                stmt = stmt.where(N8nWorkflowModel.tenant_id == tenant_id)
        if only_active:
            stmt = stmt.where(N8nWorkflowModel.is_active.is_(True))
        stmt = stmt.order_by(
            N8nWorkflowModel.tenant_id.is_(None).desc(),  # globals first
            N8nWorkflowModel.name,
        )
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [self._to_dto(w) for w in rows]

    # ---------- get ----------

    async def get(self, workflow_id: str) -> N8nWorkflowResponseDTO:
        wf = await self._load(workflow_id)
        return self._to_dto(wf)

    # ---------- create ----------

    async def create(
        self,
        dto: CreateN8nWorkflowDTO,
        created_by_user_id: str | None,
    ) -> N8nWorkflowResponseDTO:
        wf = N8nWorkflowModel(
            id=str(uuid.uuid4()),
            tenant_id=dto.tenant_id,
            name=dto.name,
            description=dto.description,
            workflow_url=str(dto.workflow_url),
            is_active=dto.is_active,
            requires_approval=dto.requires_approval,
            allowed_role_ids=dto.allowed_role_ids,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(wf)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # uq_n8n_workflow_tenant_name violation is the common case;
            # surface a friendly message.
            raise ConflictError(
                f"Ya existe un workflow con el nombre '{dto.name}' en este tenant"
            ) from exc
        await self.db.refresh(wf)
        return self._to_dto(wf)

    # ---------- update ----------

    async def update(
        self,
        workflow_id: str,
        dto: UpdateN8nWorkflowDTO,
    ) -> N8nWorkflowResponseDTO:
        wf = await self._load(workflow_id)
        # Use model_fields_set so ``None`` in payload != absent.
        set_fields = dto.model_fields_set
        if "name" in set_fields and dto.name is not None:
            wf.name = dto.name
        if "description" in set_fields:
            wf.description = dto.description
        if "workflow_url" in set_fields and dto.workflow_url is not None:
            wf.workflow_url = str(dto.workflow_url)
        if "is_active" in set_fields and dto.is_active is not None:
            wf.is_active = dto.is_active
        if "requires_approval" in set_fields and dto.requires_approval is not None:
            wf.requires_approval = dto.requires_approval
        if "allowed_role_ids" in set_fields:
            wf.allowed_role_ids = dto.allowed_role_ids
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError(
                "Nombre duplicado para este tenant"
            ) from exc
        await self.db.refresh(wf)
        return self._to_dto(wf)

    # ---------- delete ----------

    async def delete(self, workflow_id: str) -> None:
        wf = await self._load(workflow_id)
        await self.db.delete(wf)
        await self.db.commit()

    # ---------- helpers ----------

    async def _load(self, workflow_id: str) -> N8nWorkflowModel:
        wf = await self.db.get(N8nWorkflowModel, workflow_id)
        if wf is None:
            raise NotFoundError("N8nWorkflow", workflow_id)
        return wf

    def _to_dto(self, model: N8nWorkflowModel) -> N8nWorkflowResponseDTO:
        return N8nWorkflowResponseDTO(
            id=model.id,
            tenant_id=model.tenant_id,
            name=model.name,
            description=model.description,
            workflow_url=model.workflow_url,
            is_active=model.is_active,
            requires_approval=model.requires_approval,
            allowed_role_ids=model.allowed_role_ids,
            created_at=model.created_at.isoformat(),
            updated_at=model.updated_at.isoformat(),
            created_by_user_id=model.created_by_user_id,
        )


__all__: Sequence[str] = (
    "CreateN8nWorkflowDTO",
    "UpdateN8nWorkflowDTO",
    "N8nWorkflowResponseDTO",
    "N8nWorkflowCatalogUseCases",
)
