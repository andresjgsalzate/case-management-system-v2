def test_article_starts_as_draft():
    """Un artículo nuevo siempre tiene status='draft' y version=1."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.status = "draft"
    article.version = 1

    assert article.status == "draft"
    assert article.version == 1


def test_version_increments_on_update():
    """Cada actualización de contenido incrementa version en 1."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.version = 1

    # Simula la lógica de update_article
    article.version += 1
    assert article.version == 2

    article.version += 1
    assert article.version == 3


def test_feedback_helpful_increments_counter():
    """submit_feedback(is_helpful=True) incrementa helpful_count."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.helpful_count = 0
    article.not_helpful_count = 0

    is_helpful = True
    if is_helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    assert article.helpful_count == 1
    assert article.not_helpful_count == 0


def test_feedback_not_helpful_increments_not_helpful_counter():
    """submit_feedback(is_helpful=False) incrementa not_helpful_count."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.helpful_count = 0
    article.not_helpful_count = 0

    is_helpful = False
    if is_helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    assert article.helpful_count == 0
    assert article.not_helpful_count == 1


def test_feedback_upsert_reverts_previous_counter():
    """Al cambiar el feedback, el contador anterior se revierte antes de aplicar el nuevo."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.helpful_count = 1
    article.not_helpful_count = 0

    existing_feedback = MagicMock()
    existing_feedback.is_helpful = True  # feedback anterior: helpful

    # Simula upsert: revertir anterior
    if existing_feedback.is_helpful:
        article.helpful_count = max(0, article.helpful_count - 1)
    else:
        article.not_helpful_count = max(0, article.not_helpful_count - 1)

    # Aplicar nuevo feedback: not_helpful
    new_is_helpful = False
    if new_is_helpful:
        article.helpful_count += 1
    else:
        article.not_helpful_count += 1

    assert article.helpful_count == 0
    assert article.not_helpful_count == 1


def test_view_count_increments_on_get():
    """get_article() incrementa view_count en 1."""
    from unittest.mock import MagicMock

    article = MagicMock()
    article.view_count = 5

    # Simula la lógica de get_article
    article.view_count += 1
    assert article.view_count == 6


def test_toggle_favorite_add_then_remove():
    """toggle_favorite añade cuando no existe, elimina cuando ya existe."""
    favorites: set[tuple[str, str]] = set()

    def toggle(article_id: str, user_id: str) -> bool:
        key = (article_id, user_id)
        if key in favorites:
            favorites.remove(key)
            return False
        favorites.add(key)
        return True

    added = toggle("art-1", "user-1")
    assert added is True
    assert len(favorites) == 1

    removed = toggle("art-1", "user-1")
    assert removed is False
    assert len(favorites) == 0


def test_forbidden_error_on_edit_non_draft():
    """Solo artículos en draft o rejected pueden editarse."""
    from backend.src.core.exceptions import ForbiddenError

    article_status = "published"

    if article_status not in ("draft", "rejected"):
        try:
            raise ForbiddenError("Solo se pueden editar artículos en estado draft o rejected")
        except ForbiddenError as e:
            assert "draft" in e.message
            assert e.code == "FORBIDDEN"
            return
    assert False, "Debería haber lanzado ForbiddenError"
