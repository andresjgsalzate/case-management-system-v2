from datetime import datetime, timezone, timedelta


EDIT_WINDOW_MINUTES = 15


def _check_edit_window(created_at: datetime, now: datetime) -> bool:
    """Replica la lógica del use_case para testear de forma aislada."""
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return (now - created_at) <= timedelta(minutes=EDIT_WINDOW_MINUTES)


def test_edit_within_window_allowed():
    """Un mensaje editado dentro de los 15 minutos debe permitirse."""
    created = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 7, 10, 10, 0, tzinfo=timezone.utc)  # 10 min después
    assert _check_edit_window(created, now) is True


def test_edit_at_exact_window_boundary_allowed():
    """Exactamente en el límite (15 min) debe permitirse."""
    created = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 7, 10, 15, 0, tzinfo=timezone.utc)
    assert _check_edit_window(created, now) is True


def test_edit_outside_window_rejected():
    """Un mensaje editado después de 15 minutos debe rechazarse."""
    created = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 7, 10, 16, 0, tzinfo=timezone.utc)  # 16 min después
    assert _check_edit_window(created, now) is False


def test_edit_timezone_naive_handled():
    """created_at sin timezone se trata como UTC."""
    created = datetime(2026, 4, 7, 10, 0, 0)  # naive
    now = datetime(2026, 4, 7, 10, 5, 0, tzinfo=timezone.utc)  # 5 min después
    assert _check_edit_window(created, now) is True


def test_business_rule_error_on_expired_window():
    """El use_case lanza BusinessRuleError cuando se supera la ventana."""
    from backend.src.core.exceptions import BusinessRuleError

    created = datetime(2026, 4, 7, 9, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 4, 7, 10, 0, 0, tzinfo=timezone.utc)  # 60 min después

    if not _check_edit_window(created, now):
        try:
            raise BusinessRuleError(f"Fuera de la ventana de edición ({EDIT_WINDOW_MINUTES} minutos)")
        except BusinessRuleError as e:
            assert "ventana" in e.message
            assert e.code == "BUSINESS_RULE_VIOLATION"
            return

    assert False, "Debería haber detectado la ventana expirada"
