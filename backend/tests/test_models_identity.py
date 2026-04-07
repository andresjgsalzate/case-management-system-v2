def test_role_model_tablename():
    from backend.src.modules.roles.infrastructure.models import RoleModel
    assert RoleModel.__tablename__ == "roles"


def test_permission_model_tablename():
    from backend.src.modules.roles.infrastructure.models import PermissionModel
    assert PermissionModel.__tablename__ == "permissions"


def test_user_model_tablename():
    from backend.src.modules.users.infrastructure.models import UserModel
    assert UserModel.__tablename__ == "users"


def test_team_model_tablename():
    from backend.src.modules.teams.infrastructure.models import TeamModel
    assert TeamModel.__tablename__ == "teams"


def test_session_model_tablename():
    from backend.src.modules.auth.infrastructure.models import UserSessionModel
    assert UserSessionModel.__tablename__ == "user_sessions"


def test_all_models_in_base_metadata():
    # Verify all tables are registered in Base.metadata
    from backend.src.core.database import Base
    from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel
    from backend.src.modules.teams.infrastructure.models import TeamModel, TeamMemberModel
    from backend.src.modules.users.infrastructure.models import UserModel
    from backend.src.modules.auth.infrastructure.models import UserSessionModel
    table_names = set(Base.metadata.tables.keys())
    assert "roles" in table_names
    assert "permissions" in table_names
    assert "users" in table_names
    assert "teams" in table_names
    assert "team_members" in table_names
    assert "user_sessions" in table_names
