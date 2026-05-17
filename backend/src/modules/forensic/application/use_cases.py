"""Forensic use cases — READ operations + ``launch_hunt`` happy path.

Destructive-hunt governance (Task 9) and ``cancel_hunt`` (Task 10) extend
this same class. Keep the surface API stable so the router (Task 14) can
depend on it incrementally.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError, NotFoundError, OperationalError, PermissionDeniedError,
)
from backend.src.core.middleware.permission_checker import has_permission
from backend.src.modules.forensic.application.dtos import ClientSummary
from backend.src.modules.forensic.infrastructure.models import (
    ForensicArtifactModel, ForensicHuntModel,
)
from backend.src.modules.forensic.infrastructure.velo_client import (
    get_velo_client,
)
from backend.src.modules.tenants.infrastructure.models import TenantModel

logger = logging.getLogger(__name__)


class ForensicUseCases:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_artifacts(
        self,
        *,
        tenant_id: str,
        featured_only: bool = False,
        category: str | None = None,
        os: str | None = None,
        search: str | None = None,
        include_destructive: bool = False,
    ) -> list[ForensicArtifactModel]:
        """List artifacts visible to a tenant.

        Tenant scoping: rows with ``tenant_id == tenant_id`` OR ``tenant_id IS NULL``
        (the latter are "global" artifacts available to every tenant).

        Destructive artifacts are hidden unless ``include_destructive=True`` — the
        UI Hunt Launcher uses this flag so destructive operations are only
        surfaced through the n8n + approval flow, never the direct path.
        """
        stmt = select(ForensicArtifactModel).where(
            or_(
                ForensicArtifactModel.tenant_id == tenant_id,
                ForensicArtifactModel.tenant_id.is_(None),
            ),
            ForensicArtifactModel.is_active.is_(True),
        )
        if featured_only:
            stmt = stmt.where(ForensicArtifactModel.is_featured.is_(True))
        if category:
            stmt = stmt.where(ForensicArtifactModel.category == category)
        if os:
            stmt = stmt.where(ForensicArtifactModel.supported_os.contains([os]))
        if search:
            stmt = stmt.where(
                or_(
                    ForensicArtifactModel.name.ilike(f"%{search}%"),
                    ForensicArtifactModel.description.ilike(f"%{search}%"),
                )
            )
        if not include_destructive:
            stmt = stmt.where(ForensicArtifactModel.is_destructive.is_(False))

        stmt = stmt.order_by(
            ForensicArtifactModel.is_featured.desc(),
            ForensicArtifactModel.name.asc(),
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_clients(
        self,
        *,
        tenant_id: str,
        search: str | None = None,
        limit: int = 100,
    ) -> list[ClientSummary]:
        """List Velociraptor clients for a tenant (proxied to Velo)."""
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant:
            raise NotFoundError(f"Tenant {tenant_id} not found")
        if not tenant.velo_org_id:
            raise BusinessRuleError(
                "Tenant has no Velociraptor org configured "
                "(velo_org_id is NULL)"
            )

        velo_client = get_velo_client()
        clients = await velo_client.list_clients(
            org_id=tenant.velo_org_id, label=None, limit=limit
        )

        if search:
            needle = search.lower()
            clients = [
                c for c in clients
                if needle in (c.get("hostname") or "").lower()
            ]
        return [ClientSummary(**c) for c in clients]

    async def launch_hunt(
        self,
        *,
        actor,
        case_id: str | None,
        artifact_id: str,
        parameters: dict,
        target_clients: list[str],
        timeout_seconds: int | None = None,
        n8n_run_id: str | None = None,
        approval_request_id: str | None = None,
    ) -> ForensicHuntModel:
        """Central launch entry point.

        Permission + governance checks are performed here. Destructive
        artifacts have additional governance — see ``_enforce_destructive_governance``
        (Task 9). The hunt row is flushed with ``status='pending'`` before
        the Velociraptor round-trip so a Velo failure leaves an auditable
        ``status='failed'`` row behind.
        """
        artifact = await self._load_artifact(artifact_id)
        if not artifact.is_active:
            raise BusinessRuleError(f"Artifact '{artifact.name}' inactive")

        tenant_id = await self._resolve_tenant_id(case_id, actor)
        tenant = await self.db.get(TenantModel, tenant_id)
        if not tenant or not tenant.velo_org_id:
            raise BusinessRuleError(
                "Tenant has no Velociraptor org configured"
            )

        if artifact.is_destructive:
            await self._enforce_destructive_governance(
                n8n_run_id=n8n_run_id,
                approval_request_id=approval_request_id,
                case_id=case_id,
                artifact=artifact,
            )
        elif actor is not None:
            action = (
                "launch_evidence"
                if artifact.requires_evidence_handling
                else "launch_ro"
            )
            await self._require_perm(actor, "forensic", action)

        timeout_at = datetime.now(timezone.utc) + timedelta(
            seconds=timeout_seconds or artifact.default_timeout_seconds
        )

        hunt = ForensicHuntModel(
            tenant_id=tenant_id,
            case_id=case_id,
            artifact_id=artifact.id,
            artifact_name=artifact.name,
            parameters=self._merge_parameters(
                artifact.parameters_schema, parameters
            ),
            target_clients=target_clients,
            target_label=self._build_target_label(target_clients),
            velo_org_id=tenant.velo_org_id,
            status="pending",
            timeout_at=timeout_at,
            launched_by_user_id=actor.user_id if actor else None,
            launched_by_n8n_run_id=n8n_run_id,
            launched_via=self._infer_launched_via(actor, n8n_run_id),
            approval_request_id=approval_request_id,
        )
        self.db.add(hunt)
        await self.db.flush()

        velo_client = get_velo_client()
        try:
            hunt.status = "starting"
            velo_hunt_id = await velo_client.create_hunt(
                org_id=tenant.velo_org_id,
                artifact_name=artifact.name,
                parameters=hunt.parameters,
                client_ids=target_clients if "*" not in target_clients else None,
                labels=None if "*" not in target_clients else ["all"],
                description=f"CMS hunt {hunt.id} (case={case_id or 'none'})",
            )
            hunt.velo_hunt_id = velo_hunt_id
            hunt.status = "running"
        except Exception as e:
            hunt.status = "failed"
            hunt.error = f"{type(e).__name__}: {str(e)[:500]}"
            await self.db.commit()
            raise OperationalError(
                f"Failed to create hunt in Velociraptor: {e}"
            ) from e

        await self.db.commit()
        return hunt

    # ── helpers ────────────────────────────────────────────────────────

    async def _load_artifact(self, artifact_id: str) -> ForensicArtifactModel:
        artifact = await self.db.get(ForensicArtifactModel, artifact_id)
        if not artifact:
            raise NotFoundError(f"Artifact {artifact_id} not found")
        return artifact

    async def _resolve_tenant_id(
        self, case_id: str | None, actor
    ) -> str:
        if case_id:
            from backend.src.modules.cases.infrastructure.models import (
                CaseModel,
            )
            case = await self.db.get(CaseModel, case_id)
            if case:
                return case.tenant_id
        if actor and getattr(actor, "tenant_id", None):
            return actor.tenant_id
        raise BusinessRuleError(
            "Cannot resolve tenant_id (no case_id, no actor.tenant_id)"
        )

    async def _require_perm(self, actor, module: str, action: str) -> None:
        if not await has_permission(
            self.db, actor.role_id, module, action
        ):
            raise PermissionDeniedError(
                f"Permission denied: {module}.{action}"
            )

    def _merge_parameters(
        self, schema: list[dict] | None, supplied: dict
    ) -> dict:
        """Apply defaults from the artifact schema for keys the operator omitted."""
        merged = dict(supplied)
        for param in (schema or []):
            key = param.get("name")
            if key and key not in merged and "default" in param:
                merged[key] = param["default"]
        return merged

    def _build_target_label(self, target_clients: list[str]) -> str:
        if "*" in target_clients:
            return "Toda la organización"
        if len(target_clients) == 1:
            return target_clients[0]
        return f"{target_clients[0]} + {len(target_clients) - 1} hosts"

    def _infer_launched_via(self, actor, n8n_run_id: str | None) -> str:
        if actor is not None and n8n_run_id is None:
            return "ui_direct"
        if actor is not None and n8n_run_id is not None:
            return "ui_via_n8n"
        if actor is None and n8n_run_id is not None:
            return "automation_n8n"
        raise BusinessRuleError("Cannot determine launched_via")

    async def _enforce_destructive_governance(
        self,
        *,
        n8n_run_id: str | None,
        approval_request_id: str | None,
        case_id: str | None,
        artifact: ForensicArtifactModel,
    ) -> None:
        """Gate destructive hunts behind n8n + approved approval_request.

        A destructive artifact (``is_destructive=True``) can only be launched
        when ALL of the following hold:
        - ``n8n_run_id`` is set (no direct UI path).
        - ``approval_request_id`` is set and resolves to an ``ApprovalRequest``.
        - That approval is in status ``'approved'``.
        - The approval's ``case_id`` matches the hunt's ``case_id`` (if any).
        """
        if n8n_run_id is None:
            raise PermissionDeniedError(
                f"Destructive artifact '{artifact.name}' must be launched "
                f"via an n8n workflow with approval. Direct UI launch denied."
            )
        if approval_request_id is None:
            raise PermissionDeniedError(
                "Destructive hunt requires an approved approval_request_id"
            )

        from backend.src.modules.n8n_bridge.infrastructure.models import (
            ApprovalRequestModel,
        )
        approval = await self.db.get(
            ApprovalRequestModel, approval_request_id
        )
        if not approval:
            raise PermissionDeniedError(
                f"Approval request {approval_request_id} not found"
            )
        if approval.status != "approved":
            raise PermissionDeniedError(
                f"Approval {approval_request_id} "
                f"status='{approval.status}', not 'approved'"
            )
        if case_id and approval.case_id != case_id:
            raise PermissionDeniedError(
                f"Approval {approval_request_id} not for case {case_id}"
            )
