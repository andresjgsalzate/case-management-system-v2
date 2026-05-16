"""Pydantic DTOs for the n8n_bridge module router."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Inbound callback payload (n8n → CMS) ───────────────────────────────


class CallbackPayload(BaseModel):
    """Body shape n8n posts to /api/v1/integrations/callbacks/n8n."""
    model_config = ConfigDict(extra="forbid")

    action: str
    playbook_run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


# ── Operator-triggered workflow ────────────────────────────────────────


class ManualTriggerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_url: str
    extra_context: dict[str, Any] | None = None


# ── Read-side ──────────────────────────────────────────────────────────


class PlaybookRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    case_id: str
    workflow_url: str
    workflow_id: str | None
    triggered_at: datetime
    completed_at: datetime | None
    triggered_by: str
    triggered_by_user: str | None
    status: str
    callback_count: int
    last_callback_at: datetime | None
    n8n_execution_id: str | None
    error: str | None
    final_decision: str | None
    final_decision_data: dict[str, Any] | None


class PlaybookRunCallbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    playbook_run_id: str
    received_at: datetime
    action: str
    payload: dict[str, Any]
    success: bool
    error: str | None
    response_payload: dict[str, Any] | None


class ApprovalRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    case_id: str
    playbook_run_id: str | None
    requested_action: str
    action_category: str
    context_payload: dict[str, Any]
    requested_by_workflow: str
    resume_url: str
    status: str
    approver_user_id: str | None
    decided_at: datetime | None
    decided_reason: str | None
    timeout_at: datetime
    resume_attempted_at: datetime | None
    resume_succeeded: bool
    resume_error: str | None
    created_at: datetime


# ── Decide payload ─────────────────────────────────────────────────────


class ApprovalDecidePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str  # 'approved' | 'rejected'
    reason: str | None = None
