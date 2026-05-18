"""Pydantic DTOs for the alert_reports module."""
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TemplateCreate(BaseModel):
    """Input to ``create_template`` (router body)."""
    name: str
    code: str
    header_config: dict[str, Any]
    footer_config: dict[str, Any]
    blocks: list[dict[str, Any]]
    description: str | None = None
    css_overrides: str | None = None
    tenant_id: str | None = None


class TemplateUpdate(BaseModel):
    """Input to ``update_template`` — every field optional (partial update)."""
    name: str | None = None
    description: str | None = None
    header_config: dict[str, Any] | None = None
    footer_config: dict[str, Any] | None = None
    blocks: list[dict[str, Any]] | None = None
    css_overrides: str | None = None
    change_summary: str | None = None


class TemplateSummary(BaseModel):
    """Compact projection of a template for list views."""
    id: str
    tenant_id: str | None
    name: str
    code: str
    description: str | None
    current_version_number: int
    is_default: bool
    is_active: bool
    updated_at: datetime


class TemplateVersionSummary(BaseModel):
    """One entry in a template's version history list."""
    id: str
    template_id: str
    version: int
    name_snapshot: str
    change_summary: str | None
    created_by_user_id: str | None
    created_at: datetime


class GenerateReportRequest(BaseModel):
    """Input to ``generate_report``."""
    template_id: str | None = None  # None → use tenant default


class GeneratedReportSummary(BaseModel):
    id: str
    case_id: str
    template_id: str
    template_version_number: int
    generated_at: datetime
    generated_via: str
    pdf_sha256: str
    pdf_size_bytes: int
    attachment_id: str
