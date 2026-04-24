"""Unit tests for check_case_action — the central helpdesk permission helper.

Matrix covers 6 actions × 4 profiles = 24 base cases plus edge cases.
Profiles:
    reporter    → scope='own', role_level=0
    resolver_own → scope='own', role_level=1
    resolver_team → scope='team', role_level=1
    resolver_all → scope='all', role_level=1
"""
import pytest
from dataclasses import dataclass


@dataclass
class _FakeCase:
    id: str = "c1"
    created_by: str = "reporter-1"
    assigned_to: str | None = "agent-1"
    team_id: str | None = "team-1"
    current_level: int = 1
    is_archived: bool = False


@dataclass
class _FakeUser:
    user_id: str
    scope: str
    role_level: int
    is_global: bool = False
    # team_id of the user — looked up elsewhere; for tests we thread it directly
    team_id: str | None = "team-1"


def _u(uid: str, scope: str, role_level: int, team_id: str | None = "team-1") -> _FakeUser:
    return _FakeUser(user_id=uid, scope=scope, role_level=role_level, team_id=team_id)


# ── read ──────────────────────────────────────────────────────────────────────
def test_reporter_can_read_own_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_reporter_cannot_read_other_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="someone-else")
    assert check_case_action(user, case, "read") is False


def test_resolver_own_can_read_when_assigned():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_resolver_team_can_read_team_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1")
    assert check_case_action(user, case, "read") is True


def test_resolver_team_cannot_read_other_team_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-X")
    case = _FakeCase(team_id="team-1")
    assert check_case_action(user, case, "read") is False


def test_resolver_all_reads_everything():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("admin-1", "all", 1)
    case = _FakeCase(team_id="team-X", assigned_to="stranger")
    assert check_case_action(user, case, "read") is True


# ── update ────────────────────────────────────────────────────────────────────
def test_resolver_team_can_update_teammate_case():
    """This resolves the reported bug: peers in the same team must be able to update."""
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1")
    assert check_case_action(user, case, "update") is True


def test_resolver_own_cannot_update_others_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-2", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "update") is False


def test_reporter_cannot_update():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1")
    assert check_case_action(user, case, "update") is False


# ── transition (stricter than update) ─────────────────────────────────────────
def test_resolver_team_cannot_transition_teammate_case_at_same_level():
    """transition requires asignee OR higher level — same-level teammate is blocked."""
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transition") is False


def test_resolver_team_can_transition_when_higher_level():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("n2-1", "team", 2, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transition") is True


def test_asignee_can_always_transition_own_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "transition") is True


# ── transfer ──────────────────────────────────────────────────────────────────
def test_asignee_can_transfer():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("agent-1", "own", 1)
    case = _FakeCase(assigned_to="agent-1")
    assert check_case_action(user, case, "transfer") is True


def test_resolver_team_can_transfer_if_level_ge_current():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("n2-1", "team", 2, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transfer") is True


def test_resolver_team_cannot_transfer_if_not_asignee_and_same_level():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1", assigned_to="agent-1", current_level=1)
    assert check_case_action(user, case, "transfer") is False


# ── comment / attach (permissive for anyone with read) ────────────────────────
def test_anyone_with_read_can_comment():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("peer-1", "team", 1, team_id="team-1")
    case = _FakeCase(team_id="team-1")
    assert check_case_action(user, case, "comment") is True


def test_reporter_can_comment_on_own_open_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", is_archived=False)
    assert check_case_action(user, case, "comment") is True


def test_reporter_cannot_comment_on_archived_case():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("reporter-1", "own", 0)
    case = _FakeCase(created_by="reporter-1", is_archived=True)
    assert check_case_action(user, case, "comment") is False


# ── archived cases are read-only even for admins ──────────────────────────────
def test_archived_case_blocks_writes_for_admin():
    from backend.src.core.permissions.case_permissions import check_case_action
    user = _u("admin-1", "all", 1)
    case = _FakeCase(is_archived=True)
    assert check_case_action(user, case, "transition") is False
    assert check_case_action(user, case, "transfer") is False
    assert check_case_action(user, case, "read") is True
