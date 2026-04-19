"""Tests for filter_cases_by_permission — builds WHERE clauses that mirror
check_case_action. We don't hit a DB; we inspect the compiled SQL string."""
import os

# Set required env vars before any model imports trigger Settings validation.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32ch")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from sqlalchemy import select  # noqa: E402


def _make_user(scope: str, role_level: int, user_id: str = "u1", team_id: str = "t1"):
    from dataclasses import dataclass
    @dataclass
    class _U:
        user_id: str
        scope: str
        role_level: int
        team_id: str
    return _U(user_id=user_id, scope=scope, role_level=role_level, team_id=team_id)


def test_filter_scope_all_no_extra_clause():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel.__table__)
    filtered = filter_cases_by_permission(q, _make_user("all", 1))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    # 'all' scope adds no WHERE filters — check no WHERE clause exists at all
    assert "WHERE" not in sql


def test_filter_scope_own_restricts_to_self():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel.__table__)
    filtered = filter_cases_by_permission(q, _make_user("own", 1, user_id="me"))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "'me'" in sql  # either created_by or assigned_to
    assert "assigned_to" in sql or "created_by" in sql


def test_filter_scope_team_restricts_to_team():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel.__table__)
    filtered = filter_cases_by_permission(q, _make_user("team", 1, team_id="team-A"))
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "'team-A'" in sql
    assert "team_id" in sql


def test_filter_queue_mine_adds_current_level_match():
    from backend.src.core.permissions.case_queries import filter_cases_by_permission
    from backend.src.modules.cases.infrastructure.models import CaseModel
    q = select(CaseModel.__table__)
    filtered = filter_cases_by_permission(q, _make_user("team", 2), queue="mine")
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "current_level" in sql
    assert " = 2" in sql
