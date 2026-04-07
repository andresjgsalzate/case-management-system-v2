import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from backend.src.modules.teams.infrastructure.models import TeamModel, TeamMemberModel
from backend.src.modules.teams.application.dtos import (
    CreateTeamDTO, UpdateTeamDTO, AddMemberDTO, TeamResponseDTO, TeamMemberResponseDTO,
)
from backend.src.core.exceptions import NotFoundError, ConflictError
from backend.src.core.events.bus import event_bus
from backend.src.core.events.base import BaseEvent


class TeamUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_team(
        self, dto: CreateTeamDTO, actor_id: str, tenant_id: str | None
    ) -> TeamResponseDTO:
        team = TeamModel(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            name=dto.name,
            description=dto.description,
        )
        self.db.add(team)
        await self.db.commit()
        await self.db.refresh(team)
        return self._to_dto(team)

    async def list_teams(self, tenant_id: str | None) -> list[TeamResponseDTO]:
        result = await self.db.execute(
            select(TeamModel)
            .options(selectinload(TeamModel.members))
            .where(TeamModel.tenant_id == tenant_id)
        )
        return [self._to_dto(t) for t in result.scalars().all()]

    async def get_team(self, team_id: str) -> TeamResponseDTO:
        result = await self.db.execute(
            select(TeamModel)
            .options(selectinload(TeamModel.members))
            .where(TeamModel.id == team_id)
        )
        team = result.scalar_one_or_none()
        if not team:
            raise NotFoundError("Team", team_id)
        return self._to_dto(team)

    async def add_member(
        self, team_id: str, dto: AddMemberDTO, actor_id: str, tenant_id: str
    ) -> None:
        existing = await self.db.execute(
            select(TeamMemberModel).where(
                TeamMemberModel.team_id == team_id,
                TeamMemberModel.user_id == dto.user_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("User is already a member of this team")

        member = TeamMemberModel(
            id=str(uuid.uuid4()),
            team_id=team_id,
            user_id=dto.user_id,
            team_role=dto.team_role,
        )
        self.db.add(member)
        await self.db.commit()

        await event_bus.publish(BaseEvent(
            event_name="team.member_added",
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload={"team_id": team_id, "user_id": dto.user_id},
        ))

    async def remove_member(
        self, team_id: str, user_id: str, actor_id: str, tenant_id: str
    ) -> None:
        result = await self.db.execute(
            select(TeamMemberModel).where(
                TeamMemberModel.team_id == team_id,
                TeamMemberModel.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise NotFoundError("Member", f"{team_id}/{user_id}")
        await self.db.delete(member)
        await self.db.commit()

        await event_bus.publish(BaseEvent(
            event_name="team.member_removed",
            tenant_id=tenant_id,
            actor_id=actor_id,
            payload={"team_id": team_id, "user_id": user_id},
        ))

    def _to_dto(self, model: TeamModel) -> TeamResponseDTO:
        return TeamResponseDTO(
            id=model.id,
            name=model.name,
            description=model.description,
            created_at=model.created_at.isoformat(),
            members=[
                TeamMemberResponseDTO(
                    user_id=m.user_id,
                    team_role=m.team_role,
                    joined_at=m.joined_at.isoformat(),
                )
                for m in (model.members or [])
            ],
        )
