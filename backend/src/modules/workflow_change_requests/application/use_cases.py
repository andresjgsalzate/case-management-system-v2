"""Use cases for the Workflow Change Request module (sub-spec 09 §3.9).

Owns the status state machine:

    pending ──► in_review ──► approved ──► implemented
                    │            │
                    └──► rejected ┘

Permission gate for reviewer actions is enforced here (defense in depth)
in addition to the router's `PermissionChecker`. The use case looks up
the caller's role and uses `has_permission` for the
`workflow_change_requests:review` check.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    NotFoundError,
    PermissionDeniedError,
)
from backend.src.core.middleware.permission_checker import has_permission
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.workflow_change_requests.application.dtos import (
    CreateWCRDTO,
    ImplementDTO,
    UpdateStatusDTO,
    WCRResponseDTO,
)
from backend.src.modules.workflow_change_requests.infrastructure.models import (
    WorkflowChangeRequestModel,
)


VALID_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"in_review", "approved", "rejected"},
    "in_review": {"approved", "rejected"},
    "approved": {"implemented"},
    "rejected": set(),
    "implemented": set(),
}


class WCRUseCases:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ─── public surface ────────────────────────────────────────

    async def create(
        self, *, dto: CreateWCRDTO, requester_id: str
    ) -> WCRResponseDTO:
        wcr = WorkflowChangeRequestModel(
            id=str(uuid.uuid4()),
            tenant_id=dto.tenant_id,
            workflow_id=dto.workflow_id,
            title=dto.title,
            description=dto.description,
            proposed_change=dto.proposed_change.model_dump(),
            requested_by=requester_id,
            requested_at=datetime.now(timezone.utc),
            status="pending",
        )
        self.db.add(wcr)
        await self.db.commit()
        await self.db.refresh(wcr)
        return WCRResponseDTO.model_validate(wcr)

    async def list(
        self,
        *,
        status: str | None = None,
        requester_id: str | None = None,
        tenant_id: str | None = None,
    ) -> list[WCRResponseDTO]:
        stmt = select(WorkflowChangeRequestModel)
        if status:
            stmt = stmt.where(WorkflowChangeRequestModel.status == status)
        if requester_id:
            stmt = stmt.where(
                WorkflowChangeRequestModel.requested_by == requester_id
            )
        if tenant_id:
            stmt = stmt.where(
                WorkflowChangeRequestModel.tenant_id == tenant_id
            )
        stmt = stmt.order_by(WorkflowChangeRequestModel.requested_at.desc())
        rows = (await self.db.execute(stmt)).scalars().all()
        return [WCRResponseDTO.model_validate(r) for r in rows]

    async def get(self, wcr_id: str) -> WCRResponseDTO:
        wcr = await self.db.get(WorkflowChangeRequestModel, wcr_id)
        if not wcr:
            raise NotFoundError(f"WorkflowChangeRequest {wcr_id} not found")
        return WCRResponseDTO.model_validate(wcr)

    async def transition(
        self,
        *,
        wcr_id: str,
        dto: UpdateStatusDTO,
        reviewer_id: str,
    ) -> WCRResponseDTO:
        await self._ensure_reviewer(reviewer_id)

        wcr = await self.db.get(WorkflowChangeRequestModel, wcr_id)
        if not wcr:
            raise NotFoundError(f"WorkflowChangeRequest {wcr_id} not found")

        if dto.status not in VALID_TRANSITIONS.get(wcr.status, set()):
            raise ValueError(
                f"Cannot transition from {wcr.status!r} to {dto.status!r}"
            )

        wcr.status = dto.status
        wcr.reviewed_by = reviewer_id
        wcr.reviewed_at = datetime.now(timezone.utc)
        if dto.review_notes:
            wcr.review_notes = dto.review_notes

        await self.db.commit()
        await self.db.refresh(wcr)
        return WCRResponseDTO.model_validate(wcr)

    async def implement(
        self,
        *,
        wcr_id: str,
        dto: ImplementDTO,
        reviewer_id: str,
    ) -> WCRResponseDTO:
        await self._ensure_reviewer(reviewer_id)

        wcr = await self.db.get(WorkflowChangeRequestModel, wcr_id)
        if not wcr:
            raise NotFoundError(f"WorkflowChangeRequest {wcr_id} not found")

        if "implemented" not in VALID_TRANSITIONS.get(wcr.status, set()):
            raise ValueError(
                f"Cannot mark implemented from status {wcr.status!r}; "
                "the WCR must be approved first."
            )

        now = datetime.now(timezone.utc)
        wcr.status = "implemented"
        wcr.workflow_id = dto.workflow_id
        wcr.implemented_in_workflow_url = dto.workflow_url
        wcr.implemented_at = now
        wcr.reviewed_by = wcr.reviewed_by or reviewer_id
        wcr.reviewed_at = wcr.reviewed_at or now

        await self.db.commit()
        await self.db.refresh(wcr)
        return WCRResponseDTO.model_validate(wcr)

    # ─── internals ─────────────────────────────────────────────

    async def _ensure_reviewer(self, reviewer_id: str) -> None:
        """Defense in depth: the router gates this too, but checking here
        means scripts and tests can't bypass the permission accidentally.
        """
        role_id = (
            await self.db.execute(
                select(UserModel.role_id).where(UserModel.id == reviewer_id)
            )
        ).scalar_one_or_none()
        if not role_id:
            raise PermissionDeniedError(
                f"Reviewer {reviewer_id} not found or has no role"
            )

        ok = await has_permission(
            self.db, role_id, "workflow_change_requests", "review"
        )
        if not ok:
            raise PermissionDeniedError(
                "User lacks workflow_change_requests:review permission"
            )
