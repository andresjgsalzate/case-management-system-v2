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
