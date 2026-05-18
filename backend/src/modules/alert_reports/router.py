"""Alert Reports HTTP router (Sub-spec 08 Task 13).

Endpoint surface (mounted at ``/api/v1``):

Templates (admin):
    GET    /alert-report-templates                    alert_reports.read
    POST   /alert-report-templates                    alert_reports.manage_templates
    GET    /alert-report-templates/{id}               alert_reports.read
    PATCH  /alert-report-templates/{id}               alert_reports.manage_templates
    DELETE /alert-report-templates/{id}               alert_reports.manage_templates
    POST   /alert-report-templates/{id}/set-default   alert_reports.set_default
    GET    /alert-report-templates/{id}/versions      alert_reports.view_versions
    POST   /alert-report-templates/{id}/preview       alert_reports.read
    POST   /alert-report-templates/{id}/clone         alert_reports.manage_templates

Generation (operator + n8n):
    POST   /cases/{case_id}/alert-reports             alert_reports.generate
    GET    /cases/{case_id}/alert-reports             alert_reports.read
    GET    /alert-reports/{id}                        alert_reports.read
    GET    /alert-reports/{id}/download               alert_reports.read
    GET    /alert-reports/{id}/verify                 alert_reports.read
    DELETE /alert-reports/{id}                        alert_reports.delete

The n8n-driven generation flow re-uses ``POST /cases/{case_id}/alert-reports``;
the service-account user is granted ``alert_reports.generate`` and submits the
``n8n_run_id`` in the body. HMAC verification for inbound n8n traffic is
handled by the integrations webhook layer, not here.
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.src.core.dependencies import DBSession
from backend.src.core.middleware.permission_checker import (
    CurrentUser, PermissionChecker,
)
from backend.src.core.responses import SuccessResponse
from backend.src.modules.alert_reports.application.dtos import (
    TemplateCreate, TemplateUpdate,
)
from backend.src.modules.alert_reports.application.use_cases import (
    AlertReportGenerationUseCases, AlertReportTemplateUseCases,
)
from backend.src.modules.alert_reports.infrastructure.models import (
    AlertReportTemplateModel, AlertReportTemplateVersionModel,
    CaseGeneratedReportModel,
)


router = APIRouter(prefix="/api/v1", tags=["alert_reports"])

ARRead = Depends(PermissionChecker("alert_reports", "read"))
ARGenerate = Depends(PermissionChecker("alert_reports", "generate"))
ARDelete = Depends(PermissionChecker("alert_reports", "delete"))
ARManageTpl = Depends(
    PermissionChecker("alert_reports", "manage_templates")
)
ARSetDefault = Depends(PermissionChecker("alert_reports", "set_default"))
ARViewVersions = Depends(
    PermissionChecker("alert_reports", "view_versions")
)


# ── Templates ─────────────────────────────────────────────────────────────

@router.get(
    "/alert-report-templates",
    response_model=SuccessResponse[list[dict]],
)
async def list_templates(
    db: DBSession,
    include_inactive: bool = Query(default=False),
    current_user: CurrentUser = ARRead,
):
    uc = AlertReportTemplateUseCases(db=db)
    templates = await uc.list_templates(
        actor=current_user,
        tenant_id=current_user.tenant_id,
        include_inactive=include_inactive,
    )
    return SuccessResponse.ok([_serialize_template(t) for t in templates])


@router.post(
    "/alert-report-templates",
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def create_template(
    body: TemplateCreate,
    db: DBSession,
    current_user: CurrentUser = ARManageTpl,
):
    uc = AlertReportTemplateUseCases(db=db)
    template = await uc.create_template(
        actor=current_user,
        name=body.name,
        code=body.code,
        header_config=body.header_config,
        footer_config=body.footer_config,
        blocks=body.blocks,
        description=body.description,
        css_overrides=body.css_overrides,
        tenant_id=body.tenant_id,
    )
    return SuccessResponse.ok(_serialize_template(template))


@router.get(
    "/alert-report-templates/{template_id}",
    response_model=SuccessResponse[dict],
)
async def get_template(
    template_id: str,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    uc = AlertReportTemplateUseCases(db=db)
    template = await uc.get_template(
        actor=current_user, template_id=template_id,
    )
    return SuccessResponse.ok(_serialize_template(template, detailed=True))


@router.patch(
    "/alert-report-templates/{template_id}",
    response_model=SuccessResponse[dict],
)
async def update_template(
    template_id: str,
    body: TemplateUpdate,
    db: DBSession,
    current_user: CurrentUser = ARManageTpl,
):
    uc = AlertReportTemplateUseCases(db=db)
    template = await uc.update_template(
        actor=current_user,
        template_id=template_id,
        name=body.name,
        description=body.description,
        header_config=body.header_config,
        footer_config=body.footer_config,
        blocks=body.blocks,
        css_overrides=body.css_overrides,
        change_summary=body.change_summary,
    )
    return SuccessResponse.ok(_serialize_template(template))


@router.delete(
    "/alert-report-templates/{template_id}", status_code=204,
)
async def delete_template(
    template_id: str,
    db: DBSession,
    current_user: CurrentUser = ARManageTpl,
):
    uc = AlertReportTemplateUseCases(db=db)
    await uc.soft_delete(actor=current_user, template_id=template_id)


@router.post(
    "/alert-report-templates/{template_id}/set-default",
    response_model=SuccessResponse[dict],
)
async def set_default(
    template_id: str,
    db: DBSession,
    current_user: CurrentUser = ARSetDefault,
):
    uc = AlertReportTemplateUseCases(db=db)
    template = await uc.set_as_default(
        actor=current_user, template_id=template_id,
    )
    return SuccessResponse.ok(_serialize_template(template))


@router.get(
    "/alert-report-templates/{template_id}/versions",
    response_model=SuccessResponse[list[dict]],
)
async def list_versions(
    template_id: str,
    db: DBSession,
    current_user: CurrentUser = ARViewVersions,
):
    uc = AlertReportTemplateUseCases(db=db)
    versions = await uc.list_versions(
        actor=current_user, template_id=template_id,
    )
    return SuccessResponse.ok([_serialize_version(v) for v in versions])


class PreviewBody(BaseModel):
    sample_case_id: str
    blocks_override: list[dict[str, Any]] | None = None
    header_override: dict[str, Any] | None = None
    footer_override: dict[str, Any] | None = None


@router.post("/alert-report-templates/{template_id}/preview")
async def preview_template(
    template_id: str,
    body: PreviewBody,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    """Returns a PDF buffer (StreamingResponse) — no persistence."""
    uc = AlertReportGenerationUseCases(db=db)
    pdf_bytes = await uc.preview_template(
        actor=current_user,
        template_id=template_id,
        sample_case_id=body.sample_case_id,
        blocks_override=body.blocks_override,
        header_override=body.header_override,
        footer_override=body.footer_override,
    )
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="preview_{template_id[:8]}.pdf"'
            ),
        },
    )


class CloneTemplateBody(BaseModel):
    target_tenant_id: str | None = None
    new_code: str
    new_name: str | None = None


@router.post(
    "/alert-report-templates/{template_id}/clone",
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def clone_template(
    template_id: str,
    body: CloneTemplateBody,
    db: DBSession,
    current_user: CurrentUser = ARManageTpl,
):
    uc = AlertReportTemplateUseCases(db=db)
    cloned = await uc.clone_template_for_tenant(
        actor=current_user,
        template_id=template_id,
        target_tenant_id=body.target_tenant_id,
        new_code=body.new_code,
        new_name=body.new_name,
    )
    return SuccessResponse.ok(_serialize_template(cloned))


# ── Generation ────────────────────────────────────────────────────────────

class GenerateReportBody(BaseModel):
    template_id: str | None = None
    n8n_run_id: str | None = None


@router.post(
    "/cases/{case_id}/alert-reports",
    response_model=SuccessResponse[dict],
    status_code=201,
)
async def generate_report(
    case_id: str,
    body: GenerateReportBody,
    db: DBSession,
    current_user: CurrentUser = ARGenerate,
):
    uc = AlertReportGenerationUseCases(db=db)
    report = await uc.generate_report(
        actor=current_user,
        case_id=case_id,
        template_id=body.template_id,
        n8n_run_id=body.n8n_run_id,
    )
    return SuccessResponse.ok(_serialize_report(report))


@router.get(
    "/cases/{case_id}/alert-reports",
    response_model=SuccessResponse[list[dict]],
)
async def list_reports_for_case(
    case_id: str,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    uc = AlertReportGenerationUseCases(db=db)
    reports = await uc.list_reports_for_case(
        actor=current_user, case_id=case_id,
    )
    return SuccessResponse.ok([_serialize_report(r) for r in reports])


@router.get(
    "/alert-reports/{report_id}",
    response_model=SuccessResponse[dict],
)
async def get_report(
    report_id: str,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    uc = AlertReportGenerationUseCases(db=db)
    report = await uc.get_report(
        actor=current_user, report_id=report_id,
    )
    return SuccessResponse.ok(
        _serialize_report(report, include_snapshot=True)
    )


@router.get("/alert-reports/{report_id}/download")
async def download_report(
    report_id: str,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    """Stream the PDF bytes inline."""
    uc = AlertReportGenerationUseCases(db=db)
    report = await uc.get_report(
        actor=current_user, report_id=report_id,
    )
    from backend.src.modules.attachments.infrastructure.models import (
        CaseAttachmentModel,
    )
    attachment = await db.get(CaseAttachmentModel, report.attachment_id)
    if not attachment:
        raise HTTPException(
            status_code=404, detail="PDF attachment missing"
        )
    pdf_bytes = await uc._read_attachment_bytes(attachment)
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{attachment.original_filename}"'
            ),
        },
    )


@router.get(
    "/alert-reports/{report_id}/verify",
    response_model=SuccessResponse[dict],
)
async def verify_report(
    report_id: str,
    db: DBSession,
    current_user: CurrentUser = ARRead,
):
    uc = AlertReportGenerationUseCases(db=db)
    result = await uc.verify_report_integrity(
        actor=current_user, report_id=report_id,
    )
    return SuccessResponse.ok(result)


class DeleteReportBody(BaseModel):
    reason: str


@router.delete("/alert-reports/{report_id}", status_code=204)
async def delete_report(
    report_id: str,
    body: DeleteReportBody,
    db: DBSession,
    current_user: CurrentUser = ARDelete,
):
    uc = AlertReportGenerationUseCases(db=db)
    await uc.delete_report(
        actor=current_user,
        report_id=report_id,
        reason=body.reason,
    )


# ── Serializers ───────────────────────────────────────────────────────────

def _serialize_template(
    t: AlertReportTemplateModel, detailed: bool = False
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": t.id,
        "tenant_id": t.tenant_id,
        "name": t.name,
        "code": t.code,
        "description": t.description,
        "current_version_number": t.current_version_number,
        "is_default": t.is_default,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }
    if detailed:
        out["current_version_id"] = t.current_version_id
    return out


def _serialize_version(
    v: AlertReportTemplateVersionModel,
) -> dict[str, Any]:
    return {
        "id": v.id,
        "template_id": v.template_id,
        "version": v.version,
        "name_snapshot": v.name_snapshot,
        "header_config": v.header_config,
        "footer_config": v.footer_config,
        "blocks": v.blocks,
        "css_overrides": v.css_overrides,
        "change_summary": v.change_summary,
        "created_by_user_id": v.created_by_user_id,
        "created_at": v.created_at.isoformat(),
    }


def _serialize_report(
    r: CaseGeneratedReportModel,
    include_snapshot: bool = False,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "case_id": r.case_id,
        "template_id": r.template_id,
        "template_version_id": r.template_version_id,
        "template_version_number": r.template_version_number,
        "generated_at": r.generated_at.isoformat(),
        "generated_by_user_id": r.generated_by_user_id,
        "generated_by_n8n_run_id": r.generated_by_n8n_run_id,
        "generated_via": r.generated_via,
        "attachment_id": r.attachment_id,
        "pdf_sha256": r.pdf_sha256,
        "pdf_size_bytes": r.pdf_size_bytes,
    }
    if include_snapshot:
        out["data_snapshot"] = r.data_snapshot
        out["generation_context"] = r.generation_context
    return out
