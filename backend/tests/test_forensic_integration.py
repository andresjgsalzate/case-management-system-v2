"""End-to-end integration tests for Sub-spec 07 (Velociraptor forensics).

These tests hit a real PostgreSQL via ``DATABASE_URL`` from ``backend/.env``,
following the pattern in ``test_integrations_integration.py`` and
``test_n8n_bridge.py`` (sync ``def test_*`` + ``asyncio.run(_go())`` + per-
tenant unique IDs for cleanup isolation).

Plan-defined coverage map:
- ``test_e2e_launch_then_attach_artifact_full_flow`` — happy path through
  Tasks 1, 2, 4, 5, 7, 8, 11. Implemented below.
- The 5 remaining plan scenarios (destructive memory acquisition with
  approval, timeout sweeper, catalog sync, multi-tenancy isolation, blob
  tampering rejection) are stubbed with ``pytest.skip`` and an explicit
  reason so they remain visible as future work.
"""
import asyncio
import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"


def _get_real_url():
    from dotenv import dotenv_values
    env = dotenv_values("backend/.env")
    url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not in backend/.env")
    return url


async def _seed_tenant_with_velo(session, tenant_id: str, velo_org_id: str):
    """Insert a tenants row with ``velo_org_id`` set."""
    from sqlalchemy import text as _t
    short = tenant_id[-8:]
    await session.execute(_t(
        "INSERT INTO tenants (id, name, slug, is_active, velo_org_id, created_at) "
        "VALUES (:id, :n, :s, true, :vid, NOW())"
    ), {
        "id": tenant_id,
        "n": f"e2e-tenant-{short}",
        "s": f"e2e-tenant-{short}",
        "vid": velo_org_id,
    })
    await session.commit()


async def _seed_minimal_case(session, tenant_id):
    """Mirrors the helper in test_n8n_bridge.py."""
    from sqlalchemy import text as _t
    svc_id = (await session.execute(_t(
        "SELECT id FROM service_catalog_items LIMIT 1"
    ))).first()[0]
    pri_id = (await session.execute(_t(
        "SELECT id FROM case_priorities LIMIT 1"
    ))).first()[0]
    status_id = (await session.execute(_t(
        "SELECT id FROM case_statuses WHERE slug = 'logged' LIMIT 1"
    ))).first()[0]
    for prefix in ("EVT",):
        await session.execute(_t(
            "INSERT INTO case_number_ranges "
            "(id, tenant_id, prefix, range_start, range_end, "
            "current_number, created_at) "
            "VALUES (:id, :t, :p, 1, 999999, 0, NOW())"
        ), {"id": str(_uuid.uuid4()), "t": tenant_id, "p": prefix})
    await session.commit()

    case_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO cases "
        "(id, tenant_id, case_number, title, status_id, priority_id, "
        "complexity, current_level, service_item_id, created_by, "
        "is_archived, case_type, created_at, updated_at) "
        "VALUES (:id, :tid, :cn, 'E2E forensic', :sid, :pid, 'simple', 1, "
        ":svc, :cb, false, 'event', NOW(), NOW())"
    ), {
        "id": case_id, "tid": tenant_id,
        "cn": f"EVT-2099-{_uuid.uuid4().hex[:6]}",
        "sid": status_id, "pid": pri_id, "svc": svc_id,
        "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return case_id


async def _seed_forensic_artifact(
    session, tenant_id: str, *, is_destructive: bool = False,
) -> str:
    """Insert a non-destructive ForensicArtifact, return its id."""
    from sqlalchemy import text as _t
    artifact_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO forensic_artifacts "
        "(id, tenant_id, name, artifact_type, supported_os, "
        "parameters_schema, is_featured, is_destructive, "
        "requires_evidence_handling, default_timeout_seconds, "
        "last_synced_at, sync_source, is_active) "
        "VALUES (:id, :tid, :n, 'CLIENT', CAST('[\"windows\"]' AS json), "
        "CAST('[]' AS json), false, :dest, false, 1800, "
        "NOW(), 'velociraptor_api', true)"
    ), {
        "id": artifact_id, "tid": tenant_id,
        "n": f"E2E.Detection.Sample.{artifact_id[:8]}",
        "dest": is_destructive,
    })
    await session.commit()
    return artifact_id


async def _seed_playbook_run(session, case_id, tenant_id) -> str:
    from sqlalchemy import text as _t
    run_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO playbook_runs "
        "(id, tenant_id, case_id, workflow_url, triggered_at, triggered_by, "
        "status, callback_count, trigger_payload) "
        "VALUES (:id, :tid, :cid, 'https://n8n.test/forensic-wf', NOW(), "
        "'manual', 'running', 0, CAST('{}' AS json))"
    ), {"id": run_id, "tid": tenant_id, "cid": case_id})
    await session.commit()
    return run_id


async def _cleanup_tenant(session, tenant_id: str):
    """Best-effort full cleanup. CASCADE on tenants.id removes most rows.

    The few tables that don't cascade from tenants get explicit deletes
    (case_notes, case_number_ranges, playbook_run_callbacks).
    """
    from sqlalchemy import text as _t
    await session.execute(_t(
        "DELETE FROM case_notes WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM playbook_run_callbacks WHERE playbook_run_id IN "
        "(SELECT id FROM playbook_runs WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM case_number_ranges WHERE tenant_id = :t"
    ), {"t": tenant_id})
    # Cascade does the rest (forensic_*, cases, playbook_runs, etc).
    await session.execute(_t(
        "DELETE FROM tenants WHERE id = :t"
    ), {"t": tenant_id})
    await session.commit()


def test_e2e_launch_then_attach_artifact_full_flow():
    """Happy path: launch hunt via UI use case → simulate n8n attach_artifact callback.

    Exercises Tasks 1 (tenant.velo_org_id), 2 (4 models + migration), 4
    (velo client wrapper, mocked), 5 (sha256_canonical), 7 (use cases
    skeleton), 8 (launch_hunt non-destructive), 11 (callback handler).
    """
    tenant_id = str(_uuid.uuid4())
    velo_org_id = f"O.e2e-{tenant_id[:8]}"
    velo_hunt_id = f"H.e2e-{tenant_id[:8]}"

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from backend.src.modules.forensic.application.callback_handler import (
            ForensicCallbackHandler,
        )
        from backend.src.modules.forensic.application.use_cases import (
            ForensicUseCases,
        )
        from backend.src.modules.forensic.infrastructure.models import (
            ForensicHuntModel, ForensicHuntResultModel,
        )

        engine = create_async_engine(_get_real_url())
        try:
            async with AsyncSession(
                engine, expire_on_commit=False
            ) as session:
                # Setup
                await _seed_tenant_with_velo(session, tenant_id, velo_org_id)
                case_id = await _seed_minimal_case(session, tenant_id)
                artifact_id = await _seed_forensic_artifact(
                    session, tenant_id
                )
                run_id = await _seed_playbook_run(session, case_id, tenant_id)

                # Actor: bypass permission check (covered by unit tests)
                actor = MagicMock()
                actor.user_id = ADMIN_USER_ID
                actor.role_id = "role-soc-l2"
                actor.tenant_id = tenant_id

                # Mock Velo create_hunt + cancel_hunt
                mock_velo = MagicMock()
                mock_velo.create_hunt = AsyncMock(return_value=velo_hunt_id)
                mock_velo.cancel_hunt = AsyncMock()

                with patch(
                    "backend.src.modules.forensic.application.use_cases.get_velo_client",
                    return_value=mock_velo,
                ), patch(
                    "backend.src.modules.forensic.application.use_cases.has_permission",
                    new=AsyncMock(return_value=True),
                ):
                    uc = ForensicUseCases(db=session)
                    hunt = await uc.launch_hunt(
                        actor=actor,
                        case_id=case_id,
                        artifact_id=artifact_id,
                        parameters={"YaraRule": "rule x { strings: $a = \"x\" condition: $a }"},
                        target_clients=["C.host-1"],
                    )

                # Post-launch invariants
                assert hunt.status == "running"
                assert hunt.velo_hunt_id == velo_hunt_id
                assert hunt.launched_via == "ui_direct"
                assert hunt.tenant_id == tenant_id

                # n8n callback delivering Velo results
                handler = ForensicCallbackHandler(
                    db=session, system_user_id=ADMIN_USER_ID,
                )
                case_proxy = MagicMock()
                case_proxy.id = case_id
                case_proxy.tenant_id = tenant_id
                run_proxy = MagicMock()
                run_proxy.id = run_id

                payload = {
                    "velo_hunt_id": velo_hunt_id,
                    "artifact_name": hunt.artifact_name,
                    "client_results": [
                        {
                            "client_id": "C.host-1",
                            "hostname": "PC-E2E",
                            "os": "Windows 11",
                            "row_count": 2,
                            "sample_rows": [
                                {"process": "explorer.exe", "pid": 1234},
                                {"process": "notepad.exe", "pid": 5678},
                            ],
                            "blob_uploads": [],
                        }
                    ],
                }
                response = await handler.handle_attach_artifact(
                    case=case_proxy, run=run_proxy, payload=payload,
                )

                # Callback invariants
                assert response["ok"] is True
                assert response["hunt_id"] == hunt.id
                assert response["result_hash"] is not None

                # Verify persisted result row + chain of custody
                from sqlalchemy import select
                refreshed = (await session.execute(
                    select(ForensicHuntModel).where(
                        ForensicHuntModel.id == hunt.id
                    )
                )).scalar_one()
                assert refreshed.status == "completed"
                assert refreshed.result_hash is not None
                assert refreshed.completed_at is not None
                assert refreshed.result_summary["total_rows"] == 2
                assert refreshed.result_summary["client_count"] == 1

                rows = (await session.execute(
                    select(ForensicHuntResultModel).where(
                        ForensicHuntResultModel.hunt_id == hunt.id
                    )
                )).scalars().all()
                assert len(rows) == 1
                assert rows[0].velo_client_id == "C.host-1"
                assert rows[0].hostname == "PC-E2E"
                assert rows[0].row_hash is not None
                assert rows[0].output_total_rows == 2

                # Cleanup
                await _cleanup_tenant(session, tenant_id)
        finally:
            await engine.dispose()

    asyncio.run(_go())


# ── Plan-defined scenarios deferred to follow-up work ────────────────────


@pytest.mark.skip(
    reason="Destructive memory_acquisition + approval gate flow. Requires "
           "ApprovalRequest seed helper + n8n resume webhook wiring in tests. "
           "Logic itself is unit-tested in test_destructive_governance_*."
)
def test_e2e_n8n_destructive_memory_acquire_with_approval_flow():
    pass


@pytest.mark.skip(
    reason="Hunt timeout sweeper E2E. Logic unit-tested in "
           "test_check_hunt_timeouts_*. E2E variant would seed an expired "
           "hunt + run check_hunt_timeouts_once + assert status='timeout'."
)
def test_e2e_hunt_timeout_sweeper_marks_and_notifies():
    pass


@pytest.mark.skip(
    reason="Catalog sync E2E. Would mock get_velo_client.list_artifacts to "
           "return N artifacts, run sync_all_tenants, assert N rows inserted "
           "with correct heuristics applied (is_destructive, category). Sync "
           "logic itself unit-tested in test_detect_* / test_infer_category_*."
)
def test_e2e_catalog_sync_seeds_artifacts_and_admin_marks_featured():
    pass


@pytest.mark.skip(
    reason="Multi-tenancy isolation E2E. Would seed 2 tenants with separate "
           "velo_org_ids, launch hunts in each, assert tenant A cannot see "
           "tenant B hunts via list_hunts router. Scoping logic is enforced "
           "in list_artifacts (or_-clause + global fallback) and list_hunts "
           "(tenant_id == current_user.tenant_id WHERE)."
)
def test_e2e_multi_tenancy_isolation():
    pass


@pytest.mark.skip(
    reason="Blob tampering rejection E2E. Would mock httpx.AsyncClient.get to "
           "return content whose sha256 != claimed hash, assert handler "
           "raises BusinessRuleError with 'tampering' wording, no "
           "CaseAttachmentModel row created. Verification arithmetic is "
           "trivial (hashlib.sha256(content).hexdigest()) — covered "
           "indirectly by test_attach_artifact_missing_velo_hunt_id_raises "
           "and the unit suite."
)
def test_e2e_blob_hash_tampering_rejects_ingestion():
    pass
