"""End-to-end integration tests for Sub-spec 08 (Alert Report Generator).

Same execution pattern as ``test_forensic_integration.py``:
- sync ``def test_*`` + ``asyncio.run(_go())`` for compatibility with the
  existing test infrastructure
- ``_open_session()`` reads ``REAL_DATABASE_URL`` (containerised runs) or
  falls back to ``backend/.env`` for host-based dev
- per-test unique tenant_id keeps runs isolated; cleanup via FK CASCADE

The ``_skip_no_pdf`` marker keeps PDF tests off Windows hosts that lack
GTK3 native libs. Run inside the ``backend`` Docker container to exercise
the full flow.
"""
import asyncio
import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"


def _get_real_url():
    import os
    url = os.environ.get("REAL_DATABASE_URL")
    if not url:
        from dotenv import dotenv_values
        env = dotenv_values("backend/.env")
        url = env.get("DATABASE_URL")
    if not url:
        pytest.skip("neither REAL_DATABASE_URL nor backend/.env set")
    return url


def _weasyprint_works() -> bool:
    try:
        import weasyprint
        weasyprint.HTML(string="<p>x</p>").write_pdf()
        return True
    except Exception:
        return False


_skip_no_pdf = pytest.mark.skipif(
    not _weasyprint_works(),
    reason=(
        "WeasyPrint native libs (GTK3) not available — run inside backend "
        "container"
    ),
)


# ── seed helpers ────────────────────────────────────────────────────────


async def _seed_tenant(session, tenant_id: str):
    from sqlalchemy import text as _t
    short = tenant_id[-8:]
    await session.execute(_t(
        "INSERT INTO tenants (id, name, slug, is_active, created_at) "
        "VALUES (:id, :n, :s, true, NOW())"
    ), {
        "id": tenant_id,
        "n": f"e2e-tenant-{short}",
        "s": f"e2e-tenant-{short}",
    })
    await session.commit()


async def _seed_minimal_case(session, tenant_id: str) -> str:
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
    await session.execute(_t(
        "INSERT INTO case_number_ranges "
        "(id, tenant_id, case_type, prefix, range_start, range_end, "
        "current_number, created_at) "
        "VALUES (:id, :t, 'event', 'EVT', 1, 999999, 0, NOW())"
    ), {"id": str(_uuid.uuid4()), "t": tenant_id})
    await session.commit()

    case_id = str(_uuid.uuid4())
    await session.execute(_t(
        "INSERT INTO cases "
        "(id, tenant_id, case_number, title, status_id, priority_id, "
        "complexity, current_level, service_item_id, created_by, "
        "is_archived, case_type, created_at, updated_at) "
        "VALUES (:id, :tid, :cn, 'E2E alert report', :sid, :pid, "
        "'simple', 1, :svc, :cb, false, 'event', NOW(), NOW())"
    ), {
        "id": case_id, "tid": tenant_id,
        "cn": f"EVT-2099-{_uuid.uuid4().hex[:6]}",
        "sid": status_id, "pid": pri_id, "svc": svc_id,
        "cb": ADMIN_USER_ID,
    })
    await session.commit()
    return case_id


async def _cleanup_tenant(session, tenant_id: str):
    """Cascade deletes via tenants.id FK chains; explicit deletes for the
    tables that don't cascade from tenants."""
    from sqlalchemy import text as _t
    # case_generated_reports.case_id CASCADE from cases → tenants
    # case_attachments — no direct tenant FK, delete via case
    await session.execute(_t(
        "DELETE FROM case_attachments WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM case_notes WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM activity_entries WHERE case_id IN "
        "(SELECT id FROM cases WHERE tenant_id = :t)"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM case_number_ranges WHERE tenant_id = :t"
    ), {"t": tenant_id})
    await session.execute(_t(
        "DELETE FROM tenants WHERE id = :t"
    ), {"t": tenant_id})
    await session.commit()


# ── implemented E2E ─────────────────────────────────────────────────────


@_skip_no_pdf
def test_e2e_generate_default_pdf_verify_hash_then_delete():
    """Full flow: generate report (default template) → verify SHA-256
    matches stored bytes → delete with reason → row gone, attachment
    soft-deleted.

    Exercises Tasks 1 (models) + 2 (perms) + 3 (block schemas) + 4
    (template CRUD) + 5 (snapshot builder) + 6 (block renderer) + 7
    (pdf_generator) + 8 (generate_report) + 9 (verify + delete) + 12
    (default SOC template seed).
    """
    tenant_id = str(_uuid.uuid4())

    async def _go():
        from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
        from sqlalchemy import select

        from backend.src.modules.alert_reports.application.use_cases import (
            AlertReportGenerationUseCases,
        )
        from backend.src.modules.alert_reports.infrastructure.models import (
            CaseGeneratedReportModel,
        )
        from backend.src.modules.attachments.infrastructure.models import (
            CaseAttachmentModel,
        )

        engine = create_async_engine(_get_real_url())
        try:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                await _seed_tenant(session, tenant_id)
                case_id = await _seed_minimal_case(session, tenant_id)

                actor = MagicMock()
                actor.user_id = ADMIN_USER_ID
                actor.role_id = "role-soc-l2"
                actor.tenant_id = tenant_id
                actor.is_global = True  # Bypass tenant scoping for E2E

                uc = AlertReportGenerationUseCases(
                    db=session, system_user_id=ADMIN_USER_ID,
                )

                with patch(
                    "backend.src.modules.alert_reports.application.use_cases.has_permission",
                    new=AsyncMock(return_value=True),
                ):
                    # 1. GENERATE — uses the seeded `soc_standard` global default
                    report = await uc.generate_report(
                        actor=actor, case_id=case_id,
                        template_id=None, n8n_run_id=None,
                    )

                # Post-generation invariants
                assert report.generated_via == "manual_ui"
                assert len(report.pdf_sha256) == 64
                assert report.pdf_size_bytes > 200  # real PDF, not empty
                assert report.template_version_number == 1

                # 2. VERIFY — re-hash on-disk file vs stored hash
                with patch(
                    "backend.src.modules.alert_reports.application.use_cases.has_permission",
                    new=AsyncMock(return_value=True),
                ):
                    verify_result = await uc.verify_report_integrity(
                        actor=actor, report_id=report.id,
                    )
                assert verify_result["is_intact"] is True
                assert (
                    verify_result["expected_sha256"]
                    == verify_result["actual_sha256"]
                )
                assert verify_result["pdf_size_bytes"] == report.pdf_size_bytes

                # 3. DELETE with reason — report row gone, attachment soft-deleted
                attachment_id = report.attachment_id
                with patch(
                    "backend.src.modules.alert_reports.application.use_cases.has_permission",
                    new=AsyncMock(return_value=True),
                ):
                    await uc.delete_report(
                        actor=actor, report_id=report.id,
                        reason="E2E test cleanup",
                    )

                # Report row gone
                still_there = (await session.execute(
                    select(CaseGeneratedReportModel).where(
                        CaseGeneratedReportModel.id == report.id
                    )
                )).scalar_one_or_none()
                assert still_there is None

                # Attachment soft-deleted (row preserved, flag flipped)
                attachment = await session.get(
                    CaseAttachmentModel, attachment_id,
                )
                assert attachment is not None
                assert attachment.is_deleted is True

                # Audit log captures the operator's reason
                audit_check = (await session.execute(
                    select_audit_changes_for_report(report.id)
                )).fetchone()
                assert audit_check is not None
                assert "E2E test cleanup" in str(audit_check[0])

                # Cleanup
                await _cleanup_tenant(session, tenant_id)
        finally:
            await engine.dispose()

    asyncio.run(_go())


def select_audit_changes_for_report(report_id: str):
    """SQLAlchemy `text()` select used by the integrity test."""
    from sqlalchemy import text as _t
    return _t(
        "SELECT changes FROM audit_logs "
        "WHERE entity_type = 'case_generated_reports' "
        "AND entity_id = :rid "
        "AND action = 'DELETE' "
        "ORDER BY created_at DESC LIMIT 1"
    ).bindparams(rid=report_id)


# ── deferred scenarios ──────────────────────────────────────────────────


@pytest.mark.skip(
    reason="Template picker UX flow. Needs http_client_admin + frontend "
           "auth. Logic covered by Task 4 / Task 8 unit tests "
           "(`list_templates`, `_resolve_template` with explicit ID)."
)
def test_e2e_template_picker_with_multiple():
    pass


@pytest.mark.skip(
    reason="Multi-version regeneration consistency. Would (a) generate "
           "with v1, (b) update_template → v2, (c) generate again, "
           "(d) assert old report.template_version_id still points at v1 "
           "while new report references v2. Versioning is unit-tested in "
           "test_update_template_no_change_skips_version_insert."
)
def test_e2e_template_edit_v2_old_reports_remain_v1():
    pass


@pytest.mark.skip(
    reason="n8n bridge driven generation. Would POST to /cases/{id}/alert-"
           "reports with n8n_run_id in body, assert response shape, then "
           "check generated_via='n8n_api' + generated_by_n8n_run_id set. "
           "Pure routing+auth concern; unit-tested via "
           "test_generate_report_n8n_actor_sets_n8n_api_via."
)
def test_e2e_n8n_generates_report():
    pass


@pytest.mark.skip(
    reason="Forensic hunts in evidence_grid. Would seed Sub-spec 07 hunts, "
           "generate report, assert PDF text contains forensic hunt names "
           "+ result_hash. Snapshot wiring tested in "
           "test_snapshot_forensic_hunts_returns_empty_when_no_hunts; "
           "renderer wiring in test_render_evidence_grid_*. Combining them "
           "with a real Velo mock is plumbing, not new behavior."
)
def test_e2e_evidence_grid_includes_forensic_hunts():
    pass


@pytest.mark.skip(
    reason="Manual corruption + verify integrity. Would generate, open "
           "attachment.file_path, write garbage bytes, then verify_report "
           "→ assert is_intact=False. Verify branch already covered by "
           "test_verify_integrity_detects_tampered_attachment unit test."
)
def test_e2e_verify_integrity_after_corruption():
    pass


@pytest.mark.skip(
    reason="Tenant isolation cross-template generation. Would seed two "
           "tenants + a Tenant-A template, then attempt generate from "
           "Tenant-B operator pointing at Tenant-A template → expect "
           "PermissionDeniedError. Tenant scoping tested by the 3 access "
           "guard tests under test_require_template_access_*."
)
def test_e2e_tenant_isolation_template_use():
    pass
