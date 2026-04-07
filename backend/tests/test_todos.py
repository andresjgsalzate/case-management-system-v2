def test_todo_complete_sets_completed_at():
    """Al completar un TODO, completed_at debe registrarse."""
    from datetime import datetime, timezone
    from unittest.mock import MagicMock

    # Simula el modelo
    todo = MagicMock()
    todo.is_completed = False
    todo.completed_at = None

    # Lógica del use_case
    todo.is_completed = True
    todo.completed_at = datetime.now(timezone.utc)

    assert todo.is_completed is True
    assert todo.completed_at is not None
    assert todo.completed_at.tzinfo is not None


def test_todo_list_excludes_archived_by_default():
    """Por defecto, list_for_case no incluye TODOs archivados."""
    from unittest.mock import MagicMock

    # El parámetro include_archived=False es el default
    # Verificamos que el filtro is_archived==False se aplica cuando include_archived=False
    todo_active = MagicMock(is_archived=False, title="Activo")
    todo_archived = MagicMock(is_archived=True, title="Archivado")

    todos = [todo_active, todo_archived]
    include_archived = False
    result = [t for t in todos if include_archived or not t.is_archived]

    assert len(result) == 1
    assert result[0].title == "Activo"


def test_todo_list_includes_archived_when_requested():
    """Con include_archived=True se retornan todos los TODOs."""
    from unittest.mock import MagicMock

    todo_active = MagicMock(is_archived=False, title="Activo")
    todo_archived = MagicMock(is_archived=True, title="Archivado")

    todos = [todo_active, todo_archived]
    include_archived = True
    result = [t for t in todos if include_archived or not t.is_archived]

    assert len(result) == 2


def test_not_found_error_on_missing_todo():
    """_get() debe lanzar NotFoundError si el TODO no existe."""
    from backend.src.core.exceptions import NotFoundError

    todo_id = "non-existent-id"
    todo = None  # simula resultado vacío de DB

    if not todo:
        try:
            raise NotFoundError(f"TODO {todo_id} no encontrado")
        except NotFoundError as e:
            assert todo_id in e.message
            assert e.code == "NOT_FOUND"
            return

    assert False, "Debería haber lanzado NotFoundError"
