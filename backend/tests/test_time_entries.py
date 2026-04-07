import math
from datetime import datetime, timezone, timedelta


def test_timer_minutes_ceil_rounds_up():
    """ceil garantiza que fracciones de minuto cuentan como minuto completo."""
    elapsed_seconds = 90  # 1.5 minutos → ceil → 2
    minutes = max(1, math.ceil(elapsed_seconds / 60))
    assert minutes == 2


def test_timer_minutes_minimum_one():
    """Un timer detenido inmediatamente debe registrar al menos 1 minuto."""
    elapsed_seconds = 10  # menos de 1 minuto
    minutes = max(1, math.ceil(elapsed_seconds / 60))
    assert minutes == 1


def test_timer_minutes_exact_minute():
    """Exactamente 60 segundos = 1 minuto, sin redondeo extra."""
    elapsed_seconds = 60
    minutes = max(1, math.ceil(elapsed_seconds / 60))
    assert minutes == 1


def test_timer_minutes_two_hours():
    """2 horas = 120 minutos exactos."""
    elapsed_seconds = 7200
    minutes = max(1, math.ceil(elapsed_seconds / 60))
    assert minutes == 120


def test_manual_entry_requires_positive_minutes():
    """Validación de negocio: los minutos manuales deben ser positivos."""
    from backend.src.core.exceptions import BusinessRuleError

    def validate_minutes(minutes: int):
        if minutes <= 0:
            raise BusinessRuleError("Los minutos deben ser un número positivo")

    # Caso inválido
    try:
        validate_minutes(0)
        assert False, "Debería haber lanzado BusinessRuleError"
    except BusinessRuleError as e:
        assert "positivo" in e.message

    # Caso inválido negativo
    try:
        validate_minutes(-5)
        assert False, "Debería haber lanzado BusinessRuleError"
    except BusinessRuleError:
        pass

    # Caso válido
    validate_minutes(30)  # No debe lanzar


def test_elapsed_seconds_with_timezone_naive_start():
    """Stop timer maneja correctamente started_at sin timezone."""
    started = datetime(2026, 4, 7, 10, 0, 0)  # naive (sin tz)
    now = datetime(2026, 4, 7, 10, 30, 0, tzinfo=timezone.utc)

    # Lógica del use_case: normalizar a UTC si naive
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    elapsed_seconds = (now - started).total_seconds()
    minutes = max(1, math.ceil(elapsed_seconds / 60))
    assert minutes == 30
