"""Pydantic DTOs for the operational_center module router."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SeverityCountersDTO(BaseModel):
    """Open cases counted by priority slug (e.g. {'critical': 3, 'high': 7})."""
    model_config = ConfigDict(extra="allow")


class KPIsDTO(BaseModel):
    """24-hour rolling KPIs. None when there isn't enough data to compute."""
    model_config = ConfigDict(extra="forbid")

    period_hours: int
    cases_per_hour: float | None = None
    mttr_minutes: float | None = None
    mttd_minutes: float | None = None
    sla_compliance_pct: float | None = None
    false_positive_rate_pct: float | None = None


class RecentEventDTO(BaseModel):
    """One row in the dashboard "live events" feed."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    received_at: datetime
    status: str
    case_id: str | None


class IntegrationHealthSummaryDTO(BaseModel):
    """Latest 5-min snapshot per source for the dashboard widget."""
    model_config = ConfigDict(from_attributes=True)

    source_id: str
    source_name: str | None = None
    status: str
    recorded_at: datetime
    events_received_5min: int
    events_processed_5min: int
    events_failed_5min: int
    avg_latency_ms_5min: int | None


class ApprovalSummaryDTO(BaseModel):
    """Compact view of a pending approval for the dashboard widget."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    requested_action: str
    action_category: str
    requested_by_workflow: str
    timeout_at: datetime
    created_at: datetime


class DashboardSummaryDTO(BaseModel):
    """Aggregated payload returned by /operational/dashboard/summary.

    Fields marked Optional are None when the actor lacks the corresponding
    permission so the UI can hide widgets without an extra round-trip.
    """
    model_config = ConfigDict(extra="forbid")

    severity_counters: dict[str, int]
    kpis: KPIsDTO
    recent_events: list[RecentEventDTO]
    integration_health: list[IntegrationHealthSummaryDTO] | None = None
    pending_approvals_count: int | None = None
    pending_approvals: list[ApprovalSummaryDTO] | None = None
    generated_at: datetime


# ── Audit Explorer DTOs (Task 5) — slim shapes here, full builder in Task 5 ──


class AuditEventDTO(BaseModel):
    """Normalized audit event surfaced by Audit Explorer."""
    model_config = ConfigDict(extra="forbid")

    source_table: str  # 'cases_activity' | 'audit' | 'taxonomies_audit' | ...
    event_id: str
    occurred_at: datetime
    case_id: str | None = None
    actor_id: str | None = None
    summary: str
    extra: dict[str, Any] | None = None


class AuditQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[AuditEventDTO]
    total: int
