"""Use cases for the operational_center module (Sub-spec 06).

Phase 1 scope: dashboard summary aggregator. Audit Explorer + SSE land in
Tasks 4-6.
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.modules.operational_center.application.dashboard_summary import (
    compute_kpis,
    integration_health_summary,
    pending_approvals_summary,
    recent_inbound_events,
    severity_counters,
)
from sqlalchemy import select
from sqlalchemy import text as _t

from backend.src.modules.operational_center.application.dtos import (
    ApprovalSummaryDTO,
    DashboardSummaryDTO,
    IntegrationHealthSummaryDTO,
    KPIsDTO,
    RecentEventDTO,
)


class OperationalCenterUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_dashboard_summary(
        self,
        *,
        actor,
        period_hours: int = 24,
    ) -> DashboardSummaryDTO:
        """Build the aggregated dashboard payload, hiding widgets per permission.

        Widgets gated by permission:
        - integration_health requires integration_health:read
        - pending_approvals requires approvals:read
        Everything else is shown to any actor with dashboard_soc:read (the
        router enforces that gate before reaching this method).
        """
        from backend.src.core.middleware.permission_checker import (
            has_permission,
        )

        tenant_id = actor.tenant_id
        # Core widgets — visible to all dashboard_soc:read holders
        counters = await severity_counters(self.db, tenant_id)
        kpis_raw = await compute_kpis(self.db, tenant_id, period_hours=period_hours)
        events = await recent_inbound_events(self.db, tenant_id, limit=20)

        # Permission-gated optional widgets
        health = None
        if await has_permission(
            self.db, actor.role_id, "integration_health", "read",
        ):
            health_raw = await integration_health_summary(self.db, tenant_id)
            health = [IntegrationHealthSummaryDTO(**h) for h in health_raw]

        pending_count = None
        pending_list = None
        if await has_permission(self.db, actor.role_id, "approvals", "read"):
            pending_count, pending_rows = await pending_approvals_summary(
                self.db, tenant_id, top_n=5,
            )
            pending_list = [ApprovalSummaryDTO(**a) for a in pending_rows]

        return DashboardSummaryDTO(
            severity_counters=counters,
            kpis=KPIsDTO(**kpis_raw),
            recent_events=[RecentEventDTO(**e) for e in events],
            integration_health=health,
            pending_approvals_count=pending_count,
            pending_approvals=pending_list,
            generated_at=datetime.now(timezone.utc),
        )

    # ── Approval inbox (Task 6) ──────────────────────────────────────

    async def get_approval_inbox(
        self,
        *,
        actor,
        status: str = "pending",
        case_id: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """List approval_requests with filters. Returns dicts (router serializes).

        `status='all'` skips the status filter. Router enforces approvals:read
        before calling this method.
        """
        from backend.src.modules.n8n_bridge.infrastructure.models import (
            ApprovalRequestModel,
        )

        stmt = select(ApprovalRequestModel).where(
            ApprovalRequestModel.tenant_id == actor.tenant_id,
        )
        if status and status != "all":
            stmt = stmt.where(ApprovalRequestModel.status == status)
        if case_id:
            stmt = stmt.where(ApprovalRequestModel.case_id == case_id)
        if date_from:
            stmt = stmt.where(ApprovalRequestModel.created_at >= date_from)
        if date_to:
            stmt = stmt.where(ApprovalRequestModel.created_at <= date_to)
        stmt = (
            stmt.order_by(ApprovalRequestModel.created_at.desc())
            .limit(max(1, min(limit, 500)))
            .offset(max(0, offset))
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "id": a.id,
                "case_id": a.case_id,
                "playbook_run_id": a.playbook_run_id,
                "requested_action": a.requested_action,
                "action_category": a.action_category,
                "requested_by_workflow": a.requested_by_workflow,
                "status": a.status,
                "approver_user_id": a.approver_user_id,
                "decided_at": a.decided_at,
                "decided_reason": a.decided_reason,
                "timeout_at": a.timeout_at,
                "resume_succeeded": a.resume_succeeded,
                "created_at": a.created_at,
                "context_payload": a.context_payload,
            }
            for a in rows
        ]

    # ── Integration health detail (Task 6) ───────────────────────────

    async def get_integration_health_detail(
        self,
        *,
        tenant_id: str,
        source_id: str | None = None,
        hours: int = 6,
    ) -> list[dict]:
        """Return the time-series of integration_health rows for one or all
        sources of `tenant_id`. Default window covers the last 6 hours so
        the recharts widget renders ~72 points at the 5-min cadence."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        clauses = [
            "s.tenant_id = :t",
            "h.recorded_at >= :cutoff",
        ]
        params: dict = {"t": tenant_id, "cutoff": cutoff}
        if source_id:
            clauses.append("h.source_id = :sid")
            params["sid"] = source_id

        rows = (await self.db.execute(_t(
            f"""
            SELECT h.id, h.source_id, s.name AS source_name,
                   h.recorded_at, h.status,
                   h.events_received_5min, h.events_processed_5min,
                   h.events_failed_5min, h.avg_latency_ms_5min,
                   h.extra_metrics
            FROM integration_health h
            JOIN integration_sources s ON s.id = h.source_id
            WHERE {' AND '.join(clauses)}
            ORDER BY h.source_id, h.recorded_at ASC
            """
        ), params)).all()

        return [
            {
                "id": r[0], "source_id": r[1], "source_name": r[2],
                "recorded_at": r[3], "status": r[4],
                "events_received_5min": r[5],
                "events_processed_5min": r[6],
                "events_failed_5min": r[7],
                "avg_latency_ms_5min": r[8],
                "extra_metrics": r[9],
            }
            for r in rows
        ]
