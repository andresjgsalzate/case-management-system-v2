from typing import Literal
from sqlalchemy import or_
from sqlalchemy.sql import Select

from backend.src.modules.cases.infrastructure.models import CaseModel

Queue = Literal["mine", "team", "all"]

# Use table-level column references so WHERE clauses compose correctly
# regardless of whether the caller passes select(CaseModel) or
# select(CaseModel.__table__) — both share the same underlying Column objects.
_t = CaseModel.__table__.c


def filter_cases_by_permission(query: Select, user, queue: Queue = "all") -> Select:
    """Apply RBAC WHERE clauses to a cases SELECT based on user scope + queue tab.

    Args:
        query: SELECT over the cases table (ORM or Core level).
        user: Must expose .user_id, .scope, .role_level, .team_id
        queue: 'mine' restricts to current_level == user.role_level;
               'team' restricts to same team across levels; 'all' = no queue filter.
    """
    # Scope gate
    if user.scope == "own":
        query = query.where(
            or_(_t.assigned_to == user.user_id, _t.created_by == user.user_id)
        )
    elif user.scope == "team":
        team_id = getattr(user, "team_id", None)
        if team_id:
            query = query.where(_t.team_id == team_id)
        else:
            query = query.where(_t.assigned_to == user.user_id)
    # scope == "all" → no extra WHERE

    # Queue filter (only meaningful when user has at least team scope)
    if queue == "mine":
        query = query.where(_t.current_level == user.role_level)
        query = query.where(
            or_(
                _t.assigned_to == user.user_id,
                _t.assigned_to.is_(None),
            )
        )
    # queue == "team" adds no extra filters beyond scope; scope already restricts to team
    # queue == "all" no extra filters

    return query
