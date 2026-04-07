"""
Middleware de auditoría automática vía SQLAlchemy event listener.

Registra en `audit_logs` todos los INSERT, UPDATE y DELETE, excluyendo
tablas que generarían ruido o bucles recursivos.

Uso:
    # En get_db() de database.py:
    async with AsyncSessionLocal() as session:
        setup_audit_listener(session)
        yield session

    # Para inyectar el actor del request:
    from backend.src.modules.audit.application.middleware import set_current_actor
    set_current_actor(current_user.user_id)
"""
import logging
from contextvars import ContextVar

from sqlalchemy import event, inspect
from sqlalchemy.orm import InstanceState

logger = logging.getLogger(__name__)

# ContextVar para pasar el user_id al listener sin acoplamiento de capas
_current_actor: ContextVar[str | None] = ContextVar("current_actor", default=None)

# Tablas excluidas para evitar recursión y ruido de baja utilidad
EXCLUDED_TABLES = {
    "audit_logs",       # no auditamos el auditor
    "notifications",    # demasiado frecuentes
    "active_timers",    # estado efímero
    "user_sessions",    # manejado por auth
    "sla_records",      # actualizado por job periódico
}


def set_current_actor(user_id: str | None) -> None:
    """Establece el actor del request actual para el listener de auditoría."""
    _current_actor.set(user_id)


def _get_changes(instance) -> dict:
    """Extrae los campos modificados con su valor anterior y nuevo."""
    changes: dict = {}
    try:
        state: InstanceState = inspect(instance)
        for attr in state.attrs:
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
        pending_audit: list[AuditLogModel] = []

        for instance in list(session.new):
            table = getattr(instance.__class__, "__tablename__", "")
            if table in EXCLUDED_TABLES:
                continue
            entity_id = str(getattr(instance, "id", "unknown"))
            pending_audit.append(AuditLogModel(
                action="INSERT",
                entity_type=table,
                entity_id=entity_id,
                changes=None,
                actor_id=actor_id,
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
                    actor_id=actor_id,
                ))

        for instance in list(session.deleted):
            table = getattr(instance.__class__, "__tablename__", "")
            if table in EXCLUDED_TABLES:
                continue
            entity_id = str(getattr(instance, "id", "unknown"))
            pending_audit.append(AuditLogModel(
                action="DELETE",
                entity_type=table,
                entity_id=entity_id,
                changes=None,
                actor_id=actor_id,
            ))

        for log in pending_audit:
            session.add(log)
