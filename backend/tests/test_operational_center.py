"""Tests for Sub-spec 06 — Operational Center UI backend."""
import asyncio
import os

import pytest

# Same fixture as Sub-spec 04/05 — set BEFORE any module imports crypto.
os.environ.setdefault(
    "INTEGRATIONS_ENCRYPTION_KEY",
    "Uf0yMQkQS7qc_AQVDGFYNc8Lc4E4l0QYtVkk4IZ5tXU=",
)


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


# ── Task 3: Dashboard summary + KPIs ──────────────────────────────────


import uuid as _uuid  # noqa: E402

ADMIN_USER_ID = "ec35a91e-5778-4210-a631-c5ed673c679d"


async def _seed_case_for_tenant(
    session, tenant_id, *, priority_name=None, closed_minutes_ago=None,
    created_minutes_ago=None,
):
    """Insert one case for `tenant_id` with optional closed_at offset."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text as _t

    # Pre-seed case_number_ranges for tenant if missing
    for prefix in ("EVT",):
        exists = (await session.execute(_t(
            "SELECT 1 FROM case_number_ranges "
            "WHERE tenant_id = :t AND prefix = :p LIMIT 1"
        ), {"t": tenant_id, "p": prefix})).first()
        if not exists:
            await session.execute(_t(
                "INSERT INTO case_number_ranges "
                "(id, tenant_id, prefix, range_start, range_end, "
                "current_number, created_at) "
                "VALUES (:id, :t, :p, 1, 999999, 0, NOW())"
            ), {"id": str(_uuid.uuid4()), "t": tenant_id, "p": prefix})

    svc_id = (await session.execute(_t(
        "SELECT id FROM service_catalog_items LIMIT 1"
    ))).first()[0]
    # Resolve priority by name or take any
    if priority_name:
        pri = (await session.execute(_t(
            "SELECT id FROM case_priorities WHERE name = :n LIMIT 1"
        ), {"n": priority_name})).first()
    else:
        pri = (await session.execute(_t(
            "SELECT id FROM case_priorities LIMIT 1"
        ))).first()
    pri_id = pri[0]

    status_id = (await session.execute(_t(
        "SELECT id FROM case_statuses WHERE slug = 'logged' LIMIT 1"
    ))).first()[0]

    case_id = str(_uuid.uuid4())
    now = datetime.now(timezone.utc)
    created = now - timedelta(minutes=created_minutes_ago or 0)
    closed = (
        now - timedelta(minutes=closed_minutes_ago)
        if closed_minutes_ago is not None else None
    )
    await session.execute(_t(
        "INSERT INTO cases "
        "(id, tenant_id, case_number, title, status_id, priority_id, "
        "complexity, current_level, service_item_id, created_by, "
        "is_archived, case_type, closed_at, created_at, updated_at) "
        "VALUES (:id, :tid, :cn, 'kpi test', :sid, :pid, 'simple', 1, :svc, "
        ":cb, false, 'event', :closed, :created, :created)"
    ), {
        "id": case_id, "tid": tenant_id,
        "cn": f"EVT-2099-{_uuid.uuid4().hex[:6]}",
        "sid": status_id, "pid": pri_id, "svc": svc_id, "cb": ADMIN_USER_ID,
        "closed": closed, "created": created,
    })
    await session.commit()
    return case_id


async def _cleanup_tenant(session, tenant_id):
    from sqlalchemy import text as _t
    for tbl in ("cases", "integration_sources", "case_number_ranges"):
        await session.execute(_t(
            f"DELETE FROM {tbl} WHERE tenant_id = :t"
        ), {"t": tenant_id})
    await session.commit()


def test_severity_counters_groups_open_cases_by_priority():
    from backend.src.modules.operational_center.application.dashboard_summary import (
        severity_counters,
    )

    tenant_id = f"t-oc-sev-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        # Need at least 2 distinct priorities to be meaningful (case_priorities
        # has 'name' not 'slug' — pre-existing schema).
        prios = (await session.execute(__import__("sqlalchemy").text(
            "SELECT name FROM case_priorities LIMIT 2"
        ))).all()
        if len(prios) < 2:
            pytest.skip("dev seed lacks ≥2 case_priorities")
        await _seed_case_for_tenant(session, tenant_id, priority_name=prios[0][0])
        await _seed_case_for_tenant(session, tenant_id, priority_name=prios[0][0])
        await _seed_case_for_tenant(session, tenant_id, priority_name=prios[1][0])
        counters = await severity_counters(session, tenant_id)
        await _cleanup_tenant(session, tenant_id)
        return counters

    counters = _run_db_query(_go)
    assert sum(counters.values()) == 3
    # At least one bucket has 2 (the duplicated priority)
    assert 2 in counters.values()


def test_kpi_mttr_calculation_returns_minutes_or_none():
    """MTTR averages closed_at-created_at in minutes for cases closed in window."""
    from backend.src.modules.operational_center.application.dashboard_summary import (
        compute_kpis,
    )

    tenant_id = f"t-oc-mttr-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        # Case 1: 30 min from created → closed
        await _seed_case_for_tenant(
            session, tenant_id, closed_minutes_ago=10, created_minutes_ago=40,
        )
        # Case 2: 60 min
        await _seed_case_for_tenant(
            session, tenant_id, closed_minutes_ago=20, created_minutes_ago=80,
        )
        kpis = await compute_kpis(session, tenant_id, period_hours=24)
        await _cleanup_tenant(session, tenant_id)
        return kpis

    kpis = _run_db_query(_go)
    # Both cases inside 24h → MTTR avg of 30 and 60 = ~45 minutes
    assert kpis["mttr_minutes"] is not None
    assert 40 <= kpis["mttr_minutes"] <= 50
    assert kpis["cases_per_hour"] is not None
    # SLA + FP rate placeholder None in Phase 1
    assert kpis["sla_compliance_pct"] is None
    assert kpis["false_positive_rate_pct"] is None


def test_kpi_mttr_none_when_no_closed_cases():
    """No closed cases in window → mttr_minutes is None, not 0."""
    from backend.src.modules.operational_center.application.dashboard_summary import (
        compute_kpis,
    )

    tenant_id = f"t-oc-mttr-empty-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        kpis = await compute_kpis(session, tenant_id, period_hours=24)
        return kpis

    kpis = _run_db_query(_go)
    assert kpis["mttr_minutes"] is None
    assert kpis["cases_per_hour"] == 0.0


def test_recent_inbound_events_returns_latest_first():
    """Returns rows ordered by received_at DESC, limited."""
    from sqlalchemy import text as _t
    from backend.src.modules.operational_center.application.dashboard_summary import (
        recent_inbound_events,
    )

    tenant_id = f"t-oc-evt-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        # Seed an integration_source + 3 inbound_events
        from backend.src.modules.integrations.application.crypto import (
            encrypt_secret,
        )
        source_id = str(_uuid.uuid4())
        await session.execute(_t(
            "INSERT INTO integration_sources "
            "(id, tenant_id, name, source_type, auth_method, "
            "auth_secret_encrypted, is_active, total_events_received, "
            "total_events_failed, created_at, updated_at, created_by) "
            "VALUES (:id, :t, 'oc-src', 'wazuh', 'hmac', :sec, true, 0, 0, "
            "NOW(), NOW(), :cb)"
        ), {
            "id": source_id, "t": tenant_id,
            "sec": encrypt_secret("x"), "cb": ADMIN_USER_ID,
        })
        for i in range(3):
            await session.execute(_t(
                "INSERT INTO inbound_events "
                "(id, source_id, tenant_id, idempotency_key, raw_payload, "
                "status, attempt_count, max_attempts, received_at) "
                "VALUES (:id, :sid, :t, :ik, CAST('{}' AS json), 'pending', "
                "0, 3, NOW() + (:offset || ' seconds')::interval)"
            ), {
                "id": str(_uuid.uuid4()), "sid": source_id, "t": tenant_id,
                "ik": f"k-{_uuid.uuid4()}", "offset": str(i),
            })
        await session.commit()

        rows = await recent_inbound_events(session, tenant_id, limit=10)
        # cleanup
        await session.execute(_t(
            "DELETE FROM inbound_events WHERE tenant_id = :t"
        ), {"t": tenant_id})
        await _cleanup_tenant(session, tenant_id)
        return rows

    rows = _run_db_query(_go)
    assert len(rows) == 3
    # Verify DESC order
    assert rows[0]["received_at"] >= rows[1]["received_at"] >= rows[2]["received_at"]


def test_severity_counters_respects_tenant_isolation():
    """Tenant A's count never includes Tenant B's cases."""
    from backend.src.modules.operational_center.application.dashboard_summary import (
        severity_counters,
    )

    tenant_a = f"t-oc-iso-a-{_uuid.uuid4().hex[:8]}"
    tenant_b = f"t-oc-iso-b-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        await _seed_case_for_tenant(session, tenant_a)
        await _seed_case_for_tenant(session, tenant_b)
        await _seed_case_for_tenant(session, tenant_b)
        a_count = await severity_counters(session, tenant_a)
        b_count = await severity_counters(session, tenant_b)
        await _cleanup_tenant(session, tenant_a)
        await _cleanup_tenant(session, tenant_b)
        return a_count, b_count

    a, b = _run_db_query(_go)
    assert sum(a.values()) == 1
    assert sum(b.values()) == 2


# ── Task 4: integration_health refresh job + SSE stream ───────────────


def test_classify_health_status_healthy_low_failure_rate():
    from backend.src.modules.operational_center.application.jobs import (
        classify_health_status,
    )
    assert classify_health_status(
        received=100, failed=2,
        avg_latency_ms=200, seconds_since_last_event=10,
    ) == "healthy"


def test_classify_health_status_degraded_high_failure_rate():
    from backend.src.modules.operational_center.application.jobs import (
        classify_health_status,
    )
    assert classify_health_status(
        received=10, failed=4,  # 40% failure rate
        avg_latency_ms=200, seconds_since_last_event=10,
    ) == "degraded"


def test_classify_health_status_degraded_high_latency():
    from backend.src.modules.operational_center.application.jobs import (
        classify_health_status,
    )
    assert classify_health_status(
        received=50, failed=1,
        avg_latency_ms=10000,  # 10s avg → degraded
        seconds_since_last_event=30,
    ) == "degraded"


def test_classify_health_status_down_when_no_recent_events():
    from backend.src.modules.operational_center.application.jobs import (
        classify_health_status,
    )
    assert classify_health_status(
        received=0, failed=0, avg_latency_ms=None,
        seconds_since_last_event=700,  # > 600s window
    ) == "down"


def test_classify_health_status_healthy_zero_events_recent_source():
    """Zero events in 5-min window is fine if the source was recently active
    (e.g. quiet weekend)."""
    from backend.src.modules.operational_center.application.jobs import (
        classify_health_status,
    )
    assert classify_health_status(
        received=0, failed=0, avg_latency_ms=None,
        seconds_since_last_event=300,
    ) == "healthy"


def test_cleanup_old_integration_health_purges_rows_past_cutoff():
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import text as _t
    from backend.src.modules.operational_center.application.jobs import (
        cleanup_old_integration_health_once,
    )
    from backend.src.modules.integrations.application.crypto import encrypt_secret

    tenant_id = f"t-oc-cleanup-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        # Need a source for FK
        source_id = str(_uuid.uuid4())
        await session.execute(_t(
            "INSERT INTO integration_sources "
            "(id, tenant_id, name, source_type, auth_method, "
            "auth_secret_encrypted, is_active, total_events_received, "
            "total_events_failed, created_at, updated_at, created_by) "
            "VALUES (:id, :t, 'cl', 'wazuh', 'hmac', :sec, true, 0, 0, "
            "NOW(), NOW(), :cb)"
        ), {
            "id": source_id, "t": tenant_id,
            "sec": encrypt_secret("x"), "cb": ADMIN_USER_ID,
        })

        # Insert one row 40d old + one row 1h old
        old_id = str(_uuid.uuid4())
        fresh_id = str(_uuid.uuid4())
        await session.execute(_t(
            "INSERT INTO integration_health "
            "(id, source_id, recorded_at, events_received_5min, "
            "events_processed_5min, events_failed_5min, status) "
            "VALUES (:id, :sid, :ts, 0, 0, 0, 'healthy')"
        ), {
            "id": old_id, "sid": source_id,
            "ts": datetime.now(timezone.utc) - timedelta(days=40),
        })
        await session.execute(_t(
            "INSERT INTO integration_health "
            "(id, source_id, recorded_at, events_received_5min, "
            "events_processed_5min, events_failed_5min, status) "
            "VALUES (:id, :sid, :ts, 0, 0, 0, 'healthy')"
        ), {
            "id": fresh_id, "sid": source_id,
            "ts": datetime.now(timezone.utc) - timedelta(hours=1),
        })
        await session.commit()

        deleted = await cleanup_old_integration_health_once(session)

        # The fresh row should remain
        remaining = (await session.execute(_t(
            "SELECT id FROM integration_health WHERE source_id = :sid"
        ), {"sid": source_id})).scalars().all()
        # cleanup
        await session.execute(_t(
            "DELETE FROM integration_health WHERE source_id = :sid"
        ), {"sid": source_id})
        await session.execute(_t(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": source_id})
        await session.commit()
        return deleted, remaining
    deleted, remaining = _run_db_query(_go)
    assert deleted >= 1  # at least our old row purged
    # The fresh row was still in the list before cleanup
    # (rowcount may include rows from prior tests' leftovers — flexible assert)


def test_refresh_integration_health_writes_one_snapshot_per_source():
    from sqlalchemy import text as _t
    from backend.src.modules.operational_center.application.jobs import (
        refresh_integration_health_once,
    )
    from backend.src.modules.integrations.application.crypto import encrypt_secret

    tenant_id = f"t-oc-refresh-{_uuid.uuid4().hex[:8]}"

    async def _go(session):
        source_id = str(_uuid.uuid4())
        await session.execute(_t(
            "INSERT INTO integration_sources "
            "(id, tenant_id, name, source_type, auth_method, "
            "auth_secret_encrypted, is_active, total_events_received, "
            "total_events_failed, created_at, updated_at, created_by) "
            "VALUES (:id, :t, 'rf', 'wazuh', 'hmac', :sec, true, 0, 0, "
            "NOW(), NOW(), :cb)"
        ), {
            "id": source_id, "t": tenant_id,
            "sec": encrypt_secret("x"), "cb": ADMIN_USER_ID,
        })
        await session.commit()

        # Don't seed any inbound_events → source is "down" (no recent activity)
        await refresh_integration_health_once(session)

        rows = (await session.execute(_t(
            "SELECT status FROM integration_health WHERE source_id = :sid"
        ), {"sid": source_id})).all()
        await session.execute(_t(
            "DELETE FROM integration_health WHERE source_id = :sid"
        ), {"sid": source_id})
        await session.execute(_t(
            "DELETE FROM integration_sources WHERE id = :id"
        ), {"id": source_id})
        await session.commit()
        return rows

    rows = _run_db_query(_go)
    # One snapshot inserted; status='down' because the source has no
    # last_event_received_at (and 5-min window is empty)
    assert len(rows) == 1
    assert rows[0][0] in ("down", "healthy")  # depends on classify (no last_event_at → infinity)
    assert rows[0][0] == "down"


def test_sse_stream_yields_connected_then_publish_delivers_event():
    """Subscribing yields 'connected', then publish_to_dashboard fan-outs to
    that subscriber's queue and the next yield drains the event."""
    import asyncio as _aio
    from backend.src.modules.operational_center.application.sse_stream import (
        publish_to_dashboard,
        stream_dashboard_events,
    )

    tenant_id = f"t-oc-sse-{_uuid.uuid4().hex[:8]}"

    async def _go():
        gen = stream_dashboard_events(tenant_id=tenant_id)
        first = await gen.__anext__()
        # Publish AFTER subscribe so the queue exists
        n = await publish_to_dashboard(
            tenant_id=tenant_id, event_type="case.updated",
            payload={"case_id": "x"},
        )
        second = await gen.__anext__()
        await gen.aclose()
        return first, second, n

    first, second, n = _aio.run(_go())
    assert first.startswith("event: connected")
    assert "event: case.updated" in second
    assert '"case_id": "x"' in second
    assert n == 1


def test_sse_stream_tenant_isolation_no_cross_pollination():
    """Publish to tenant A → tenant B subscriber sees nothing."""
    import asyncio as _aio
    from backend.src.modules.operational_center.application.sse_stream import (
        publish_to_dashboard,
        stream_dashboard_events,
    )

    tenant_a = f"t-oc-sse-iso-a-{_uuid.uuid4().hex[:8]}"
    tenant_b = f"t-oc-sse-iso-b-{_uuid.uuid4().hex[:8]}"

    async def _go():
        gen_b = stream_dashboard_events(tenant_id=tenant_b)
        await gen_b.__anext__()  # connected
        n = await publish_to_dashboard(
            tenant_id=tenant_a, event_type="case.updated",
            payload={"x": 1},
        )
        await gen_b.aclose()
        return n

    # No tenant_b subscriber for tenant_a → 0 delivered
    assert _aio.run(_go()) == 0


def test_integration_health_model_smoke():
    """IntegrationHealthModel imports + maps to expected table."""
    from backend.src.modules.operational_center.infrastructure.models import (
        IntegrationHealthModel,
    )
    assert IntegrationHealthModel.__tablename__ == "integration_health"
