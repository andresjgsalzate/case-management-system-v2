"""Alert Reports use cases.

- Task 4: ``AlertReportTemplateUseCases`` — template CRUD + immutable
  versioning + default management.
- Task 8: ``AlertReportGenerationUseCases`` — end-to-end ``generate_report``
  orchestrating snapshot building (Task 5) + block rendering (Task 6) +
  PDF rendering (Task 7) + persistence (CaseAttachment + CaseGeneratedReport
  rows) + activity log + event publish.

The router (Task 13) calls into these two classes.
"""
import hashlib
import logging
import uuid as _uuid
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.events.base import BaseEvent
from backend.src.core.events.bus import event_bus as global_event_bus
from backend.src.core.exceptions import (
    BusinessRuleError, NotFoundError, PermissionDeniedError,
)
from backend.src.core.middleware.permission_checker import has_permission
from backend.src.modules.alert_reports.application.block_renderer import (
    BlockRenderer,
)
from backend.src.modules.alert_reports.application.blocks_catalog import (
    validate_blocks,
)
from backend.src.modules.alert_reports.application.pdf_generator import (
    html_to_pdf,
)
from backend.src.modules.alert_reports.application.snapshot_builder import (
    build_data_snapshot, is_snapshot_too_large, serialize_snapshot,
)
from backend.src.modules.alert_reports.infrastructure.models import (
    AlertReportTemplateModel, AlertReportTemplateVersionModel,
    CaseGeneratedReportModel,
)
from backend.src.modules.attachments.application.storage import (
    generate_stored_filename, save_file,
)
from backend.src.modules.attachments.infrastructure.models import (
    CaseAttachmentModel,
)

logger = logging.getLogger(__name__)


class AlertReportTemplateUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_template(
        self,
        *,
        actor,
        name: str,
        code: str,
        header_config: dict[str, Any],
        footer_config: dict[str, Any],
        blocks: list[dict[str, Any]],
        description: str | None = None,
        css_overrides: str | None = None,
        tenant_id: str | None = None,
    ) -> AlertReportTemplateModel:
        """Create a template + initial version (v1) atomically."""
        await self._require_perm(actor, "alert_reports", "manage_templates")

        # Validate blocks BEFORE touching the DB — typos shouldn't leave
        # a half-created template behind.
        validate_blocks(blocks)

        effective_tenant_id = self._resolve_template_tenant(actor, tenant_id)

        template = AlertReportTemplateModel(
            tenant_id=effective_tenant_id,
            name=name,
            code=code,
            description=description,
            created_by_user_id=actor.user_id,
        )
        self.db.add(template)
        await self.db.flush()  # need template.id for the v1 row

        version = AlertReportTemplateVersionModel(
            template_id=template.id,
            version=1,
            name_snapshot=name,
            header_config=header_config,
            footer_config=footer_config,
            blocks=blocks,
            css_overrides=css_overrides,
            created_by_user_id=actor.user_id,
            change_summary="Versión inicial",
        )
        self.db.add(version)
        await self.db.flush()

        template.current_version_id = version.id
        template.current_version_number = 1
        await self.db.commit()
        return template

    async def update_template(
        self,
        *,
        actor,
        template_id: str,
        name: str | None = None,
        description: str | None = None,
        header_config: dict[str, Any] | None = None,
        footer_config: dict[str, Any] | None = None,
        blocks: list[dict[str, Any]] | None = None,
        css_overrides: str | None = None,
        change_summary: str | None = None,
    ) -> AlertReportTemplateModel:
        """Edit a template — creates a NEW version row (immutable history).

        Returns early without inserting a new version if every snapshot
        field matches the current version (idempotent). Mutable display
        fields (``description``) can still be touched without versioning.
        """
        await self._require_perm(actor, "alert_reports", "manage_templates")
        template = await self._load_template_for_update(template_id)
        self._require_template_access(actor, template)

        current = await self._load_version(template.current_version_id)

        new_name = name if name is not None else current.name_snapshot
        new_header = (
            header_config if header_config is not None
            else current.header_config
        )
        new_footer = (
            footer_config if footer_config is not None
            else current.footer_config
        )
        new_blocks = blocks if blocks is not None else current.blocks
        new_css = (
            css_overrides if css_overrides is not None
            else current.css_overrides
        )

        if blocks is not None:
            validate_blocks(new_blocks)

        unchanged = (
            new_name == current.name_snapshot
            and new_header == current.header_config
            and new_footer == current.footer_config
            and new_blocks == current.blocks
            and new_css == current.css_overrides
        )

        if unchanged:
            if description is not None:
                template.description = description
                await self.db.commit()
            return template

        new_version_number = template.current_version_number + 1
        new_version = AlertReportTemplateVersionModel(
            template_id=template.id,
            version=new_version_number,
            name_snapshot=new_name,
            header_config=new_header,
            footer_config=new_footer,
            blocks=new_blocks,
            css_overrides=new_css,
            created_by_user_id=actor.user_id,
            change_summary=(
                change_summary or f"Versión {new_version_number}"
            ),
        )
        self.db.add(new_version)
        await self.db.flush()

        template.name = new_name
        if description is not None:
            template.description = description
        template.current_version_id = new_version.id
        template.current_version_number = new_version_number
        await self.db.commit()
        return template

    async def list_templates(
        self,
        *,
        actor,
        tenant_id: str | None = None,
        include_inactive: bool = False,
    ) -> list[AlertReportTemplateModel]:
        """List templates visible to a tenant + global rows."""
        await self._require_perm(actor, "alert_reports", "read")

        effective = tenant_id or actor.tenant_id
        stmt = select(AlertReportTemplateModel).where(
            (AlertReportTemplateModel.tenant_id == effective)
            | (AlertReportTemplateModel.tenant_id.is_(None))
        )
        if not include_inactive:
            stmt = stmt.where(
                AlertReportTemplateModel.is_active.is_(True)
            )
        stmt = stmt.order_by(
            AlertReportTemplateModel.is_default.desc(),
            AlertReportTemplateModel.name.asc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_template(
        self, *, actor, template_id: str
    ) -> AlertReportTemplateModel:
        await self._require_perm(actor, "alert_reports", "read")
        template = await self.db.get(AlertReportTemplateModel, template_id)
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        self._require_template_access(actor, template)
        return template

    async def list_versions(
        self, *, actor, template_id: str
    ) -> list[AlertReportTemplateVersionModel]:
        await self._require_perm(actor, "alert_reports", "view_versions")
        result = await self.db.execute(
            select(AlertReportTemplateVersionModel)
            .where(
                AlertReportTemplateVersionModel.template_id == template_id
            )
            .order_by(
                AlertReportTemplateVersionModel.version.desc()
            )
        )
        return list(result.scalars().all())

    async def set_as_default(
        self, *, actor, template_id: str
    ) -> AlertReportTemplateModel:
        """Atomically swap which template is the tenant default."""
        await self._require_perm(actor, "alert_reports", "set_default")
        template = await self._load_template_for_update(template_id)
        self._require_template_access(actor, template)

        await self.db.execute(
            update(AlertReportTemplateModel)
            .where(
                AlertReportTemplateModel.tenant_id == template.tenant_id,
                AlertReportTemplateModel.is_default.is_(True),
            )
            .values(is_default=False)
        )
        template.is_default = True
        await self.db.commit()
        return template

    async def soft_delete(
        self, *, actor, template_id: str
    ) -> None:
        """Soft-delete (``is_active=False``) — historical reports survive."""
        await self._require_perm(actor, "alert_reports", "manage_templates")
        template = await self._load_template_for_update(template_id)
        self._require_template_access(actor, template)
        if template.is_default:
            raise BusinessRuleError(
                "No se puede eliminar la plantilla default — "
                "designe otra como default primero"
            )
        template.is_active = False
        await self.db.commit()

    # ── helpers ────────────────────────────────────────────────────────

    async def _require_perm(
        self, actor, module: str, action: str
    ) -> None:
        if not await has_permission(
            self.db, actor.role_id, module, action
        ):
            raise PermissionDeniedError(
                f"Permission denied: {module}.{action}"
            )

    def _resolve_template_tenant(
        self, actor, tenant_id: str | None
    ) -> str | None:
        """Determine which tenant a new template belongs to.

        Platform-level admins (``is_global`` role) can pass an explicit
        ``tenant_id`` or ``None`` (global template). Tenant-scoped admins
        always create templates within their own tenant — any explicit
        ``tenant_id`` other than their own is rejected.
        """
        is_global = bool(getattr(actor, "is_global", False))
        if is_global:
            return tenant_id
        if tenant_id is not None and tenant_id != actor.tenant_id:
            raise PermissionDeniedError(
                "Sólo administradores globales pueden crear plantillas "
                "fuera de su tenant"
            )
        return actor.tenant_id

    def _require_template_access(
        self, actor, template: AlertReportTemplateModel
    ) -> None:
        if template.tenant_id is None:
            return  # global templates visible/editable per perm only
        if bool(getattr(actor, "is_global", False)):
            return
        if template.tenant_id != actor.tenant_id:
            raise PermissionDeniedError(
                "Plantilla pertenece a otro tenant"
            )

    async def _load_template_for_update(
        self, template_id: str
    ) -> AlertReportTemplateModel:
        result = await self.db.execute(
            select(AlertReportTemplateModel)
            .where(AlertReportTemplateModel.id == template_id)
            .with_for_update()
        )
        template = result.scalar_one_or_none()
        if not template:
            raise NotFoundError(f"Template {template_id} not found")
        return template

    async def _load_version(
        self, version_id: str | None
    ) -> AlertReportTemplateVersionModel:
        if not version_id:
            raise BusinessRuleError(
                "Template has no current version pointer set"
            )
        version = await self.db.get(
            AlertReportTemplateVersionModel, version_id
        )
        if not version:
            raise NotFoundError(
                f"Template version {version_id} not found"
            )
        return version


# ──────────────────────────────────────────────────────────────────────────
# Task 8 — generate_report end-to-end
# ──────────────────────────────────────────────────────────────────────────


class AlertReportGenerationUseCases:
    """Orchestrates template resolution → snapshot → render → PDF → persist.

    A single ``generate_report`` call produces:
    - a ``CaseAttachmentModel`` row holding the PDF on disk
    - a ``CaseGeneratedReportModel`` row with the immutable
      ``data_snapshot`` and ``pdf_sha256`` (chain of custody)
    - an ``ActivityEntryModel`` row in the case timeline
    - an ``alert_report.generated`` event published on the global event bus
      for any downstream listener (SSE, notifications, etc.)

    System user fallback: when ``actor`` is None (n8n flow) the attachment
    row needs SOMETHING in its non-nullable ``user_id`` FK column.
    ``system_user_id`` provides a pre-seeded service-account user id —
    same pattern as ``n8n_bridge``'s ``_action_attach_artifact``.
    """

    def __init__(
        self,
        db: AsyncSession,
        *,
        system_user_id: str | None = None,
        upload_dir: str = "uploads",
        event_bus=None,
    ):
        self.db = db
        self.system_user_id = system_user_id
        self.upload_dir = upload_dir
        self.event_bus = event_bus or global_event_bus
        self.renderer = BlockRenderer()

    async def generate_report(
        self,
        *,
        actor,
        case_id: str,
        template_id: str | None = None,
        n8n_run_id: str | None = None,
    ) -> CaseGeneratedReportModel:
        """Produce a PDF report + persist all the audit-trail rows."""
        if actor is not None:
            if not await has_permission(
                self.db, actor.role_id, "alert_reports", "generate"
            ):
                raise PermissionDeniedError(
                    "Permission denied: alert_reports.generate"
                )

        case = await self._load_case(case_id)
        if actor is not None:
            self._require_case_access(actor, case)

        template, version = await self._resolve_template(
            tenant_id=case.tenant_id,
            template_id=template_id,
        )

        # Build snapshot + render HTML + render PDF
        snapshot = await build_data_snapshot(self.db, case)
        html = self.renderer.render(
            blocks=version.blocks,
            snapshot=snapshot,
            header_config=version.header_config,
            footer_config=version.footer_config,
        )
        pdf_bytes = await html_to_pdf(
            html=html,
            header_config=version.header_config,
            footer_config=version.footer_config,
            snapshot=snapshot,
            css_overrides=version.css_overrides,
        )

        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        actor_id = (
            actor.user_id if actor is not None else self.system_user_id
        )
        filename = self._build_pdf_filename(case, snapshot, version)

        attachment = await self._persist_pdf_attachment(
            pdf_bytes=pdf_bytes,
            filename=filename,
            case=case,
            actor_id=actor_id,
        )

        # Snapshot overflow: persist full snapshot as JSON attachment and
        # store a stub on the report itself.
        persisted_snapshot: dict[str, Any]
        if is_snapshot_too_large(snapshot):
            snap_attachment = await self._persist_snapshot_overflow(
                snapshot=snapshot, case=case, actor_id=actor_id,
            )
            persisted_snapshot = {
                "truncated": True,
                "snapshot_attachment_id": snap_attachment.id,
                "case_summary": snapshot.get("case", {}),
            }
        else:
            persisted_snapshot = snapshot

        report = CaseGeneratedReportModel(
            tenant_id=case.tenant_id,
            case_id=case.id,
            template_id=template.id,
            template_version_id=version.id,
            template_version_number=version.version,
            generated_by_user_id=actor.user_id if actor is not None else None,
            generated_by_n8n_run_id=n8n_run_id,
            generated_via="manual_ui" if actor is not None else "n8n_api",
            attachment_id=attachment.id,
            pdf_sha256=pdf_sha256,
            pdf_size_bytes=len(pdf_bytes),
            data_snapshot=persisted_snapshot,
            generation_context={
                "renderer_locale": "es",
            },
        )
        self.db.add(report)
        await self.db.flush()

        await self._log_activity(
            case=case, actor_id=actor_id,
            report=report, version=version, pdf_size=len(pdf_bytes),
            pdf_sha256=pdf_sha256,
        )

        try:
            await self.event_bus.publish(BaseEvent(
                event_name="alert_report.generated",
                tenant_id=case.tenant_id,
                actor_id=actor_id or "",
                payload={
                    "report_id": report.id,
                    "case_id": case.id,
                    "tenant_id": case.tenant_id,
                    "generated_via": report.generated_via,
                    "pdf_sha256": pdf_sha256,
                },
            ))
        except Exception as e:
            logger.warning(
                "event_bus.publish failed for alert_report.generated: %s",
                e,
            )

        await self.db.commit()
        return report

    # ── template resolution ────────────────────────────────────────────

    async def _resolve_template(
        self,
        *,
        tenant_id: str,
        template_id: str | None,
        current_version_id_resolver=None,
    ) -> tuple[AlertReportTemplateModel, AlertReportTemplateVersionModel]:
        """Pick which template + version to render with.

        Priority:
        1. Explicit ``template_id`` supplied by the caller.
        2. Tenant default (``tenant_id=tenant_id AND is_default=true``).
        3. Global default (``tenant_id IS NULL AND is_default=true``).
        4. ``BusinessRuleError`` — no default anywhere.

        The ``current_version_id_resolver`` parameter exists only so the
        unit tests can mock the version lookup; production callers leave
        it ``None`` and the method falls back to ``self.db.get(...)``.
        """
        template: AlertReportTemplateModel | None = None
        if template_id is not None:
            template = await self.db.get(
                AlertReportTemplateModel, template_id
            )
            if not template:
                raise NotFoundError(f"Template {template_id} not found")
        else:
            stmt_tenant = (
                select(AlertReportTemplateModel)
                .where(
                    AlertReportTemplateModel.tenant_id == tenant_id,
                    AlertReportTemplateModel.is_default.is_(True),
                    AlertReportTemplateModel.is_active.is_(True),
                )
                .limit(1)
            )
            template = (
                await self.db.execute(stmt_tenant)
            ).scalar_one_or_none()
            if template is None:
                stmt_global = (
                    select(AlertReportTemplateModel)
                    .where(
                        AlertReportTemplateModel.tenant_id.is_(None),
                        AlertReportTemplateModel.is_default.is_(True),
                        AlertReportTemplateModel.is_active.is_(True),
                    )
                    .limit(1)
                )
                template = (
                    await self.db.execute(stmt_global)
                ).scalar_one_or_none()

        if template is None:
            raise BusinessRuleError(
                "No default alert_report template configured for this "
                "tenant nor globally. Set one via /alert-report-templates."
            )

        version = await self.db.get(
            AlertReportTemplateVersionModel, template.current_version_id
        )
        if version is None:
            raise BusinessRuleError(
                f"Template {template.id} has no current_version_id set"
            )
        return template, version

    # ── persistence helpers ────────────────────────────────────────────

    async def _persist_pdf_attachment(
        self, *, pdf_bytes: bytes, filename: str, case, actor_id: str | None
    ) -> CaseAttachmentModel:
        stored = generate_stored_filename(filename)
        file_path = await save_file(
            pdf_bytes, stored, case.id, self.upload_dir
        )
        attachment = CaseAttachmentModel(
            id=str(_uuid.uuid4()),
            case_id=case.id,
            user_id=actor_id or self.system_user_id or "alert_report_system",
            tenant_id=case.tenant_id,
            original_filename=filename,
            stored_filename=stored,
            file_path=file_path,
            mime_type="application/pdf",
            file_size=len(pdf_bytes),
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment

    async def _persist_snapshot_overflow(
        self, *, snapshot: dict, case, actor_id: str | None
    ) -> CaseAttachmentModel:
        payload = serialize_snapshot(snapshot)
        filename = f"snapshot_{case.id}.json"
        stored = generate_stored_filename(filename)
        file_path = await save_file(
            payload, stored, case.id, self.upload_dir
        )
        attachment = CaseAttachmentModel(
            id=str(_uuid.uuid4()),
            case_id=case.id,
            user_id=actor_id or self.system_user_id or "alert_report_system",
            tenant_id=case.tenant_id,
            original_filename=filename,
            stored_filename=stored,
            file_path=file_path,
            mime_type="application/json",
            file_size=len(payload),
        )
        self.db.add(attachment)
        await self.db.flush()
        return attachment

    # ── activity log ───────────────────────────────────────────────────

    async def _log_activity(
        self,
        *,
        case,
        actor_id: str | None,
        report: CaseGeneratedReportModel,
        version: AlertReportTemplateVersionModel,
        pdf_size: int,
        pdf_sha256: str,
    ) -> None:
        """Persist an ActivityEntryModel row directly.

        We don't go through ``event_bus`` for the activity log because the
        repo's activity handler subscribes to a fixed list of event names
        (see ``activity/application/handlers.py``) and ``alert_report.generated``
        is not on that list. Direct insert is simpler than wiring a new
        subscription just for this one event.
        """
        from backend.src.modules.activity.infrastructure.models import (
            ActivityEntryModel,
        )
        entry = ActivityEntryModel(
            id=str(_uuid.uuid4()),
            case_id=case.id,
            tenant_id=case.tenant_id,
            actor_id=actor_id,
            event_type="alert_report.generated",
            description=(
                f"Reporte generado con plantilla '{version.name_snapshot}' "
                f"v{version.version}"
            ),
            payload={
                "report_id": report.id,
                "template_id": report.template_id,
                "template_version_id": report.template_version_id,
                "template_version": version.version,
                "pdf_sha256": pdf_sha256,
                "size_bytes": pdf_size,
                "generated_via": report.generated_via,
            },
        )
        self.db.add(entry)
        await self.db.flush()

    # ── case access ────────────────────────────────────────────────────

    async def _load_case(self, case_id: str):
        from backend.src.modules.cases.infrastructure.models import (
            CaseModel,
        )
        case = await self.db.get(CaseModel, case_id)
        if not case:
            raise NotFoundError(f"Case {case_id} not found")
        return case

    def _require_case_access(self, actor, case) -> None:
        if bool(getattr(actor, "is_global", False)):
            return
        if actor.tenant_id != case.tenant_id:
            raise PermissionDeniedError(
                "Caso pertenece a otro tenant"
            )

    @staticmethod
    def _build_pdf_filename(case, snapshot: dict, version) -> str:
        case_number = (
            snapshot.get("case", {}).get("case_number")
            or getattr(case, "case_number", None)
            or case.id[:8]
        )
        # Keep filename safe across filesystems — strip anything that
        # could break Windows/Linux path rules.
        safe = "".join(
            c if c.isalnum() or c in ("-", "_", ".") else "_"
            for c in case_number
        )
        return f"alert_report_{safe}_v{version.version}.pdf"
