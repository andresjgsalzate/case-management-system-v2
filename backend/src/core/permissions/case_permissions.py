from typing import Literal, Protocol

CaseAction = Literal["read", "update", "transition", "transfer", "comment", "attach"]


class _UserLike(Protocol):
    user_id: str
    scope: str
    role_level: int
    team_id: str | None


class _CaseLike(Protocol):
    created_by: str
    assigned_to: str | None
    team_id: str | None
    current_level: int
    is_archived: bool


def check_case_action(user: _UserLike, case: _CaseLike, action: CaseAction) -> bool:
    """Return True iff *user* is allowed to perform *action* on *case*.

    Single source of truth for all per-case gates. See spec
    `docs/superpowers/specs/2026-04-18-helpdesk-permissions-levels-design.md` §4.1.
    """
    if case.is_archived and action != "read":
        return False

    is_reporter = user.role_level == 0
    is_asignee = case.assigned_to == user.user_id
    is_creator = case.created_by == user.user_id
    same_team = case.team_id is not None and case.team_id == user.team_id

    # read ─────────────────────────────────────────────────────────────────────
    if action == "read":
        if user.scope == "all":
            return True
        if is_creator or is_asignee:
            return True
        if user.scope == "team" and same_team:
            return True
        return False

    # comment / attach — any user who can read, plus case must not be archived
    if action in ("comment", "attach"):
        return check_case_action(user, case, "read")

    # update ───────────────────────────────────────────────────────────────────
    if action == "update":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if user.scope == "team" and same_team:
            return True
        return is_asignee

    # transition ──────────────────────────────────────────────────────────────
    if action == "transition":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if is_asignee:
            return True
        if user.scope == "team" and same_team and user.role_level > case.current_level:
            return True
        return False

    # transfer ────────────────────────────────────────────────────────────────
    if action == "transfer":
        if is_reporter:
            return False
        if user.scope == "all":
            return True
        if is_asignee:
            return True
        if user.scope == "team" and same_team and user.role_level > case.current_level:
            return True
        return False

    return False
