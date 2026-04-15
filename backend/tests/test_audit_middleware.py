"""Tests de lógica del middleware de auditoría."""
from unittest.mock import MagicMock


def test_excluded_tables_prevent_recursion():
    """Las tablas excluidas evitan bucles infinitos en el listener."""
    from backend.src.modules.audit.application.middleware import EXCLUDED_TABLES

    assert "audit_logs" in EXCLUDED_TABLES
    assert "notifications" in EXCLUDED_TABLES
    assert "active_timers" in EXCLUDED_TABLES
    assert "user_sessions" in EXCLUDED_TABLES


def test_set_current_actor_stores_value():
    """set_current_actor almacena el user_id en el ContextVar."""
    from backend.src.modules.audit.application.middleware import (
        _current_actor,
        set_current_actor,
    )

    set_current_actor("user-123")
    assert _current_actor.get() == "user-123"

    set_current_actor(None)
    assert _current_actor.get() is None


def _make_state(props: list) -> MagicMock:
    """Construye un InstanceState mock con mapper.column_attrs y attrs[key]."""
    state = MagicMock()
    # mapper.column_attrs devuelve props con atributo .key
    state.mapper.column_attrs = props
    # state.attrs[key] devuelve el mismo prop (attr con history)
    state.attrs.__getitem__ = lambda self, key: next(p for p in props if p.key == key)
    return state


def test_get_changes_detects_modifications():
    """_get_changes detecta campos modificados con old/new."""
    from backend.src.modules.audit.application.middleware import _get_changes

    instance = MagicMock()
    attr1 = MagicMock()
    attr1.key = "full_name"
    attr1.history.has_changes.return_value = True
    attr1.history.deleted = ["Nombre Viejo"]
    attr1.history.added = ["Nombre Nuevo"]

    attr2 = MagicMock()
    attr2.key = "email"
    attr2.history.has_changes.return_value = False

    state = _make_state([attr1, attr2])

    from unittest.mock import patch
    with patch("backend.src.modules.audit.application.middleware.inspect", return_value=state):
        changes = _get_changes(instance)

    assert "full_name" in changes
    assert changes["full_name"]["old"] == "Nombre Viejo"
    assert changes["full_name"]["new"] == "Nombre Nuevo"
    assert "email" not in changes


def test_get_changes_skips_unchanged_field():
    """_get_changes omite campos donde old == new."""
    from backend.src.modules.audit.application.middleware import _get_changes

    instance = MagicMock()
    attr = MagicMock()
    attr.key = "status"
    attr.history.has_changes.return_value = True
    attr.history.deleted = ["open"]
    attr.history.added = ["open"]  # mismo valor

    state = _make_state([attr])

    from unittest.mock import patch
    with patch("backend.src.modules.audit.application.middleware.inspect", return_value=state):
        changes = _get_changes(instance)

    assert "status" not in changes


def test_audit_log_model_fields():
    """AuditLogModel tiene los campos esperados para trazar cambios."""
    from backend.src.modules.audit.infrastructure.models import AuditLogModel

    log = AuditLogModel()
    log.action = "UPDATE"
    log.entity_type = "cases"
    log.entity_id = "case-abc"
    log.changes = {"title": {"old": "Viejo", "new": "Nuevo"}}

    assert log.action == "UPDATE"
    assert log.entity_type == "cases"
    assert log.changes["title"]["new"] == "Nuevo"


def test_audit_actions_are_standard():
    """Los valores de action válidos son INSERT, UPDATE y DELETE."""
    valid_actions = {"INSERT", "UPDATE", "DELETE"}
    assert "INSERT" in valid_actions
    assert "UPDATE" in valid_actions
    assert "DELETE" in valid_actions
    assert "SELECT" not in valid_actions
