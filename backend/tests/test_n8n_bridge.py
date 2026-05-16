"""Tests for Sub-spec 05 — n8n Bridge."""
import asyncio

import pytest


def _run_db_query(async_query):
    """Run an async DB callable using the real DATABASE_URL (mirrors Spec 04 helper)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from dotenv import dotenv_values

    env = dotenv_values("backend/.env")
    real_url = env.get("DATABASE_URL")
    if not real_url:
        pytest.skip("DATABASE_URL not in backend/.env")

    async def _go():
        engine = create_async_engine(real_url)
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                return await async_query(session)
        finally:
            await engine.dispose()

    return asyncio.run(_go())


def test_n8n_bridge_permissions_seeded():
    """Migration 538c6aad7c8f inserted 5 (module, action) pairs across
    n8n_bridge + approvals."""
    from sqlalchemy import text as _t

    async def _go(session):
        rows = (await session.execute(_t(
            "SELECT DISTINCT module, action FROM permissions "
            "WHERE module IN ('n8n_bridge', 'approvals')"
        ))).all()
        return {(r[0], r[1]) for r in rows}

    pairs = _run_db_query(_go)
    assert pairs == {
        ("n8n_bridge", "trigger_workflow"),
        ("n8n_bridge", "read_runs"),
        ("n8n_bridge", "cancel_run"),
        ("approvals", "approve"),
        ("approvals", "read"),
    }, f"Unexpected seeded pairs: {pairs}"


# ── Task 3: JWT helper for callback auth ───────────────────────────────


def test_callback_jwt_issue_and_validate_roundtrip():
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-1", ttl_seconds=3600)
    claims = validate_callback_jwt(token, expected_case_id="case-1")
    assert claims["case_id"] == "case-1"
    assert claims["sub"] == "n8n"


def test_callback_jwt_case_id_mismatch_rejected():
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-A", ttl_seconds=3600)
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt(token, expected_case_id="case-B")


def test_callback_jwt_validation_skips_check_when_no_expected_case_id():
    """Validation without expected_case_id returns claims for inspection (used by
    callback dispatch when case_id comes from URL path)."""
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-X", ttl_seconds=3600)
    claims = validate_callback_jwt(token, expected_case_id=None)
    assert claims["case_id"] == "case-X"


def test_callback_jwt_expired_rejected():
    """Token issued with ttl=-1s is already expired → UnauthorizedError."""
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        issue_callback_jwt,
        validate_callback_jwt,
    )
    token = issue_callback_jwt(case_id="case-1", ttl_seconds=-1)
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt(token, expected_case_id="case-1")


def test_callback_jwt_garbage_token_rejected():
    from backend.src.core.exceptions import UnauthorizedError
    from backend.src.modules.n8n_bridge.application.jwt_helper import (
        validate_callback_jwt,
    )
    with pytest.raises(UnauthorizedError):
        validate_callback_jwt("not.a.jwt", expected_case_id=None)


def test_models_import_smoke():
    """All 3 n8n_bridge models import without errors."""
    from backend.src.modules.n8n_bridge.infrastructure.models import (
        ApprovalRequestModel,
        PlaybookRunCallbackModel,
        PlaybookRunModel,
    )
    assert PlaybookRunModel.__tablename__ == "playbook_runs"
    assert ApprovalRequestModel.__tablename__ == "approval_requests"
    assert PlaybookRunCallbackModel.__tablename__ == "playbook_run_callbacks"
