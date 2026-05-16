"""Use cases for the n8n_bridge module (Sub-spec 05).

Phase 1 scope: trigger_workflow (CMS → n8n). Callback dispatch and approval
flow land in Tasks 5-12.
"""
import hashlib
import hmac
import json
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import BusinessRuleError, NotFoundError
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.integrations.application.crypto import decrypt_secret
from backend.src.modules.integrations.infrastructure.models import (
    IntegrationSourceModel,
)
from backend.src.modules.n8n_bridge.application.jwt_helper import (
    issue_callback_jwt,
)
from backend.src.modules.n8n_bridge.infrastructure.models import (
    PlaybookRunModel,
)


CALLBACK_JWT_TTL_SECONDS = 3600
HTTP_TIMEOUT_SECONDS = 10.0


class N8nBridgeUseCases:
    def __init__(
        self,
        db: AsyncSession,
        cms_base_url: str = "http://localhost:8000",
    ):
        self.db = db
        self.cms_base_url = cms_base_url.rstrip("/")

    # ── trigger_workflow (Task 4) ────────────────────────────────────

    async def trigger_workflow(
        self,
        *,
        case_id: str,
        workflow_url: str,
        triggered_by: str = "automation_rule",
        triggered_by_user: str | None = None,
        extra_context: dict | None = None,
    ) -> PlaybookRunModel:
        """POST a signed payload to `workflow_url` and persist a PlaybookRun.

        On HTTP error, marks run.status='failed' and raises BusinessRuleError
        so the caller (Sub-spec 04 process_event, automation rule, manual UI)
        can decide how to surface the failure.
        """
        case = await self._load_case(case_id)
        run = PlaybookRunModel(
            tenant_id=case.tenant_id,
            case_id=case.id,
            workflow_url=workflow_url,
            workflow_id=self._extract_workflow_id_from_url(workflow_url),
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
            status="triggered",
            trigger_payload={},
        )
        self.db.add(run)
        await self.db.flush()  # need run.id for payload + headers

        trigger_payload = self._build_trigger_payload(
            case=case, run=run,
            triggered_by=triggered_by,
            triggered_by_user=triggered_by_user,
            extra_context=extra_context,
        )
        run.trigger_payload = trigger_payload

        source = await self._get_n8n_source(case.tenant_id)
        secret = decrypt_secret(source.auth_secret_encrypted)

        body = json.dumps(
            trigger_payload, separators=(",", ":"), default=str,
        ).encode("utf-8")
        signature = hmac.new(
            secret.encode(), body, hashlib.sha256,
        ).hexdigest()

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(HTTP_TIMEOUT_SECONDS),
            ) as client:
                r = await client.post(
                    workflow_url,
                    content=body,
                    headers={
                        "Content-Type": "application/json",
                        "X-CMS-Signature": f"sha256={signature}",
                        "X-CMS-Playbook-Run-Id": run.id,
                    },
                )
                r.raise_for_status()
                resp = r.json() if r.content else {}
                run.n8n_execution_id = (
                    resp.get("executionId") or resp.get("execution_id")
                )
        except httpx.HTTPError as e:
            run.status = "failed"
            run.error = f"{type(e).__name__}: {str(e)[:500]}"
            await self.db.commit()
            raise BusinessRuleError(
                f"Failed to trigger n8n workflow: {e}",
            ) from e

        await self.db.commit()
        await self.db.refresh(run)
        return run

    # ── Helpers ──────────────────────────────────────────────────────

    async def _load_case(self, case_id: str) -> CaseModel:
        case = await self.db.get(CaseModel, case_id)
        if case is None:
            raise NotFoundError(f"case {case_id} not found")
        return case

    async def _get_n8n_source(self, tenant_id: str) -> IntegrationSourceModel:
        """Locate the tenant's n8n integration_source (auto_method='hmac')."""
        stmt = (
            select(IntegrationSourceModel)
            .where(
                IntegrationSourceModel.tenant_id == tenant_id,
                IntegrationSourceModel.source_type == "n8n",
                IntegrationSourceModel.is_active.is_(True),
            )
            .limit(1)
        )
        source = (await self.db.execute(stmt)).scalar_one_or_none()
        if source is None:
            raise BusinessRuleError(
                f"No active n8n integration_source for tenant {tenant_id}",
            )
        return source

    def _extract_workflow_id_from_url(self, url: str) -> str | None:
        """Best-effort extract: take the last path segment (n8n webhook IDs)."""
        try:
            return url.rstrip("/").rsplit("/", 1)[-1] or None
        except Exception:
            return None

    def _build_trigger_payload(
        self,
        *,
        case: CaseModel,
        run: PlaybookRunModel,
        triggered_by: str,
        triggered_by_user: str | None,
        extra_context: dict | None,
    ) -> dict[str, Any]:
        """Minimal payload n8n needs to act on the case and call back.

        Keeps fields shallow (no relations loaded inline) so we don't need
        eager loading on `case`. Workflows that need deeper data fetch via
        `details_url`.
        """
        return {
            "case_id": case.id,
            "case_number": case.case_number,
            "case_type": case.case_type,
            "tenant_id": case.tenant_id,
            "title": case.title,
            "priority_id": case.priority_id,
            "taxonomy_id": getattr(case, "taxonomy_id", None),
            "status_id": case.status_id,
            "created_at": case.created_at.isoformat() if case.created_at else None,
            "details_url": f"{self.cms_base_url}/api/v1/cases/{case.id}",
            "callback_jwt": issue_callback_jwt(
                case_id=case.id, ttl_seconds=CALLBACK_JWT_TTL_SECONDS,
            ),
            "callback_url": (
                f"{self.cms_base_url}/api/v1/integrations/callbacks/n8n"
            ),
            "playbook_run_id": run.id,
            "context": {
                "triggered_by": triggered_by,
                "triggered_by_user": triggered_by_user,
                **(extra_context or {}),
            },
        }
