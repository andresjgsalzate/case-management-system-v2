"""Tests for the Workflow Change Request module (sub-spec 09 §3.9)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


def test_wcr_model_tablename():
    """Smoke test: the model exists and binds to the expected table."""
    from backend.src.modules.workflow_change_requests.infrastructure.models import (
        WorkflowChangeRequestModel,
    )

    assert WorkflowChangeRequestModel.__tablename__ == "workflow_change_requests"


def test_wcr_model_columns_present():
    """Every column the use cases will read or write must be declared."""
    from backend.src.modules.workflow_change_requests.infrastructure.models import (
        WorkflowChangeRequestModel,
    )

    cols = {c.name for c in WorkflowChangeRequestModel.__table__.columns}
    expected = {
        "id", "tenant_id", "workflow_id",
        "title", "description", "proposed_change",
        "requested_by", "requested_at",
        "status", "reviewed_by", "reviewed_at", "review_notes",
        "implemented_at", "implemented_in_workflow_url",
    }
    missing = expected - cols
    assert not missing, f"Missing columns: {missing}"


# ─────────────────────────────────────────────────────────────
#  Task 4.2 — DTOs + use cases
# ─────────────────────────────────────────────────────────────


def _mock_db(get_return=None, has_permission=True):
    """Return an AsyncMock SQLAlchemy session that:
       * stubs `get(...)`  -> `get_return`
       * stubs the permission lookup so the use case sees `has_permission`.
    """
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.flush = AsyncMock()
    db.get = AsyncMock(return_value=get_return)

    # has_permission() does one execute().scalar_one_or_none()
    perm_result = MagicMock()
    perm_result.scalar_one_or_none = MagicMock(
        return_value=MagicMock() if has_permission else None
    )
    # Role lookup also goes through execute(); a single-side_effect list of
    # results forces ordering. Use cases query: (a) user row -> role_id,
    # (b) permission row.
    user_result = MagicMock()
    user_result.scalar_one_or_none = MagicMock(return_value="role-reviewer")
    db.execute = AsyncMock(side_effect=[user_result, perm_result])
    return db


def _make_wcr_row(status: str = "pending", id_: str = "wcr-1"):
    """Real SQLAlchemy row (not a Mock) so Pydantic `model_validate`
    with `from_attributes=True` can serialize it back into a DTO."""
    from datetime import datetime, timezone
    from backend.src.modules.workflow_change_requests.infrastructure.models import (
        WorkflowChangeRequestModel,
    )

    return WorkflowChangeRequestModel(
        id=id_,
        tenant_id="tenant-1",
        workflow_id=None,
        title="Add retry to Slack notif",
        description="Slack step occasionally 5xxs",
        proposed_change={"type": "modify_step", "details": "wrap with retry"},
        requested_by="user-requester",
        requested_at=datetime.now(timezone.utc),
        status=status,
        reviewed_by=None,
        reviewed_at=None,
        review_notes=None,
        implemented_at=None,
        implemented_in_workflow_url=None,
    )


async def test_create_wcr_persists():
    from backend.src.modules.workflow_change_requests.application.dtos import (
        CreateWCRDTO,
    )
    from backend.src.modules.workflow_change_requests.application.use_cases import (
        WCRUseCases,
    )

    db = _mock_db()
    uc = WCRUseCases(db)
    dto = CreateWCRDTO(
        title="Add retry to Slack notif",
        description="Slack step occasionally 5xxs; add a retry wrapper.",
        proposed_change={"type": "modify_step", "details": "wrap with retry"},
        workflow_id=None,
        tenant_id="tenant-1",
    )

    result = await uc.create(dto=dto, requester_id="user-requester")

    db.add.assert_called_once()
    db.commit.assert_awaited()
    assert result.title == dto.title
    assert result.status == "pending"
    assert result.requested_by == "user-requester"


def test_create_wcr_rejects_invalid_proposed_change_type():
    """CreateWCRDTO should reject a proposed_change.type outside the enum."""
    from backend.src.modules.workflow_change_requests.application.dtos import (
        CreateWCRDTO,
    )

    with pytest.raises(Exception):
        CreateWCRDTO(
            title="x",
            description="y",
            proposed_change={"type": "delete_universe", "details": "boom"},
        )


async def test_transition_pending_to_in_review():
    from backend.src.modules.workflow_change_requests.application.dtos import (
        UpdateStatusDTO,
    )
    from backend.src.modules.workflow_change_requests.application.use_cases import (
        WCRUseCases,
    )

    wcr = _make_wcr_row(status="pending")
    db = _mock_db(get_return=wcr, has_permission=True)
    uc = WCRUseCases(db)

    result = await uc.transition(
        wcr_id="wcr-1",
        dto=UpdateStatusDTO(status="in_review"),
        reviewer_id="user-reviewer",
    )

    assert result.status == "in_review"
    assert wcr.status == "in_review"
    assert wcr.reviewed_by == "user-reviewer"
    assert wcr.reviewed_at is not None


async def test_transition_rejects_invalid_target_state():
    """`pending → implemented` is not a legal direct transition."""
    from backend.src.modules.workflow_change_requests.application.dtos import (
        UpdateStatusDTO,
    )
    from backend.src.modules.workflow_change_requests.application.use_cases import (
        WCRUseCases,
    )

    wcr = _make_wcr_row(status="pending")
    db = _mock_db(get_return=wcr, has_permission=True)
    uc = WCRUseCases(db)

    with pytest.raises(ValueError):
        await uc.transition(
            wcr_id="wcr-1",
            dto=UpdateStatusDTO(status="implemented"),
            reviewer_id="user-reviewer",
        )


async def test_implement_marks_implemented_and_links_workflow():
    from backend.src.modules.workflow_change_requests.application.dtos import (
        ImplementDTO,
    )
    from backend.src.modules.workflow_change_requests.application.use_cases import (
        WCRUseCases,
    )

    wcr = _make_wcr_row(status="approved")
    db = _mock_db(get_return=wcr, has_permission=True)
    uc = WCRUseCases(db)

    result = await uc.implement(
        wcr_id="wcr-1",
        dto=ImplementDTO(
            workflow_id="wf-99",
            workflow_url="https://cms.local/webhook/wf-99",
        ),
        reviewer_id="user-reviewer",
    )

    assert result.status == "implemented"
    assert wcr.workflow_id == "wf-99"
    assert wcr.implemented_at is not None
    assert wcr.implemented_in_workflow_url == "https://cms.local/webhook/wf-99"


async def test_only_reviewer_can_transition():
    """A user without `workflow_change_requests:review` cannot transition."""
    from backend.src.core.exceptions import PermissionDeniedError
    from backend.src.modules.workflow_change_requests.application.dtos import (
        UpdateStatusDTO,
    )
    from backend.src.modules.workflow_change_requests.application.use_cases import (
        WCRUseCases,
    )

    wcr = _make_wcr_row(status="pending")
    db = _mock_db(get_return=wcr, has_permission=False)
    uc = WCRUseCases(db)

    with pytest.raises(PermissionDeniedError):
        await uc.transition(
            wcr_id="wcr-1",
            dto=UpdateStatusDTO(status="in_review"),
            reviewer_id="user-no-perm",
        )
