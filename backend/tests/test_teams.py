import pytest
from backend.src.modules.teams.application.dtos import (
    CreateTeamDTO, AddMemberDTO, TeamResponseDTO, TeamMemberResponseDTO,
)


def test_create_team_dto_min_length():
    dto = CreateTeamDTO(name="Alpha Team")
    assert dto.name == "Alpha Team"
    assert dto.description is None


def test_create_team_dto_name_too_short():
    with pytest.raises(Exception):
        CreateTeamDTO(name="A")


def test_add_member_dto_default_role():
    dto = AddMemberDTO(user_id="user-123")
    assert dto.team_role == "member"


def test_add_member_dto_valid_roles():
    for role in ("manager", "lead", "member"):
        dto = AddMemberDTO(user_id="u1", team_role=role)
        assert dto.team_role == role


def test_add_member_dto_invalid_role_raises():
    with pytest.raises(Exception):
        AddMemberDTO(user_id="u1", team_role="admin")


def test_team_response_dto_empty_members():
    dto = TeamResponseDTO(
        id="t1", name="Team A", description=None,
        created_at="2024-01-01T00:00:00", members=[]
    )
    assert dto.members == []
