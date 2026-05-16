"""Use cases for the n8n_bridge module (Sub-spec 05).

Phase 1 scope: trigger_workflow (CMS → n8n). Callback dispatch and approval
flow land in Tasks 5-12.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.core.exceptions import (
    BusinessRuleError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from backend.src.modules.cases.infrastructure.models import CaseModel
from backend.src.modules.integrations.application.crypto import (
    decrypt_secret,
    encrypt_secret,
)
from backend.src.modules.integrations.infrastructure.models import (
    IntegrationSourceModel,
)
from backend.src.modules.n8n_bridge.application.jwt_helper import (
    issue_callback_jwt,
    validate_callback_jwt,
)
from backend.src.modules.n8n_bridge.infrastructure.models import (
    ApprovalRequestModel,
    PlaybookRunCallbackModel,
    PlaybookRunModel,
)


CALLBACK_JWT_TTL_SECONDS = 3600
HTTP_TIMEOUT_SECONDS = 10.0


class N8nBridgeUseCases:
    def __init__(
        self,
        db: AsyncSession,
        cms_base_url: str = "http://localhost:8000",
        system_user_id: str | None = None,
    ):
        self.db = db
        self.cms_base_url = cms_base_url.rstrip("/")
        # User attributed to actions n8n performs (case_notes.user_id, etc.).
        # Phase 1 default is None; router wires this from env at request time.
        self.system_user_id = system_user_id

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

    # ── approve_or_reject (Task 10) ──────────────────────────────────

    _RESUME_HTTP_TIMEOUT = 10.0
    _ALLOWED_DECISIONS_APPROVAL = frozenset({"approved", "rejected"})

    async def approve_or_reject(
        self,
        *,
        approval_id: str,
        decision: str,
        approver_user_id: str,
        approver_name: str | None = None,
        reason: str | None = None,
    ) -> dict:
        """Operator decides on a pending approval; CMS POSTs to n8n's resume_url.

        Decision is persisted FIRST (atomic with state transition), then the
        POST to resume_url is attempted. If httpx fails, the decision still
        sticks but resume_succeeded=false + resume_error is stamped, and
        BusinessRuleError is raised so the UI can show a "n8n unreachable,
        retry resume" banner.
        """
        if decision not in self._ALLOWED_DECISIONS_APPROVAL:
            raise ValidationError(
                f"decision must be 'approved' or 'rejected', got {decision!r}",
            )
        if decision == "rejected" and not reason:
            raise ValidationError("rejection requires a reason")

        approval = await self._load_approval_for_update(approval_id)
        if approval is None:
            raise NotFoundError(f"approval_request {approval_id} not found")
        if approval.status != "pending":
            raise ValidationError(
                f"approval already decided (status={approval.status!r})",
            )

        # Mutate decision state and commit BEFORE attempting the resume POST,
        # so an httpx failure doesn't leave the approval in 'pending' limbo.
        now = datetime.now(timezone.utc)
        approval.status = decision
        approval.approver_user_id = approver_user_id
        approval.decided_reason = reason
        approval.decided_at = now
        await self.db.commit()
        await self.db.refresh(approval)

        # Build resume payload
        resume_payload = {
            "decision": decision,
            "approval_request_id": approval.id,
            "case_id": approval.case_id,
            "playbook_run_id": approval.playbook_run_id,
            "approver_user_id": approver_user_id,
            "approver_name": approver_name,
            "decided_at": now.isoformat(),
            "reason": reason,
        }
        body = json.dumps(
            resume_payload, separators=(",", ":"), default=str,
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        if approval.resume_hmac_secret_encrypted:
            resume_secret = decrypt_secret(approval.resume_hmac_secret_encrypted)
            sig = hmac.new(
                resume_secret.encode(), body, hashlib.sha256,
            ).hexdigest()
            headers["X-CMS-Signature"] = f"sha256={sig}"

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self._RESUME_HTTP_TIMEOUT),
            ) as client:
                r = await client.post(
                    approval.resume_url, content=body, headers=headers,
                )
                r.raise_for_status()
        except httpx.HTTPError as e:
            approval.resume_attempted_at = datetime.now(timezone.utc)
            approval.resume_succeeded = False
            approval.resume_error = f"{type(e).__name__}: {str(e)[:500]}"
            await self.db.commit()
            raise BusinessRuleError(
                f"Failed to POST resume_url for approval {approval.id}: {e}",
            ) from e

        approval.resume_attempted_at = datetime.now(timezone.utc)
        approval.resume_succeeded = True
        approval.resume_error = None
        await self.db.commit()
        return {"ok": True, "approval_id": approval.id, "decision": decision}

    async def _load_approval_for_update(
        self, approval_id: str,
    ) -> ApprovalRequestModel | None:
        stmt = (
            select(ApprovalRequestModel)
            .where(ApprovalRequestModel.id == approval_id)
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ── handle_callback (Task 5) ─────────────────────────────────────

    async def handle_callback(
        self,
        *,
        action: str,
        payload: dict,
        playbook_run_id: str,
        request_body: bytes,
        request_headers: dict,
    ) -> dict:
        """Inbound dispatcher for n8n → CMS callbacks.

        Auth: HMAC of body verified with tenant's n8n source secret; if
        x-cms-callback-jwt header present, also validates the JWT against
        the run's case_id. Returns the handler's response dict.

        Action stubs return {"ok": True, "todo": "<task>"} until Task 6-9
        replace them with real handlers.
        """
        run = await self._load_playbook_run_for_update(playbook_run_id)
        if run is None:
            raise NotFoundError(
                f"playbook_run {playbook_run_id} not found",
            )
        case = await self._load_case(run.case_id)

        # HMAC verification with the tenant's n8n source secret
        source = await self._get_n8n_source(case.tenant_id)
        secret = decrypt_secret(source.auth_secret_encrypted)
        self._validate_hmac(secret, request_body, request_headers)

        # Optional second factor: JWT bound to case_id
        jwt_header = request_headers.get("x-cms-callback-jwt")
        if jwt_header:
            validate_callback_jwt(jwt_header, expected_case_id=case.id)

        # State transitions on every callback
        run.last_callback_at = datetime.now(timezone.utc)
        run.callback_count += 1
        if run.status == "triggered":
            run.status = "running"

        handler = self._action_handlers().get(action)
        if handler is None:
            await self._log_callback(
                run.id, action, payload,
                success=False, error="unknown action",
            )
            await self.db.commit()
            raise ValidationError(f"Unknown callback action: {action}")

        try:
            response = await handler(case=case, run=run, payload=payload)
            await self._log_callback(
                run.id, action, payload,
                success=True, response=response,
            )
            await self.db.commit()
            return response
        except Exception as e:
            await self._log_callback(
                run.id, action, payload,
                success=False, error=f"{type(e).__name__}: {str(e)[:500]}",
            )
            await self.db.commit()
            raise

    def _action_handlers(self):
        """Map action name → handler. Task 7-9 will replace remaining stubs."""
        return {
            "update_case_field": self._action_update_case_field,
            "update_priority": self._action_update_priority,
            "update_taxonomy": self._action_update_taxonomy,
            "add_note": self._action_add_note,
            "request_approval": self._action_request_approval,
            "record_decision": self._action_record_decision,
            "attach_artifact": self._action_attach_artifact,
            "set_pending_triage_complete": self._action_set_pending_triage_complete,
        }

    async def _stub_action(self, *, case, run, payload) -> dict:
        """Placeholder — actions still pending: request_approval, record_decision,
        attach_artifact, set_pending_triage_complete (Tasks 7-9)."""
        return {"ok": True, "todo": "real handler lands in Task 7-9"}

    # ── Task 6 handlers ──────────────────────────────────────────────

    # Fields n8n is allowed to mutate via update_case_field. Status transitions
    # and archive flips intentionally excluded — those need either approval
    # (Task 7) or human in CMS UI.
    _UPDATE_CASE_FIELD_ALLOWLIST = {
        "title", "description", "team_id", "complexity",
        "application_id", "origin_id",
    }

    async def _action_update_case_field(
        self, *, case: CaseModel, run, payload: dict,
    ) -> dict:
        updates = {
            k: v for k, v in payload.items()
            if k in self._UPDATE_CASE_FIELD_ALLOWLIST and k != "action"
        }
        if not updates:
            return {"ok": True, "noop": True, "reason": "no allowed fields in payload"}

        for field, value in updates.items():
            setattr(case, field, value)
        case.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"ok": True, "updated_fields": list(updates.keys())}

    async def _action_update_priority(
        self, *, case: CaseModel, run, payload: dict,
    ) -> dict:
        priority_id = payload.get("priority_id")
        if not priority_id:
            raise ValidationError("update_priority requires priority_id in payload")
        case.priority_id = priority_id
        case.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"ok": True, "priority_id": priority_id}

    async def _action_update_taxonomy(
        self, *, case: CaseModel, run, payload: dict,
    ) -> dict:
        taxonomy_id = payload.get("taxonomy_id")
        if not taxonomy_id:
            raise ValidationError("update_taxonomy requires taxonomy_id in payload")
        case.taxonomy_id = taxonomy_id
        case.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"ok": True, "taxonomy_id": taxonomy_id}

    # Default approval TTL when n8n omits `timeout_minutes`. SLA spec says 60min
    # is the upper bound for incident response decisions; tunable per-call via
    # payload.timeout_minutes.
    _DEFAULT_APPROVAL_TIMEOUT_MINUTES = 60

    # Allowlist for record_decision payload — governance: n8n CANNOT close
    # cases. Decisions that need terminal status transitions ('resolved',
    # 'closed') must be made by a human operator in the CMS UI.
    _ALLOWED_DECISIONS = frozenset({
        "promoted_to_incident",
        "confirmed_as_event",
        "discarded",
        "requires_human_review",
    })

    async def _action_record_decision(
        self, *, case: CaseModel, run: PlaybookRunModel, payload: dict,
    ) -> dict:
        """Terminal callback: n8n reports the playbook's final decision.

        Idempotent — second call on an already-completed run returns noop
        (the audit table still records the inbound callback).
        """
        if run.status == "completed":
            return {"ok": True, "noop": True, "reason": "run already completed"}

        decision = payload.get("decision")
        if decision not in self._ALLOWED_DECISIONS:
            raise ValidationError(
                f"Unknown decision '{decision}'. Allowed: "
                f"{sorted(self._ALLOWED_DECISIONS)}",
            )

        # Apply per-decision case mutations (allowlist enforced above)
        if decision == "discarded":
            await self._set_case_status_by_slug(case, "discarded")
        elif decision == "requires_human_review":
            await self._set_case_status_by_slug(case, "triage")
        elif decision == "promoted_to_incident":
            # Lightweight promotion: flip case_type. Full promote (with
            # case_number re-issue) is operator-initiated via UI.
            case.case_type = "incident"
        # 'confirmed_as_event' is a no-op on the case — workflow just records
        # the verdict in run.final_decision for audit.

        # Always clear pending_triage_until and stamp run completion
        case.pending_triage_until = None
        case.updated_at = datetime.now(timezone.utc)
        run.final_decision = decision
        run.final_decision_data = {
            k: v for k, v in payload.items() if k != "decision"
        }
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"ok": True, "decision": decision, "run_id": run.id}

    async def _set_case_status_by_slug(
        self, case: CaseModel, slug: str,
    ) -> None:
        """Look up case_statuses by slug and assign to case.status_id."""
        from sqlalchemy import text as _t
        row = (await self.db.execute(_t(
            "SELECT id FROM case_statuses WHERE slug = :s LIMIT 1"
        ), {"s": slug})).first()
        if not row:
            raise BusinessRuleError(
                f"case_status with slug '{slug}' not found",
            )
        case.status_id = row[0]

    async def _action_attach_artifact(
        self, *, case: CaseModel, run: PlaybookRunModel, payload: dict,
    ) -> dict:
        """Phase 1 stub: record the artifact reference as a case note.

        Sub-spec 07 (Velociraptor forensics) will replace this with a real
        forensic_artifacts row + a download link. For now operators see the
        reference in the case timeline.
        """
        artifact_type = payload.get("artifact_type") or "unknown"
        artifact_ref = payload.get("artifact_ref") or ""
        summary = payload.get("summary") or ""
        if not self.system_user_id:
            raise BusinessRuleError(
                "system_user_id not configured for n8n_bridge.attach_artifact",
            )

        import uuid as _uuid
        from sqlalchemy import text as _t
        note_id = str(_uuid.uuid4())
        short_marker = (run.id or "")[:8]
        content = (
            f"[n8n run {short_marker}] Artifact attached: "
            f"type={artifact_type}, ref={artifact_ref}"
            + (f" — {summary}" if summary else "")
        )
        await self.db.execute(_t(
            "INSERT INTO case_notes "
            "(id, case_id, user_id, tenant_id, content, is_deleted, "
            "created_at, updated_at) "
            "VALUES (:id, :cid, :uid, :tid, :content, false, NOW(), NOW())"
        ), {
            "id": note_id, "cid": case.id, "uid": self.system_user_id,
            "tid": case.tenant_id, "content": content,
        })
        await self.db.flush()
        return {
            "ok": True, "note_id": note_id,
            "artifact_type": artifact_type, "artifact_ref": artifact_ref,
        }

    async def _action_set_pending_triage_complete(
        self, *, case: CaseModel, run: PlaybookRunModel, payload: dict,
    ) -> dict:
        """Transition a `pending_triage` case to `logged` and clear the timer.
        No-op on any other status (defense against double-call from n8n)."""
        from sqlalchemy import text as _t
        current = (await self.db.execute(_t(
            "SELECT slug FROM case_statuses WHERE id = :id"
        ), {"id": case.status_id})).first()
        if not current or current[0] != "pending_triage":
            return {"ok": True, "noop": True, "current_status": current[0] if current else None}

        await self._set_case_status_by_slug(case, "logged")
        case.pending_triage_until = None
        case.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return {"ok": True, "transitioned": True, "new_status": "logged"}

    async def _action_request_approval(
        self, *, case: CaseModel, run: PlaybookRunModel, payload: dict,
    ) -> dict:
        """Persist an ApprovalRequestModel pending operator decision.

        Required payload: requested_action, action_category, resume_url.
        Optional: timeout_minutes (default 60), context (any dict),
        resume_hmac_secret (encrypted at rest via Fernet).
        """
        requested_action = payload.get("requested_action")
        action_category = payload.get("action_category")
        resume_url = payload.get("resume_url")
        if not (requested_action and action_category and resume_url):
            raise ValidationError(
                "request_approval requires requested_action, action_category, "
                "and resume_url in payload",
            )

        timeout_minutes = payload.get("timeout_minutes") or self._DEFAULT_APPROVAL_TIMEOUT_MINUTES
        timeout_at = datetime.now(timezone.utc) + timedelta(
            minutes=int(timeout_minutes),
        )

        resume_secret = payload.get("resume_hmac_secret")
        resume_secret_encrypted = (
            encrypt_secret(resume_secret) if resume_secret else None
        )

        approval = ApprovalRequestModel(
            tenant_id=case.tenant_id,
            case_id=case.id,
            playbook_run_id=run.id,
            requested_action=requested_action,
            action_category=action_category,
            context_payload=payload.get("context") or {},
            requested_by_workflow=run.workflow_url,
            resume_url=resume_url,
            resume_hmac_secret_encrypted=resume_secret_encrypted,
            status="pending",
            timeout_at=timeout_at,
        )
        self.db.add(approval)
        await self.db.flush()
        return {
            "ok": True,
            "approval_id": approval.id,
            "timeout_at": timeout_at.isoformat(),
        }

    async def _action_add_note(
        self, *, case: CaseModel, run, payload: dict,
    ) -> dict:
        """Insert a case_notes row attributed to the configured system_user_id.
        Content is prefixed with a `[n8n run <short_id>]` marker so operators
        can trace it back to the playbook execution without a JOIN."""
        content = payload.get("content") or payload.get("text")
        if not content:
            raise ValidationError("add_note requires 'content' or 'text' in payload")
        if not self.system_user_id:
            raise BusinessRuleError(
                "system_user_id not configured for n8n_bridge.add_note",
            )

        import uuid as _uuid
        from sqlalchemy import text as _t
        note_id = str(_uuid.uuid4())
        short_marker = (run.id or "")[:8]
        prefixed = f"[n8n run {short_marker}] {content}"
        await self.db.execute(_t(
            "INSERT INTO case_notes "
            "(id, case_id, user_id, tenant_id, content, is_deleted, "
            "created_at, updated_at) "
            "VALUES (:id, :cid, :uid, :tid, :content, false, NOW(), NOW())"
        ), {
            "id": note_id, "cid": case.id, "uid": self.system_user_id,
            "tid": case.tenant_id, "content": prefixed,
        })
        await self.db.flush()
        return {"ok": True, "note_id": note_id}

    # ── Auth + persistence helpers ───────────────────────────────────

    def _validate_hmac(
        self, secret: str, request_body: bytes, request_headers: dict,
    ) -> None:
        """Case-insensitive header lookup; mirrors Sub-spec 04 auth.validate_auth."""
        provided = (
            request_headers.get("x-cms-signature")
            or request_headers.get("X-CMS-Signature")
        )
        if not provided:
            raise UnauthorizedError("Missing X-CMS-Signature header")
        if not provided.startswith("sha256="):
            raise UnauthorizedError("HMAC signature format invalid")
        expected_hex = provided[len("sha256="):]
        computed = hmac.new(
            secret.encode("utf-8"), request_body, hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(computed, expected_hex):
            raise UnauthorizedError("HMAC signature mismatch")

    async def _load_playbook_run_for_update(
        self, run_id: str,
    ) -> PlaybookRunModel | None:
        """SELECT FOR UPDATE so concurrent callbacks for the same run serialize
        cleanly (callback_count increments atomically)."""
        stmt = (
            select(PlaybookRunModel)
            .where(PlaybookRunModel.id == run_id)
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def _log_callback(
        self,
        run_id: str,
        action: str,
        payload: dict,
        *,
        success: bool,
        error: str | None = None,
        response: dict | None = None,
    ) -> None:
        cb = PlaybookRunCallbackModel(
            playbook_run_id=run_id,
            action=action,
            payload=payload,
            success=success,
            error=error,
            response_payload=response,
        )
        self.db.add(cb)
        await self.db.flush()

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
