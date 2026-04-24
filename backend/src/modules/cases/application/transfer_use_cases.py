import uuid
from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import NotFoundError, ForbiddenError, ValidationError
from backend.src.core.permissions.case_permissions import check_case_action
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.cases.infrastructure.transfer_models import CaseTransferModel
from backend.src.modules.cases.application.transfer_dtos import (
    TransferCaseDTO,
    TransferResponseDTO,
)
from backend.src.modules.users.infrastructure.models import UserModel
from backend.src.modules.roles.infrastructure.models import RoleModel

TransferType = Literal["escalate", "reassign", "de-escalate"]


def classify_transfer(from_level: int, to_level: int) -> TransferType:
    if to_level > from_level:
        return "escalate"
    if to_level < from_level:
        return "de-escalate"
    return "reassign"


class CaseTransferUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def transfer(
        self, case_id: str, dto: TransferCaseDTO, actor
    ) -> TransferResponseDTO:
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        if not check_case_action(actor, case, "transfer"):
            raise ForbiddenError("Cannot transfer this case")

        target_user = await self.db.get(UserModel, dto.to_user_id)
        if not target_user or not target_user.is_active:
            raise NotFoundError(f"Target user {dto.to_user_id} not found or inactive")
        if not target_user.team_id:
            raise ValidationError("Target user must belong to a team")

        target_role = (
            await self.db.get(RoleModel, target_user.role_id)
            if target_user.role_id
            else None
        )
        to_level = target_role.level if target_role else 1

        from_level = case.current_level
        transfer_type = classify_transfer(from_level, to_level)

        transfer = CaseTransferModel(
            id=str(uuid.uuid4()),
            tenant_id=case.tenant_id,
            case_id=case.id,
            from_user_id=case.assigned_to,
            from_level=from_level,
            to_user_id=dto.to_user_id,
            to_team_id=target_user.team_id,
            to_level=to_level,
            transfer_type=transfer_type,
            reason=dto.reason,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(transfer)
        case.assigned_to = dto.to_user_id
        case.team_id = target_user.team_id
        case.current_level = to_level
        await self.db.commit()
        await self.db.refresh(transfer)

        return TransferResponseDTO(
            id=transfer.id,
            case_id=transfer.case_id,
            from_user_id=transfer.from_user_id,
            from_level=transfer.from_level,
            to_user_id=transfer.to_user_id,
            to_team_id=transfer.to_team_id,
            to_level=transfer.to_level,
            transfer_type=transfer.transfer_type,
            reason=transfer.reason,
            created_at=transfer.created_at.isoformat(),
        )

    async def list_transfers(self, case_id: str) -> list[TransferResponseDTO]:
        result = await self.db.execute(
            select(CaseTransferModel)
            .where(CaseTransferModel.case_id == case_id)
            .order_by(CaseTransferModel.created_at.desc())
        )
        return [
            TransferResponseDTO(
                id=t.id,
                case_id=t.case_id,
                from_user_id=t.from_user_id,
                from_level=t.from_level,
                to_user_id=t.to_user_id,
                to_team_id=t.to_team_id,
                to_level=t.to_level,
                transfer_type=t.transfer_type,
                reason=t.reason,
                created_at=t.created_at.isoformat(),
            )
            for t in result.scalars().all()
        ]
