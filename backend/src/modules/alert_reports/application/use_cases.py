"""Alert Reports use cases — Template CRUD + versioning (Task 4).

Future tasks extend this module: snapshot building (Task 5), block
rendering (Task 6), PDF generation (Task 7), the end-to-end
``generate_report`` (Task 8), verify/delete (Task 9), preview (Task 10).
This file owns the surface API that the router (Task 13) calls.
"""
import logging
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError, NotFoundError, PermissionDeniedError,
)
from backend.src.core.middleware.permission_checker import has_permission
from backend.src.modules.alert_reports.application.blocks_catalog import (
    validate_blocks,
)
from backend.src.modules.alert_reports.infrastructure.models import (
    AlertReportTemplateModel, AlertReportTemplateVersionModel,
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
