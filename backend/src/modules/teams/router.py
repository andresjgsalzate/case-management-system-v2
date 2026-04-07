from fastapi import APIRouter, Depends
from backend.src.core.dependencies import DBSession
from backend.src.modules.teams.application.dtos import (
    CreateTeamDTO, AddMemberDTO, TeamResponseDTO,
)
from backend.src.modules.teams.application.use_cases import TeamUseCases
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker

router = APIRouter(prefix="/teams", tags=["teams"])
TeamsRead = Depends(PermissionChecker("teams", "read"))
TeamsManage = Depends(PermissionChecker("teams", "manage"))


@router.get("", response_model=SuccessResponse[list[TeamResponseDTO]])
async def list_teams(db: DBSession, current_user: CurrentUser = TeamsRead):
    uc = TeamUseCases(db)
    teams = await uc.list_teams(current_user.tenant_id)
    return SuccessResponse.ok(teams)


@router.post("", response_model=SuccessResponse[TeamResponseDTO], status_code=201)
async def create_team(
    dto: CreateTeamDTO, db: DBSession, current_user: CurrentUser = TeamsManage
):
    uc = TeamUseCases(db)
    team = await uc.create_team(dto, current_user.user_id, current_user.tenant_id)
    return SuccessResponse.ok(team)


@router.get("/{team_id}", response_model=SuccessResponse[TeamResponseDTO])
async def get_team(team_id: str, db: DBSession, current_user: CurrentUser = TeamsRead):
    uc = TeamUseCases(db)
    team = await uc.get_team(team_id)
    return SuccessResponse.ok(team)


@router.post("/{team_id}/members", status_code=201)
async def add_member(
    team_id: str, dto: AddMemberDTO, db: DBSession, current_user: CurrentUser = TeamsManage
):
    uc = TeamUseCases(db)
    await uc.add_member(team_id, dto, current_user.user_id, current_user.tenant_id)
    return {"success": True}


@router.delete("/{team_id}/members/{user_id}", status_code=204)
async def remove_member(
    team_id: str,
    user_id: str,
    db: DBSession,
    current_user: CurrentUser = TeamsManage,
):
    uc = TeamUseCases(db)
    await uc.remove_member(team_id, user_id, current_user.user_id, current_user.tenant_id)
