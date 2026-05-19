"""N8nWorkflowCatalogUseCases — unit tests.

DB-backed: each test creates the model + commits via an in-process
async session pointing at the dev DB (same conftest pattern as
test_alert_reports.py). Tests clean up their rows on exit.
"""
import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _get_real_url() -> str:
    url = os.environ.get("REAL_DATABASE_URL")
    if not url:
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        url = env.get("DATABASE_URL")
    if not url:
        pytest.skip(
            "neither REAL_DATABASE_URL nor backend/.env DATABASE_URL set"
        )
    return url


@asynccontextmanager
async def _session():
    engine = create_async_engine(_get_real_url())
    try:
        sm = async_sessionmaker(engine, expire_on_commit=False)
        async with sm() as s:
            yield s
    finally:
        await engine.dispose()


def test_n8n_workflow_model_smoke():
    from backend.src.modules.n8n_bridge.infrastructure.models import (
        N8nWorkflowModel,
    )
    assert N8nWorkflowModel.__tablename__ == "n8n_workflows"


def test_create_workflow_returns_dto():
    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        CreateN8nWorkflowDTO,
        N8nWorkflowCatalogUseCases,
    )

    async def _run():
        async with _session() as db:
            uc = N8nWorkflowCatalogUseCases(db)
            name = f"test-wf-{uuid.uuid4().hex[:8]}"
            wf = await uc.create(
                CreateN8nWorkflowDTO(
                    tenant_id=None,
                    name=name,
                    description="smoke",
                    workflow_url="https://n8n.example.com/webhook/abc",
                    is_active=True,
                    requires_approval=False,
                    allowed_role_ids=None,
                ),
                created_by_user_id=None,
            )
            assert wf.name == name
            assert wf.tenant_id is None
            assert wf.workflow_url.startswith("https://")
            # Cleanup
            await uc.delete(wf.id)

    asyncio.run(_run())


def test_create_duplicate_name_in_tenant_raises_conflict():
    """Duplicate (tenant_id, name) hits the unique constraint.

    Uses a real tenant from the DB; Postgres treats NULL tenant_id as
    distinct so globals can collide — see model docstring."""
    from sqlalchemy import select

    from backend.src.core.exceptions import ConflictError
    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        CreateN8nWorkflowDTO,
        N8nWorkflowCatalogUseCases,
    )
    from backend.src.modules.tenants.infrastructure.models import TenantModel

    async def _run():
        async with _session() as db:
            tenant = (
                await db.execute(select(TenantModel).limit(1))
            ).scalar_one_or_none()
            if tenant is None:
                pytest.skip("no tenant rows available")
            uc = N8nWorkflowCatalogUseCases(db)
            name = f"dup-{uuid.uuid4().hex[:8]}"
            payload = CreateN8nWorkflowDTO(
                tenant_id=tenant.id,
                name=name,
                workflow_url="https://n8n.example.com/webhook/dup",
            )
            wf = await uc.create(payload, created_by_user_id=None)
            try:
                with pytest.raises(ConflictError):
                    await uc.create(payload, created_by_user_id=None)
            finally:
                await uc.delete(wf.id)

    asyncio.run(_run())


def test_update_partial_only_touches_set_fields():
    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        CreateN8nWorkflowDTO,
        N8nWorkflowCatalogUseCases,
        UpdateN8nWorkflowDTO,
    )

    async def _run():
        async with _session() as db:
            uc = N8nWorkflowCatalogUseCases(db)
            name = f"upd-{uuid.uuid4().hex[:8]}"
            wf = await uc.create(
                CreateN8nWorkflowDTO(
                    name=name,
                    workflow_url="https://n8n.example.com/webhook/orig",
                    description="original",
                ),
                created_by_user_id=None,
            )
            try:
                updated = await uc.update(
                    wf.id,
                    UpdateN8nWorkflowDTO(is_active=False),
                )
                assert updated.is_active is False
                assert updated.name == name  # unchanged
                assert updated.description == "original"  # unchanged
            finally:
                await uc.delete(wf.id)

    asyncio.run(_run())


def test_list_filters_by_tenant_and_active():
    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        CreateN8nWorkflowDTO,
        N8nWorkflowCatalogUseCases,
    )

    async def _run():
        async with _session() as db:
            uc = N8nWorkflowCatalogUseCases(db)
            base = uuid.uuid4().hex[:8]
            inactive = await uc.create(
                CreateN8nWorkflowDTO(
                    name=f"inactive-{base}",
                    workflow_url="https://n8n.example.com/webhook/inactive",
                    is_active=False,
                ),
                created_by_user_id=None,
            )
            active = await uc.create(
                CreateN8nWorkflowDTO(
                    name=f"active-{base}",
                    workflow_url="https://n8n.example.com/webhook/active",
                    is_active=True,
                ),
                created_by_user_id=None,
            )
            try:
                all_rows = await uc.list(tenant_id=None, only_active=False)
                names = {r.name for r in all_rows}
                assert f"inactive-{base}" in names
                assert f"active-{base}" in names

                only_active = await uc.list(
                    tenant_id=None, only_active=True,
                )
                active_names = {r.name for r in only_active}
                assert f"active-{base}" in active_names
                assert f"inactive-{base}" not in active_names
            finally:
                await uc.delete(active.id)
                await uc.delete(inactive.id)

    asyncio.run(_run())


def test_invalid_url_rejected_by_pydantic():
    from pydantic import ValidationError

    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        CreateN8nWorkflowDTO,
    )
    with pytest.raises(ValidationError):
        CreateN8nWorkflowDTO(
            name="bad",
            workflow_url="not-a-url",  # type: ignore[arg-type]
        )


def test_delete_unknown_raises_notfound():
    from backend.src.core.exceptions import NotFoundError
    from backend.src.modules.n8n_bridge.application.workflow_catalog import (
        N8nWorkflowCatalogUseCases,
    )

    async def _run():
        async with _session() as db:
            uc = N8nWorkflowCatalogUseCases(db)
            with pytest.raises(NotFoundError):
                await uc.delete(str(uuid.uuid4()))

    asyncio.run(_run())
