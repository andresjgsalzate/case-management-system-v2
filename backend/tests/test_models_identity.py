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


def test_all_models_have_correct_tablenames():
    # Verify each model class has the correct __tablename__
    # NOTE: Checking Base.metadata is unreliable in test suites that reload
    # database.py (test_database.py), which creates a fresh Base instance.
    # Instead, verify the __tablename__ attribute on each model class directly.
    from backend.src.modules.roles.infrastructure.models import RoleModel, PermissionModel
    from backend.src.modules.teams.infrastructure.models import TeamModel, TeamMemberModel
    from backend.src.modules.users.infrastructure.models import UserModel
    from backend.src.modules.auth.infrastructure.models import UserSessionModel
    assert RoleModel.__tablename__ == "roles"
    assert PermissionModel.__tablename__ == "permissions"
    assert UserModel.__tablename__ == "users"
    assert TeamModel.__tablename__ == "teams"
    assert TeamMemberModel.__tablename__ == "team_members"
    assert UserSessionModel.__tablename__ == "user_sessions"
