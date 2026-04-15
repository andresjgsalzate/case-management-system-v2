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
                old_raw = hist.deleted[0] if hist.deleted else None
                new_raw = hist.added[0] if hist.added else None
                old = _serialize_value(old_raw)
                new = _serialize_value(new_raw)
                # Skip relationship attributes — ORM objects serialize to None
                if (old_raw is not None and old is None) or (new_raw is not None and new is None):
                    continue
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
