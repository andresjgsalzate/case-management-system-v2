"""Tests for Sub-spec 06 — Operational Center UI backend."""
import asyncio

import pytest


def _run_db_query(async_query):
    """Helper mirroring Sub-spec 04/05: uses real DATABASE_URL from .env."""
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


def test_operational_permissions_seeded():
    """Migration 5308b8cc935f inserted 4 (module, action) pairs across the 3
    operational_center modules."""
    from sqlalchemy import text as _t

    async def _go(session):
        rows = (await session.execute(_t(
            "SELECT DISTINCT module, action FROM permissions "
            "WHERE module IN ('dashboard_soc', 'audit_explorer', "
            "'integration_health')"
        ))).all()
        return {(r[0], r[1]) for r in rows}

    pairs = _run_db_query(_go)
    assert pairs == {
        ("dashboard_soc", "read"),
        ("audit_explorer", "read"),
        ("audit_explorer", "export"),
        ("integration_health", "read"),
    }, f"Unexpected seeded pairs: {pairs}"


def test_integration_health_model_smoke():
    """IntegrationHealthModel imports + maps to expected table."""
    from backend.src.modules.operational_center.infrastructure.models import (
        IntegrationHealthModel,
    )
    assert IntegrationHealthModel.__tablename__ == "integration_health"
