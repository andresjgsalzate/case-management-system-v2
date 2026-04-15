# Forensic Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing audit system with `correlation_id`, `before_snapshot`, HTTP request context, PostgreSQL immutability trigger, two forensic endpoints, and three frontend UI improvements (entity timeline, correlated operation panel, before-state accordion).

**Architecture:** The SQLAlchemy `before_flush` middleware is extended with new ContextVars and a `_get_before_snapshot` function. A Starlette HTTP middleware injects `correlation_id` + request context before every handler runs. Two new endpoints expose timeline-per-entity and all-changes-per-operation queries. The frontend adds a `TimelineModal` and enriches the existing `DetailModal`.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, PostgreSQL (PL/pgSQL trigger), Alembic, Next.js 14, TanStack Query v5, TypeScript

---

## Task 1: Alembic migration — 4 new columns + immutability trigger

**Files:**
- Create: `backend/alembic/versions/f9a0b1c2d3e4_forensic_audit_columns.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/f9a0b1c2d3e4_forensic_audit_columns.py
"""forensic audit columns

Revision ID: f9a0b1c2d3e4
Revises: e7f8a9b0c1d2
Create Date: 2026-04-15
"""
from alembic import op
import sqlalchemy as sa

revision = "f9a0b1c2d3e4"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("audit_logs", sa.Column("correlation_id", sa.String(36), nullable=True))
    op.add_column("audit_logs", sa.Column("before_snapshot", sa.JSON(), nullable=True))
    op.add_column("audit_logs", sa.Column("user_agent", sa.String(500), nullable=True))
    op.add_column("audit_logs", sa.Column("request_path", sa.String(200), nullable=True))

    op.create_index("ix_audit_logs_correlation_id", "audit_logs", ["correlation_id"])

    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_audit_modification()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs records are immutable';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS audit_logs_immutable ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS prevent_audit_modification();")
    op.drop_index("ix_audit_logs_correlation_id", table_name="audit_logs")
    op.drop_column("audit_logs", "request_path")
    op.drop_column("audit_logs", "user_agent")
    op.drop_column("audit_logs", "before_snapshot")
    op.drop_column("audit_logs", "correlation_id")
```

- [ ] **Step 2: Run the migration**

```bash
cd backend
alembic upgrade head
```

Expected output: `Running upgrade e7f8a9b0c1d2 -> f9a0b1c2d3e4, forensic audit columns`

- [ ] **Step 3: Verify the trigger is active**

```bash
psql $DATABASE_URL -c "\d audit_logs"
```

Expected: columns `correlation_id`, `before_snapshot`, `user_agent`, `request_path` present.

```bash
psql $DATABASE_URL -c "SELECT tgname FROM pg_trigger WHERE tgrelid = 'audit_logs'::regclass;"
```

Expected: row `audit_logs_immutable`.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/f9a0b1c2d3e4_forensic_audit_columns.py
git commit -m "feat(audit): migration — 4 forensic columns + immutability trigger"
```

---

## Task 2: AuditLogModel — add 4 new mapped columns

**Files:**
- Modify: `backend/src/modules/audit/infrastructure/models.py`

- [ ] **Step 1: Replace the file content**

```python
# backend/src/modules/audit/infrastructure/models.py
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.src.core.database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    action: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    request_path: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    tenant_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
```

- [ ] **Step 2: Verify the import works**

```bash
cd backend
python -c "from backend.src.modules.audit.infrastructure.models import AuditLogModel; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/modules/audit/infrastructure/models.py
git commit -m "feat(audit): add correlation_id, before_snapshot, user_agent, request_path to model"
```

---

## Task 3: middleware.py — new ContextVars, set_audit_context, _get_before_snapshot

**Files:**
- Modify: `backend/src/modules/audit/application/middleware.py`

- [ ] **Step 1: Replace the file content**

```python
# backend/src/modules/audit/application/middleware.py
"""
Middleware de auditoría automática vía SQLAlchemy event listener.

Registra en `audit_logs` todos los INSERT, UPDATE y DELETE, excluyendo
tablas que generarían ruido o bucles recursivos.

Uso:
    # En get_db() de database.py:
    async with AsyncSessionLocal() as session:
        setup_audit_listener(session)
        yield session

    # Para inyectar el contexto del request:
    from backend.src.modules.audit.application.middleware import set_audit_context
    set_audit_context(actor_id=user_id, correlation_id=corr_id, user_agent=ua, request_path=path)
"""
import logging
import uuid
from contextvars import ContextVar
from datetime import date, datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import InstanceState

logger = logging.getLogger(__name__)

# ── ContextVars — uno por campo de contexto ────────────────────────────────────
_current_actor: ContextVar[str | None] = ContextVar("current_actor", default=None)
_current_correlation: ContextVar[str | None] = ContextVar("current_correlation", default=None)
_current_user_agent: ContextVar[str | None] = ContextVar("current_user_agent", default=None)
_current_request_path: ContextVar[str | None] = ContextVar("current_request_path", default=None)

# Tablas excluidas para evitar recursión y ruido de baja utilidad
EXCLUDED_TABLES = {
    "audit_logs",
    "notifications",
    "active_timers",
    "user_sessions",
    "sla_records",
}

_SKIP_SNAPSHOT_FIELDS = {"hashed_password", "password"}


def set_audit_context(
    actor_id: str | None,
    correlation_id: str | None = None,
    user_agent: str | None = None,
    request_path: str | None = None,
) -> None:
    """Establece el contexto completo del request actual para el listener de auditoría."""
    _current_actor.set(actor_id)
    _current_correlation.set(correlation_id)
    _current_user_agent.set(user_agent)
    _current_request_path.set(request_path)


def set_current_actor(user_id: str | None) -> None:
    """Alias de compatibilidad — solo actualiza el actor, no toca el correlation_id."""
    _current_actor.set(user_id)


def _serialize_value(value):
    """Serializa un valor de campo para almacenamiento JSON."""
    if value is None or isinstance(value, (str, int, float, bool, dict, list)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return None  # skip relationship proxies


def _get_snapshot(instance) -> dict:
    """Captura todos los campos escalares del objeto (para INSERT/DELETE)."""
    snapshot: dict = {}
    try:
        state: InstanceState = inspect(instance)
        for attr in state.attrs:
            if attr.key in _SKIP_SNAPSHOT_FIELDS:
                continue
            try:
                value = getattr(instance, attr.key)
                serialized = _serialize_value(value)
                if serialized is not None or value is None:
                    snapshot[attr.key] = serialized
            except Exception:
                pass
    except Exception as e:
        logger.debug("Error capturando snapshot de auditoría: %s", e)
    return snapshot


def _get_before_snapshot(instance) -> dict:
    """
    Para UPDATE: reconstruye el estado ANTERIOR al cambio.
    Usa attr.history.deleted para campos modificados; valor actual para sin cambios.
    """
    snapshot: dict = {}
    try:
        state: InstanceState = inspect(instance)
        for attr in state.attrs:
            if attr.key in _SKIP_SNAPSHOT_FIELDS:
                continue
            try:
                hist = attr.history
                if hist.has_changes():
                    value = hist.deleted[0] if hist.deleted else None
                else:
                    value = getattr(instance, attr.key, None)
                serialized = _serialize_value(value)
                if serialized is not None or value is None:
                    snapshot[attr.key] = serialized
            except Exception:
                pass
    except Exception as e:
        logger.debug("Error capturando before_snapshot de auditoría: %s", e)
    return snapshot


def _get_changes(instance) -> dict:
    """Extrae los campos modificados con su valor anterior y nuevo."""
    changes: dict = {}
    try:
        state: InstanceState = inspect(instance)
        for attr in state.attrs:
            if attr.key in _SKIP_SNAPSHOT_FIELDS:
                continue
            hist = attr.history
            if hist.has_changes():
                old = hist.deleted[0] if hist.deleted else None
                new = hist.added[0] if hist.added else None
                if old != new:
                    changes[attr.key] = {"old": old, "new": new}
    except Exception as e:
        logger.debug("Error extrayendo cambios de auditoría: %s", e)
    return changes


def setup_audit_listener(async_session) -> None:
    """
    Registra el listener before_flush en el sync_session subyacente
    de la AsyncSession proporcionada.
    """
    from backend.src.modules.audit.infrastructure.models import AuditLogModel

    sync_session = async_session.sync_session

    @event.listens_for(sync_session, "before_flush")
    def before_flush(session, flush_context, instances):
        actor_id = _current_actor.get()
        correlation_id = _current_correlation.get()
        user_agent = _current_user_agent.get()
        request_path = _current_request_path.get()
        pending_audit: list[AuditLogModel] = []

        for instance in list(session.new):
            table = getattr(instance.__class__, "__tablename__", "")
            if table in EXCLUDED_TABLES:
                continue
            entity_id = str(getattr(instance, "id", "unknown"))
            snapshot = _get_snapshot(instance)
            pending_audit.append(AuditLogModel(
                action="INSERT",
                entity_type=table,
                entity_id=entity_id,
                changes={"_snapshot": snapshot} if snapshot else None,
                before_snapshot=None,
                actor_id=actor_id,
                correlation_id=correlation_id,
                user_agent=user_agent,
                request_path=request_path,
            ))

        for instance in list(session.dirty):
            table = getattr(instance.__class__, "__tablename__", "")
            if table in EXCLUDED_TABLES:
                continue
            if not session.is_modified(instance):
                continue
            entity_id = str(getattr(instance, "id", "unknown"))
            changes = _get_changes(instance)
            if changes:
                pending_audit.append(AuditLogModel(
                    action="UPDATE",
                    entity_type=table,
                    entity_id=entity_id,
                    changes=changes,
                    before_snapshot=_get_before_snapshot(instance),
                    actor_id=actor_id,
                    correlation_id=correlation_id,
                    user_agent=user_agent,
                    request_path=request_path,
                ))

        for instance in list(session.deleted):
            table = getattr(instance.__class__, "__tablename__", "")
            if table in EXCLUDED_TABLES:
                continue
            entity_id = str(getattr(instance, "id", "unknown"))
            snapshot = _get_snapshot(instance)
            pending_audit.append(AuditLogModel(
                action="DELETE",
                entity_type=table,
                entity_id=entity_id,
                changes={"_snapshot": snapshot} if snapshot else None,
                before_snapshot=None,
                actor_id=actor_id,
                correlation_id=correlation_id,
                user_agent=user_agent,
                request_path=request_path,
            ))

        for log in pending_audit:
            session.add(log)
```

- [ ] **Step 2: Verify import and alias work**

```bash
cd backend
python -c "
from backend.src.modules.audit.application.middleware import (
    set_audit_context, set_current_actor, _get_before_snapshot, _get_snapshot
)
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/modules/audit/application/middleware.py
git commit -m "feat(audit): add correlation_id context, before_snapshot capture for UPDATE"
```

---

## Task 4: AuditContextMiddleware — HTTP middleware + registration

**Files:**
- Create: `backend/src/core/middleware/audit_context.py`
- Modify: `backend/src/main.py`

- [ ] **Step 1: Create the middleware file**

```python
# backend/src/core/middleware/audit_context.py
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuditContextMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that generates one correlation_id per HTTP request
    and injects it (along with User-Agent and request path) into the audit
    ContextVars before any handler runs.

    The actor_id is set later by the PermissionChecker dependency after JWT
    verification — it calls set_current_actor() which only updates _current_actor
    without overwriting the correlation_id already set here.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        from backend.src.modules.audit.application.middleware import set_audit_context

        correlation_id = str(uuid.uuid4())
        user_agent = (request.headers.get("user-agent") or "")[:500]
        request_path = f"{request.method} {request.url.path}"[:200]

        set_audit_context(
            actor_id=None,
            correlation_id=correlation_id,
            user_agent=user_agent,
            request_path=request_path,
        )

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response
```

- [ ] **Step 2: Register in main.py — add after the CORSMiddleware block**

In `backend/src/main.py`, add the import at the top with the other middleware imports:

```python
from backend.src.core.middleware.audit_context import AuditContextMiddleware
```

Then add the middleware registration **after** `app.add_middleware(CORSMiddleware, ...)`:

```python
    app.add_middleware(AuditContextMiddleware)
```

The full middleware block in `create_app()` becomes:

```python
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(AuditContextMiddleware)
```

In Starlette/FastAPI, middleware registered last runs first (outermost layer), so `AuditContextMiddleware` will execute before any handler, ensuring `correlation_id` is always set before `PermissionChecker` runs.

- [ ] **Step 3: Start the backend and verify the header appears**

```bash
cd backend
uvicorn backend.src.main:app --reload
```

In another terminal:
```bash
curl -s -I http://localhost:8000/api/v1/health | grep -i correlation
```

Expected: `x-correlation-id: <some-uuid>`

- [ ] **Step 4: Commit**

```bash
git add backend/src/core/middleware/audit_context.py backend/src/main.py
git commit -m "feat(audit): AuditContextMiddleware — correlation_id injected per HTTP request"
```

---

## Task 5: AuditUseCases — list_timeline and list_by_correlation

**Files:**
- Modify: `backend/src/modules/audit/application/use_cases.py`

- [ ] **Step 1: Add the two new methods at the end of the class**

Add after `resolve_fk_values`, inside `class AuditUseCases`:

```python
    async def list_timeline(
        self,
        entity_type: str,
        entity_id: str,
    ) -> list[AuditLogModel]:
        """
        Returns all audit events for a specific entity in chronological order (ASC).
        Used to reconstruct the complete history of a record from creation to present.
        """
        stmt = (
            select(AuditLogModel)
            .where(
                AuditLogModel.entity_type == entity_type,
                AuditLogModel.entity_id == entity_id,
            )
            .order_by(AuditLogModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_correlation(
        self,
        correlation_id: str,
    ) -> list[AuditLogModel]:
        """
        Returns all audit events that share the same correlation_id (same HTTP request).
        Used to answer: "what else changed in this same operation?"
        """
        stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.correlation_id == correlation_id)
            .order_by(AuditLogModel.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
```

- [ ] **Step 2: Verify import**

```bash
cd backend
python -c "
from backend.src.modules.audit.application.use_cases import AuditUseCases
import inspect
assert 'list_timeline' in dir(AuditUseCases)
assert 'list_by_correlation' in dir(AuditUseCases)
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/src/modules/audit/application/use_cases.py
git commit -m "feat(audit): add list_timeline and list_by_correlation use cases"
```

---

## Task 6: Router — extend serializer and add 2 forensic endpoints

**Files:**
- Modify: `backend/src/modules/audit/router.py`

- [ ] **Step 1: Replace the file content**

```python
# backend/src/modules/audit/router.py
from fastapi import APIRouter, Depends, Query

from backend.src.core.dependencies import DBSession
from backend.src.core.responses import SuccessResponse
from backend.src.core.middleware.permission_checker import CurrentUser, PermissionChecker
from backend.src.modules.audit.application.use_cases import AuditUseCases
from backend.src.modules.audit.infrastructure.models import AuditLogModel

router = APIRouter(prefix="/api/v1/audit", tags=["audit"])
AuditRead = Depends(PermissionChecker("audit", "read"))

_FK_FIELDS = {
    "status_id", "priority_id", "assigned_to", "team_id", "role_id",
    "category_id", "application_id", "origin_id", "created_by_id",
    "approved_by_id", "created_by",
}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=SuccessResponse[list[dict]])
async def get_audit_logs(
    db: DBSession,
    entity_type: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    current_user: CurrentUser = AuditRead,
):
    uc = AuditUseCases(db=db)
    logs = await uc.list_logs(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Forensic: entity timeline ─────────────────────────────────────────────────

@router.get("/timeline/{entity_type}/{entity_id}", response_model=SuccessResponse[list[dict]])
async def get_entity_timeline(
    entity_type: str,
    entity_id: str,
    db: DBSession,
    current_user: CurrentUser = AuditRead,
):
    """All audit events for one entity in chronological order (oldest first)."""
    uc = AuditUseCases(db=db)
    logs = await uc.list_timeline(entity_type=entity_type, entity_id=entity_id)
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Forensic: correlated operation ───────────────────────────────────────────

@router.get("/operation/{correlation_id}", response_model=SuccessResponse[list[dict]])
async def get_operation_logs(
    correlation_id: str,
    db: DBSession,
    current_user: CurrentUser = AuditRead,
):
    """All audit events that share a correlation_id (same HTTP request)."""
    uc = AuditUseCases(db=db)
    logs = await uc.list_by_correlation(correlation_id=correlation_id)
    actor_names, entity_labels = await uc.resolve_labels(logs)
    fk_values = await uc.resolve_fk_values(logs)
    return SuccessResponse.ok([
        _serialize(log, actor_names, entity_labels, fk_values) for log in logs
    ])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _enrich_changes(changes: dict, fk_values: dict[str, str]) -> dict:
    """Replace UUID values in known FK fields with human-readable labels."""
    if not fk_values:
        return changes
    enriched: dict = {}
    for field, info in changes.items():
        if field == "_snapshot" and isinstance(info, dict):
            enriched["_snapshot"] = {
                k: (fk_values[str(v)] if k in _FK_FIELDS and isinstance(v, str) and v in fk_values else v)
                for k, v in info.items()
            }
        elif field in _FK_FIELDS and isinstance(info, dict):
            enriched[field] = {
                "old": fk_values.get(info["old"], info["old"]) if isinstance(info.get("old"), str) else info.get("old"),
                "new": fk_values.get(info["new"], info["new"]) if isinstance(info.get("new"), str) else info.get("new"),
            }
        else:
            enriched[field] = info
    return enriched


def _enrich_snapshot(snapshot: dict | None, fk_values: dict[str, str]) -> dict | None:
    """Replace UUID values in FK fields of a before_snapshot dict."""
    if not snapshot or not fk_values:
        return snapshot
    return {
        k: (fk_values[str(v)] if k in _FK_FIELDS and isinstance(v, str) and v in fk_values else v)
        for k, v in snapshot.items()
    }


def _serialize(
    log: AuditLogModel,
    actor_names: dict[str, str],
    entity_labels: dict[str, str],
    fk_values: dict[str, str],
) -> dict:
    raw_changes = log.changes
    enriched_changes = _enrich_changes(raw_changes, fk_values) if raw_changes else None
    enriched_before = _enrich_snapshot(log.before_snapshot, fk_values)
    return {
        "id": log.id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "entity_label": entity_labels.get(log.entity_id),
        "changes": enriched_changes,
        "before_snapshot": enriched_before,
        "actor_id": log.actor_id,
        "actor_name": actor_names.get(log.actor_id) if log.actor_id else None,
        "correlation_id": log.correlation_id,
        "user_agent": log.user_agent,
        "request_path": log.request_path,
        "ip_address": log.ip_address,
        "created_at": log.created_at.isoformat(),
    }
```

- [ ] **Step 2: Verify the endpoints are registered**

```bash
cd backend
python -c "
from backend.src.modules.audit.router import router
paths = [r.path for r in router.routes]
assert '/api/v1/audit/timeline/{entity_type}/{entity_id}' in paths or any('timeline' in p for p in paths)
assert any('operation' in p for p in paths)
print('Paths:', paths)
print('OK')
"
```

Expected: paths list includes `timeline` and `operation` routes, then `OK`.

- [ ] **Step 3: Commit**

```bash
git add backend/src/modules/audit/router.py
git commit -m "feat(audit): add timeline and operation endpoints, enrich before_snapshot"
```

---

## Task 7: Frontend — types + three UI improvements in audit page

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/app/(dashboard)/audit/page.tsx`

- [ ] **Step 1: Update AuditLog interface in types.ts**

In `frontend/lib/types.ts`, replace the existing `AuditLog` interface (lines 157–168) with:

```typescript
export type AuditAction = 'INSERT' | 'UPDATE' | 'DELETE';

export interface AuditLog {
  id: string;
  action: AuditAction;
  entity_type: string;
  entity_id: string;
  entity_label?: string | null;
  changes?: Record<string, { old: unknown; new: unknown }>;
  before_snapshot?: Record<string, unknown> | null;
  actor_id?: string;
  actor_name?: string | null;
  correlation_id?: string | null;
  user_agent?: string | null;
  request_path?: string | null;
  ip_address?: string;
  created_at: string;
}
```

- [ ] **Step 2: Add two new hooks at the top of audit/page.tsx (after the existing `useAuditLogs` hook)**

```typescript
function useTimelineLogs(entityType: string, entityId: string) {
  return useQuery({
    queryKey: ["audit-timeline", entityType, entityId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AuditLog[]>>(
        `/audit/timeline/${entityType}/${entityId}`
      );
      return data.data ?? [];
    },
    enabled: !!entityType && !!entityId,
  });
}

function useOperationLogs(correlationId: string | null | undefined) {
  return useQuery({
    queryKey: ["audit-operation", correlationId],
    queryFn: async () => {
      const { data } = await apiClient.get<ApiResponse<AuditLog[]>>(
        `/audit/operation/${correlationId}`
      );
      return data.data ?? [];
    },
    enabled: !!correlationId,
  });
}
```

- [ ] **Step 3: Add TimelineModal component (add before the DetailModal component)**

```typescript
function TimelineModal({
  entityType,
  entityId,
  entityLabel,
  onClose,
  onSelectLog,
}: {
  entityType: string;
  entityId: string;
  entityLabel?: string | null;
  onClose: () => void;
  onSelectLog: (log: AuditLog) => void;
}) {
  const { data: logs = [], isLoading } = useTimelineLogs(entityType, entityId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-xl w-full max-w-2xl mx-4 max-h-[85vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
          <div className="flex flex-col gap-0.5">
            <p className="text-sm font-semibold text-foreground">Línea de tiempo</p>
            <p className="text-xs text-muted-foreground">
              {entityLabel ?? entityId} · {ENTITY_LABELS[entityType] ?? entityType}
            </p>
          </div>
          <button type="button" onClick={onClose}
            className="text-muted-foreground hover:text-foreground p-1 rounded hover:bg-muted transition-colors">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-5 py-4">
          {isLoading && <div className="flex justify-center py-8"><Spinner size="lg" /></div>}
          {!isLoading && logs.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-8">Sin eventos registrados.</p>
          )}
          {!isLoading && logs.length > 0 && (
            <div className="relative">
              {/* Vertical line */}
              <div className="absolute left-[7px] top-2 bottom-2 w-px bg-border" />
              <div className="flex flex-col gap-0">
                {logs.map((log, i) => (
                  <button
                    key={log.id}
                    type="button"
                    onClick={() => onSelectLog(log)}
                    className="flex items-start gap-4 py-3 text-left hover:bg-muted/40 rounded-lg px-2 transition-colors group"
                  >
                    {/* Dot */}
                    <div className={[
                      "mt-1 h-3.5 w-3.5 rounded-full border-2 shrink-0 z-10",
                      log.action === "INSERT" ? "bg-emerald-500 border-emerald-500" :
                      log.action === "DELETE" ? "bg-destructive border-destructive" :
                      "bg-amber-500 border-amber-500",
                    ].join(" ")} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge variant={ACTION_VARIANTS[log.action] ?? "outline"} >
                          {ACTION_LABELS[log.action] ?? log.action}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {log.actor_name ?? "Sistema"}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {new Date(log.created_at).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}
                      </p>
                      {log.request_path && (
                        <p className="text-xs font-mono text-muted-foreground/60 truncate mt-0.5">
                          {log.request_path}
                        </p>
                      )}
                    </div>
                    <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/40 group-hover:text-muted-foreground mt-1 shrink-0" />
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Enrich DetailModal with "Estado anterior" and "Operación completa" sections**

Inside the existing `DetailModal` component, add the `useOperationLogs` call right after the existing change-parsing lines:

```typescript
function DetailModal({ log, onClose }: { log: AuditLog; onClose: () => void }) {
  const allChanges = log.changes ?? {};
  const snapshot = allChanges._snapshot as Record<string, unknown> | undefined;
  const fieldChanges = Object.fromEntries(
    Object.entries(allChanges).filter(([k]) => k !== "_snapshot")
  ) as Record<string, { old: unknown; new: unknown }>;
  const hasFieldChanges = Object.keys(fieldChanges).length > 0;
  const hasSnapshot = !!snapshot && Object.keys(snapshot).length > 0;
  const hasBefore = !!log.before_snapshot && Object.keys(log.before_snapshot).length > 0;

  // Fetch correlated logs only when this modal is open
  const { data: operationLogs = [] } = useOperationLogs(log.correlation_id);
  const relatedLogs = operationLogs.filter(l => l.id !== log.id);
  const [beforeOpen, setBeforeOpen] = useState(false);
```

Then add two new sections inside the modal body (after the existing "Raw JSON fallback" section, before the closing `</div>` of the body):

**Sección "Estado anterior completo" (solo UPDATE con before_snapshot):**
```typescript
          {/* UPDATE: full before state */}
          {log.action === "UPDATE" && hasBefore && (
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => setBeforeOpen(o => !o)}
                className="flex items-center gap-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider hover:text-foreground transition-colors"
              >
                <ChevronRight className={["h-3.5 w-3.5 transition-transform", beforeOpen ? "rotate-90" : ""].join(" ")} />
                Estado anterior completo
              </button>
              {beforeOpen && (
                <div className="rounded-lg border border-border overflow-hidden">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground w-1/3">Campo</th>
                        <th className="px-3 py-2 text-left font-medium text-muted-foreground">Valor anterior</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {Object.entries(log.before_snapshot!)
                        .filter(([field]) => !["id", "tenant_id", "usage_count"].includes(field))
                        .map(([field, value]) => (
                          <tr key={field} className="hover:bg-muted/20">
                            <td className="px-3 py-2 font-medium text-foreground">
                              {FIELD_LABELS[field] ?? field}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground break-all whitespace-pre-wrap max-w-[300px]">
                              {renderValue(value)}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
```

**Sección "Operación completa":**
```typescript
          {/* Correlated operation */}
          {relatedLogs.length > 0 && (
            <div className="flex flex-col gap-2">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                Operación completa · {relatedLogs.length + 1} cambios en este request
              </p>
              <div className="rounded-lg border border-border overflow-hidden divide-y divide-border">
                {relatedLogs.map(related => (
                  <div key={related.id} className="flex items-center gap-3 px-3 py-2.5">
                    <Badge variant={ACTION_VARIANTS[related.action] ?? "outline"}>
                      {ACTION_LABELS[related.action] ?? related.action}
                    </Badge>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-foreground truncate">
                        {ENTITY_LABELS[related.entity_type] ?? related.entity_type}
                        {related.entity_label ? ` · ${related.entity_label}` : ""}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              {log.request_path && (
                <p className="text-xs font-mono text-muted-foreground/60">{log.request_path}</p>
              )}
              {log.user_agent && (
                <p className="text-xs text-muted-foreground/60 truncate">{log.user_agent}</p>
              )}
            </div>
          )}
```

- [ ] **Step 5: Add timeline button to table rows and wire up state**

In `AuditPage`, add state for the timeline modal:

```typescript
const [timeline, setTimeline] = useState<{ entityType: string; entityId: string; entityLabel?: string | null } | null>(null);
```

In each table row, add a timeline button before the chevron cell. Import `History` from lucide-react:

```typescript
import { Shield, X, User, Box, Clock, Wifi, ChevronRight, History } from "lucide-react";
```

Add the button cell right before `<td className="px-4 py-3"><ChevronRight ...`:

```typescript
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={e => {
                        e.stopPropagation();
                        setTimeline({ entityType: log.entity_type, entityId: log.entity_id, entityLabel: log.entity_label });
                      }}
                      title="Ver línea de tiempo"
                      className="text-muted-foreground/40 hover:text-muted-foreground transition-colors p-0.5 rounded"
                    >
                      <History className="h-3.5 w-3.5" />
                    </button>
                  </td>
```

Update the table header array to include the new column:

```typescript
{["Acción", "Entidad", "Registro", "Actor", "Campos", "Fecha", "", ""].map((col, i) => (
```

Add the modals at the bottom of the return, alongside the existing `selected` modal:

```typescript
      {timeline && (
        <TimelineModal
          entityType={timeline.entityType}
          entityId={timeline.entityId}
          entityLabel={timeline.entityLabel}
          onClose={() => setTimeline(null)}
          onSelectLog={log => { setTimeline(null); setSelected(log); }}
        />
      )}
```

- [ ] **Step 6: Verify TypeScript compiles**

```bash
cd frontend
npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/lib/types.ts frontend/app/\(dashboard\)/audit/page.tsx
git commit -m "feat(audit): timeline modal, operation panel, before-state accordion in frontend"
```

---

## Spec Coverage Self-Review

| Spec requirement | Task that covers it |
|---|---|
| `correlation_id` column + index | Task 1 (migration), Task 2 (model), Task 3 (middleware), Task 6 (serializer) |
| `before_snapshot` column for UPDATE | Task 1, Task 2, Task 3 (`_get_before_snapshot`), Task 6 (serializer + enrich) |
| `user_agent` column | Task 1, Task 2, Task 3, Task 6 |
| `request_path` column | Task 1, Task 2, Task 3, Task 6 |
| PostgreSQL immutability trigger | Task 1 |
| HTTP middleware injects correlation_id | Task 4 |
| `X-Correlation-Id` response header | Task 4 |
| `set_current_actor` remains alias | Task 3 |
| `GET /audit/timeline/{type}/{id}` | Task 5 (use case), Task 6 (endpoint) |
| `GET /audit/operation/{correlation_id}` | Task 5 (use case), Task 6 (endpoint) |
| Frontend: entity timeline modal | Task 7 (TimelineModal) |
| Frontend: "Operación completa" panel | Task 7 (DetailModal enrichment) |
| Frontend: "Estado anterior completo" | Task 7 (DetailModal before accordion) |
| FK values enriched in before_snapshot | Task 6 (`_enrich_snapshot`) |
