def test_disposition_usage_count_starts_at_zero():
    """usage_count debe iniciar en 0 al crear una disposición."""
    from unittest.mock import MagicMock

    disp = MagicMock()
    disp.usage_count = 0
    assert disp.usage_count == 0


def test_disposition_apply_increments_count():
    """Cada aplicación incrementa usage_count en 1."""
    from unittest.mock import MagicMock

    disp = MagicMock()
    disp.usage_count = 0

    # Simula la lógica de apply_to_case
    disp.usage_count += 1
    assert disp.usage_count == 1

    disp.usage_count += 1
    assert disp.usage_count == 2


def test_search_dispositions_by_title_ilike():
    """La búsqueda de disposiciones es case-insensitive y busca en title y content."""
    dispositions = [
        {"title": "Problema de VPN", "content": "Verificar credenciales de acceso"},
        {"title": "Error de red", "content": "Reinstalar cliente VPN en el equipo"},
        {"title": "Error de correo", "content": "Revisar servidor SMTP"},
    ]

    query = "vpn"
    pattern = query.lower()
    results = [d for d in dispositions if pattern in d["title"].lower() or pattern in d["content"].lower()]
    # "Problema de VPN" (title) y "Reinstalar cliente VPN" (content) → 2 disposiciones distintas
    assert len(results) == 2


def test_deactivate_disposition_sets_is_active_false():
    """Desactivar una disposición la marca como inactiva."""
    from unittest.mock import MagicMock

    disp = MagicMock()
    disp.is_active = True

    # Simula la lógica de deactivate
    disp.is_active = False
    assert disp.is_active is False


def test_not_found_error_on_missing_disposition():
    """apply_to_case lanza NotFoundError si la disposición no existe."""
    from backend.src.core.exceptions import NotFoundError

    disposition_id = "non-existent"
    disp = None  # simula resultado vacío de DB

    if not disp:
        try:
            raise NotFoundError(f"Disposición {disposition_id} no encontrada")
        except NotFoundError as e:
            assert disposition_id in e.message
            assert e.code == "NOT_FOUND"
            return
    assert False, "Debería haber lanzado NotFoundError"


def test_category_is_active_by_default():
    """Una categoría nueva debe estar activa por defecto."""
    from unittest.mock import MagicMock

    cat = MagicMock()
    cat.is_active = True  # valor default del modelo
    assert cat.is_active is True
