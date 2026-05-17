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
